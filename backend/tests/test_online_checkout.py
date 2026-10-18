# ruff: noqa: F811  (pytest fixtures imported from another test module)
"""Pay-first online checkout: Razorpay opens BEFORE any order exists, and the
order is placed only after the payment succeeds (app/services/checkout_session.py).

Runs the real RazorpayGateway adapter against the in-memory fake of
Razorpay's REST API used by test_razorpay_payments.py.
"""

from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.cart import Cart
from app.models.checkout_session import CheckoutSession
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.payment import Payment
from tests.test_phase_13_cart_orders import _ready_customer
from tests.test_razorpay_payments import (  # noqa: F401 - razorpay is a pytest fixture
    FakeRazorpay,
    _checkout_signature,
    _webhook,
    razorpay,
)

# 2 x Rs 25 basket + the configured base delivery fee (the test addresses have no
# coordinates, so no per-km charge) - follows DELIVERY_BASE_FEE instead of a literal.
BASKET_TOTAL = Decimal("50.00") + settings.DELIVERY_BASE_FEE
BASKET_TOTAL_MINOR = int(BASKET_TOTAL * 100)
PROMO_TOTAL = BASKET_TOTAL - Decimal("5.00")  # 10% off the Rs 50 subtotal
PROMO_TOTAL_MINOR = int(PROMO_TOTAL * 100)


def _basket(client: TestClient, db_session: Session, tag: str, quantity: str = "2"):
    user, headers, variant, address = _ready_customer(db_session, tag, price=Decimal("25.00"))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": quantity}, headers=headers)
    return user, headers, variant, address


def _start(client: TestClient, headers: dict, address_id: int):
    return client.post("/api/v1/payments/online/start", json={"address_id": address_id}, headers=headers)


def _pay_and_confirm(client: TestClient, razorpay: FakeRazorpay, headers: dict, started: dict):
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")
    return client.post(
        f"/api/v1/payments/online/{started['session_id']}/confirm",
        json={
            "razorpay_order_id": started["gateway_order_id"],
            "razorpay_payment_id": payment["id"],
            "razorpay_signature": _checkout_signature(started["gateway_order_id"], payment["id"]),
        },
        headers=headers,
    )


def test_start_opens_razorpay_without_creating_an_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    user, headers, _variant, address = _basket(client, db_session, "OC1")

    response = _start(client, headers, address.id)

    assert response.status_code == 200, response.text
    body = response.json()
    # 2 x 25.00 + Rs 20 base delivery (one product, not a 15-product Bazaar).
    assert Decimal(body["amount"]) == BASKET_TOTAL
    assert body["amount_minor"] == BASKET_TOTAL_MINOR
    assert body["gateway_order_id"] in razorpay.orders
    assert razorpay.orders[body["gateway_order_id"]]["amount"] == BASKET_TOTAL_MINOR

    db_session.expire_all()
    assert db_session.query(Order).count() == 0  # nothing placed yet
    assert db_session.query(Payment).count() == 0
    cart = db_session.query(Cart).filter_by(user_id=user.id).one()
    assert cart.status == "ACTIVE"  # cart untouched
    reserved = db_session.query(InventoryLot).first().reserved_quantity
    assert reserved == 0  # no stock reserved either


def test_start_twice_for_same_basket_reuses_the_razorpay_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC2")
    first = _start(client, headers, address.id).json()
    second = _start(client, headers, address.id).json()
    assert first["session_id"] == second["session_id"]
    assert first["gateway_order_id"] == second["gateway_order_id"]
    assert len(razorpay.orders) == 1


def test_confirm_after_payment_places_the_paid_confirmed_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    user, headers, _variant, address = _basket(client, db_session, "OC3")
    started = _start(client, headers, address.id).json()

    response = _pay_and_confirm(client, razorpay, headers, started)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order"]["status"] == "CONFIRMED"
    assert Decimal(body["order"]["total_amount"]) == BASKET_TOTAL
    assert Decimal(body["order"]["delivery_fee"]) == settings.DELIVERY_BASE_FEE
    assert body["payment"]["status"] == "PAID"
    assert body["payment"]["payment_method"] == "UPI"

    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(Cart).filter_by(user_id=user.id).one().status == "CHECKED_OUT"
    session = db_session.query(CheckoutSession).one()
    assert session.status == "COMPLETED" and session.order_id == body["order"]["id"]


def test_confirm_twice_returns_the_same_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC4")
    started = _start(client, headers, address.id).json()
    first = _pay_and_confirm(client, razorpay, headers, started)
    payment = razorpay.payments[started["gateway_order_id"]][0]
    second = client.post(
        f"/api/v1/payments/online/{started['session_id']}/confirm",
        json={
            "razorpay_order_id": started["gateway_order_id"],
            "razorpay_payment_id": payment["id"],
            "razorpay_signature": _checkout_signature(started["gateway_order_id"], payment["id"]),
        },
        headers=headers,
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["order"]["id"] == second.json()["order"]["id"]
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(Payment).count() == 1


def test_confirm_without_a_captured_payment_places_no_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    user, headers, _variant, address = _basket(client, db_session, "OC5")
    started = _start(client, headers, address.id).json()
    # Razorpay reports the attempt as failed - never captured.
    payment = razorpay.add_payment(started["gateway_order_id"], "failed")

    response = client.post(
        f"/api/v1/payments/online/{started['session_id']}/confirm",
        json={
            "razorpay_order_id": started["gateway_order_id"],
            "razorpay_payment_id": payment["id"],
            "razorpay_signature": _checkout_signature(started["gateway_order_id"], payment["id"]),
        },
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PAYMENT_NOT_CONFIRMED"
    db_session.expire_all()
    assert db_session.query(Order).count() == 0
    assert db_session.query(Cart).filter_by(user_id=user.id).one().status == "ACTIVE"


def test_confirm_with_a_bad_signature_is_rejected(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC6")
    started = _start(client, headers, address.id).json()
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")

    response = client.post(
        f"/api/v1/payments/online/{started['session_id']}/confirm",
        json={
            "razorpay_order_id": started["gateway_order_id"],
            "razorpay_payment_id": payment["id"],
            "razorpay_signature": "0" * 64,
        },
        headers=headers,
    )

    assert response.status_code == 422  # BusinessValidationError
    db_session.expire_all()
    assert db_session.query(Order).count() == 0


def test_another_customer_cannot_confirm_my_checkout(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC7")
    started = _start(client, headers, address.id).json()
    from tests.test_phase_14_payments import _customer

    _other, other_headers = _customer(db_session, "OC7B")
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")
    response = client.post(
        f"/api/v1/payments/online/{started['session_id']}/confirm",
        json={
            "razorpay_order_id": started["gateway_order_id"],
            "razorpay_payment_id": payment["id"],
            "razorpay_signature": _checkout_signature(started["gateway_order_id"], payment["id"]),
        },
        headers=other_headers,
    )
    assert response.status_code == 404


def test_webhook_places_the_order_when_the_app_never_calls_back(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """Customer paid in their UPI app and the app was killed before the
    success callback - the Razorpay webhook must still produce the order."""
    user, headers, _variant, address = _basket(client, db_session, "OC8")
    started = _start(client, headers, address.id).json()
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")

    body, hdrs = _webhook("payment.captured", payment)
    response = client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=hdrs)

    assert response.status_code == 200, response.text
    db_session.expire_all()
    order = db_session.query(Order).one()
    assert order.status == "CONFIRMED" and order.user_id == user.id
    assert db_session.query(Payment).one().status == "PAID"
    assert db_session.query(CheckoutSession).one().status == "COMPLETED"

    # ...and the late app callback is then just an idempotent no-op.
    late = _pay_and_confirm(client, razorpay, headers, started)
    assert late.status_code == 200
    db_session.expire_all()
    assert db_session.query(Order).count() == 1


def test_paid_but_out_of_stock_is_refunded_and_no_order_is_placed(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    user, headers, _variant, address = _basket(client, db_session, "OC9")
    started = _start(client, headers, address.id).json()
    # Stock disappears between starting the payment and paying.
    db_session.query(InventoryLot).update({"quantity": Decimal("0")})
    db_session.commit()

    response = _pay_and_confirm(client, razorpay, headers, started)

    assert response.status_code == 409
    assert "refunded" in response.json()["message"].lower()
    assert len(razorpay.refunds) == 1
    assert razorpay.refunds[0]["amount"] == BASKET_TOTAL_MINOR
    db_session.expire_all()
    assert db_session.query(Order).count() == 0
    assert db_session.query(CheckoutSession).one().status == "REFUNDED"
    assert db_session.query(Cart).filter_by(user_id=user.id).one().status == "ACTIVE"


def test_start_refuses_when_an_item_is_already_out_of_stock(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC10")
    db_session.query(InventoryLot).update({"quantity": Decimal("0")})
    db_session.commit()

    response = _start(client, headers, address.id)

    assert response.status_code == 409
    assert "stock" in response.json()["message"].lower()
    assert not razorpay.orders  # no Razorpay order created for an unfulfillable basket


def test_start_with_an_empty_cart_is_refused(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    from tests.test_phase_13_cart_orders import _create_address
    from tests.test_phase_14_payments import _customer

    user, headers = _customer(db_session, "OC11")
    address = _create_address(db_session, user)
    assert _start(client, headers, address.id).status_code in (404, 409)
    assert not razorpay.orders


def test_verify_places_the_order_when_paid_without_a_callback(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """The sheet closed with no success callback but the money moved (UPI app
    hand-off lost): the app re-checks and the order is placed."""
    _user, headers, _variant, address = _basket(client, db_session, "OC12")
    started = _start(client, headers, address.id).json()
    razorpay.add_payment(started["gateway_order_id"], "captured")

    response = client.post(f"/api/v1/payments/online/{started['session_id']}/verify", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["order"]["status"] == "CONFIRMED"
    db_session.expire_all()
    assert db_session.query(Order).count() == 1


def test_verify_when_nothing_was_paid_places_no_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC13")
    started = _start(client, headers, address.id).json()

    response = client.post(f"/api/v1/payments/online/{started['session_id']}/verify", headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "PAYMENT_NOT_CONFIRMED"
    db_session.expire_all()
    assert db_session.query(Order).count() == 0


def test_promo_code_discount_is_what_razorpay_is_asked_to_charge(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.core.roles import ADMIN
    from tests.test_phase_18_cancellation_refunds import _staff

    _admin, admin_headers = _staff(db_session, ADMIN, "oc-promo")
    created = client.post(
        "/api/v1/promotions",
        json={
            "name": "Ten off", "code": "TEN", "discount_type": "PERCENTAGE", "discount_value": 10,
            "status": "ACTIVE", "starts_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    _user, headers, _variant, address = _basket(client, db_session, "OC14")  # 2 x 25.00 = 50.00

    started = client.post(
        "/api/v1/payments/online/start",
        json={"address_id": address.id, "promo_code": "TEN"},
        headers=headers,
    ).json()

    # 50.00 - 5.00 (10%) + the base delivery fee
    assert Decimal(started["amount"]) == PROMO_TOTAL
    assert razorpay.orders[started["gateway_order_id"]]["amount"] == PROMO_TOTAL_MINOR

    done = _pay_and_confirm(client, razorpay, headers, started).json()
    assert done["order"]["discount_amount"] == "5.00"
    assert Decimal(done["order"]["total_amount"]) == PROMO_TOTAL
    assert done["order"]["applied_promo_code"] == "TEN"


# ---------------------------------------------------------------------------
# PAY-004 / PAY-001 regression tests. Written 2026-10-18 together with the fix;

# ---------------------------------------------------------------------------


def test_webhook_is_retryable_after_a_transient_razorpay_error(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """PAY-004: Razorpay's status API fails once while the webhook completes the
    checkout. The webhook must fail (so Razorpay retries) and the retry of the
    SAME event id must place the order - not be dropped as a duplicate."""
    import httpx

    _user, headers, _variant, address = _basket(client, db_session, "OC20")
    started = _start(client, headers, address.id).json()
    payment = razorpay.add_payment(started["gateway_order_id"], "captured")
    body, hdrs = _webhook("payment.captured", payment, event_id="evt_retry_me")

    razorpay.next_error = httpx.Response(500, json={"error": {"description": "boom"}})
    first = client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=hdrs)
    assert first.status_code >= 400, first.text
    db_session.expire_all()
    assert db_session.query(Order).count() == 0

    second = client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=hdrs)
    assert second.status_code == 200, second.text
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(Payment).one().status == "PAID"
    assert db_session.query(CheckoutSession).one().status == "COMPLETED"


def test_second_paid_session_for_the_same_cart_is_refunded_not_attached(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """PAY-001: two Razorpay orders were opened for one basket and BOTH were paid.
    One order, one payment; the second capture is refunded in full."""
    _user, headers, _variant, address = _basket(client, db_session, "OC21")
    first = _start(client, headers, address.id).json()
    # A second, independent session for the same basket (e.g. another device).
    second_order = razorpay.gateway().initiate_payment(
        reference="dup", amount=Decimal(str(first["amount"])), currency="INR", idempotency_key="dup-key"
    )
    second = CheckoutSession(
        user_id=db_session.query(CheckoutSession).one().user_id,
        cart_id=db_session.query(CheckoutSession).one().cart_id,
        address_id=address.id,
        amount=Decimal(str(first["amount"])),
        currency="INR",
        gateway_name="RAZORPAY",
        gateway_order_id=second_order.gateway_order_id,
        status="PENDING",
    )
    db_session.add(second)
    db_session.commit()
    second_id = second.id

    assert _pay_and_confirm(client, razorpay, headers, first).status_code == 200

    paid_twice = razorpay.add_payment(second_order.gateway_order_id, "captured")
    response = client.post(
        f"/api/v1/payments/online/{second_id}/confirm",
        json={
            "razorpay_order_id": second_order.gateway_order_id,
            "razorpay_payment_id": paid_twice["id"],
            "razorpay_signature": _checkout_signature(second_order.gateway_order_id, paid_twice["id"]),
        },
        headers=headers,
    )

    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(Payment).count() == 1
    assert db_session.get(CheckoutSession, second_id).status == "REFUNDED"
    assert [r["payment_id"] for r in razorpay.refunds] == [paid_twice["id"]]


# PAY-005 regression tests (paid but the webhook and the app both missed it).


def test_reconcile_sweep_places_the_order_for_a_missed_payment(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.services.checkout_session import CheckoutSessionService

    _user, headers, _variant, address = _basket(client, db_session, "OC22")
    paid = _start(client, headers, address.id).json()
    razorpay.add_payment(paid["gateway_order_id"], "captured")  # no webhook, no confirm call

    # An abandoned session for another customer must stay untouched.
    _user2, headers2, _variant2, address2 = _basket(client, db_session, "OC23")
    abandoned = _start(client, headers2, address2.id).json()

    later = datetime.now(UTC) + timedelta(minutes=5)
    settled = CheckoutSessionService(db_session, razorpay.gateway()).reconcile_pending(now=later)

    assert settled == 1
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.get(CheckoutSession, paid["session_id"]).status == "COMPLETED"
    assert db_session.get(CheckoutSession, abandoned["session_id"]).status == "PENDING"
    assert db_session.query(Payment).one().status == "PAID"


def test_start_again_after_a_missed_payment_places_the_order_instead_of_reopening_the_sheet(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _variant, address = _basket(client, db_session, "OC24")
    started = _start(client, headers, address.id).json()
    razorpay.add_payment(started["gateway_order_id"], "captured")  # paid, callback lost

    again = _start(client, headers, address.id)

    assert again.status_code == 409, again.text
    assert "placed" in again.json()["message"].lower()
    db_session.expire_all()
    assert db_session.query(Order).count() == 1
    assert db_session.query(CheckoutSession).one().status == "COMPLETED"


# PAY-008 / PAY-009 regression tests.


def test_concurrent_start_calls_share_one_razorpay_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """PAY-008: a double tap / two devices must not create two Razorpay orders."""
    from concurrent.futures import ThreadPoolExecutor

    _user, headers, _variant, address = _basket(client, db_session, "OC25")
    razorpay.order_delay_seconds = 0.5  # keep the first request busy while the others arrive

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [f.result() for f in [pool.submit(_start, client, headers, address.id) for _ in range(4)]]

    assert [r.status_code for r in results] == [200] * 4, [r.text for r in results]
    assert len({r.json()["gateway_order_id"] for r in results}) == 1
    assert len(razorpay.orders) == 1
    db_session.expire_all()
    assert db_session.query(CheckoutSession).count() == 1


def _out_of_stock_after_start(client, db_session, tag):
    _user, headers, _variant, address = _basket(client, db_session, tag)
    started = _start(client, headers, address.id).json()
    db_session.query(InventoryLot).update({"quantity": Decimal("0")})
    db_session.commit()
    return headers, started


def test_failed_automatic_refund_is_retried_by_the_sweep(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """PAY-009: the refund call fails once; the customer is told it is coming, the
    session is REFUND_FAILED, and the sweep then completes the refund."""
    from datetime import UTC, datetime

    import httpx

    from app.services.checkout_session import CheckoutSessionService

    headers, started = _out_of_stock_after_start(client, db_session, "OC26")
    razorpay.refund_error = httpx.Response(500, json={"error": {"description": "boom"}})

    response = _pay_and_confirm(client, razorpay, headers, started)

    assert response.status_code == 409
    assert "shortly" in response.json()["message"].lower()
    db_session.expire_all()
    assert db_session.query(CheckoutSession).one().status == "REFUND_FAILED"
    assert razorpay.refunds == []

    refunded = CheckoutSessionService(db_session, razorpay.gateway()).retry_failed_refunds(now=datetime.now(UTC))

    assert refunded == 1
    db_session.expire_all()
    assert db_session.query(CheckoutSession).one().status == "REFUNDED"
    assert len(razorpay.refunds) == 1


def test_refund_whose_reply_was_lost_is_recorded_as_refunded_not_failed(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """PAY-009: Razorpay processed the refund but the reply timed out. Do not tell
    support to refund it again by hand - the payment is looked up and found refunded."""
    headers, started = _out_of_stock_after_start(client, db_session, "OC27")
    razorpay.refund_reply_lost = True

    response = _pay_and_confirm(client, razorpay, headers, started)

    assert response.status_code == 409
    assert "has been refunded" in response.json()["message"]
    db_session.expire_all()
    assert db_session.query(CheckoutSession).one().status == "REFUNDED"
    assert len(razorpay.refunds) == 1
