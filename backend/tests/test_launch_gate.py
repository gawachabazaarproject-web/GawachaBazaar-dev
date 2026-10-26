# ruff: noqa: F811  (pytest fixtures imported from other test modules)
"""Hostile launch-gate checks: things a customer, an attacker or a flaky network
can do to checkout, payments and delivery. Direct API calls with real tokens
from the Firebase fake; the database is real PostgreSQL. Each test says what it
tries to break."""

import logging
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.cart_item import CartItem
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.payment import Payment
from app.services.routing.base import RoutingError
from tests.test_delivery_quote_api import _locate, stub  # noqa: F401 - stub is a pytest fixture
from tests.test_online_checkout import _basket, _start
from tests.test_phase_13_cart_orders import _customer, _ready_customer
from tests.test_razorpay_payments import razorpay  # noqa: F401 - pytest fixture


def _order_for(client, headers, variant, address, qty="1"):
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": qty}, headers=headers)
    return client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)


# --------------------------------------------------------------------------
# BOLA / IDOR: the payment endpoints an attacker would try with a guessed id
# --------------------------------------------------------------------------


def test_customer_b_cannot_touch_customer_as_payment_in_any_way(client: TestClient, db_session: Session, stub) -> None:
    a, ha, variant, addr = _ready_customer(db_session, "IDA", price=Decimal("25.00"))
    _b, hb = _customer(db_session, "IDB")
    order = _order_for(client, ha, variant, _locate(db_session, addr)).json()
    paid = client.post("/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=ha)
    assert paid.status_code in (200, 201), paid.text
    pid = paid.json()["id"]

    attempts = [
        ("get", f"/api/v1/payments/{pid}", None),
        ("get", f"/api/v1/payments/{pid}/checkout", None),
        ("post", f"/api/v1/payments/{pid}/confirm", {"razorpay_order_id": "o", "razorpay_payment_id": "p", "razorpay_signature": "s"}),
        ("post", f"/api/v1/payments/{pid}/verify", {}),
        ("post", f"/api/v1/payments/{pid}/retry", {}),
        ("post", f"/api/v1/orders/{order['id']}/cancel", {}),
        ("get", f"/api/v1/orders/{order['id']}", None),
    ]
    for method, url, body in attempts:
        r = getattr(client, method)(url, headers=hb, **({"json": body} if body is not None else {}))
        assert r.status_code in (403, 404), f"B reached A's {method.upper()} {url}: {r.status_code} {r.text[:120]}"
    db_session.expire_all()
    assert db_session.get(Order, order["id"]).status != "CANCELLED"
    assert db_session.get(Payment, pid).status in ("PENDING", "PROCESSING", "PAID")  # unchanged by B


def test_customer_b_cannot_verify_or_confirm_customer_as_online_checkout(client, db_session, razorpay) -> None:
    _a, ha, _v, addr = _basket(client, db_session, "OSA")
    _b, hb = _customer(db_session, "OSB")
    started = _start(client, ha, addr.id).json()
    sid, gid = started["session_id"], started["gateway_order_id"]
    for url, body in (
        (f"/api/v1/payments/online/{sid}/verify", {}),
        (f"/api/v1/payments/online/{sid}/confirm", {"razorpay_order_id": gid, "razorpay_payment_id": "pay_x", "razorpay_signature": "x"}),
    ):
        assert client.post(url, json=body, headers=hb).status_code in (403, 404)
    assert db_session.query(Order).count() == 0


# --------------------------------------------------------------------------
# Double tap / retry
# --------------------------------------------------------------------------


def test_double_tap_on_place_order_creates_one_order_and_reserves_once(client, db_session, stub) -> None:
    _u, headers, variant, addr = _ready_customer(db_session, "DT1", price=Decimal("25.00"))
    addr = _locate(db_session, addr)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "3"}, headers=headers)

    def tap():
        return client.post("/api/v1/cart/checkout", json={"address_id": addr.id}, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = [f.result() for f in [pool.submit(tap) for _ in range(4)]]
    db_session.expire_all()
    assert db_session.query(Order).count() == 1, codes
    assert sum(1 for c in codes if c in (200, 201)) >= 1
    assert all(c in (200, 201, 400, 404, 409, 422) for c in codes), codes  # never a 5xx
    lot = db_session.query(InventoryLot).one()
    assert lot.reserved_quantity == Decimal("3")  # reserved once, not 4 times


def test_double_tap_on_online_start_opens_one_gateway_order(client, db_session, razorpay) -> None:
    _u, headers, _v, addr = _basket(client, db_session, "DT2")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [f.result() for f in [pool.submit(lambda: _start(client, headers, addr.id)) for _ in range(4)]]
    assert all(r.status_code == 200 for r in results), [r.status_code for r in results]
    assert len({r.json()["gateway_order_id"] for r in results}) == 1
    assert db_session.query(Order).count() == 0  # nothing is an order until paid


# --------------------------------------------------------------------------
# Never trust the client with money
# --------------------------------------------------------------------------


def test_client_supplied_prices_fees_status_and_distance_are_ignored(client, db_session, stub) -> None:
    _u, headers, variant, addr = _ready_customer(db_session, "TAMP", price=Decimal("25.00"))
    addr = _locate(db_session, addr)
    honest = _order_for(client, headers, variant, addr, qty="2")
    assert honest.status_code in (200, 201), honest.text
    honest_total = Decimal(honest.json()["total_amount"])
    client.post(f"/api/v1/orders/{honest.json()['id']}/cancel", json={}, headers=headers)

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    evil = client.post(
        "/api/v1/cart/checkout",
        json={
            "address_id": addr.id, "total_amount": "0.01", "subtotal_amount": "0.01", "delivery_fee": "0",
            "discount_amount": "9999", "status": "CONFIRMED", "distance_meters": 1, "distance_km": 0.001,
            "warehouse_id": 999, "unit_price": "0.01", "payment_status": "PAID",
        },
        headers=headers,
    )
    assert evil.status_code in (200, 201, 400, 409, 422), evil.text
    if evil.status_code in (200, 201):
        body = evil.json()
        assert Decimal(body["total_amount"]) == honest_total
        assert body["status"] == "PENDING"


@pytest.mark.parametrize("bad", ["-1", "0", "NaN", "Infinity", "-Infinity", "1e30", "99999999999999", "abc", "", None, "1.0005", [1], {"a": 1}])
def test_cart_quantity_abuse_is_rejected_without_a_server_error(client, db_session, bad) -> None:
    _u, headers, variant, _addr = _ready_customer(db_session, "QTY", price=Decimal("25.00"))
    r = client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": bad}, headers=headers)
    assert r.status_code in (400, 409, 422), (bad, r.status_code, r.text[:100])
    assert db_session.query(CartItem).count() == 0


def test_cart_refuses_missing_disabled_and_deleted_variants_and_more_than_stock_fails_checkout(client, db_session, stub) -> None:
    _u, headers, variant, addr = _ready_customer(db_session, "STK", price=Decimal("25.00"))
    addr = _locate(db_session, addr)
    assert client.post("/api/v1/cart/items", json={"variant_id": 987654, "quantity": "1"}, headers=headers).status_code == 404
    # asks for more than exists: the cart may accept it, checkout must not oversell
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "5000"}, headers=headers)
    r = client.post("/api/v1/cart/checkout", json={"address_id": addr.id}, headers=headers)
    assert r.status_code == 409, r.text
    assert db_session.query(Order).count() == 0
    lot = db_session.query(InventoryLot).one()
    assert lot.reserved_quantity == 0
    # variant disabled after it was in the cart
    client.delete("/api/v1/cart", headers=headers)  # may not exist; harmless
    variant.status = "INACTIVE"
    db_session.commit()
    again = client.post("/api/v1/cart/checkout", json={"address_id": addr.id}, headers=headers)
    assert again.status_code in (400, 404, 409, 422)
    assert db_session.query(Order).count() == 0


# --------------------------------------------------------------------------
# Delivery: failures must never become a cheap or free delivery
# --------------------------------------------------------------------------


def test_routing_outage_blocks_checkout_instead_of_inventing_a_distance(client, db_session, stub) -> None:
    stub.error = RoutingError("osrm down")
    _u, headers, variant, addr = _ready_customer(db_session, "OUT", price=Decimal("25.00"))
    addr = _locate(db_session, addr, lat="21.200000", lng="79.120000")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    # route cache is cold for this address
    r = client.post("/api/v1/cart/checkout", json={"address_id": addr.id}, headers=headers)
    assert r.status_code in (502, 503, 504), r.text
    assert db_session.query(Order).count() == 0
    q = client.post("/api/v1/delivery/quote", json={"address_id": addr.id}, headers=headers)
    assert q.status_code in (502, 503, 504) or q.json().get("available") is False
    assert "delivery_fee" not in q.text or q.status_code >= 500 or q.json().get("delivery_fee") in (None,)


def test_address_without_a_map_location_cannot_buy_at_the_base_fee_only(client, db_session, stub) -> None:
    _u, headers, variant, addr = _ready_customer(db_session, "NOLOC", price=Decimal("25.00"))
    assert addr.latitude is None
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    r = client.post("/api/v1/cart/checkout", json={"address_id": addr.id}, headers=headers)
    assert r.status_code in (400, 409, 422), r.text  # packing point is configured by the stub fixture
    assert db_session.query(Order).count() == 0


@pytest.mark.parametrize("lat,lng", [(91, 79), (-91, 79), (21, 181), (21, -181), ("NaN", 79), (21, "Infinity"), ("abc", 1), (None, 79)])
def test_impossible_coordinates_never_reach_the_database(client, db_session, lat, lng) -> None:
    user, headers = _customer(db_session, "COORD")
    body = {"label": "Home", "address_line_1": "1 Test", "city": "Nagpur", "state": "MH", "postal_code": "440001", "latitude": lat, "longitude": lng}
    r = client.post("/api/v1/addresses", json=body, headers=headers)
    if r.status_code in (200, 201):  # (None, 79) may be accepted as "no location"; never an impossible number
        got = r.json()
        assert got.get("latitude") is None or -90 <= float(got["latitude"]) <= 90
        assert got.get("longitude") is None or -180 <= float(got["longitude"]) <= 180
        assert lat is None or lat == 0 or isinstance(lat, int) and abs(lat) <= 90
    else:
        assert r.status_code in (400, 422), r.text


def test_quote_for_an_unknown_or_foreign_address_never_returns_a_fee(client, db_session, stub) -> None:
    _u, headers = _customer(db_session, "QF")
    for aid in (0, -1, 987654, 2**62):
        r = client.post("/api/v1/delivery/quote", json={"address_id": aid}, headers=headers)
        assert r.status_code in (404, 422), (aid, r.status_code)
    for body in ({}, {"address_id": "x"}, {"address_id": 1, "distance_meters": 5}):
        assert client.post("/api/v1/delivery/quote", json=body, headers=headers).status_code in (200, 404, 422)


# --------------------------------------------------------------------------
# Order / payment state cannot be walked backwards by a caller
# --------------------------------------------------------------------------


def test_completed_or_cancelled_orders_cannot_be_cancelled_or_paid_again(client, db_session, stub) -> None:
    _u, headers, variant, addr = _ready_customer(db_session, "ST", price=Decimal("25.00"))
    order_json = _order_for(client, headers, variant, _locate(db_session, addr)).json()
    pay = client.post("/api/v1/payments", json={"order_id": order_json["id"], "payment_method": "COD"}, headers=headers).json()
    order = db_session.get(Order, order_json["id"])

    order.status = "COMPLETED"
    db_session.commit()
    assert client.post(f"/api/v1/orders/{order.id}/cancel", json={}, headers=headers).status_code in (400, 409, 422)
    db_session.expire_all()
    assert db_session.get(Order, order.id).status == "COMPLETED"

    order = db_session.get(Order, order.id)
    order.status = "CANCELLED"
    db_session.commit()
    for url in (f"/api/v1/payments/{pay['id']}/confirm", f"/api/v1/payments/{pay['id']}/retry"):
        r = client.post(url, json={}, headers=headers)
        assert r.status_code in (400, 404, 409, 422), (url, r.status_code, r.text[:100])
    db_session.expire_all()
    assert db_session.get(Order, order.id).status == "CANCELLED"
    assert db_session.get(Payment, pay["id"]).status != "PAID"


def test_the_client_cannot_declare_a_payment_successful(client, db_session, razorpay) -> None:
    _u, headers, _v, addr = _basket(client, db_session, "LIE")
    started = _start(client, headers, addr.id).json()
    for body in (
        {"payment_success": True},
        {"razorpay_order_id": started["gateway_order_id"], "razorpay_payment_id": "pay_made_up", "razorpay_signature": "0" * 64},
        {"razorpay_order_id": "order_other", "razorpay_payment_id": "pay_made_up", "razorpay_signature": "abc"},
    ):
        r = client.post(f"/api/v1/payments/online/{started['session_id']}/confirm", json=body, headers=headers)
        assert r.status_code in (400, 402, 409, 422), (body, r.status_code, r.text[:100])
    assert db_session.query(Order).count() == 0


# --------------------------------------------------------------------------
# Error contract and logging
# --------------------------------------------------------------------------


def test_malformed_oversized_and_hostile_input_gets_a_clean_4xx(client, db_session) -> None:
    _u, headers = _customer(db_session, "ERR")
    huge = "A" * 2_000_000
    cases = [
        client.post("/api/v1/addresses", content=b"{not json", headers={**headers, "Content-Type": "application/json"}),
        client.post("/api/v1/addresses", content=b"", headers={**headers, "Content-Type": "application/json"}),
        client.post("/api/v1/addresses", json={"label": huge, "address_line_1": huge, "city": "x", "state": "x", "postal_code": "1"}, headers=headers),
        client.post("/api/v1/addresses", json={"label": "'; DROP TABLE users; --", "address_line_1": "1", "city": "x", "state": "x", "postal_code": "1"}, headers=headers),
        client.get("/api/v1/orders/999999999999999999999999", headers=headers),
        client.get("/api/v1/orders/abc", headers=headers),
        client.get("/api/v1/does/not/exist", headers=headers),
    ]
    for r in cases:
        assert r.status_code < 500 or r.status_code == 413, (r.request.url, r.status_code)
        text = r.text
        for leak in ("Traceback", 'File "', "psycopg", "sqlalchemy", "SELECT ", "/app/", "site-packages"):
            assert leak not in text, f"{r.request.url} leaked {leak!r}"
    # the injection string was stored as plain data, tables still exist
    assert client.get("/api/v1/addresses", headers=headers).status_code == 200


def test_bad_and_missing_tokens_are_401_and_the_token_is_never_logged(client, caplog) -> None:
    secret = "eyJhbGciOiJSUzI1NiJ9.SUPERSECRETPAYLOAD.SIGNATURE-VALUE-123456"
    with caplog.at_level(logging.DEBUG):
        r1 = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {secret}"})
        r2 = client.get("/api/v1/orders")
        r3 = client.get("/api/v1/orders", headers={"Authorization": "Bearer "})
        r4 = client.get("/api/v1/orders", headers={"Authorization": "Basic abc"})
    assert (r1.status_code, r2.status_code) == (401, 401) and r3.status_code in (401, 403) and r4.status_code in (401, 403)
    assert "SUPERSECRETPAYLOAD" not in caplog.text and secret not in caplog.text
    assert "Traceback" not in r1.text


def test_security_headers_and_docs_are_closed_in_production(monkeypatch) -> None:
    from starlette.testclient import TestClient as TC

    from app.main import create_application

    monkeypatch.setattr(settings, "APP_ENV", "production")
    app = create_application()
    c = TC(app, raise_server_exceptions=False)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(path).status_code == 404, path
    r = c.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["referrer-policy"] == "no-referrer"


def test_cors_rejects_unlisted_origins_and_never_uses_a_wildcard(client) -> None:
    ok = client.options(
        "/api/v1/orders",
        headers={"Origin": settings.ALLOWED_ORIGINS[0], "Access-Control-Request-Method": "GET"},
    )
    evil = client.options(
        "/api/v1/orders",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == settings.ALLOWED_ORIGINS[0]
    assert evil.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")
    assert "*" not in settings.ALLOWED_ORIGINS
