"""Customer B must not be able to read or change customer A's private data by
guessing/using A's ids. Direct API calls with B's valid token (not UI paths).

Existing suites already cover: cart, order detail, payment, reservation,
fulfillment, bulk-order request and checkout-session confirm. This file covers
what had no tests: the addresses router, cart-item ids, order sub-resources
(refund/payment/reservation/fulfillment) and push tokens.
"""

from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.models.address import Address
from app.models.cart_item import CartItem
from app.models.push_token import PushToken
from tests.test_phase_13_cart_orders import _create_address, _customer, _ready_customer


def _two_customers(client: TestClient, db_session: Session):
    a, ha, variant, addr_a = _ready_customer(db_session, "XA", price=Decimal("25.00"))
    b, hb = _customer(db_session, "XB")
    addr_b = _create_address(db_session, b)
    return (a, ha, variant, addr_a), (b, hb, addr_b)


def test_addresses_are_private_to_their_owner(client: TestClient, db_session: Session) -> None:
    (a, ha, _v, addr_a), (_b, hb, addr_b) = _two_customers(client, db_session)

    assert client.get(f"/api/v1/addresses/{addr_a.id}", headers=hb).status_code == 404
    patch = client.patch(f"/api/v1/addresses/{addr_a.id}", json={"label": "pwned", "city": "Evil"}, headers=hb)
    assert patch.status_code == 404
    assert client.delete(f"/api/v1/addresses/{addr_a.id}", headers=hb).status_code == 404

    listing = client.get("/api/v1/addresses", headers=hb).json()
    assert "items" in listing, listing  # guard against a vacuous check if the shape changes
    listed_ids = {x["id"] for x in listing["items"]}
    assert addr_a.id not in listed_ids and addr_b.id in listed_ids

    db_session.expire_all()
    still = db_session.get(Address, addr_a.id)
    assert still is not None and still.label == "Home" and still.city == "Nagpur" and still.user_id == a.id
    # and the owner still can
    assert client.get(f"/api/v1/addresses/{addr_a.id}", headers=ha).status_code == 200


def test_cart_items_cannot_be_changed_by_another_customer(client: TestClient, db_session: Session) -> None:
    (_a, ha, variant, _addr), (_b, hb, _addr_b) = _two_customers(client, db_session)
    added = client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=ha)
    assert added.status_code in (200, 201), added.text
    item_id = db_session.query(CartItem).one().id

    assert client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": "99"}, headers=hb).status_code == 404
    assert client.delete(f"/api/v1/cart/items/{item_id}", headers=hb).status_code == 404

    db_session.expire_all()
    item = db_session.query(CartItem).one()
    assert item.id == item_id and item.quantity == Decimal("2")


def test_order_sub_resources_are_private_to_the_buyer(client: TestClient, db_session: Session) -> None:
    (_a, ha, variant, addr_a), (_b, hb, _addr_b) = _two_customers(client, db_session)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=ha)
    order = client.post("/api/v1/cart/checkout", json={"address_id": addr_a.id}, headers=ha)
    assert order.status_code in (200, 201), order.text
    order_id = order.json()["id"]

    for suffix in ("", "/payment", "/reservation", "/fulfillment", "/refund"):
        r = client.get(f"/api/v1/orders/{order_id}{suffix}", headers=hb)
        assert r.status_code == 404, f"B can reach A's order{suffix or ''}: {r.status_code}"
    assert client.post(f"/api/v1/orders/{order_id}/cancel", json={}, headers=hb).status_code == 404
    b_orders = client.get("/api/v1/orders", headers=hb).json()
    assert "items" in b_orders, b_orders
    assert b_orders["items"] == []

    mine = client.get(f"/api/v1/orders/{order_id}", headers=ha)
    assert mine.status_code == 200 and mine.json()["status"] != "CANCELLED"


def test_one_customer_cannot_unregister_anothers_push_token(client: TestClient, db_session: Session) -> None:
    (a, ha, *_), (_b, hb, _addr_b) = _two_customers(client, db_session)
    token = "ExponentPushToken[qa-test-token-a]"
    assert client.post("/api/v1/push-tokens", json={"token": token, "platform": "android"}, headers=ha).status_code < 300
    client.post("/api/v1/push-tokens/unregister", json={"token": token}, headers=hb)

    db_session.expire_all()
    row = db_session.query(PushToken).filter_by(token=token).one_or_none()
    assert row is not None and row.user_id == a.id
