"""Pay-first online checkout: Razorpay opens BEFORE any order exists, and the
order is placed only after the payment succeeds (app/services/checkout_session.py).

Runs the real RazorpayGateway adapter against the in-memory fake of
Razorpay's REST API used by test_razorpay_payments.py.
"""

from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

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
    assert Decimal(body["amount"]) == Decimal("70.00")
    assert body["amount_minor"] == 7000
    assert body["gateway_order_id"] in razorpay.orders
    assert razorpay.orders[body["gateway_order_id"]]["amount"] == 7000

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
    assert body["order"]["total_amount"] == "70.00"
    assert body["order"]["delivery_fee"] == "20.00"
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
    assert razorpay.refunds[0]["amount"] == 7000
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

    # 50.00 - 5.00 (10%) + Rs 20 delivery = 65.00
    assert Decimal(started["amount"]) == Decimal("65.00")
    assert razorpay.orders[started["gateway_order_id"]]["amount"] == 6500

    done = _pay_and_confirm(client, razorpay, headers, started).json()
    assert done["order"]["discount_amount"] == "5.00"
    assert done["order"]["total_amount"] == "65.00"
    assert done["order"]["applied_promo_code"] == "TEN"
