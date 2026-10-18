# ruff: noqa: F811  (pytest fixtures imported from another test module)
"""Money / stock integrity of the pay-first online checkout under concurrency
and cross-path conditions. Real PostgreSQL, real threads, real row locks; only
Razorpay's REST API is faked (same fake the existing suite uses).

Assertions are business rules, not implementation details:
  * one basket => at most one order and one payment
  * money captured is either an order's payment or refunded exactly once
  * stock is committed exactly once and never goes negative
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.models.checkout_session import CheckoutSession
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.payment import Payment
from tests.test_online_checkout import _basket, _start
from tests.test_razorpay_payments import (  # noqa: F401 - razorpay is a pytest fixture
    FakeRazorpay,
    _checkout_signature,
    _webhook,
    razorpay,
)


def _confirm(client: TestClient, headers: dict, started: dict, payment: dict):
    return client.post(
        f"/api/v1/payments/online/{started['session_id']}/confirm",
        json={
            "razorpay_order_id": started["gateway_order_id"],
            "razorpay_payment_id": payment["id"],
            "razorpay_signature": _checkout_signature(started["gateway_order_id"], payment["id"]),
        },
        headers=headers,
    )


def _lot_state(db: Session):
    db.expire_all()
    lot = db.query(InventoryLot).one()
    return lot.quantity, lot.reserved_quantity


# ---------------------------------------------------------------------------
# T1 - a basket ordered through another path must not swallow an online payment
# ---------------------------------------------------------------------------


def test_online_payment_for_a_basket_already_ordered_by_cod_is_refunded_not_attached(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """Customer opens the Razorpay sheet, then places the SAME basket as Cash on
    Delivery, then the online payment is captured anyway (open UPI app, second
    tab). The captured money must not be silently attached to the COD order."""
    _user, headers, _variant, address = _basket(client, db_session, "MI1")
    started = _start(client, headers, address.id).json()

    cod_order = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert cod_order.status_code in (200, 201), cod_order.text
    cod = client.post(
        "/api/v1/payments",
        json={"order_id": cod_order.json()["id"], "payment_method": "COD"},
        headers=headers,
    )
    assert cod.status_code in (200, 201), cod.text

    payment = razorpay.add_payment(started["gateway_order_id"], "captured")
    response = _confirm(client, headers, started, payment)

    db_session.expire_all()
    orders = db_session.query(Order).all()
    payments = db_session.query(Payment).all()
    session = db_session.query(CheckoutSession).one()
    refunded_minor = sum(r["amount"] for r in razorpay.refunds if r["payment_id"] == payment["id"])

    # Business rule: the customer was charged online (7000 paise captured) for a
    # basket that already became a COD order. Either the money is returned, or
    # the request is rejected AND flagged; it must not be "completed" against
    # the COD order while the money stays captured.
    assert len(orders) == 1 and len(payments) == 1 and payments[0].payment_method == "COD"
    attached_silently = session.status == "COMPLETED" and refunded_minor == 0
    assert not attached_silently, (
        f"captured online payment kept and attached to the COD order "
        f"(response={response.status_code}, session={session.status}, refunded_minor={refunded_minor})"
    )
    assert refunded_minor in (0, started["amount_minor"])


# ---------------------------------------------------------------------------
# T2 / T3 - the same captured payment arriving twice at once
# ---------------------------------------------------------------------------


def test_confirm_and_webhook_racing_place_exactly_one_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "MI2", quantity="2")
    started = _start(client, headers, address.id).json()
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")
    body, hdrs = _webhook("payment.captured", payment)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_confirm, client, headers, started, payment)
        f2 = pool.submit(client.post, "/api/v1/payments/webhooks/razorpay", content=body, headers=hdrs)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(Payment).count() == 1
    assert db_session.query(Payment).one().status == "PAID"
    assert db_session.query(CheckoutSession).one().status == "COMPLETED"
    assert razorpay.refunds == []
    quantity, reserved = _lot_state(db_session)
    assert reserved == Decimal("2")  # committed once, not twice
    assert quantity - reserved >= 0


def test_two_simultaneous_confirms_place_exactly_one_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "MI3", quantity="2")
    started = _start(client, headers, address.id).json()
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_confirm, client, headers, started, payment) for _ in range(2)]
        results = [f.result() for f in futures]

    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert results[0].json()["order"]["id"] == results[1].json()["order"]["id"]
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(Payment).count() == 1
    assert razorpay.refunds == []
    _quantity, reserved = _lot_state(db_session)
    assert reserved == Decimal("2")


# ---------------------------------------------------------------------------
# T4 - two customers pay for the last unit at the same moment
# ---------------------------------------------------------------------------


def test_two_customers_paying_for_the_last_unit_one_order_one_refund(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    from tests.test_phase_13_cart_orders import _create_address, _customer

    _u1, h1, variant, a1 = _basket(client, db_session, "MI4", quantity="1")
    lot = db_session.query(InventoryLot).one()
    lot.quantity = Decimal("1")  # exactly one unit exists
    db_session.commit()

    u2, h2 = _customer(db_session, "MI4B")
    a2 = _create_address(db_session, u2)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=h2)

    s1 = _start(client, h1, a1.id)
    s2 = _start(client, h2, a2.id)
    assert s1.status_code == 200 and s2.status_code == 200, (s1.text, s2.text)  # both see stock at start
    s1, s2 = s1.json(), s2.json()
    p1 = razorpay.add_payment(s1["gateway_order_id"], "captured")
    p2 = razorpay.add_payment(s2["gateway_order_id"], "captured")

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_confirm, client, h1, s1, p1)
        f2 = pool.submit(_confirm, client, h2, s2, p2)
        r1, r2 = f1.result(), f2.result()

    assert sorted([r1.status_code, r2.status_code]) == [200, 409], (r1.text, r2.text)
    db_session.expire_all()
    assert db_session.query(Order).count() == 1  # never oversold
    assert db_session.query(Payment).count() == 1
    quantity, reserved = _lot_state(db_session)
    assert 0 <= reserved <= quantity  # non-negative stock invariant
    loser_payment = p2 if r1.status_code == 200 else p1
    refunds = [r for r in razorpay.refunds]
    assert len(refunds) == 1 and refunds[0]["payment_id"] == loser_payment["id"]
    assert refunds[0]["amount"] == loser_payment["amount"]
    statuses = sorted(s.status for s in db_session.query(CheckoutSession).all())
    assert statuses == ["COMPLETED", "REFUNDED"]
