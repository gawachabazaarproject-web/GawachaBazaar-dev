"""COD delivery OTP: a partner cannot complete an unpaid COD delivery without the
code the customer holds. Real PostgreSQL; every step goes through the HTTP API.
The plaintext code is read the way the customer reads it (GET /orders/{id}/delivery-otp)."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.core.roles import ADMIN, DELIVERY_PARTNER, HUB_STAFF
from app.models.delivery_otp import DeliveryOtp
from app.models.delivery_partner import DeliveryAssignment, DeliveryPartnerEarning
from app.models.order import Order
from app.models.payment import Payment
from app.services import delivery_otp as otp_service
from tests.test_delivery_partner import Scene
from tests.test_phase_16_fulfillment_delivery import _customer, _staff

pytestmark = pytest.mark.delivery_otp

P = "/api/v1/delivery-partner"


@pytest.fixture(autouse=True)
def pushes(monkeypatch):
    """Mocked push: records (user_id, order_id, otp) instead of calling Expo."""
    sent: list[dict] = []
    monkeypatch.setattr(
        otp_service, "notify_delivery_otp", lambda **kw: sent.append(kw)
    )
    return sent


def _out(client, db, tag) -> Scene:
    s = Scene(client, db, tag)
    s.to_out()
    return s


def _send(s: Scene, headers=None, aid=None):
    return s.client.post(
        f"{P}/assignments/{aid or s.aid()}/otp/send", headers=headers or s.ph, json={}
    )


def _code(s: Scene) -> str:
    r = s.client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ACTIVE", r.json()
    return r.json()["otp"]


def _deliver(s: Scene, otp, aid=None, headers=None):
    body = {"cod_collected_amount": str(s.total)}
    if otp is not None:
        body["otp"] = otp
    return s.act("deliver", json=body, aid=aid, headers=headers)


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def _row(db, order_id) -> DeliveryOtp:
    db.expire_all()
    return db.query(DeliveryOtp).filter_by(order_id=order_id).order_by(DeliveryOtp.id.desc()).first()


# ---------------------------------------------------------------- generation


def test_generated_code_is_six_digits_hashed_and_expiring(client, db_session, pushes) -> None:
    s = _out(client, db_session, "g1")
    r = _send(s)
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    code = _code(s)
    assert len(code) == 6 and code.isdigit()
    row = _row(db_session, s.order["id"])
    assert len(row.otp_hash) == 64 and row.otp_hash != code
    assert code.encode() not in bytes(row.otp_encrypted)  # encrypted, not plaintext
    assert row.attempts == 0 and row.max_attempts == settings.DELIVERY_OTP_MAX_ATTEMPTS
    life = row.expires_at - row.created_at
    assert timedelta(minutes=settings.DELIVERY_OTP_EXPIRY_MINUTES - 1) < life <= timedelta(
        minutes=settings.DELIVERY_OTP_EXPIRY_MINUTES, seconds=5
    )
    assert pushes and pushes[0]["otp"] == code and pushes[0]["order_id"] == s.order["id"]


def test_code_generator_keeps_leading_zeros(monkeypatch) -> None:
    monkeypatch.setattr(otp_service.secrets, "randbelow", lambda n: 42)
    assert otp_service.generate_code() == "000042"


def test_hash_is_bound_to_order_assignment_and_secret() -> None:
    h = otp_service.hash_code("123456", 1, 1)
    assert h != otp_service.hash_code("123456", 2, 1)
    assert h != otp_service.hash_code("123456", 1, 2)
    assert h != otp_service.hash_code("123457", 1, 1)
    assert "123456" not in h


def test_partner_never_receives_the_code(client, db_session) -> None:
    s = _out(client, db_session, "g2")
    sent = _send(s)
    code = _code(s)
    for resp in (
        sent,
        client.get(f"{P}/assignments/{s.aid()}", headers=s.ph),
        client.get(f"{P}/assignments", headers=s.ph),
    ):
        assert code not in resp.text, resp.request.url
    assert client.get(f"{P}/assignments/{s.aid()}", headers=s.ph).json()["delivery_otp"]["status"] == "ACTIVE"


def test_code_never_reaches_the_logs(client, db_session, caplog) -> None:
    s = _out(client, db_session, "g3")
    with caplog.at_level(logging.DEBUG):
        _send(s)
        code = _code(s)
        _deliver(s, _wrong(code))
        assert _deliver(s, code).status_code == 200
    assert code not in caplog.text
    assert "DELIVERY_OTP_GENERATED" in caplog.text and "DELIVERY_OTP_VERIFIED" in caplog.text


# -------------------------------------------------------------- verification


def test_full_cod_lifecycle_with_otp(client, db_session) -> None:
    s = _out(client, db_session, "v1")
    # the customer sees "waiting" before the partner sends anything
    waiting = client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()
    assert waiting["status"] == "WAITING" and waiting["otp"] is None
    _send(s)
    code = _code(s)
    done = _deliver(s, code)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "DELIVERED" and done.json()["cod_status"] == "COD_COLLECTED"
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "COMPLETED"
    assert db_session.query(Payment).filter_by(order_id=s.order["id"]).one().status == "PAID"
    assert db_session.query(DeliveryPartnerEarning).count() == 1
    row = _row(db_session, s.order["id"])
    assert row.verified_at is not None and row.otp_encrypted is None
    # the code is no longer shown, and it cannot be replayed
    after = client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()
    assert after["status"] == "VERIFIED" and after["otp"] is None
    # replay is the existing idempotent no-op: it must not create a second effect
    again = _deliver(s, code, aid=done.json()["id"])
    assert again.status_code in (200, 409)
    db_session.expire_all()
    assert db_session.query(DeliveryPartnerEarning).count() == 1
    assert db_session.query(DeliveryOtp).filter_by(order_id=s.order["id"]).count() == 1


def test_delivery_without_or_with_wrong_code_changes_nothing(client, db_session) -> None:
    s = _out(client, db_session, "v2")
    _send(s)
    code = _code(s)
    r_none = _deliver(s, None)
    assert r_none.status_code == 422 and r_none.json()["code"] == "OTP_INVALID"
    r_bad = _deliver(s, _wrong(code))
    assert r_bad.status_code == 422 and r_bad.json()["code"] == "OTP_INVALID"
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    assert db_session.query(Payment).filter_by(order_id=s.order["id"]).one().status != "PAID"
    assert db_session.query(DeliveryPartnerEarning).count() == 0
    assert db_session.query(DeliveryAssignment).one().status == "OUT_FOR_DELIVERY"
    assert _row(db_session, s.order["id"]).attempts == 1  # the failed attempt was committed
    assert _deliver(s, code).status_code == 200  # the real code still works


def test_delivery_with_no_code_issued_is_refused(client, db_session) -> None:
    s = _out(client, db_session, "v3")
    r = _deliver(s, "123456")
    assert r.status_code == 409 and r.json()["code"] == "OTP_NOT_FOUND"
    assert db_session.query(DeliveryPartnerEarning).count() == 0


def test_malformed_code_is_rejected_by_validation(client, db_session) -> None:
    s = _out(client, db_session, "v4")
    _send(s)
    for bad in ("12345", "1234567", "12345a", " 12345", "١٢٣٤٥٦"):
        assert _deliver(s, bad).status_code == 422, bad
    assert _row(db_session, s.order["id"]).attempts == 0


def test_expired_code_is_refused_at_the_boundary(client, db_session) -> None:
    s = _out(client, db_session, "e1")
    _send(s)
    code = _code(s)
    row = _row(db_session, s.order["id"])
    # one second left: still valid
    row.expires_at = datetime.now(UTC) + timedelta(seconds=30)
    db_session.commit()
    assert client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()["status"] == "ACTIVE"
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()["status"] == "EXPIRED"
    r = _deliver(s, code)
    assert r.status_code == 409 and r.json()["code"] == "OTP_EXPIRED"
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    # a fresh code recovers the delivery
    assert _send(s).status_code == 200
    assert _deliver(s, _code(s)).status_code == 200


def test_attempt_limit_locks_the_code_even_for_the_right_answer(client, db_session) -> None:
    s = _out(client, db_session, "a1")
    _send(s)
    code = _code(s)
    bad = _wrong(code)
    max_attempts = settings.DELIVERY_OTP_MAX_ATTEMPTS
    results = [_deliver(s, bad) for _ in range(max_attempts)]
    assert [r.status_code for r in results[:-1]] == [422] * (max_attempts - 1)
    assert results[-1].status_code == 429 and results[-1].json()["code"] == "OTP_ATTEMPTS_EXCEEDED"
    r = _deliver(s, code)  # correct, but the code is dead
    assert r.status_code == 409 and r.json()["code"] == "OTP_NOT_FOUND"
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    assert client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()["status"] == "LOCKED"
    # a new code resets the situation
    assert _send(s).status_code == 200
    assert _deliver(s, _code(s)).status_code == 200


def test_new_code_invalidates_the_old_one_and_only_one_stays_active(client, db_session) -> None:
    s = _out(client, db_session, "r1")
    _send(s)
    old = _code(s)
    for _ in range(20):  # same code is astronomically unlikely, but make it deterministic
        _send(s)
        new = _code(s)
        if new != old:
            break
    if new == old:  # pragma: no cover
        pytest.skip("generator returned the same code twice")
    assert _deliver(s, old).status_code == 422
    db_session.expire_all()
    rows = db_session.query(DeliveryOtp).filter_by(order_id=s.order["id"]).all()
    assert sum(1 for r in rows if r.invalidated_at is None and r.verified_at is None) == 1
    assert any(r.invalidated_reason == "REPLACED" and r.otp_encrypted is None for r in rows)
    assert _deliver(s, new).status_code == 200


def test_resend_is_rate_limited_per_order(client, db_session, pushes) -> None:
    s = _out(client, db_session, "r2")
    limit = settings.DELIVERY_OTP_RESEND_LIMIT
    for _ in range(limit):
        assert _send(s).status_code == 200
    r = _send(s)
    assert r.status_code == 429
    assert len(pushes) == limit
    db_session.expire_all()
    assert db_session.query(DeliveryOtp).filter_by(order_id=s.order["id"]).count() == limit


def test_push_failure_never_breaks_code_generation_or_delivery(client, db_session, monkeypatch) -> None:
    def boom(**_kw):
        raise RuntimeError("fcm down")

    monkeypatch.setattr(otp_service, "notify_delivery_otp", boom)
    s = _out(client, db_session, "p1")
    assert _send(s).status_code == 200
    assert _deliver(s, _code(s)).status_code == 200  # the customer still sees it in the app


# ----------------------------------------------------------- eligibility


def test_code_can_only_be_sent_while_out_for_delivery(client, db_session) -> None:
    s = Scene(client, db_session, "s1")
    assert s.assign().status_code == 200
    aid = s.aid()
    assert _send(s, aid=aid).status_code == 409  # ASSIGNED
    for a in ("accept", "pickup"):
        assert s.act(a).status_code == 200
        assert _send(s, aid=aid).status_code == 409
    assert db_session.query(DeliveryOtp).count() == 0


def test_prepaid_orders_have_no_code_and_need_none(client, db_session) -> None:
    s = Scene(client, db_session, "s2")
    pay = db_session.query(Payment).filter_by(order_id=s.order["id"]).one()
    pay.payment_method, pay.status = "UPI", "PAID"
    db_session.commit()
    s.to_out()
    assert _send(s).status_code == 409
    view = client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()
    assert view["required"] is False and view["status"] == "NOT_REQUIRED"
    assert s.act("deliver", json={}).status_code == 200


def test_cancelled_order_cannot_be_delivered_and_code_dies(client, db_session) -> None:
    s = _out(client, db_session, "s3")
    _send(s)
    code = _code(s)
    aid = s.aid()
    assert client.post(f"/api/v1/orders/{s.order['id']}/cancel", json={}, headers=s.ch).status_code == 200
    r = _deliver(s, code, aid=aid)
    assert r.status_code in (409, 422)
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CANCELLED"
    assert _row(db_session, s.order["id"]).invalidated_at is not None
    assert client.get(f"/api/v1/orders/{s.order['id']}/delivery-otp", headers=s.ch).json()["status"] == "CANCELLED"


def test_failed_delivery_invalidates_the_code(client, db_session) -> None:
    s = _out(client, db_session, "s4")
    _send(s)
    aid = s.aid()
    assert s.act("fail", json={"reason": "customer absent"}, aid=aid).status_code == 200
    row = _row(db_session, s.order["id"])
    assert row.invalidated_reason == "DELIVERY_FAILED" and row.otp_encrypted is None


def test_reassigned_delivery_does_not_inherit_the_old_code(client, db_session) -> None:
    s = _out(client, db_session, "s5")
    _send(s)
    code = _code(s)
    p2, h2 = _staff(db_session, DELIVERY_PARTNER, "s5b")
    _admin, admin_h = _staff(db_session, ADMIN, "s5a")
    r = client.post(
        f"/api/v1/fulfillments/{s.fid}/reassign",
        json={"delivery_partner_user_id": p2.id, "reason": "partner unavailable"},
        headers=admin_h,
    )
    if r.status_code != 200:  # reassignment is blocked once out for delivery
        assert r.status_code == 409
        return
    for a in ("accept", "pickup", "out-for-delivery"):  # pragma: no cover
        assert s.act(a, headers=h2).status_code == 200
    assert _deliver(s, code, headers=h2).status_code in (409, 422)  # pragma: no cover


# --------------------------------------------------------- authorization


def test_only_the_owning_customer_sees_the_code(client, db_session) -> None:
    s = _out(client, db_session, "z1")
    _send(s)
    code = _code(s)
    url = f"/api/v1/orders/{s.order['id']}/delivery-otp"
    _other, other_h = _customer(db_session, "z1other")
    r = client.get(url, headers=other_h)
    assert r.status_code == 404 and code not in r.text
    assert client.get(url, headers=s.ph).status_code == 403  # partner role
    assert client.get(url, headers=s.ops).status_code == 403  # staff role
    _admin, admin_h = _staff(db_session, ADMIN, "z1a")
    assert client.get(url, headers=admin_h).status_code == 403
    assert client.get(url).status_code in (401, 403)
    assert client.get("/api/v1/orders/999999999/delivery-otp", headers=s.ch).status_code == 404


def test_other_partners_and_roles_cannot_send_or_verify(client, db_session) -> None:
    s = _out(client, db_session, "z2")
    _send(s)
    code = _code(s)
    aid = s.aid()
    _p2, h2 = _staff(db_session, DELIVERY_PARTNER, "z2b")
    assert _send(s, headers=h2, aid=aid).status_code == 404
    assert _deliver(s, code, headers=h2, aid=aid).status_code == 404
    assert _send(s, headers=s.ch, aid=aid).status_code == 403  # customer
    assert _deliver(s, code, headers=s.ch, aid=aid).status_code == 403
    assert client.post(f"{P}/assignments/{aid}/otp/send", json={}).status_code in (401, 403)
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    assert _row(db_session, s.order["id"]).attempts == 0


def test_legacy_fulfillment_deliver_endpoint_also_requires_the_code(client, db_session) -> None:
    s = _out(client, db_session, "z3")
    url = f"/api/v1/fulfillments/{s.fid}/deliver"
    r = client.post(url, headers=s.ph)  # no body at all: still accepted syntactically
    assert r.status_code in (409, 422)
    assert r.json()["code"] in ("OTP_NOT_FOUND", "OTP_INVALID")
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    _send(s)
    code = _code(s)
    assert client.post(url, headers=s.ph, json={"otp": _wrong(code)}).status_code == 422
    assert client.post(url, headers=s.ph, json={"otp": code}).status_code == 200
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "COMPLETED"


def test_admin_override_completes_consistently_and_is_audited(client, db_session, caplog) -> None:
    from decimal import Decimal

    from app.models.inventory_lot import InventoryLot

    s = _out(client, db_session, "z4")
    start_qty = s.lot.quantity
    _admin, admin_h = _staff(db_session, ADMIN, "z4a")
    with caplog.at_level(logging.WARNING):
        r = client.post(f"/api/v1/fulfillments/{s.fid}/deliver", headers=admin_h)
    assert r.status_code == 200, r.text
    assert caplog.text.count("DELIVERY_OTP_ADMIN_OVERRIDE") == 1
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "COMPLETED"
    assert db_session.query(Payment).filter_by(order_id=s.order["id"]).one().status == "PAID"
    assert db_session.query(DeliveryAssignment).one().status == "DELIVERED"
    assert db_session.query(DeliveryPartnerEarning).count() == 1
    lot = db_session.get(InventoryLot, s.lot.id)
    assert lot.quantity == start_qty - Decimal("3") and lot.reserved_quantity == 0
    # a second admin call is an idempotent no-op: no second earning, no second audit line
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        client.post(f"/api/v1/fulfillments/{s.fid}/deliver", headers=admin_h)
    assert "DELIVERY_OTP_ADMIN_OVERRIDE" not in caplog.text
    db_session.expire_all()
    assert db_session.query(DeliveryPartnerEarning).count() == 1


def test_override_is_not_reachable_by_partner_customer_or_other_roles(client, db_session, caplog) -> None:
    s = _out(client, db_session, "z6")
    url = f"/api/v1/fulfillments/{s.fid}/deliver"
    _p2, h2 = _staff(db_session, DELIVERY_PARTNER, "z6b")
    _ops, ops_h = _staff(db_session, HUB_STAFF, "z6c")
    with caplog.at_level(logging.WARNING):
        assert client.post(url, headers=s.ch).status_code == 403  # customer
        assert client.post(url, headers=h2).status_code in (403, 404)  # other partner
        assert client.post(url, headers=ops_h).status_code == 403  # warehouse staff
        assert client.post(url, headers=s.ph).status_code in (409, 422)  # assigned partner: no bypass
        # the partner endpoint never inherits the override either
        assert s.act("deliver", json={"cod_collected_amount": str(s.total)}).status_code in (409, 422)
    assert "DELIVERY_OTP_ADMIN_OVERRIDE" not in caplog.text
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"
    assert db_session.query(DeliveryPartnerEarning).count() == 0


def test_a_user_who_is_both_admin_and_the_assigned_partner_gets_no_bypass(client, db_session) -> None:
    from app.models.user_role import UserRole
    from tests.test_phase_16_fulfillment_delivery import _get_or_create_role

    s = Scene(client, db_session, "z7")
    role = _get_or_create_role(db_session, ADMIN)
    db_session.add(UserRole(user_id=s.partner.id, role_id=role.id))
    db_session.commit()
    s.to_out()
    r = client.post(f"/api/v1/fulfillments/{s.fid}/deliver", headers=s.ph)
    assert r.status_code in (409, 422)
    db_session.expire_all()
    assert db_session.get(Order, s.order["id"]).status == "CONFIRMED"


def test_production_defaults_enforce_the_code() -> None:
    """The autouse fixture switches enforcement off for legacy suites; the
    declared default (what production gets) must stay ON."""
    from app.core.config import Settings

    assert Settings.model_fields["DELIVERY_OTP_ENFORCED"].default is True
    assert Settings.model_fields["DELIVERY_OTP_EXPIRY_MINUTES"].default == 10
    assert Settings.model_fields["DELIVERY_OTP_MAX_ATTEMPTS"].default == 5


def test_production_refuses_to_start_without_a_strong_otp_secret() -> None:
    from app.core.config import Settings

    base = {"APP_ENV": "production", "DEBUG": False, "FIREBASE_PROJECT_ID": "demo-project"}
    for secret in ("", "short-secret", "x" * 31):
        with pytest.raises(Exception) as ei:
            Settings(_env_file=None, **base, DELIVERY_OTP_ENFORCED=True, DELIVERY_OTP_SECRET=secret)
        assert "DELIVERY_OTP_SECRET" in str(ei.value)
    # strong secret: starts; enforcement explicitly off: starts (rollout switch)
    Settings(_env_file=None, **base, DELIVERY_OTP_ENFORCED=True, DELIVERY_OTP_SECRET="x" * 32)
    Settings(_env_file=None, **base, DELIVERY_OTP_ENFORCED=False, DELIVERY_OTP_SECRET="")


def test_enforcement_switch_off_restores_the_old_behaviour(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "DELIVERY_OTP_ENFORCED", False)
    s = _out(client, db_session, "z5")
    assert _deliver(s, None).status_code == 200


# ------------------------------------------------------------ concurrency


def test_concurrent_correct_submissions_complete_once(client, db_session) -> None:
    s = _out(client, db_session, "c1")
    _send(s)
    code = _code(s)
    aid = s.aid()
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = [
            f.result().status_code
            for f in [pool.submit(lambda: _deliver(s, code, aid=aid)) for _ in range(6)]
        ]
    assert codes.count(200) >= 1 and all(c in (200, 409) for c in codes), codes
    db_session.expire_all()
    assert db_session.query(DeliveryPartnerEarning).count() == 1
    assert db_session.get(Order, s.order["id"]).status == "COMPLETED"
    assert _row(db_session, s.order["id"]).verified_at is not None
    assert db_session.query(DeliveryOtp).filter_by(order_id=s.order["id"]).count() == 1


def test_concurrent_wrong_guesses_cannot_exceed_the_attempt_limit(client, db_session) -> None:
    s = _out(client, db_session, "c2")
    _send(s)
    code = _code(s)
    aid = s.aid()
    bad = _wrong(code)
    with ThreadPoolExecutor(max_workers=8) as pool:
        res = [
            f.result().status_code
            for f in [pool.submit(lambda: _deliver(s, bad, aid=aid)) for _ in range(12)]
        ]
    assert 200 not in res
    row = _row(db_session, s.order["id"])
    assert row.attempts <= row.max_attempts
    assert row.invalidated_at is not None
    assert _deliver(s, code).status_code == 409  # locked: even the real code is refused


def test_concurrent_sends_leave_exactly_one_active_code(client, db_session) -> None:
    s = _out(client, db_session, "c3")
    aid = s.aid()
    with ThreadPoolExecutor(max_workers=3) as pool:
        res = [f.result().status_code for f in [pool.submit(lambda: _send(s, aid=aid)) for _ in range(3)]]
    assert all(c in (200, 409, 429) for c in res), res
    db_session.expire_all()
    rows = db_session.query(DeliveryOtp).filter_by(order_id=s.order["id"]).all()
    assert sum(1 for r in rows if r.invalidated_at is None and r.verified_at is None) == 1


# -------------------------------------------------------------- database


def test_database_allows_only_one_active_code_per_order(client, db_session) -> None:
    from sqlalchemy.exc import IntegrityError

    s = _out(client, db_session, "d1")
    _send(s)
    row = _row(db_session, s.order["id"])
    dup = DeliveryOtp(
        order_id=row.order_id,
        assignment_id=row.assignment_id,
        otp_hash="0" * 64,
        expires_at=row.expires_at,
        max_attempts=5,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
