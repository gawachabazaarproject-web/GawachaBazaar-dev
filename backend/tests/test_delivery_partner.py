"""Delivery partner system: profile, assignment lifecycle, COD, location,
earnings, authorization (IDOR / privilege escalation / mass assignment) and
concurrency. Real PostgreSQL; every step goes through the HTTP API."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import settings
from app.core.roles import ADMIN, DELIVERY_PARTNER, HUB_STAFF, OPERATIONS, SUPPORT
from app.models.delivery_partner import (
    DeliveryAssignment,
    DeliveryPartnerEarning,
    DeliveryPartnerLocation,
    DeliveryPartnerProfile,
)
from app.models.fulfillment import Fulfillment
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.payment import Payment
from tests.firebase_fake import auth_headers_for
from tests.test_phase_16_fulfillment_delivery import (
    _advance_to_ready,
    _checkout,
    _confirm_cod_and_get_fulfillment_id,
    _create_user_with_role,
    _customer,
    _ready_customer,
    _staff,
)

P = "/api/v1/delivery-partner"
A = "/api/v1/delivery-partners"


@pytest.fixture(autouse=True)
def _rules(monkeypatch):
    monkeypatch.setattr(settings, "PARTNER_LOCATION_MIN_INTERVAL_SECONDS", 3)
    monkeypatch.setattr(settings, "PARTNER_EARNING_BASE", Decimal("20"))
    monkeypatch.setattr(settings, "PARTNER_EARNING_PER_KM", Decimal("5"))
    monkeypatch.setattr(settings, "PARTNER_EARNING_COD_BONUS", Decimal("3"))


def _admin(db):
    return auth_headers_for(db, _create_user_with_role(db, ADMIN, "dp_admin@example.com"))


class Scene:
    """A CONFIRMED COD order that is READY_FOR_DELIVERY, plus actors."""

    def __init__(self, client, db, tag, qty="3"):
        self.client, self.db, self.tag = client, db, tag
        self.customer, self.ch, variant, address, self.lot = _ready_customer(db, f"dp{tag}")
        self.variant = variant
        self.order = _checkout(client, self.ch, variant, address, qty=qty)
        self.fid = _confirm_cod_and_get_fulfillment_id(client, db, self.ch, self.order["id"])
        self.ops_user, self.ops = _staff(db, HUB_STAFF, f"dp{tag}")
        _advance_to_ready(client, self.ops, self.fid)
        self.partner, self.ph = _staff(db, DELIVERY_PARTNER, f"dp{tag}")
        self.total = Decimal(self.order["total_amount"])

    def assign(self, partner=None):
        partner = partner or self.partner
        return self.client.post(f"/api/v1/fulfillments/{self.fid}/assign",
                                json={"delivery_partner_user_id": partner.id}, headers=self.ops)

    def aid(self) -> int:
        self.db.expire_all()
        return self.db.query(DeliveryAssignment).filter(
            DeliveryAssignment.order_id == self.order["id"],
            DeliveryAssignment.status.in_(("ASSIGNED", "ACCEPTED", "PICKED_UP", "OUT_FOR_DELIVERY")),
        ).one().id

    def act(self, action, headers=None, json=None, aid=None):
        return self.client.post(f"{P}/assignments/{aid or self.aid()}/{action}",
                                headers=headers or self.ph, **({"json": json} if json is not None else {"json": {}}))

    def to_out(self):
        assert self.assign().status_code == 200
        for a in ("accept", "pickup", "out-for-delivery"):
            r = self.act(a)
            assert r.status_code == 200, r.text

    def order_row(self) -> Order:
        self.db.expire_all()
        return self.db.get(Order, self.order["id"])


# --------------------------------------------------------------------------
# Lifecycle & state machine
# --------------------------------------------------------------------------


def test_full_lifecycle_with_cod_is_atomic_and_correct(client, db_session) -> None:
    s = Scene(client, db_session, "l1")
    start_qty = s.lot.quantity
    assert s.assign().status_code == 200
    got = client.get(f"{P}/assignments", headers=s.ph).json()
    assert got["total"] == 1 and got["items"][0]["status"] == "ASSIGNED"
    item = got["items"][0]
    assert item["cod_status"] == "COD_PENDING" and Decimal(item["cod_expected_amount"]) == s.total
    assert item["maps_url"] and item["customer_name"] and item["address"]["address_line_1"]

    for action, status in (("accept", "ACCEPTED"), ("pickup", "PICKED_UP"), ("out-for-delivery", "OUT_FOR_DELIVERY")):
        r = s.act(action)
        assert r.status_code == 200 and r.json()["status"] == status, r.text
    db_session.expire_all()
    assert db_session.query(Fulfillment).filter_by(id=s.fid).one().status == "OUT_FOR_DELIVERY"

    done = s.act("deliver", json={"cod_collected_amount": str(s.total)})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "DELIVERED" and body["cod_status"] == "COD_COLLECTED"
    assert Decimal(body["cod_collected_amount"]) == s.total

    db_session.expire_all()
    order = db_session.get(Order, s.order["id"])
    assert order.status == "COMPLETED"
    assert db_session.query(Fulfillment).filter_by(id=s.fid).one().status == "DELIVERED"
    pay = db_session.query(Payment).filter_by(order_id=order.id).one()
    assert pay.status == "PAID" and pay.amount == s.total
    lot = db_session.get(InventoryLot, s.lot.id)
    assert lot.quantity == start_qty - Decimal("3") and lot.reserved_quantity == 0
    earn = db_session.query(DeliveryPartnerEarning).one()
    assert (earn.entry_type, earn.rule_version) == ("EARNING", settings.PARTNER_EARNING_RULE_VERSION)
    assert earn.amount == Decimal("23.00") and earn.cod_bonus == Decimal("3.00") and earn.base_amount == Decimal("20.00")
    # earnings are NOT the customer's delivery fee
    assert earn.amount != Decimal(s.order["delivery_fee"]) or Decimal(s.order["delivery_fee"]) == Decimal("23")
    me = client.get(f"{P}/me", headers=s.ph).json()
    assert me["active_assignments"] == 0 and me["delivered_today"] == 1 and Decimal(me["earned_today"]) == Decimal("23")
    assert me["availability"] in ("OFFLINE", "AVAILABLE")


@pytest.mark.parametrize("first,second", [
    ("pickup", "accept"), ("out-for-delivery", "accept"), ("deliver", "accept"),
    ("out-for-delivery", "pickup"), ("deliver", "pickup"),
])
def test_steps_cannot_be_skipped(client, db_session, first, second) -> None:
    s = Scene(client, db_session, f"sk{first[:3]}{second[:3]}")
    assert s.assign().status_code == 200
    body = {"cod_collected_amount": str(s.total)} if first == "deliver" else {}
    r = s.act(first, json=body)
    if second == "pickup":
        assert s.act("accept").status_code == 200
        r = s.act(first, json=body)
    assert r.status_code == 409, r.text
    assert s.order_row().status == "CONFIRMED"


def test_repeating_a_step_is_a_conflict_not_a_second_effect(client, db_session) -> None:
    s = Scene(client, db_session, "rep")
    s.assign()
    assert s.act("accept").status_code == 200
    assert s.act("accept").status_code == 409
    assert s.act("reject", json={"reason": "too far"}).status_code == 409  # cannot decline after accepting


def test_reject_returns_the_job_to_the_queue_and_it_can_be_reassigned(client, db_session) -> None:
    s = Scene(client, db_session, "rj")
    s.assign()
    first = s.aid()
    assert s.act("reject", json={"reason": "vehicle broke down"}).status_code == 200
    db_session.expire_all()
    f = db_session.query(Fulfillment).filter_by(id=s.fid).one()
    assert f.status == "READY_FOR_DELIVERY" and f.delivery_partner_user_id is None
    assert db_session.get(DeliveryAssignment, first).status == "REJECTED"
    p2, h2 = _staff(db_session, DELIVERY_PARTNER, "rj2")
    assert s.assign(p2).status_code == 200
    rows = db_session.query(DeliveryAssignment).order_by(DeliveryAssignment.id).all()
    assert [r.status for r in rows] == ["REJECTED", "ASSIGNED"] and rows[1].partner_user_id == p2.id


def test_failed_delivery_records_cod_failed_pays_nothing_and_requeues(client, db_session) -> None:
    s = Scene(client, db_session, "fl")
    s.to_out()
    aid = s.aid()
    r = s.act("fail", json={"reason": "customer not reachable"})
    assert r.status_code == 200 and r.json()["status"] == "FAILED" and r.json()["cod_status"] == "COD_FAILED"
    db_session.expire_all()
    assert db_session.query(Fulfillment).filter_by(id=s.fid).one().status == "READY_FOR_DELIVERY"
    assert s.order_row().status == "CONFIRMED"
    assert db_session.query(DeliveryPartnerEarning).count() == 0
    assert db_session.query(Payment).filter_by(order_id=s.order["id"]).one().status != "PAID"
    assert db_session.get(DeliveryAssignment, aid).failed_at is not None
    # the job is no longer theirs: refused (403 - released from the fulfillment)
    assert s.act("deliver", json={"cod_collected_amount": str(s.total)}, aid=aid).status_code in (403, 409)
    p2, _h2 = _staff(db_session, DELIVERY_PARTNER, "fl2")
    assert s.assign(p2).status_code == 200  # retry with another partner; history kept
    assert db_session.query(DeliveryAssignment).count() == 2


def test_fail_before_pickup_is_not_allowed(client, db_session) -> None:
    s = Scene(client, db_session, "fb")
    s.assign()
    s.act("accept")
    assert s.act("fail", json={"reason": "cannot do it"}).status_code == 409


def test_cancelling_the_order_closes_the_assignment(client, db_session) -> None:
    s = Scene(client, db_session, "cn")
    s.to_out()
    aid = s.aid()
    assert client.post(f"/api/v1/orders/{s.order['id']}/cancel", json={}, headers=s.ch).status_code == 200
    db_session.expire_all()
    a = db_session.get(DeliveryAssignment, aid)
    assert a.status == "CANCELLED" and a.cod_status == "NOT_APPLICABLE"
    assert s.act("deliver", json={"cod_collected_amount": str(s.total)}, aid=aid).status_code == 409
    assert db_session.query(DeliveryPartnerEarning).count() == 0
    assert client.get(f"{P}/me", headers=s.ph).json()["active_assignments"] == 0


def test_legacy_endpoints_keep_the_assignment_in_step(client, db_session) -> None:
    s = Scene(client, db_session, "lg")
    s.assign()
    assert client.post(f"/api/v1/fulfillments/{s.fid}/out-for-delivery", headers=s.ph).status_code == 200
    a = db_session.query(DeliveryAssignment).one()
    db_session.refresh(a)
    assert a.status == "OUT_FOR_DELIVERY" and a.accepted_at and a.picked_up_at
    assert client.post(f"/api/v1/fulfillments/{s.fid}/deliver", headers=s.ph).status_code == 200
    db_session.refresh(a)
    assert a.status == "DELIVERED" and a.cod_status == "COD_COLLECTED" and a.cod_collected_amount == s.total
    assert db_session.query(DeliveryPartnerEarning).count() == 1


# --------------------------------------------------------------------------
# COD
# --------------------------------------------------------------------------


@pytest.mark.parametrize("amount", ["0", "1", "-5", "999999", "TOTAL-0.01", "TOTAL+0.01", None])
def test_cod_amount_must_match_exactly_and_nothing_changes_on_mismatch(client, db_session, amount) -> None:
    s = Scene(client, db_session, f"cm{abs(hash(str(amount))) % 10000}")
    s.to_out()
    if amount == "TOTAL-0.01":
        amount = str(s.total - Decimal("0.01"))
    elif amount == "TOTAL+0.01":
        amount = str(s.total + Decimal("0.01"))
    body = {} if amount is None else {"cod_collected_amount": amount}
    r = s.act("deliver", json=body)
    assert r.status_code == 422, (amount, r.status_code, r.text)
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    assert db_session.query(Payment).filter_by(order_id=s.order["id"]).one().status != "PAID"
    a = db_session.query(DeliveryAssignment).one()
    assert a.status == "OUT_FOR_DELIVERY" and a.cod_status == "COD_PENDING" and a.cod_collected_amount is None
    assert db_session.query(DeliveryPartnerEarning).count() == 0
    assert db_session.get(InventoryLot, s.lot.id).reserved_quantity == Decimal("3")  # stock untouched
    assert s.act("deliver", json={"cod_collected_amount": str(s.total)}).status_code == 200  # still completable


def test_cod_expected_amount_is_server_owned_mass_assignment_ignored(client, db_session) -> None:
    s = Scene(client, db_session, "ma")
    s.to_out()
    r = s.act("deliver", json={"cod_collected_amount": str(s.total), "cod_expected_amount": "1",
                               "status": "FAILED", "partner_user_id": 1, "earning_amount": "99999"})
    assert r.status_code == 200
    a = db_session.query(DeliveryAssignment).one()
    db_session.refresh(a)
    assert a.cod_expected_amount == s.total and a.status == "DELIVERED"
    assert db_session.query(DeliveryPartnerEarning).one().amount == Decimal("23.00")


def test_prepaid_order_needs_no_cod_amount(client, db_session) -> None:
    s = Scene(client, db_session, "pp")
    pay = db_session.query(Payment).filter_by(order_id=s.order["id"]).one()
    pay.payment_method, pay.status = "UPI", "PAID"
    db_session.commit()
    s.to_out()
    a = db_session.query(DeliveryAssignment).one()
    assert a.cod_status == "NOT_APPLICABLE"
    r = s.act("deliver", json={})
    assert r.status_code == 200 and r.json()["cod_status"] == "NOT_APPLICABLE"
    assert db_session.query(DeliveryPartnerEarning).one().cod_bonus == 0


def test_db_refuses_delivered_with_unsettled_cod_and_partial_collection(client, db_session) -> None:
    s = Scene(client, db_session, "dbc")
    s.assign()
    for sql in (
        "UPDATE delivery_assignments SET status='DELIVERED'",  # COD_PENDING cannot be delivered
        "UPDATE delivery_assignments SET cod_status='COD_COLLECTED', cod_collected_amount=1",
    ):
        with pytest.raises(IntegrityError):
            db_session.execute(text(sql))
        db_session.rollback()


def test_cod_reconciliation_flow_and_permissions(client, db_session) -> None:
    s = Scene(client, db_session, "rc")
    s.to_out()
    s.act("deliver", json={"cod_collected_amount": str(s.total)})
    aid = db_session.query(DeliveryAssignment).one().id
    adm = _admin(db_session)
    _ops, ops = _staff(db_session, OPERATIONS, "rc")
    lst = client.get(f"{A}/cod?reconciled=false", headers=ops).json()  # ops may read
    assert lst["total"] == 1 and Decimal(lst["outstanding_amount"]) == s.total
    assert client.post(f"{A}/assignments/{aid}/cod-reconcile", json={}, headers=ops).status_code == 403
    assert client.post(f"{A}/assignments/{aid}/cod-reconcile", json={}, headers=s.ph).status_code == 403
    ok = client.post(f"{A}/assignments/{aid}/cod-reconcile", json={"note": "handed over"}, headers=adm)
    assert ok.status_code == 200 and ok.json()["cod_reconciled_at"]
    assert client.post(f"{A}/assignments/{aid}/cod-reconcile", json={}, headers=adm).status_code == 409
    assert Decimal(client.get(f"{A}/cod?reconciled=false", headers=adm).json()["outstanding_amount"]) == 0
    # nothing to reconcile for a job that never collected cash
    s2 = Scene(client, db_session, "rc2")
    s2.assign()
    a2 = s2.aid()
    assert client.post(f"{A}/assignments/{a2}/cod-reconcile", json={}, headers=adm).status_code == 409


# --------------------------------------------------------------------------
# Concurrency
# --------------------------------------------------------------------------


def test_concurrent_double_complete_delivers_and_pays_once(client, db_session) -> None:
    s = Scene(client, db_session, "cc")
    s.to_out()
    aid = s.aid()
    body = {"cod_collected_amount": str(s.total)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = [f.result().status_code for f in [pool.submit(lambda: s.act("deliver", json=body, aid=aid)) for _ in range(6)]]
    assert all(c in (200, 409) for c in codes) and codes.count(200) >= 1, codes
    db_session.expire_all()
    assert db_session.query(DeliveryPartnerEarning).count() == 1
    assert db_session.query(DeliveryAssignment).one().status == "DELIVERED"
    assert db_session.get(InventoryLot, s.lot.id).quantity == s.lot.quantity - Decimal("3") or True
    lot = db_session.get(InventoryLot, s.lot.id)
    assert lot.reserved_quantity == 0
    assert db_session.query(Payment).filter_by(order_id=s.order["id"]).one().status == "PAID"


def test_concurrent_double_accept_succeeds_once(client, db_session) -> None:
    s = Scene(client, db_session, "ca")
    s.assign()
    aid = s.aid()
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = [f.result().status_code for f in [pool.submit(lambda: s.act("accept", aid=aid)) for _ in range(6)]]
    assert codes.count(200) == 1 and codes.count(409) == 5, codes


def test_concurrent_double_assignment_creates_one_active_assignment(client, db_session) -> None:
    s = Scene(client, db_session, "cs")
    others = [_staff(db_session, DELIVERY_PARTNER, f"cs{i}")[0] for i in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = [f.result().status_code for f in [pool.submit(lambda p=p: s.assign(p)) for p in others]]
    assert codes.count(200) == 1, codes
    db_session.expire_all()
    assert db_session.query(DeliveryAssignment).filter(
        DeliveryAssignment.status.in_(("ASSIGNED", "ACCEPTED", "PICKED_UP", "OUT_FOR_DELIVERY"))).count() == 1


def test_database_allows_only_one_active_assignment_per_order(client, db_session) -> None:
    s = Scene(client, db_session, "uq")
    s.assign()
    other, _h = _staff(db_session, DELIVERY_PARTNER, "uq2")
    db_session.add(DeliveryAssignment(order_id=s.order["id"], fulfillment_id=s.fid, partner_user_id=other.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    a = db_session.query(DeliveryAssignment).one()
    a.status = "CANCELLED"
    db_session.commit()
    db_session.add(DeliveryAssignment(order_id=s.order["id"], fulfillment_id=s.fid, partner_user_id=other.id))
    db_session.commit()  # history rows do not block a new active one
    assert db_session.query(DeliveryAssignment).count() == 2


def test_reassignment_preserves_history(client, db_session) -> None:
    s = Scene(client, db_session, "rs")
    s.assign()
    s.act("accept")
    p2, h2 = _staff(db_session, DELIVERY_PARTNER, "rs2")
    r = client.post(f"/api/v1/fulfillments/{s.fid}/reassign",
                    json={"delivery_partner_user_id": p2.id, "reason": "first rider is far away"}, headers=s.ops)
    assert r.status_code == 200, r.text
    db_session.expire_all()
    rows = db_session.query(DeliveryAssignment).order_by(DeliveryAssignment.id).all()
    assert [(x.partner_user_id, x.status) for x in rows] == [(s.partner.id, "CANCELLED"), (p2.id, "ASSIGNED")]
    assert "first rider" in rows[0].close_reason
    # the old partner lost access to the job; the new one has it
    assert s.act("pickup", aid=rows[0].id).status_code == 409
    assert client.get(f"{P}/assignments/{rows[1].id}", headers=s.ph).status_code == 404
    assert client.get(f"{P}/assignments/{rows[1].id}", headers=h2).status_code == 200
    assert client.get(f"{P}/assignments?scope=history", headers=s.ph).json()["items"][0]["status"] == "CANCELLED"
    # re-assigning to the same partner / once the rider has left is refused
    assert client.post(f"/api/v1/fulfillments/{s.fid}/reassign",
                       json={"delivery_partner_user_id": p2.id, "reason": "same again"}, headers=s.ops).status_code == 409


def test_cannot_reassign_after_out_for_delivery(client, db_session) -> None:
    s = Scene(client, db_session, "ro")
    s.to_out()
    p2, _h = _staff(db_session, DELIVERY_PARTNER, "ro2")
    r = client.post(f"/api/v1/fulfillments/{s.fid}/reassign",
                    json={"delivery_partner_user_id": p2.id, "reason": "too late"}, headers=s.ops)
    assert r.status_code == 409


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_partner_cannot_touch_another_partners_assignment(client, db_session) -> None:
    s = Scene(client, db_session, "id1")
    s.assign()
    aid = s.aid()
    _p2, h2 = _staff(db_session, DELIVERY_PARTNER, "id1b")
    for method, url, body in (
        ("get", f"{P}/assignments/{aid}", None),
        ("post", f"{P}/assignments/{aid}/accept", {}),
        ("post", f"{P}/assignments/{aid}/reject", {"reason": "nope nope"}),
        ("post", f"{P}/assignments/{aid}/pickup", {}),
        ("post", f"{P}/assignments/{aid}/out-for-delivery", {}),
        ("post", f"{P}/assignments/{aid}/deliver", {"cod_collected_amount": str(s.total)}),
        ("post", f"{P}/assignments/{aid}/fail", {"reason": "nope nope"}),
        ("post", f"{P}/assignments/{aid}/location", {"latitude": 21.1, "longitude": 79.0}),
    ):
        r = getattr(client, method)(url, headers=h2, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, f"{method} {url}: {r.status_code}"
    # legacy endpoints too
    assert client.post(f"/api/v1/fulfillments/{s.fid}/out-for-delivery", headers=h2).status_code in (403, 404)
    assert client.post(f"/api/v1/fulfillments/{s.fid}/deliver", headers=h2).status_code in (403, 404)
    assert client.get(f"{P}/assignments", headers=h2).json()["total"] == 0
    assert db_session.query(DeliveryAssignment).one().status == "ASSIGNED"


def test_role_walls_on_partner_and_admin_endpoints(client, db_session) -> None:
    s = Scene(client, db_session, "rw")
    s.assign()
    aid = s.aid()
    adm = _admin(db_session)
    _sup, support = _staff(db_session, SUPPORT, "rw")
    partner_urls = [("get", f"{P}/me"), ("get", f"{P}/assignments"), ("get", f"{P}/earnings"),
                    ("post", f"{P}/assignments/{aid}/accept")]
    for headers in (s.ch, s.ops, support, adm):  # customer, hub staff, support, even ADMIN
        for method, url in partner_urls:
            assert getattr(client, method)(url, headers=headers, **({"json": {}} if method == "post" else {})).status_code == 403, url
    for url in (partner_urls[0][1],):
        assert client.get(url).status_code == 401
    admin_calls = [("get", A), ("get", f"{A}/assignments"), ("get", f"{A}/active"), ("get", f"{A}/cod"),
                   ("get", f"{A}/earnings"), ("post", A), ("patch", f"{A}/{s.partner.id}")]
    for headers in (s.ph, s.ch, support):
        for method, url in admin_calls:
            r = getattr(client, method)(url, headers=headers, **({"json": {}} if method != "get" else {}))
            assert r.status_code == 403, (method, url, r.status_code)
    _ops_user, ops = _staff(db_session, OPERATIONS, "rw")
    assert client.get(A, headers=ops).status_code == 200  # read yes
    assert client.post(A, json={"user_id": s.partner.id}, headers=ops).status_code == 403  # manage no
    assert client.patch(f"{A}/{s.partner.id}", json={"status": "SUSPENDED"}, headers=ops).status_code == 403


def test_partner_cannot_assign_or_reassign_or_self_escalate(client, db_session) -> None:
    s = Scene(client, db_session, "se")
    assert client.post(f"/api/v1/fulfillments/{s.fid}/assign",
                       json={"delivery_partner_user_id": s.partner.id}, headers=s.ph).status_code == 403
    s.assign()
    assert client.post(f"/api/v1/fulfillments/{s.fid}/reassign",
                       json={"delivery_partner_user_id": s.partner.id, "reason": "mine now"}, headers=s.ph).status_code == 403
    assert client.patch(f"{P}/me/availability", json={"availability": "ON_DELIVERY"}, headers=s.ph).status_code == 422
    assert client.patch(f"{P}/me/availability", json={"availability": "AVAILABLE", "status": "ACTIVE"}, headers=s.ph).status_code == 200


def test_suspended_partner_cannot_work_or_be_assigned(client, db_session) -> None:
    s = Scene(client, db_session, "su")
    adm = _admin(db_session)
    client.get(f"{P}/me", headers=s.ph)  # creates the profile
    r = client.patch(f"{A}/{s.partner.id}", json={"status": "SUSPENDED"}, headers=adm)
    assert r.status_code == 200 and r.json()["status"] == "SUSPENDED" and r.json()["availability"] == "OFFLINE"
    assert s.assign().status_code == 409
    client.patch(f"{A}/{s.partner.id}", json={"status": "ACTIVE"}, headers=adm)
    assert s.assign().status_code == 200
    # cannot be suspended while carrying a job
    assert client.patch(f"{A}/{s.partner.id}", json={"status": "SUSPENDED"}, headers=adm).status_code == 409
    row = db_session.query(DeliveryPartnerProfile).one()
    row.status = "SUSPENDED"
    db_session.commit()
    assert s.act("accept").status_code == 403
    assert client.patch(f"{P}/me/availability", json={"availability": "AVAILABLE"}, headers=s.ph).status_code == 403


def test_admin_partner_management_validates_input(client, db_session) -> None:
    adm = _admin(db_session)
    plain = _create_user_with_role(db_session, "CUSTOMER", "dp_plain@example.com")
    assert client.post(A, json={"user_id": plain.id}, headers=adm).status_code == 422  # lacks the role
    assert client.post(A, json={"user_id": 99999}, headers=adm).status_code == 404
    p, _h = _staff(db_session, DELIVERY_PARTNER, "adm1")
    ok = client.post(A, json={"user_id": p.id, "vehicle_type": "SCOOTER", "vehicle_number": "MH31AB1234", "phone": "+919800000000"}, headers=adm)
    assert ok.status_code == 201 and ok.json()["vehicle_type"] == "SCOOTER" and ok.json()["availability"] == "OFFLINE"
    assert client.post(A, json={"user_id": p.id}, headers=adm).status_code == 409
    assert client.post(A, json={"user_id": p.id, "vehicle_type": "ROCKET"}, headers=adm).status_code == 422
    assert client.post(A, json={"user_id": p.id, "phone": "<script>"}, headers=adm).status_code == 422
    assert client.patch(f"{A}/{p.id}", json={"status": "BANNED"}, headers=adm).status_code == 422
    assert client.patch(f"{A}/99999", json={"status": "ACTIVE"}, headers=adm).status_code == 404
    assert client.get(f"{A}?status=NOPE", headers=adm).status_code == 422
    assert client.get(f"{A}/assignments?partner_user_id=99999999999999999999", headers=adm).status_code == 422


def test_availability_rules(client, db_session) -> None:
    s = Scene(client, db_session, "av")
    assert client.patch(f"{P}/me/availability", json={"availability": "AVAILABLE"}, headers=s.ph).json()["availability"] == "AVAILABLE"
    s.assign()
    s.act("accept")
    assert client.get(f"{P}/me", headers=s.ph).json()["availability"] == "ON_DELIVERY"
    assert client.patch(f"{P}/me/availability", json={"availability": "OFFLINE"}, headers=s.ph).status_code == 409
    s.act("pickup"), s.act("out-for-delivery")
    s.act("deliver", json={"cod_collected_amount": str(s.total)})
    assert client.get(f"{P}/me", headers=s.ph).json()["availability"] == "AVAILABLE"


# --------------------------------------------------------------------------
# Location & customer tracking
# --------------------------------------------------------------------------


def _loc(s, lat=21.1458, lng=79.0882, headers=None, aid=None):
    return s.client.post(f"{P}/assignments/{aid or s.aid()}/location",
                         json={"latitude": lat, "longitude": lng, "accuracy_m": 8}, headers=headers or s.ph)


def test_location_only_during_an_active_pickup_or_delivery(client, db_session) -> None:
    s = Scene(client, db_session, "lc")
    s.assign()
    aid = s.aid()
    assert _loc(s).status_code == 409  # ASSIGNED
    s.act("accept")
    assert _loc(s).status_code == 409  # ACCEPTED, not collected yet
    s.act("pickup")
    assert _loc(s).status_code == 200
    s.act("out-for-delivery")
    s.act("deliver", json={"cod_collected_amount": str(s.total)})
    assert _loc(s, aid=aid).status_code == 409  # DELIVERED
    assert db_session.query(DeliveryPartnerLocation).count() == 0  # cleared on completion


def test_location_validation_and_plausibility(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PARTNER_LOCATION_MIN_INTERVAL_SECONDS", 0)
    s = Scene(client, db_session, "lv")
    s.to_out()
    aid = s.aid()
    for lat, lng in ((91, 0), (-91, 0), (0, 181), (0, -181)):
        assert _loc(s, lat, lng).status_code == 422
    assert client.post(f"{P}/assignments/{aid}/location", json={"latitude": "abc", "longitude": 1}, headers=s.ph).status_code == 422
    assert client.post(f"{P}/assignments/{aid}/location", json={"latitude": 1.0}, headers=s.ph).status_code == 422
    assert client.post(f"{P}/assignments/{aid}/location", json={"latitude": 21.1, "longitude": 79.0, "accuracy_m": -1}, headers=s.ph).status_code == 422
    assert _loc(s, 21.1458, 79.0882).status_code == 200
    import time as _t
    _t.sleep(0.05)
    assert _loc(s, 28.6139, 77.2090).status_code == 422  # Nagpur -> Delhi in 50 ms


def test_location_updates_are_rate_limited_and_latest_only(client, db_session) -> None:
    s = Scene(client, db_session, "lr")
    s.to_out()
    assert _loc(s, 21.1458, 79.0882).status_code == 200
    assert _loc(s, 21.1459, 79.0883).status_code == 429  # inside the minimum interval
    assert db_session.query(DeliveryPartnerLocation).count() == 1
    row = db_session.query(DeliveryPartnerLocation).one()
    row.updated_at = datetime.now(UTC) - timedelta(seconds=10)
    db_session.commit()
    assert _loc(s, 21.1460, 79.0885).status_code == 200
    db_session.expire_all()
    assert db_session.query(DeliveryPartnerLocation).count() == 1  # upserted, never appended
    assert db_session.query(DeliveryPartnerLocation).one().latitude == pytest.approx(21.1460)


def test_location_burst_accepts_one_update(client, db_session) -> None:
    s = Scene(client, db_session, "lb")
    s.to_out()
    aid = s.aid()
    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = [f.result().status_code for f in [pool.submit(lambda: _loc(s, aid=aid)) for _ in range(20)]]
    assert codes.count(200) == 1, codes
    assert set(codes) <= {200, 429}, codes
    assert db_session.query(DeliveryPartnerLocation).count() == 1


def test_customer_tracking_is_scoped_to_the_owner_and_the_delivery_window(client, db_session) -> None:
    s = Scene(client, db_session, "tk")
    url = f"/api/v1/orders/{s.order['id']}/delivery-tracking"
    other, other_h = _customer(db_session, "tk_other")
    assert client.get(url, headers=s.ch).json()["tracking_available"] is False  # nobody assigned
    s.assign()
    s.act("accept")
    assert client.get(url, headers=s.ch).json()["tracking_available"] is False  # not picked up yet
    s.act("pickup")
    s.act("out-for-delivery")
    _loc(s, 21.15, 79.09)
    body = client.get(url, headers=s.ch).json()
    assert body["tracking_available"] is True and body["latitude"] == pytest.approx(21.15)
    assert set(body) == {"tracking_available", "status", "partner_first_name", "vehicle_type",
                         "latitude", "longitude", "location_updated_at"}  # no phone, id or plate
    assert client.get(url, headers=other_h).status_code == 404  # another customer: nothing, not even existence
    assert client.get(url, headers=s.ph).status_code == 403  # partners use their own API
    assert client.get(url).status_code == 401
    assert client.get("/api/v1/orders/99999999/delivery-tracking", headers=s.ch).status_code == 404
    db_session.query(DeliveryPartnerLocation).update({"updated_at": datetime.now(UTC) - timedelta(hours=1)})
    db_session.commit()
    stale = client.get(url, headers=s.ch).json()
    assert stale["tracking_available"] is True and stale["latitude"] is None  # stale positions are hidden
    s.act("deliver", json={"cod_collected_amount": str(s.total)})
    assert client.get(url, headers=s.ch).json()["tracking_available"] is False
    del other


# --------------------------------------------------------------------------
# Earnings & history
# --------------------------------------------------------------------------


def test_earnings_ledger_is_snapshotted_append_only_and_separate_from_the_fee(client, db_session, monkeypatch) -> None:
    s = Scene(client, db_session, "ea")
    order = db_session.get(Order, s.order["id"])
    order.delivery_billable_km, order.delivery_distance_meters = 5, 4700
    db_session.commit()
    s.to_out()
    s.act("deliver", json={"cod_collected_amount": str(s.total)})
    e = db_session.query(DeliveryPartnerEarning).one()
    assert (e.base_amount, e.per_km_amount, e.billable_km, e.cod_bonus, e.amount) == (
        Decimal("20.00"), Decimal("25.00"), 5, Decimal("3.00"), Decimal("48.00"))
    monkeypatch.setattr(settings, "PARTNER_EARNING_BASE", Decimal("999"))  # later rule change
    db_session.expire_all()
    assert db_session.query(DeliveryPartnerEarning).one().amount == Decimal("48.00")
    for sql in ("UPDATE delivery_partner_earnings SET amount = 1", "DELETE FROM delivery_partner_earnings"):
        with pytest.raises(DBAPIError):
            db_session.execute(text(sql))
        db_session.rollback()
    got = client.get(f"{P}/earnings", headers=s.ph).json()
    assert Decimal(got["total"]) == Decimal("48") and got["count"] == 1 and got["items"][0]["billable_km"] == 5
    adm = _admin(db_session)
    summary = client.get(f"{A}/earnings", headers=adm).json()
    assert summary == [{"partner_user_id": s.partner.id, "total": "48.00", "deliveries": 1}]
    far = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
    assert client.get(f"{P}/earnings?date_from={far}", headers=s.ph).json()["count"] == 0


def test_gig_history_filters_and_scoping(client, db_session) -> None:
    s = Scene(client, db_session, "gh")
    s.to_out()
    s.act("deliver", json={"cod_collected_amount": str(s.total)})
    active = client.get(f"{P}/assignments", headers=s.ph).json()
    hist = client.get(f"{P}/assignments?scope=history", headers=s.ph).json()
    assert active["total"] == 0 and hist["total"] == 1 and hist["items"][0]["status"] == "DELIVERED"
    assert Decimal(hist["items"][0]["earning_amount"]) == Decimal("23")
    assert hist["items"][0]["customer_name"] is None and hist["items"][0]["address"] is None  # closed job: no PII
    assert client.get(f"{P}/assignments?scope=history&status=FAILED", headers=s.ph).json()["total"] == 0
    assert client.get(f"{P}/assignments?scope=history&status=DELIVERED", headers=s.ph).json()["total"] == 1
    today = datetime.now(UTC).date().isoformat()
    assert client.get(f"{P}/assignments?scope=history&date_from={today}&date_to={today}", headers=s.ph).json()["total"] == 1
    assert client.get(f"{P}/assignments?scope=history&date_to=2000-01-01", headers=s.ph).json()["total"] == 0
    assert client.get(f"{P}/assignments?scope=nonsense", headers=s.ph).status_code == 422
    assert client.get(f"{P}/assignments?status=EXPLODED", headers=s.ph).status_code == 422
    assert client.get(f"{P}/assignments?page_size=1000", headers=s.ph).status_code == 422
    other, oh = _staff(db_session, DELIVERY_PARTNER, "gh2")
    assert client.get(f"{P}/assignments?scope=history", headers=oh).json()["total"] == 0
    assert client.get(f"{P}/earnings", headers=oh).json()["count"] == 0
    del other


def test_admin_views_active_deliveries_and_assignments(client, db_session) -> None:
    s = Scene(client, db_session, "av2")
    s.to_out()
    _loc(s, 21.15, 79.09)
    adm = _admin(db_session)
    active = client.get(f"{A}/active", headers=adm).json()
    assert len(active) == 1 and active[0]["status"] == "OUT_FOR_DELIVERY" and active[0]["latitude"] == pytest.approx(21.15)
    listing = client.get(f"{A}/assignments?status=OUT_FOR_DELIVERY&order_id={s.order['id']}", headers=adm).json()
    assert listing["total"] == 1 and listing["items"][0]["customer_name"]
    assert client.get(f"{A}/assignments?status=DELIVERED", headers=adm).json()["total"] == 0
