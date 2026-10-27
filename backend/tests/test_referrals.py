"""Refer & Earn: code issue, apply rules, qualification, reward ledger, reversal,
abuse and concurrency. Real PostgreSQL; delivery is driven through the real API."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.roles import ADMIN, CUSTOMER, DELIVERY_PARTNER, HUB_STAFF, OPERATIONS
from app.models.order import Order
from app.models.referral import Referral, ReferralCode, ReferralRewardLedger
from app.services.referral import ReferralService
from tests.test_phase_16_fulfillment_delivery import (
    _advance_to_ready,
    _checkout,
    _confirm_cod_and_get_fulfillment_id,
    _create_user_with_role,
    _customer,
    _ready_customer,
    _staff,
)


@pytest.fixture(autouse=True)
def _program(monkeypatch):
    monkeypatch.setattr(settings, "REFERRAL_ENABLED", True)
    monkeypatch.setattr(settings, "REFERRAL_REFERRER_REWARD", Decimal("50"))
    monkeypatch.setattr(settings, "REFERRAL_REFERRED_REWARD", Decimal("30"))
    monkeypatch.setattr(settings, "REFERRAL_MIN_ORDER_VALUE", Decimal("199"))
    monkeypatch.setattr(settings, "REFERRAL_APPLY_WINDOW_DAYS", 14)
    monkeypatch.setattr(settings, "REFERRAL_QUALIFY_WINDOW_DAYS", 30)
    monkeypatch.setattr(settings, "REFERRAL_MAX_REWARDS_PER_REFERRER", 20)


def _code(client, headers) -> str:
    r = client.get("/api/v1/referrals/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def _deliver(client, db, headers, variant, address, tag, qty="5") -> dict:
    """Checkout -> COD -> ready -> assign -> out -> delivered, through the real API."""
    order = _checkout(client, headers, variant, address, qty=qty)
    fid = _confirm_cod_and_get_fulfillment_id(client, db, headers, order["id"])
    _o, ops = _staff(db, HUB_STAFF, f"r{tag}")
    _advance_to_ready(client, ops, fid)
    partner, ph = _staff(db, DELIVERY_PARTNER, f"r{tag}")
    assert client.post(f"/api/v1/fulfillments/{fid}/assign", json={"delivery_partner_user_id": partner.id}, headers=ops).status_code == 200
    assert client.post(f"/api/v1/fulfillments/{fid}/out-for-delivery", headers=ph).status_code == 200
    done = client.post(f"/api/v1/fulfillments/{fid}/deliver", headers=ph)
    assert done.status_code == 200, done.text
    return order


def _pair(db, client, tag):
    """(referrer, referrer_headers, referred(user, headers, variant, address))"""
    a, ha = _customer(db, f"ra{tag}")
    b, hb, variant, address, _lot = _ready_customer(db, f"rb{tag}")
    return a, ha, (b, hb, variant, address)


# --------------------------------------------------------------------------
# Program switch, codes
# --------------------------------------------------------------------------


def test_program_is_disabled_by_default_in_code() -> None:
    from app.core.config import Settings

    assert Settings.model_fields["REFERRAL_ENABLED"].default is False


def test_disabled_program_issues_no_code_and_rejects_apply(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REFERRAL_ENABLED", False)
    _a, ha = _customer(db_session, "dis1")
    me = client.get("/api/v1/referrals/me", headers=ha).json()
    assert me["program"]["enabled"] is False and me["code"] is None and me["can_apply_code"] is False
    r = client.post("/api/v1/referrals/apply", json={"code": "ABCDEFGH"}, headers=ha)
    assert r.status_code == 422


def test_code_is_random_unique_upper_and_stable(client, db_session) -> None:
    a, ha = _customer(db_session, "c1")
    b, hb = _customer(db_session, "c2")
    ca, cb = _code(client, ha), _code(client, hb)
    assert ca != cb and ca == _code(client, ha)  # stable per user
    for code, uid in ((ca, a.id), (cb, b.id)):
        assert code == code.upper() and len(code) == 8 and code.isalnum()
        assert str(uid) not in code or len(str(uid)) < 2  # not built from the internal id
        assert not any(ch in code for ch in "0O1IL")  # unambiguous alphabet
    assert db_session.query(ReferralCode).count() == 2


def test_me_response_carries_all_program_values_from_the_server(client, db_session) -> None:
    _a, ha = _customer(db_session, "me1")
    body = client.get("/api/v1/referrals/me", headers=ha).json()
    p = body["program"]
    assert (Decimal(p["referrer_reward"]), Decimal(p["referred_reward"])) == (Decimal("50"), Decimal("30"))
    assert Decimal(p["min_order_value"]) == Decimal("199") and p["qualify_window_days"] == 30
    assert body["share_message"] and body["code"] in body["share_message"]
    assert body["stats"]["total_referrals"] == 0 and Decimal(body["stats"]["total_earned"]) == 0


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------


def test_apply_is_case_insensitive_and_creates_a_pending_referral(client, db_session) -> None:
    a, ha, (b, hb, *_r) = _pair(db_session, client, "ap1")
    code = _code(client, ha)
    r = client.post("/api/v1/referrals/apply", json={"code": code.lower()}, headers=hb)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PENDING"
    ref = db_session.query(Referral).one()
    assert (ref.referrer_user_id, ref.referred_user_id, ref.status) == (a.id, b.id, "PENDING")
    assert ref.expires_at > datetime.now(UTC) + timedelta(days=29)


def test_self_referral_is_blocked(client, db_session) -> None:
    _a, ha = _customer(db_session, "self1")
    code = _code(client, ha)
    r = client.post("/api/v1/referrals/apply", json={"code": code}, headers=ha)
    assert r.status_code == 422 and db_session.query(Referral).count() == 0


def test_a_second_account_with_the_same_phone_or_email_counts_as_self(client, db_session) -> None:
    a, ha, (b, hb, *_r) = _pair(db_session, client, "ph1")
    code = _code(client, ha)
    digits = "".join(ch for ch in a.phone if ch.isdigit())[-10:]
    b.phone = f"+91 {digits[:5]} {digits[5:]}"  # same number, different formatting
    db_session.commit()
    assert client.post("/api/v1/referrals/apply", json={"code": code}, headers=hb).status_code == 422
    b.phone = "+919000000001"
    b.email = a.email.upper()
    db_session.commit()
    assert client.post("/api/v1/referrals/apply", json={"code": code}, headers=hb).status_code == 422
    assert db_session.query(Referral).count() == 0


def test_second_application_is_rejected_even_with_another_code(client, db_session) -> None:
    a, ha, (b, hb, *_r) = _pair(db_session, client, "dup1")
    c, hc = _customer(db_session, "dupc")
    assert client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb).status_code == 200
    again = client.post("/api/v1/referrals/apply", json={"code": _code(client, hc)}, headers=hb)
    assert again.status_code == 409
    assert db_session.query(Referral).count() == 1
    assert client.get("/api/v1/referrals/me", headers=hb).json()["already_referred"] is True
    del c


def test_circular_referral_is_blocked(client, db_session) -> None:
    a, ha, (b, hb, *_r) = _pair(db_session, client, "circ1")
    assert client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb).status_code == 200
    r = client.post("/api/v1/referrals/apply", json={"code": _code(client, hb)}, headers=ha)
    assert r.status_code == 422  # a refers b, so b cannot refer a back
    assert db_session.query(Referral).count() == 1
    del a


def test_users_who_already_ordered_or_are_not_new_cannot_apply(client, db_session) -> None:
    a, ha = _customer(db_session, "old0")
    b, hb, variant, address, _lot = _ready_customer(db_session, "old1")
    code = _code(client, ha)
    _checkout(client, hb, variant, address)  # PENDING order counts: they are not new
    r = client.post("/api/v1/referrals/apply", json={"code": code}, headers=hb)
    assert r.status_code == 422 and "new customers" in r.json()["message"]
    c, hc = _customer(db_session, "old2")
    c.created_at = datetime.now(UTC) - timedelta(days=60)
    db_session.commit()
    assert client.post("/api/v1/referrals/apply", json={"code": code}, headers=hc).status_code == 422
    del a


def test_unknown_and_malformed_codes(client, db_session) -> None:
    _b, hb = _customer(db_session, "bad1")
    assert client.post("/api/v1/referrals/apply", json={"code": "ZZZZZZZZ"}, headers=hb).status_code == 404
    for bad in ("ab", "x" * 40, "ABC DEF!", "ABC-DEFG", ""):
        assert client.post("/api/v1/referrals/apply", json={"code": bad}, headers=hb).status_code == 422, bad
    assert db_session.query(Referral).count() == 0


def test_mass_assignment_on_apply_cannot_pick_the_referrer_or_status(client, db_session) -> None:
    a, ha, (b, hb, *_r) = _pair(db_session, client, "mass1")
    evil, _he = _customer(db_session, "mass2")
    r = client.post(
        "/api/v1/referrals/apply",
        json={"code": _code(client, ha), "referrer_user_id": evil.id, "referred_user_id": evil.id,
              "status": "REWARDED", "reward": 99999},
        headers=hb,
    )
    assert r.status_code == 200
    ref = db_session.query(Referral).one()
    assert (ref.referrer_user_id, ref.referred_user_id, ref.status) == (a.id, b.id, "PENDING")
    assert db_session.query(ReferralRewardLedger).count() == 0


def test_concurrent_double_apply_creates_exactly_one_referral(client, db_session) -> None:
    a, ha, (b, hb, *_r) = _pair(db_session, client, "race1")
    code = _code(client, ha)
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = [f.result().status_code for f in [
            pool.submit(lambda: client.post("/api/v1/referrals/apply", json={"code": code}, headers=hb))
            for _ in range(6)]]
    assert sorted(codes).count(200) == 1, codes
    assert all(c in (200, 409, 429) for c in codes), codes
    assert db_session.query(Referral).count() == 1
    del a, b


def test_apply_is_rate_limited(client, db_session) -> None:
    _b, hb = _customer(db_session, "rl1")
    seen = [client.post("/api/v1/referrals/apply", json={"code": "ZZZZZZZZ"}, headers=hb).status_code for _ in range(14)]
    assert 429 in seen, seen  # 10/minute per user


# --------------------------------------------------------------------------
# Qualification & ledger
# --------------------------------------------------------------------------


def test_first_delivered_eligible_order_rewards_both_sides_once(client, db_session) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "q1")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    order = _deliver(client, db_session, hb, variant, address, "q1")  # 5 x 50 = 250 >= 199
    db_session.expire_all()
    ref = db_session.query(Referral).one()
    assert ref.status == "REWARDED" and ref.qualifying_order_id == order["id"]
    rows = {(r.beneficiary_user_id, r.beneficiary_role): r.amount for r in db_session.query(ReferralRewardLedger).all()}
    assert rows == {(a.id, "REFERRER"): Decimal("50.00"), (b.id, "REFERRED"): Decimal("30.00")}
    assert Decimal(client.get("/api/v1/referrals/rewards", headers=ha).json()["balance"]) == Decimal("50")
    assert Decimal(client.get("/api/v1/referrals/rewards", headers=hb).json()["balance"]) == Decimal("30")
    me = client.get("/api/v1/referrals/me", headers=ha).json()["stats"]
    assert me["rewarded"] == 1 and Decimal(me["total_earned"]) == 50
    hist = client.get("/api/v1/referrals/history", headers=ha).json()
    assert hist["total"] == 1 and hist["items"][0]["status"] == "REWARDED"
    assert Decimal(hist["items"][0]["reward_amount"]) == 50


def test_order_below_minimum_does_not_qualify_but_a_later_one_does(client, db_session) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "q2")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    _deliver(client, db_session, hb, variant, address, "q2a", qty="1")  # Rs 50 < 199
    db_session.expire_all()
    assert db_session.query(Referral).one().status == "PENDING"
    assert db_session.query(ReferralRewardLedger).count() == 0
    _deliver(client, db_session, hb, variant, address, "q2b", qty="5")
    db_session.expire_all()
    assert db_session.query(Referral).one().status == "REWARDED"
    assert db_session.query(ReferralRewardLedger).count() == 2
    del a


def test_a_second_qualifying_order_never_rewards_again(client, db_session) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "q3")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    _deliver(client, db_session, hb, variant, address, "q3a")
    _deliver(client, db_session, hb, variant, address, "q3b")
    db_session.expire_all()
    assert db_session.query(ReferralRewardLedger).count() == 2
    del a


def test_undelivered_or_cancelled_orders_never_qualify(client, db_session) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "q4")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    order = _checkout(client, hb, variant, address, qty="5")
    _confirm_cod_and_get_fulfillment_id(client, db_session, hb, order["id"])
    assert client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=hb).status_code == 200
    db_session.expire_all()
    assert db_session.query(Referral).one().status == "PENDING"
    assert db_session.query(ReferralRewardLedger).count() == 0
    del a


def test_expired_referral_is_cancelled_not_rewarded(client, db_session) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "q5")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    db_session.query(Referral).update({"expires_at": datetime.now(UTC) - timedelta(minutes=1)})
    db_session.commit()
    _deliver(client, db_session, hb, variant, address, "q5")
    db_session.expire_all()
    ref = db_session.query(Referral).one()
    assert ref.status == "CANCELLED" and db_session.query(ReferralRewardLedger).count() == 0
    del a


def test_reward_cap_per_referrer_keeps_the_referral_qualified_without_money(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REFERRAL_MAX_REWARDS_PER_REFERRER", 1)
    a, ha = _customer(db_session, "cap0")
    code = _code(client, ha)
    for i in (1, 2):
        b, hb, variant, address, _l = _ready_customer(db_session, f"cap{i}")
        assert client.post("/api/v1/referrals/apply", json={"code": code}, headers=hb).status_code == 200
        _deliver(client, db_session, hb, variant, address, f"cap{i}")
    db_session.expire_all()
    statuses = sorted(r.status for r in db_session.query(Referral).all())
    assert statuses == ["QUALIFIED", "REWARDED"]
    assert db_session.query(ReferralRewardLedger).filter_by(beneficiary_user_id=a.id).count() == 1


def test_disabled_program_never_rewards_even_with_a_pending_referral(client, db_session, monkeypatch) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "off1")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    monkeypatch.setattr(settings, "REFERRAL_ENABLED", False)
    _deliver(client, db_session, hb, variant, address, "off1")
    db_session.expire_all()
    assert db_session.query(Referral).one().status == "PENDING"
    assert db_session.query(ReferralRewardLedger).count() == 0
    del a


def test_double_reward_race_pays_exactly_once(client, db_session, test_engine, monkeypatch) -> None:
    """Six workers qualify the SAME delivered order at the same instant."""
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "dr1")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    monkeypatch.setattr(settings, "REFERRAL_ENABLED", False)
    order = _deliver(client, db_session, hb, variant, address, "dr1")
    monkeypatch.setattr(settings, "REFERRAL_ENABLED", True)
    Session_ = sessionmaker(bind=test_engine)

    def work():
        s = Session_()
        try:
            o = s.get(Order, order["id"])
            ReferralService(s).qualify_for_order(o)
            s.commit()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            s.rollback()
            return type(exc).__name__
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = [f.result() for f in [pool.submit(work) for _ in range(6)]]
    assert "ok" in results
    db_session.expire_all()
    assert db_session.query(ReferralRewardLedger).filter_by(entry_type="REWARD").count() == 2, results
    assert db_session.query(Referral).one().status == "REWARDED"
    del a, b


def test_ledger_is_append_only_in_the_database(client, db_session) -> None:
    a, ha, (b, hb, variant, address) = _pair(db_session, client, "imm1")
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    _deliver(client, db_session, hb, variant, address, "imm1")
    for sql in (
        "UPDATE referral_reward_ledger SET amount = 9999",
        "DELETE FROM referral_reward_ledger",
    ):
        with pytest.raises(DBAPIError):
            db_session.execute(text(sql))
        db_session.rollback()
    assert db_session.query(ReferralRewardLedger).count() == 2
    # and the table has no balance column to tamper with
    cols = {r[0] for r in db_session.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='referral_reward_ledger'"))}
    assert "balance" not in cols
    del a, b


def test_db_constraints_reject_a_self_referral_and_a_bad_ledger_sign(db_session) -> None:
    from sqlalchemy.exc import IntegrityError

    a = _create_user_with_role(db_session, CUSTOMER, "dbc_a@example.com")
    code = ReferralCode(user_id=a.id, code="ABCDEFGH")
    db_session.add(code)
    db_session.commit()
    db_session.add(Referral(referrer_user_id=a.id, referred_user_id=a.id, referral_code_id=code.id,
                            expires_at=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(ReferralCode(user_id=a.id, code="ZZZZZZZZ"))  # second code for same user
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(ReferralCode(user_id=_create_user_with_role(db_session, CUSTOMER, "dbc_b@example.com").id,
                                code="abcdefgh"))  # lower case rejected
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------------
# Reversal & admin
# --------------------------------------------------------------------------


def _rewarded(client, db, tag):
    a, ha, (b, hb, variant, address) = _pair(db, client, tag)
    client.post("/api/v1/referrals/apply", json={"code": _code(client, ha)}, headers=hb)
    order = _deliver(client, db, hb, variant, address, tag)
    db.expire_all()
    return a, ha, b, hb, order, db.query(Referral).one()


def test_admin_reversal_appends_negative_entries_and_is_idempotent(client, db_session) -> None:
    a, ha, b, hb, _order, ref = _rewarded(client, db_session, "rv1")
    admin = _create_user_with_role(db_session, ADMIN, "rv_admin@example.com")
    from tests.firebase_fake import auth_headers_for

    adm = auth_headers_for(db_session, admin)
    r = client.post(f"/api/v1/referrals/admin/{ref.id}/reverse", json={"reason": "fraud review"}, headers=adm)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REVERSED"
    assert Decimal(client.get("/api/v1/referrals/rewards", headers=ha).json()["balance"]) == 0
    assert Decimal(client.get("/api/v1/referrals/rewards", headers=hb).json()["balance"]) == 0
    again = client.post(f"/api/v1/referrals/admin/{ref.id}/reverse", json={"reason": "again"}, headers=adm)
    assert again.status_code == 200
    db_session.expire_all()
    assert db_session.query(ReferralRewardLedger).count() == 4  # 2 rewards + 2 reversals, no more
    assert sorted(x.amount for x in db_session.query(ReferralRewardLedger)) == [
        Decimal("-50.00"), Decimal("-30.00"), Decimal("30.00"), Decimal("50.00")]
    del a, b


def test_refund_of_the_qualifying_order_reverses_the_reward(client, db_session) -> None:
    a, ha, b, hb, order, ref = _rewarded(client, db_session, "rv2")
    ReferralService(db_session).reverse_for_order(order["id"], "Order refunded")
    db_session.commit()
    db_session.expire_all()
    assert db_session.query(Referral).one().status == "REVERSED"
    assert db_session.query(ReferralRewardLedger).count() == 4
    del a, b, ha, hb, ref


def test_authorization_on_referral_endpoints(client, db_session) -> None:
    a, ha, b, hb, _o, ref = _rewarded(client, db_session, "az1")
    _s, support = _staff(db_session, OPERATIONS, "az1")
    _p, partner = _staff(db_session, DELIVERY_PARTNER, "az1")
    for headers in (ha, hb, support, partner):  # customers and non-admin staff
        assert client.get("/api/v1/referrals/admin", headers=headers).status_code == 403
        assert client.get(f"/api/v1/referrals/admin/{ref.id}", headers=headers).status_code == 403
        assert client.post(f"/api/v1/referrals/admin/{ref.id}/reverse", json={"reason": "xxx"}, headers=headers).status_code == 403
    for method, url in (("get", "/api/v1/referrals/me"), ("get", "/api/v1/referrals/history"), ("get", "/api/v1/referrals/rewards")):
        assert getattr(client, method)(url).status_code == 401
        assert getattr(client, method)(url, headers=partner).status_code == 403
    db_session.expire_all()
    assert db_session.query(Referral).one().status == "REWARDED"
    del a, b


def test_history_and_rewards_only_show_the_callers_own_data(client, db_session) -> None:
    a, ha, b, hb, _o, _ref = _rewarded(client, db_session, "idor1")
    c, hc = _customer(db_session, "idor2")
    hist_c = client.get("/api/v1/referrals/history", headers=hc).json()
    assert hist_c["total"] == 0 and hist_c["items"] == []
    assert client.get("/api/v1/referrals/rewards", headers=hc).json()["items"] == []
    # the referrer's history shows a masked name only - never phone / email / ids of the referred user
    item = client.get("/api/v1/referrals/history", headers=ha).json()["items"][0]
    assert set(item) == {"id", "referred_display_name", "status", "applied_at", "expires_at",
                         "qualified_at", "rewarded_at", "reward_amount"}
    # the referred user sees no history of someone else's referral
    assert client.get("/api/v1/referrals/history", headers=hb).json()["total"] == 0
    del a, b, c


def test_admin_list_validates_filters(client, db_session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "lf_admin@example.com")
    from tests.firebase_fake import auth_headers_for

    adm = auth_headers_for(db_session, admin)
    assert client.get("/api/v1/referrals/admin?status=NOPE", headers=adm).status_code == 422
    assert client.get("/api/v1/referrals/admin?page_size=5000", headers=adm).status_code == 422
    assert client.get("/api/v1/referrals/admin?user_id=99999999999999999999", headers=adm).status_code == 422
    assert client.get("/api/v1/referrals/admin", headers=adm).status_code == 200
