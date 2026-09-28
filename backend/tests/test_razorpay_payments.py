"""Razorpay integration.

Two layers, both exercising the REAL RazorpayGateway adapter code:

1. Adapter unit tests - request shapes (paise, Basic auth), status mapping,
   error mapping, and both signature schemes.
2. API-level flows - the app wired to RazorpayGateway whose HTTP transport
   is an in-memory fake of Razorpay's REST API (httpx.MockTransport), so
   checkout, confirm, webhooks, retries and refunds run end-to-end without
   network access or real credentials.
"""

import hashlib
import hmac
import json
import re
import secrets
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN
from app.dependencies.payments import get_payment_gateway
from app.main import app
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.refund import Refund
from app.services.payment_gateway import (
    GatewayConnectionError,
    GatewayError,
    GatewayRejectedError,
    GatewayTimeoutError,
    WebhookEventIgnored,
    WebhookParseError,
)
from app.services.payment_state import TransactionStatus
from app.services.razorpay_gateway import RazorpayGateway, from_paise, to_paise
from tests.test_phase_14_payments import _create_order, _customer
from tests.test_phase_18_cancellation_refunds import _staff

KEY_ID = "rzp_test_FakeKeyId123"
KEY_SECRET = "fake-key-secret-for-tests"
WEBHOOK_SECRET = "fake-webhook-secret-for-tests"


class FakeRazorpay:
    """Just enough of Razorpay's REST API for this integration."""

    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.payments: dict[str, list[dict]] = {}
        self.refunds: list[dict] = []
        self.requests: list[httpx.Request] = []
        self.refund_status = "processed"
        self.next_error: httpx.Response | Exception | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.next_error is not None:
            error, self.next_error = self.next_error, None
            if isinstance(error, Exception):
                raise error
            return error

        path = request.url.path
        if request.method == "POST" and path == "/v1/orders":
            body = json.loads(request.content)
            order = {
                "id": f"order_{secrets.token_hex(7)}", "entity": "order",
                "amount": body["amount"], "currency": body["currency"],
                "receipt": body["receipt"], "status": "created",
            }
            self.orders[order["id"]] = order
            self.payments[order["id"]] = []
            return httpx.Response(200, json=order)

        m = re.fullmatch(r"/v1/orders/([\w]+)/payments", path)
        if m and request.method == "GET":
            if m.group(1) not in self.orders:
                return httpx.Response(400, json={"error": {"description": "The id provided does not exist"}})
            items = self.payments[m.group(1)]
            return httpx.Response(200, json={"entity": "collection", "count": len(items), "items": items})

        m = re.fullmatch(r"/v1/refunds/([\w]+)", path)
        if m and request.method == "GET":
            refund = next((r for r in self.refunds if r["id"] == m.group(1)), None)
            if refund is None:
                return httpx.Response(400, json={"error": {"description": "The id provided does not exist"}})
            return httpx.Response(200, json=refund)

        m = re.fullmatch(r"/v1/payments/([\w]+)/refund", path)
        if m and request.method == "POST":
            body = json.loads(request.content)
            refund = {
                "id": f"rfnd_{secrets.token_hex(7)}", "payment_id": m.group(1),
                "amount": body["amount"], "status": self.refund_status,
            }
            self.refunds.append(refund)
            return httpx.Response(200, json=refund)

        return httpx.Response(404, json={"error": {"description": "not found"}})

    def add_payment(self, order_id: str, status: str = "captured", amount: int | None = None) -> dict:
        payment = {
            "id": f"pay_{secrets.token_hex(7)}", "entity": "payment",
            "order_id": order_id, "status": status, "currency": "INR",
            "amount": amount if amount is not None else self.orders[order_id]["amount"],
            "method": "upi",
        }
        self.payments[order_id].insert(0, payment)  # Razorpay lists newest first
        return payment

    def gateway(self, **overrides) -> RazorpayGateway:
        kwargs = {
            "key_id": KEY_ID, "key_secret": KEY_SECRET, "webhook_secret": WEBHOOK_SECRET,
            "transport": httpx.MockTransport(self.handler),
        }
        kwargs.update(overrides)
        return RazorpayGateway(**kwargs)


def _checkout_signature(order_id: str, payment_id: str) -> str:
    return hmac.new(KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def _webhook(event: str, payment: dict, *, event_id: str | None = None, secret: str = WEBHOOK_SECRET):
    body = json.dumps({
        "entity": "event", "event": event, "contains": ["payment"],
        "payload": {"payment": {"entity": payment}},
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
        "X-Razorpay-Event-Id": event_id or f"evt_{secrets.token_hex(6)}",
    }
    return body, headers


def _refund_webhook(event: str, refund: dict, *, event_id: str | None = None):
    body = json.dumps({
        "entity": "event", "event": event, "contains": ["refund", "payment"],
        "payload": {"refund": {"entity": refund}},
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest(),
        "X-Razorpay-Event-Id": event_id or f"evt_{secrets.token_hex(6)}",
    }
    return body, headers


@pytest.fixture
def razorpay():
    fake = FakeRazorpay()
    gateway = fake.gateway()
    app.dependency_overrides[get_payment_gateway] = lambda: gateway
    yield fake
    app.dependency_overrides.pop(get_payment_gateway, None)


# ---------------------------------------------------------------------------
# 1. Adapter
# ---------------------------------------------------------------------------


def test_paise_conversion_is_exact() -> None:
    assert to_paise(Decimal("240.00")) == 24000
    assert to_paise(Decimal("0.01")) == 1
    assert from_paise(24050) == Decimal("240.50")


def test_initiate_creates_order_in_paise_with_basic_auth() -> None:
    fake = FakeRazorpay()
    result = fake.gateway().initiate_payment(
        reference="order-7-payment-3", amount=Decimal("240.50"), currency="INR", idempotency_key="k1"
    )
    assert result.status == TransactionStatus.INITIATED
    assert result.gateway_order_id in fake.orders
    [request] = fake.requests
    assert request.headers["authorization"].startswith("Basic ")
    body = json.loads(request.content)
    assert body["amount"] == 24050
    assert body["currency"] == "INR"
    assert body["receipt"] == "order-7-payment-3"


def test_initiate_with_existing_order_reuses_it_and_reports_capture() -> None:
    fake = FakeRazorpay()
    gateway = fake.gateway()
    first = gateway.initiate_payment(reference="r", amount=Decimal("100.00"), currency="INR", idempotency_key="a")

    again = gateway.initiate_payment(
        reference="r", amount=Decimal("100.00"), currency="INR", idempotency_key="b",
        existing_gateway_order_id=first.gateway_order_id,
    )
    assert again.gateway_order_id == first.gateway_order_id
    assert again.status == TransactionStatus.INITIATED
    assert len(fake.orders) == 1  # no second Razorpay order

    paid = fake.add_payment(first.gateway_order_id)
    captured = gateway.initiate_payment(
        reference="r", amount=Decimal("100.00"), currency="INR", idempotency_key="c",
        existing_gateway_order_id=first.gateway_order_id,
    )
    assert captured.status == TransactionStatus.SUCCESS
    assert captured.gateway_transaction_id == paid["id"]


def test_query_status_is_order_level_truth() -> None:
    fake = FakeRazorpay()
    gateway = fake.gateway()
    order_id = gateway.initiate_payment(
        reference="r", amount=Decimal("99.00"), currency="INR", idempotency_key="a"
    ).gateway_order_id

    assert gateway.query_status(gateway_order_id=order_id, gateway_transaction_id=None).status == TransactionStatus.INITIATED
    fake.add_payment(order_id, status="failed")
    # A failed attempt is not a failed Payment - the customer can try again.
    assert gateway.query_status(gateway_order_id=order_id, gateway_transaction_id=None).status == TransactionStatus.PROCESSING
    paid = fake.add_payment(order_id, status="captured")
    result = gateway.query_status(gateway_order_id=order_id, gateway_transaction_id="pay_somethingElse")
    assert result.status == TransactionStatus.SUCCESS
    assert result.gateway_transaction_id == paid["id"]
    assert result.amount == Decimal("99.00")


def test_http_error_mapping() -> None:
    """Calls whose outcome can matter (status checks, refunds) keep the
    unknown-outcome distinction: a timeout or a 5xx is never a rejection."""
    fake = FakeRazorpay()
    gateway = fake.gateway()
    order_id = gateway.initiate_payment(
        reference="r", amount=Decimal("10.00"), currency="INR", idempotency_key="k"
    ).gateway_order_id
    status = {"gateway_order_id": order_id, "gateway_transaction_id": None}

    fake.next_error = httpx.ReadTimeout("slow")
    with pytest.raises(GatewayTimeoutError):
        gateway.query_status(**status)

    fake.next_error = httpx.ConnectError("refused")
    with pytest.raises(GatewayConnectionError):
        gateway.query_status(**status)

    fake.next_error = httpx.Response(502, text="bad gateway")
    with pytest.raises(GatewayError) as exc_info:
        gateway.query_status(**status)
    assert not isinstance(exc_info.value, GatewayRejectedError)  # outcome unknown, not a rejection

    fake.next_error = httpx.Response(400, json={"error": {"description": "The id provided does not exist"}})
    with pytest.raises(GatewayRejectedError, match="does not exist"):
        gateway.query_status(**status)


def test_order_creation_failures_are_definite() -> None:
    """Creating an order moves no money and its id never reached anyone,
    so every failure there is reported as a (retryable) rejection."""
    fake = FakeRazorpay()
    gateway = fake.gateway()
    args = {"reference": "r", "amount": Decimal("10.00"), "currency": "INR", "idempotency_key": "k"}

    for error in (
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("refused"),
        httpx.Response(502, text="bad gateway"),
    ):
        fake.next_error = error
        with pytest.raises(GatewayRejectedError, match="Could not create the Razorpay order"):
            gateway.initiate_payment(**args)

    fake.next_error = httpx.Response(400, json={"error": {"description": "Amount exceeds maximum amount allowed."}})
    with pytest.raises(GatewayRejectedError, match="Amount exceeds"):
        gateway.initiate_payment(**args)


def test_webhook_signature_and_parsing() -> None:
    gateway = FakeRazorpay().gateway()
    payment = {"id": "pay_abc", "order_id": "order_xyz", "amount": 24000, "currency": "INR", "status": "captured"}
    body, headers = _webhook("payment.captured", payment, event_id="evt_1")

    assert gateway.verify_webhook_signature(raw_body=body, headers=headers)
    assert not gateway.verify_webhook_signature(raw_body=body + b" ", headers=headers)
    assert not FakeRazorpay().gateway(webhook_secret="").verify_webhook_signature(raw_body=body, headers=headers)

    event = gateway.parse_webhook_event(raw_body=body, headers=headers)
    assert event.event_id == "evt_1"
    assert event.status == TransactionStatus.SUCCESS
    assert event.gateway_order_id == "order_xyz"
    assert event.gateway_transaction_id == "pay_abc"
    assert event.amount == Decimal("240.00")

    ignored_body, ignored_headers = _webhook("payment.dispute.created", payment)
    with pytest.raises(WebhookEventIgnored):
        gateway.parse_webhook_event(raw_body=ignored_body, headers=ignored_headers)
    with pytest.raises(WebhookParseError):
        gateway.parse_webhook_event(raw_body=b"not json", headers={})


def test_checkout_signature() -> None:
    gateway = FakeRazorpay().gateway()
    good = _checkout_signature("order_1", "pay_1")
    assert gateway.verify_checkout_signature(gateway_order_id="order_1", gateway_payment_id="pay_1", signature=good)
    assert not gateway.verify_checkout_signature(gateway_order_id="order_1", gateway_payment_id="pay_2", signature=good)
    assert not gateway.verify_checkout_signature(gateway_order_id="order_1", gateway_payment_id="pay_1", signature="")


def test_refund_resolves_captured_payment_and_maps_status() -> None:
    fake = FakeRazorpay()
    gateway = fake.gateway()
    order_id = gateway.initiate_payment(
        reference="r", amount=Decimal("50.00"), currency="INR", idempotency_key="a"
    ).gateway_order_id
    with pytest.raises(GatewayRejectedError):  # nothing captured yet
        gateway.refund_payment(gateway_order_id=order_id, gateway_transaction_id=None,
                               amount=Decimal("50.00"), currency="INR", idempotency_key="r1")

    paid = fake.add_payment(order_id)
    result = gateway.refund_payment(gateway_order_id=order_id, gateway_transaction_id=None,
                                    amount=Decimal("20.00"), currency="INR", idempotency_key="r2")
    assert result.status == TransactionStatus.SUCCESS
    assert fake.refunds[-1] == {**fake.refunds[-1], "payment_id": paid["id"], "amount": 2000}

    fake.refund_status = "pending"
    pending = gateway.refund_payment(gateway_order_id=order_id, gateway_transaction_id=None,
                                     amount=Decimal("1.00"), currency="INR", idempotency_key="r3")
    assert pending.status == TransactionStatus.PROCESSING


# ---------------------------------------------------------------------------
# 2. API flows
# ---------------------------------------------------------------------------


def _start_online_payment(client: TestClient, db_session: Session, tag: str, amount: str = "240.00"):
    user, headers = _customer(db_session, tag)
    order = _create_order(db_session, user, total_amount=Decimal(amount))
    response = client.post("/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers)
    assert response.status_code == 201, response.text
    return user, headers, order, response.json()


def test_online_payment_checkout_and_confirm(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    user, headers, order, payment = _start_online_payment(client, db_session, "RZP1")
    assert payment["status"] == "PROCESSING"
    assert payment["gateway_name"] == "RAZORPAY"
    assert payment["gateway_order_id"] in razorpay.orders

    checkout = client.get(f"/api/v1/payments/{payment['id']}/checkout", headers=headers)
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["key_id"] == KEY_ID
    assert body["gateway_order_id"] == payment["gateway_order_id"]
    assert body["amount_minor"] == 24000
    assert body["customer_email"] == user.email
    assert body["test_mode"] is True
    assert KEY_SECRET not in checkout.text

    paid = razorpay.add_payment(payment["gateway_order_id"])
    confirm = client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        json={
            "razorpay_order_id": payment["gateway_order_id"],
            "razorpay_payment_id": paid["id"],
            "razorpay_signature": _checkout_signature(payment["gateway_order_id"], paid["id"]),
        },
        headers=headers,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "PAID"

    db_session.expire_all()
    assert db_session.get(Order, order.id).status == "CONFIRMED"
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).one()
    assert txn.gateway_transaction_id == paid["id"]

    # Paid - no checkout to re-open any more.
    assert client.get(f"/api/v1/payments/{payment['id']}/checkout", headers=headers).status_code == 409


def test_confirm_never_trusts_the_client(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _order, payment = _start_online_payment(client, db_session, "RZP2")
    oid = payment["gateway_order_id"]
    url = f"/api/v1/payments/{payment['id']}/confirm"

    forged = client.post(url, json={
        "razorpay_order_id": oid, "razorpay_payment_id": "pay_forged",
        "razorpay_signature": "0" * 64,
    }, headers=headers)
    assert forged.status_code == 422

    other_order = client.post(url, json={
        "razorpay_order_id": "order_someoneElse", "razorpay_payment_id": "pay_x",
        "razorpay_signature": _checkout_signature("order_someoneElse", "pay_x"),
    }, headers=headers)
    assert other_order.status_code == 422

    # Correctly signed, but Razorpay has only an authorized (not captured)
    # payment - the order stays unpaid until the capture really lands.
    held = razorpay.add_payment(oid, status="authorized")
    pending = client.post(url, json={
        "razorpay_order_id": oid, "razorpay_payment_id": held["id"],
        "razorpay_signature": _checkout_signature(oid, held["id"]),
    }, headers=headers)
    assert pending.status_code == 200
    assert pending.json()["status"] == "PROCESSING"

    db_session.expire_all()
    assert db_session.get(Payment, payment["id"]).status == "PROCESSING"


def test_other_customer_cannot_use_my_payment(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, _headers, _order, payment = _start_online_payment(client, db_session, "RZP3")
    _other, other_headers = _customer(db_session, "RZP3B")
    assert client.get(f"/api/v1/payments/{payment['id']}/checkout", headers=other_headers).status_code == 404
    assert client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        json={"razorpay_order_id": "o", "razorpay_payment_id": "p", "razorpay_signature": "s"},
        headers=other_headers,
    ).status_code == 404


def test_webhook_capture_marks_paid_exactly_once(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, _headers, order, payment = _start_online_payment(client, db_session, "RZP4")
    paid = razorpay.add_payment(payment["gateway_order_id"])
    body, headers = _webhook("payment.captured", paid, event_id="evt_capture_1")

    first = client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers)
    assert first.status_code == 200, first.text
    replay = client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers)
    assert replay.status_code == 200

    db_session.expire_all()
    assert db_session.get(Payment, payment["id"]).status == "PAID"
    assert db_session.get(Order, order.id).status == "CONFIRMED"
    assert db_session.query(PaymentWebhookEvent).filter_by(event_id="evt_capture_1").count() == 1
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).one()
    assert txn.gateway_transaction_id == paid["id"]


def test_webhook_rejects_bad_signature_and_ignores_unrelated_events(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, _headers, _order, payment = _start_online_payment(client, db_session, "RZP5")
    paid = razorpay.add_payment(payment["gateway_order_id"])

    body, headers = _webhook("payment.captured", paid, secret="not-the-secret")
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 401

    body, headers = _webhook("payment.dispute.created", paid)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200

    body, headers = _webhook("payment.failed", {**paid, "status": "failed"})
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200

    # Only the configured gateway's webhook path exists.
    assert client.post("/api/v1/payments/webhooks/pnb", content=body, headers=headers).status_code == 404

    db_session.expire_all()
    assert db_session.get(Payment, payment["id"]).status == "PROCESSING"


def test_webhook_amount_mismatch_is_not_applied(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, _headers, _order, payment = _start_online_payment(client, db_session, "RZP6")
    tampered = razorpay.add_payment(payment["gateway_order_id"], amount=100)  # 1 rupee, not 240
    body, headers = _webhook("payment.captured", tampered)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200
    db_session.expire_all()
    assert db_session.get(Payment, payment["id"]).status == "PROCESSING"


def test_retry_reuses_the_same_razorpay_order(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, _order, payment = _start_online_payment(client, db_session, "RZP7")
    row = db_session.get(Payment, payment["id"])
    row.status = "EXPIRED"
    db_session.commit()
    orders_before = len(razorpay.orders)

    retried = client.post(f"/api/v1/payments/{payment['id']}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["gateway_order_id"] == payment["gateway_order_id"]
    assert retried.json()["status"] == "PROCESSING"
    assert len(razorpay.orders) == orders_before


def test_online_payment_refused_cleanly_when_razorpay_not_configured(
    client: TestClient, db_session: Session
) -> None:
    unconfigured = RazorpayGateway(key_id="", key_secret="", webhook_secret="")
    app.dependency_overrides[get_payment_gateway] = lambda: unconfigured
    try:
        user, headers = _customer(db_session, "RZP8")
        online = _create_order(db_session, user)
        response = client.post("/api/v1/payments", json={"order_id": online.id, "payment_method": "UPI"}, headers=headers)
        assert response.status_code == 503
        assert response.json()["code"] == "ONLINE_PAYMENTS_NOT_CONFIGURED"
        db_session.expire_all()
        assert db_session.query(Payment).filter_by(order_id=online.id).count() == 0

        cod = _create_order(db_session, user)
        response = client.post("/api/v1/payments", json={"order_id": cod.id, "payment_method": "COD"}, headers=headers)
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(get_payment_gateway, None)


def test_unreachable_gateway_at_order_creation_is_retryable(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """Razorpay unreachable while creating its order: the payment must not
    get stuck PROCESSING with nothing to verify - it fails cleanly and the
    customer can retry once Razorpay is back."""
    user, headers = _customer(db_session, "RZP9")
    order = _create_order(db_session, user)
    razorpay.next_error = httpx.ConnectTimeout("no route")
    response = client.post("/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers)
    assert response.status_code == 502
    assert response.json()["code"] == "PAYMENT_GATEWAY_REJECTED"
    db_session.expire_all()
    payment = db_session.query(Payment).filter_by(order_id=order.id).one()
    assert payment.status == "FAILED"
    assert payment.gateway_order_id is None

    retried = client.post(f"/api/v1/payments/{payment.id}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "PROCESSING"
    assert retried.json()["gateway_order_id"] in razorpay.orders


def test_unreachable_gateway_while_rechecking_existing_order_stays_processing(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """Once a Razorpay order exists the customer may already have paid it,
    so an unreachable gateway there must NOT fail the payment."""
    _user, headers, _order, payment = _start_online_payment(client, db_session, "RZP9B")
    razorpay.next_error = httpx.ConnectTimeout("no route")
    response = client.post(f"/api/v1/payments/{payment['id']}/verify", headers=headers)
    assert response.status_code == 502
    assert response.json()["code"] == "PAYMENT_GATEWAY_UNAVAILABLE"
    db_session.expire_all()
    assert db_session.get(Payment, payment["id"]).status == "PROCESSING"


def test_refund_of_cancelled_paid_order_goes_to_razorpay(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, order, payment = _start_online_payment(client, db_session, "RZP10")
    paid = razorpay.add_payment(payment["gateway_order_id"])
    body, wh_headers = _webhook("payment.captured", paid)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=wh_headers).status_code == 200

    cancel = client.post(f"/api/v1/orders/{order.id}/cancel", json={"reason": "changed my mind"}, headers=headers)
    assert cancel.status_code == 200, cancel.text
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(payment_id=payment["id"]).one()

    _admin, admin_headers = _staff(db_session, ADMIN, "RZP10")
    assert client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin_headers).status_code == 200
    processed = client.post(f"/api/v1/payments/refunds/{refund.id}/process", headers=admin_headers)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "REFUNDED"

    [sent] = razorpay.refunds
    assert sent["payment_id"] == paid["id"]
    assert sent["amount"] == 24000


# ---------------------------------------------------------------------------
# 3. Refunds that resolve later (Razorpay: pending -> processed/failed)
# ---------------------------------------------------------------------------


def _processing_refund(client: TestClient, db_session: Session, razorpay: FakeRazorpay, tag: str):
    """Paid order -> cancelled -> refund approved -> processed while Razorpay
    still reports the refund as pending. Returns (refund_id, admin_headers,
    razorpay refund dict)."""
    razorpay.refund_status = "pending"
    _user, headers, order, payment = _start_online_payment(client, db_session, tag)
    paid = razorpay.add_payment(payment["gateway_order_id"])
    body, wh_headers = _webhook("payment.captured", paid)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=wh_headers).status_code == 200
    assert client.post(f"/api/v1/orders/{order.id}/cancel", json={}, headers=headers).status_code == 200
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(payment_id=payment["id"]).one()
    _admin, admin_headers = _staff(db_session, ADMIN, tag)
    assert client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin_headers).status_code == 200
    processed = client.post(f"/api/v1/payments/refunds/{refund.id}/process", headers=admin_headers)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "PROCESSING"
    return refund.id, admin_headers, razorpay.refunds[-1]


def test_adapter_refund_events_and_query() -> None:
    fake = FakeRazorpay()
    gateway = fake.gateway()
    body, headers = _refund_webhook("refund.processed", {"id": "rfnd_1", "status": "processed"}, event_id="evt_r1")
    event = gateway.parse_webhook_event(raw_body=body, headers=headers)
    assert event.gateway_refund_id == "rfnd_1"
    assert event.status == TransactionStatus.SUCCESS
    assert event.event_id == "evt_r1"
    body, headers = _refund_webhook("refund.created", {"id": "rfnd_1"})
    with pytest.raises(WebhookEventIgnored):
        gateway.parse_webhook_event(raw_body=body, headers=headers)

    fake.refunds.append({"id": "rfnd_2", "status": "failed", "error_description": "Bank rejected"})
    result = gateway.query_refund(gateway_refund_id="rfnd_2")
    assert result.status == TransactionStatus.FAILED
    assert result.failure_reason == "Bank rejected"


def test_refund_webhook_completes_a_pending_refund(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    refund_id, admin_headers, rz_refund = _processing_refund(client, db_session, razorpay, "RZR1")

    body, headers = _refund_webhook("refund.processed", {**rz_refund, "status": "processed"}, event_id="evt_rf_1")
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200
    # A re-delivery of the same event changes nothing.
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200

    detail = client.get(f"/api/v1/payments/refunds/{refund_id}", headers=admin_headers).json()
    assert detail["status"] == "REFUNDED"
    assert detail["processed_at"] is not None
    db_session.expire_all()
    assert db_session.query(PaymentWebhookEvent).filter_by(event_id="evt_rf_1").count() == 1


def test_refund_webhook_failure_allows_reprocessing(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    refund_id, admin_headers, rz_refund = _processing_refund(client, db_session, razorpay, "RZR2")

    body, headers = _refund_webhook("refund.failed", {**rz_refund, "status": "failed"})
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200
    assert client.get(f"/api/v1/payments/refunds/{refund_id}", headers=admin_headers).json()["status"] == "FAILED"

    razorpay.refund_status = "processed"
    again = client.post(f"/api/v1/payments/refunds/{refund_id}/process", headers=admin_headers)
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "REFUNDED"


def test_admin_sync_resolves_a_pending_refund(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    refund_id, admin_headers, rz_refund = _processing_refund(client, db_session, razorpay, "RZR3")
    url = f"/api/v1/payments/refunds/{refund_id}/sync"

    still_pending = client.post(url, headers=admin_headers)
    assert still_pending.status_code == 200
    assert still_pending.json()["status"] == "PROCESSING"

    rz_refund["status"] = "processed"  # Razorpay finished it
    synced = client.post(url, headers=admin_headers)
    assert synced.status_code == 200
    assert synced.json()["status"] == "REFUNDED"

    # Only PROCESSING refunds can be synced.
    assert client.post(url, headers=admin_headers).status_code == 409


def test_refund_webhook_for_unknown_refund_is_acknowledged(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    body, headers = _refund_webhook("refund.processed", {"id": "rfnd_notOurs", "status": "processed"})
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200
    db_session.expire_all()
    event = db_session.query(PaymentWebhookEvent).order_by(PaymentWebhookEvent.id.desc()).first()
    assert event.status == "FAILED"


# ---------------------------------------------------------------------------
# 4. Late payments on an order that expired first (found in live testing)
# ---------------------------------------------------------------------------


def test_payment_arriving_after_order_expired_creates_refund(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    """The reservation sweep expired the order while the customer still had
    Razorpay open; Razorpay kept accepting payment on its own order. The
    money must not be stranded: the payment is recorded PAID and a refund
    is queued for admin approval."""
    _user, _headers, order, payment = _start_online_payment(client, db_session, "RZL1")
    db_session.query(Order).filter(Order.id == order.id).update({"status": "EXPIRED"})
    db_session.commit()

    paid = razorpay.add_payment(payment["gateway_order_id"])
    body, headers = _webhook("payment.captured", paid)
    assert client.post("/api/v1/payments/webhooks/razorpay", content=body, headers=headers).status_code == 200

    db_session.expire_all()
    assert db_session.get(Payment, payment["id"]).status == "PAID"
    assert db_session.get(Order, order.id).status == "EXPIRED"
    refund = db_session.query(Refund).filter_by(order_id=order.id).one()
    assert refund.status == "PENDING_APPROVAL"
    assert refund.amount == Decimal("240.00")


def test_checkout_refused_once_order_is_no_longer_payable(
    client: TestClient, db_session: Session, razorpay: FakeRazorpay
) -> None:
    _user, headers, order, payment = _start_online_payment(client, db_session, "RZL2")
    db_session.query(Order).filter(Order.id == order.id).update({"status": "EXPIRED"})
    db_session.commit()
    response = client.get(f"/api/v1/payments/{payment['id']}/checkout", headers=headers)
    assert response.status_code == 409
    assert "expired" in response.json()["message"]
