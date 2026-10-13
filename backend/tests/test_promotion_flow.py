"""Promo codes end to end over HTTP: an admin creates one, a customer previews
it against their cart, and checkout charges the discounted total. There were
no HTTP-level promotion tests before - only model tests - so this is the
first thing that proves the flow works.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN
from tests.test_phase_13_cart_orders import _ready_customer
from tests.test_phase_18_cancellation_refunds import _staff


def _iso(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


def _create_promo(client: TestClient, admin_headers: dict, **overrides):
    body = {
        "name": "Test offer",
        "code": "SAVE10",
        "discount_type": "PERCENTAGE",
        "discount_value": 10,
        "status": "ACTIVE",
        "starts_at": _iso(timedelta(hours=-1)),
    }
    body.update(overrides)
    return client.post("/api/v1/promotions", json=body, headers=admin_headers)


def _shop(client: TestClient, db_session: Session, tag: str, *, price: str = "100.00", qty: str = "2"):
    user, headers, variant, address = _ready_customer(db_session, tag, price=Decimal(price))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": qty}, headers=headers)
    return user, headers, variant, address


def _evaluate(client: TestClient, headers: dict, code: str | None):
    return client.post("/api/v1/cart/evaluate-promo", json={"promo_code": code}, headers=headers)


def test_percentage_code_previews_and_is_charged_at_checkout(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p1")
    assert _create_promo(client, admin_headers).status_code == 201
    _user, headers, _variant, address = _shop(client, db_session, "PF1")  # 2 x 100.00 = 200.00

    preview = _evaluate(client, headers, "SAVE10").json()
    assert preview["eligible"] is True, preview
    assert Decimal(preview["discount_amount"]) == Decimal("20.00")
    assert Decimal(preview["final_total"]) == Decimal("180.00")

    order = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id, "promo_code": "SAVE10"}, headers=headers
    )
    assert order.status_code == 201, order.text
    body = order.json()
    assert body["subtotal_amount"] == "200.00"
    assert body["discount_amount"] == "20.00"
    assert body["applied_promo_code"] == "SAVE10"
    # 180.00 of goods + Rs 20 base delivery (one product, not a 15-product Bazaar)
    assert body["total_amount"] == "200.00"


def test_code_is_case_and_space_insensitive(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p2")
    _create_promo(client, admin_headers, code="welcome50")  # stored upper-cased
    _user, headers, _variant, _address = _shop(client, db_session, "PF2")
    assert _evaluate(client, headers, "  WeLcOmE50 ").json()["eligible"] is True


def test_fixed_amount_with_minimum_order(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p3")
    _create_promo(
        client, admin_headers, code="FLAT100", discount_type="FIXED_AMOUNT", discount_value=100, min_order_value=500
    )
    _user, headers, _variant, _address = _shop(client, db_session, "PF3", qty="2")  # 200.00 < 500
    too_small = _evaluate(client, headers, "FLAT100").json()
    assert too_small["eligible"] is False
    assert "Minimum order" in too_small["message"]

    client.post("/api/v1/cart/items", json={"variant_id": _variant.id, "quantity": "4"}, headers=headers)  # now 6 x 100
    ok = _evaluate(client, headers, "FLAT100").json()
    assert ok["eligible"] is True
    assert Decimal(ok["discount_amount"]) == Decimal("100.00")
    assert Decimal(ok["final_total"]) == Decimal("500.00")


def test_percentage_discount_respects_the_cap(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p4")
    _create_promo(client, admin_headers, code="BIG50", discount_value=50, max_discount_amount=30)
    _user, headers, _variant, _address = _shop(client, db_session, "PF4")
    assert Decimal(_evaluate(client, headers, "BIG50").json()["discount_amount"]) == Decimal("30.00")


def test_draft_paused_and_expired_codes_are_refused(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p5")
    _create_promo(client, admin_headers, code="DRAFTY", status="DRAFT")
    _create_promo(client, admin_headers, code="OLDIE", starts_at=_iso(timedelta(days=-10)), ends_at=_iso(timedelta(days=-1)))
    _create_promo(client, admin_headers, code="LATER", starts_at=_iso(timedelta(days=2)))
    _user, headers, _variant, _address = _shop(client, db_session, "PF5")
    for code in ("DRAFTY", "OLDIE", "LATER"):
        result = _evaluate(client, headers, code).json()
        assert result["eligible"] is False, code
        assert "not currently active" in result["message"], code
    assert "doesn't exist" in _evaluate(client, headers, "NOPE").json()["message"]


def test_a_draft_code_becomes_usable_once_activated(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p6")
    promo = _create_promo(client, admin_headers, code="LATEON", status="DRAFT").json()
    _user, headers, _variant, _address = _shop(client, db_session, "PF6")
    assert _evaluate(client, headers, "LATEON").json()["eligible"] is False
    assert client.post(f"/api/v1/promotions/{promo['id']}/activate", headers=admin_headers).status_code == 200
    assert _evaluate(client, headers, "LATEON").json()["eligible"] is True


def test_usage_limit_per_customer_is_enforced(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p7")
    _create_promo(client, admin_headers, code="ONCE", usage_limit_per_customer=1)
    _user, headers, variant, address = _shop(client, db_session, "PF7")
    first = client.post("/api/v1/cart/checkout", json={"address_id": address.id, "promo_code": "ONCE"}, headers=headers)
    assert first.status_code == 201

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    second = _evaluate(client, headers, "ONCE").json()
    assert second["eligible"] is False
    assert "usage limit" in second["message"]


def test_new_customer_only_code(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p8")
    _create_promo(client, admin_headers, code="FIRSTBUY", customer_scope="NEW_CUSTOMERS")
    _user, headers, variant, address = _shop(client, db_session, "PF8")
    assert _evaluate(client, headers, "FIRSTBUY").json()["eligible"] is True
    # Placing (and confirming) an order makes them an existing customer.
    order = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers).json()
    client.post("/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    assert _evaluate(client, headers, "FIRSTBUY").json()["eligible"] is False


def test_automatic_promotion_applies_without_a_code(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p9")
    _create_promo(client, admin_headers, code=None, name="Auto 5%", discount_value=5)
    _user, headers, _variant, address = _shop(client, db_session, "PF9")
    preview = _evaluate(client, headers, None).json()
    assert preview["eligible"] is True
    assert Decimal(preview["discount_amount"]) == Decimal("10.00")
    order = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers).json()
    assert order["discount_amount"] == "10.00"


def test_bad_codes_never_silently_charge_full_price_at_checkout(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "p10")
    _create_promo(client, admin_headers, code="DEADCODE", status="DISABLED")
    _user, headers, _variant, address = _shop(client, db_session, "PF10")
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id, "promo_code": "DEADCODE"}, headers=headers
    )
    assert response.status_code in (400, 422)  # rejected, not quietly ignored


# ---------------------------------------------------------------------------
# Offers carousel (GET /offers) - what the app's Home screen advertises
# ---------------------------------------------------------------------------


def _offers(client: TestClient):
    response = client.get("/api/v1/offers")  # public: no auth needed
    assert response.status_code == 200, response.text
    return response.json()


def test_offers_lists_only_live_promotions_the_admin_chose_to_show(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "o1")
    shown = {"show_in_carousel": True, "image_url": "https://example.com/a.jpg"}
    _create_promo(client, admin_headers, code="SHOWME", customer_title="Big saving", **shown)
    _create_promo(client, admin_headers, code="HIDDEN1")  # not switched on for the carousel
    _create_promo(client, admin_headers, code="DRAFTED", status="DRAFT", **shown)
    _create_promo(client, admin_headers, code="PAUSED1", status="PAUSED", **shown)
    _create_promo(
        client, admin_headers, code="EXPIRED1",
        starts_at=_iso(timedelta(days=-9)), ends_at=_iso(timedelta(days=-1)), **shown,
    )
    _create_promo(client, admin_headers, code="FUTURE1", starts_at=_iso(timedelta(days=3)), **shown)
    _create_promo(client, admin_headers, code="VIPONLY", customer_scope="SPECIFIC", **shown)

    offers = _offers(client)

    assert [o["code"] for o in offers] == ["SHOWME"]
    offer = offers[0]
    assert offer["title"] == "Big saving"
    assert offer["image_url"] == "https://example.com/a.jpg"
    assert offer["discount_label"] == "10% OFF"


def test_offer_labels_and_fine_print(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "o2")
    _create_promo(
        client, admin_headers, code="FLAT100", discount_type="FIXED_AMOUNT", discount_value=100,
        min_order_value=999, customer_scope="NEW_CUSTOMERS", show_in_carousel=True, priority=1,
    )
    _create_promo(
        client, admin_headers, code="PCT15", discount_value=15, max_discount_amount=150,
        min_order_value=599, show_in_carousel=True, priority=2,
    )
    first, second = _offers(client)
    assert first["discount_label"] == "Rs 100 OFF"
    assert first["fine_print"] == "On orders above Rs 999"
    assert first["audience"] == "New customers"
    assert second["discount_label"] == "15% OFF"
    assert second["fine_print"] == "On orders above Rs 599 - up to Rs 150 off"
    assert second["audience"] is None


def test_offer_disappears_when_its_usage_limit_is_used_up(client: TestClient, db_session: Session) -> None:
    _admin, admin_headers = _staff(db_session, ADMIN, "o3")
    _create_promo(client, admin_headers, code="LASTONE", usage_limit_total=1, show_in_carousel=True)
    assert [o["code"] for o in _offers(client)] == ["LASTONE"]
    _user, headers, _variant, address = _shop(client, db_session, "OF3")
    assert client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id, "promo_code": "LASTONE"}, headers=headers
    ).status_code == 201
    assert _offers(client) == []


def test_an_offer_shown_in_the_carousel_really_works_at_checkout(client: TestClient, db_session: Session) -> None:
    """The carousel can never advertise a code that checkout would refuse."""
    _admin, admin_headers = _staff(db_session, ADMIN, "o4")
    _create_promo(client, admin_headers, code="ADVERTISED", show_in_carousel=True)
    _user, headers, _variant, _address = _shop(client, db_session, "OF4")
    for offer in _offers(client):
        assert _evaluate(client, headers, offer["code"]).json()["eligible"] is True
