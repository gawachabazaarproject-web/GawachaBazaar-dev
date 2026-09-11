"""Phase 14 focused validation: payments (PNB UPI + COD).

Fast-development-mode focused validation, against real PostgreSQL.
Mutation tests re-read the database afterward (not just the HTTP response)
per established project testing principle. Concurrency tests use real
threads against real Postgres row locks, never mocked.

FakePNBGateway is a test-only double implementing the PaymentGateway
protocol (subclassing PNBGateway so webhook signature verification/parsing
use the exact same code path production would, just with a fully
controllable initiate_payment/query_status). It is injected via FastAPI's
dependency-override mechanism - the same pattern already used for `get_db`
in conftest.py - so these tests exercise the full HTTP stack, not just
PaymentService in isolation.
"""

import hashlib
import hmac
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, CUSTOMER
from app.core.security import create_access_token, hash_password
from app.dependencies.payments import get_payment_gateway
from app.main import app
from app.models.auth_session import AuthSession
from app.models.inventory_reservation import InventoryReservation
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.payment_gateway import (
    GatewayConnectionError,
    GatewayInitiateResult,
    GatewayRejectedError,
    GatewayStatusResult,
    GatewayTimeoutError,
    PNBGateway,
)
from app.services.payment_state import TransactionStatus

WEBHOOK_SECRET = "test-webhook-secret-for-phase-14-min-32-chars"


class FakePNBGateway(PNBGateway):
    """Subclasses PNBGateway so webhook verify/parse use the real (placeholder)
    code path; only initiate_payment/query_status are faked and fully
    scriptable per-test.
    """

    def __init__(self, *, webhook_secret: str = WEBHOOK_SECRET) -> None:
        super().__init__(
            merchant_id="fake-merchant",
            webhook_secret=webhook_secret,
            base_url="https://fake-pnb.invalid",
        )
        self._next_initiate = None
        self._next_query = None
        self._counter = 0
        self.initiate_calls: list[dict] = []
        self.query_calls: list[dict] = []

    def queue_initiate(self, result_or_exc) -> None:
        self._next_initiate = result_or_exc

    def queue_query(self, result_or_exc) -> None:
        self._next_query = result_or_exc

    def initiate_payment(self, **kwargs) -> GatewayInitiateResult:
        self.initiate_calls.append(kwargs)
        if self._next_initiate is not None:
            value = self._next_initiate
            self._next_initiate = None
            if isinstance(value, Exception):
                raise value
            return value
        self._counter += 1
        return GatewayInitiateResult(
            gateway_order_id=f"fake-order-{self._counter}-{secrets.token_hex(3)}",
            gateway_transaction_id=f"fake-txn-{self._counter}-{secrets.token_hex(3)}",
            status=TransactionStatus.PROCESSING,
        )

    def query_status(self, **kwargs) -> GatewayStatusResult:
        self.query_calls.append(kwargs)
        if self._next_query is not None:
            value = self._next_query
            self._next_query = None
            if isinstance(value, Exception):
                raise value
            return value
        return GatewayStatusResult(
            gateway_order_id=kwargs["gateway_order_id"],
            gateway_transaction_id=kwargs.get("gateway_transaction_id"),
            status=TransactionStatus.PROCESSING,
        )


@pytest.fixture
def gateway() -> FakePNBGateway:
    fake = FakePNBGateway()
    app.dependency_overrides[get_payment_gateway] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_payment_gateway, None)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _webhook_body(
    *, event_id: str, event_type: str, gateway_order_id: str | None,
    gateway_transaction_id: str | None, status: str,
    amount: str | None = None, currency: str | None = None,
) -> bytes:
    payload = {
        "event_id": event_id, "event_type": event_type,
        "gateway_order_id": gateway_order_id, "gateway_transaction_id": gateway_transaction_id,
        "status": status,
    }
    if amount is not None:
        payload["amount"] = amount
    if currency is not None:
        payload["currency"] = currency
    return json.dumps(payload).encode()


def _webhook_headers(secret: str, body: bytes) -> dict[str, str]:
    return {"X-PNB-Signature": _sign(secret, body), "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helpers (matching established Phase 10-13 patterns)
# ---------------------------------------------------------------------------


def _get_or_create_role(db_session: Session, name: str) -> Role:
    role = db_session.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db_session.add(role)
        db_session.commit()
        db_session.refresh(role)
    return role


def _create_user_with_role(db_session: Session, role_name: str, email: str) -> User:
    user = User(
        name="Test User", email=email,
        phone=f"+9194{abs(hash(email)) % 100000000:08d}",
        password_hash=hash_password("SecurePass123"), status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    role = _get_or_create_role(db_session, role_name)
    db_session.add(UserRole(user_id=user.id, role_id=role.id, is_primary=True))
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(db_session: Session, user: User) -> dict[str, str]:
    session = AuthSession(
        user_id=user.id, refresh_token_hash=f"dummy-hash-{user.id}-{user.email}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    token = create_access_token(user_id=user.id, session_id=session.id)
    return {"Authorization": f"Bearer {token}"}


def _customer(db_session: Session, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, CUSTOMER, f"cust_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _create_order(
    db_session: Session, user: User, *, total_amount: Decimal = Decimal("100.00"),
    currency: str = "INR", status: str = "PENDING",
) -> Order:
    """Bypasses checkout (this file tests Payment behavior, not checkout),
    but Phase 15 made "every order has a reservation" a structural
    invariant that PaymentService now depends on
    (commit_reservation_for_order gates order confirmation) - so this
    helper creates a matching ACTIVE reservation (with no allocated
    items, since there is no real inventory behind these bare test
    orders) to keep it valid under that invariant. Without this, every
    COD/UPI-success test in this file would incorrectly get a 409/skip
    for "reservation not found".
    """
    order = Order(
        user_id=user.id, cart_id=None,
        order_number=f"ORD-{secrets.token_hex(6).upper()}",
        status=status, total_amount=total_amount, currency=currency,
        placed_at=datetime.now(UTC),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        InventoryReservation(
            order_id=order.id,
            status="ACTIVE",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    db_session.commit()
    db_session.refresh(order)
    return order


# ---------------------------------------------------------------------------
# COD
# ---------------------------------------------------------------------------


def test_cod_payment_created_pending_and_order_confirmed(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "COD1")
    order = _create_order(db_session, user, total_amount=Decimal("250.00"))

    response = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["payment_method"] == "COD"
    assert body["amount"] == "250.00"
    assert body["gateway_name"] is None

    assert gateway.initiate_calls == []  # COD never calls the gateway

    db_session.expire_all()
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "CONFIRMED"
    payment = db_session.query(Payment).filter_by(order_id=order.id).first()
    assert payment.status == "PENDING"
    assert db_session.query(PaymentTransaction).filter_by(payment_id=payment.id).count() == 0


def test_cod_payment_cannot_be_retried(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "COD2")
    order = _create_order(db_session, user)
    created = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "COD"}, headers=headers
    ).json()

    response = client.post(f"/api/v1/payments/{created['id']}/retry", headers=headers)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# UPI happy path
# ---------------------------------------------------------------------------


def test_upi_initiation_sets_processing_and_gateway_reference(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "UPI1")
    order = _create_order(db_session, user, total_amount=Decimal("500.00"))

    response = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PROCESSING"
    assert body["gateway_name"] == "PNB"
    assert body["gateway_order_id"] is not None
    assert len(gateway.initiate_calls) == 1
    assert gateway.initiate_calls[0]["amount"] == Decimal("500.00")

    db_session.expire_all()
    order_after = db_session.get(Order, order.id)
    assert order_after.status == "PENDING"  # not confirmed yet - only PROCESSING so far
    txns = db_session.query(PaymentTransaction).filter_by(payment_id=body["id"]).all()
    assert len(txns) == 1
    assert txns[0].status == "PROCESSING"


def test_upi_webhook_success_marks_paid_and_confirms_order_exactly_once(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "UPI2")
    order = _create_order(db_session, user, total_amount=Decimal("300.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()

    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()
    body = _webhook_body(
        event_id="evt-1", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"],
        gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="300.00", currency="INR",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PAID"
    assert refreshed_payment.paid_at is not None
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "CONFIRMED"
    refreshed_txn = db_session.get(PaymentTransaction, txn.id)
    assert refreshed_txn.status == "SUCCESS"
    webhook_event = db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-1").first()
    assert webhook_event.status == "PROCESSED"


def test_upi_webhook_failure_leaves_order_pending(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "UPI3")
    order = _create_order(db_session, user, total_amount=Decimal("150.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()

    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()
    body = _webhook_body(
        event_id="evt-fail-1", event_type="PAYMENT_FAILED",
        gateway_order_id=payment["gateway_order_id"],
        gateway_transaction_id=txn.gateway_transaction_id,
        status="FAILED",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "FAILED"
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "PENDING"


def test_retry_creates_new_transaction_without_overwriting_history(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "UPI4")
    order = _create_order(db_session, user)
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    first_txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()
    body = _webhook_body(
        event_id="evt-fail-retry", event_type="PAYMENT_FAILED",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=first_txn.gateway_transaction_id,
        status="FAILED",
    )
    client.post("/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body))

    retried = client.post(f"/api/v1/payments/{payment['id']}/retry", headers=headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "PROCESSING"

    db_session.expire_all()
    txns = (
        db_session.query(PaymentTransaction)
        .filter_by(payment_id=payment["id"])
        .order_by(PaymentTransaction.id)
        .all()
    )
    assert len(txns) == 2
    assert txns[0].status == "FAILED"  # original attempt untouched, never overwritten
    assert txns[1].status == "PROCESSING"
    # Same gateway_order_id reused across the retry (§6.1: on the logical payment).
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.gateway_order_id == payment["gateway_order_id"]


def test_cannot_retry_processing_payment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "UPI5")
    order = _create_order(db_session, user)
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    assert payment["status"] == "PROCESSING"

    response = client.post(f"/api/v1/payments/{payment['id']}/retry", headers=headers)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Amount / currency validation
# ---------------------------------------------------------------------------


def test_webhook_amount_mismatch_does_not_mark_paid(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "AMT1")
    order = _create_order(db_session, user, total_amount=Decimal("500.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    body = _webhook_body(
        event_id="evt-amt-mismatch", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="400.00", currency="INR",  # our order is 500.00
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 200  # ack the gateway; we chose not to act on it

    db_session.expire_all()
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PROCESSING"  # NOT PAID
    webhook_event = db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-amt-mismatch").first()
    assert webhook_event.status == "FAILED"


def test_webhook_currency_mismatch_does_not_mark_paid(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "CUR1")
    order = _create_order(db_session, user, total_amount=Decimal("500.00"), currency="INR")
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    body = _webhook_body(
        event_id="evt-cur-mismatch", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="500.00", currency="USD",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PROCESSING"


# ---------------------------------------------------------------------------
# Duplicate / out-of-order webhooks
# ---------------------------------------------------------------------------


def test_duplicate_webhook_is_a_safe_noop(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "DUP1")
    order = _create_order(db_session, user, total_amount=Decimal("200.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    body = _webhook_body(
        event_id="evt-dup-1", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="200.00", currency="INR",
    )
    headers_sig = _webhook_headers(WEBHOOK_SECRET, body)

    first = client.post("/api/v1/payments/webhooks/pnb", content=body, headers=headers_sig)
    second = client.post("/api/v1/payments/webhooks/pnb", content=body, headers=headers_sig)
    third = client.post("/api/v1/payments/webhooks/pnb", content=body, headers=headers_sig)
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    db_session.expire_all()
    assert db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-dup-1").count() == 1
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "CONFIRMED"  # confirmed exactly once, not re-processed


def test_late_failed_after_paid_does_not_downgrade(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "ORD1")
    order = _create_order(db_session, user, total_amount=Decimal("120.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    success_body = _webhook_body(
        event_id="evt-success", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="120.00", currency="INR",
    )
    client.post(
        "/api/v1/payments/webhooks/pnb", content=success_body,
        headers=_webhook_headers(WEBHOOK_SECRET, success_body),
    )

    late_fail_body = _webhook_body(
        event_id="evt-late-fail", event_type="PAYMENT_FAILED",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="FAILED",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=late_fail_body,
        headers=_webhook_headers(WEBHOOK_SECRET, late_fail_body),
    )
    assert response.status_code == 200  # acked, but ignored

    db_session.expire_all()
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PAID"  # never downgraded
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "CONFIRMED"


# ---------------------------------------------------------------------------
# Webhook authenticity / malformed payloads
# ---------------------------------------------------------------------------


def test_invalid_webhook_signature_rejected_and_no_db_mutation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    body = _webhook_body(
        event_id="evt-bad-sig", event_type="PAYMENT_SUCCESS",
        gateway_order_id="whatever", gateway_transaction_id="whatever", status="SUCCESS",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body,
        headers={"X-PNB-Signature": "0" * 64, "Content-Type": "application/json"},
    )
    assert response.status_code == 401

    db_session.expire_all()
    assert db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-bad-sig").count() == 0


def test_missing_webhook_signature_rejected(client: TestClient, gateway: FakePNBGateway) -> None:
    body = _webhook_body(
        event_id="evt-no-sig", event_type="PAYMENT_SUCCESS",
        gateway_order_id="x", gateway_transaction_id="x", status="SUCCESS",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 401


def test_malformed_webhook_body_handled_gracefully(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    body = b"{not valid json"
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 422


def test_unknown_gateway_reference_handled_gracefully(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    body = _webhook_body(
        event_id="evt-unknown-ref", event_type="PAYMENT_SUCCESS",
        gateway_order_id="never-existed", gateway_transaction_id="never-existed", status="SUCCESS",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 200  # acked; nothing to act on

    db_session.expire_all()
    event = db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-unknown-ref").first()
    assert event.status == "FAILED"


# ---------------------------------------------------------------------------
# Security / ownership
# ---------------------------------------------------------------------------


def test_user_cannot_read_another_users_payment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user_a, headers_a = _customer(db_session, "SEC1A")
    order_a = _create_order(db_session, user_a)
    payment_a = client.post(
        "/api/v1/payments", json={"order_id": order_a.id, "payment_method": "COD"}, headers=headers_a
    ).json()

    _user_b, headers_b = _customer(db_session, "SEC1B")
    response = client.get(f"/api/v1/payments/{payment_a['id']}", headers=headers_b)
    assert response.status_code == 404


def test_user_cannot_initiate_payment_for_another_users_order(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user_a, _headers_a = _customer(db_session, "SEC2A")
    order_a = _create_order(db_session, user_a)

    _user_b, headers_b = _customer(db_session, "SEC2B")
    response = client.post(
        "/api/v1/payments", json={"order_id": order_a.id, "payment_method": "COD"}, headers=headers_b
    )
    assert response.status_code == 404


def test_user_cannot_read_another_users_order_payment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user_a, headers_a = _customer(db_session, "SEC3A")
    order_a = _create_order(db_session, user_a)
    client.post(
        "/api/v1/payments", json={"order_id": order_a.id, "payment_method": "COD"}, headers=headers_a
    )

    _user_b, headers_b = _customer(db_session, "SEC3B")
    response = client.get(f"/api/v1/orders/{order_a.id}/payment", headers=headers_b)
    assert response.status_code == 404


def test_non_customer_role_forbidden(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_pay@example.com")
    response = client.get("/api/v1/payments/1", headers=_auth_headers(db_session, admin))
    assert response.status_code == 403


def test_unauthenticated_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/payments", json={"order_id": 1, "payment_method": "COD"})
    assert response.status_code == 401


def test_client_cannot_control_amount_or_status(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "SEC4")
    order = _create_order(db_session, user, total_amount=Decimal("999.00"))
    response = client.post(
        "/api/v1/payments",
        json={
            "order_id": order.id, "payment_method": "COD",
            "amount": "1.00", "status": "PAID", "currency": "USD",  # all ignored
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "999.00"  # server-authoritative, from the order
    assert body["currency"] == "INR"
    assert body["status"] == "PENDING"  # never client-settable


def test_secrets_never_in_payment_response(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "SEC5")
    order = _create_order(db_session, user)
    response = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    )
    body_text = response.text
    assert WEBHOOK_SECRET not in body_text
    assert "webhook_secret" not in body_text
    assert "merchant_id" not in body_text
    assert "gateway_response" not in body_text


# ---------------------------------------------------------------------------
# Order payability
# ---------------------------------------------------------------------------


def test_order_already_confirmed_rejects_new_payment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "PAYA1")
    order = _create_order(db_session, user, status="CONFIRMED")
    response = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 409


def test_already_paid_payment_rejects_recreation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "PAYA2")
    order = _create_order(db_session, user, total_amount=Decimal("80.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()
    body = _webhook_body(
        event_id="evt-paid-already", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="80.00", currency="INR",
    )
    client.post("/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body))

    # Order is now CONFIRMED (not PENDING) so a fresh create_payment call
    # hits the "already exists, already PAID" branch.
    response = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Failure injection: outcome-unknown vs definitive failure
# ---------------------------------------------------------------------------


def test_gateway_timeout_leaves_payment_processing_not_failed(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "FAIL1")
    order = _create_order(db_session, user)
    gateway.queue_initiate(GatewayTimeoutError("simulated network timeout"))

    response = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    )
    assert response.status_code == 500  # honest error to the client

    db_session.expire_all()
    payment = db_session.query(Payment).filter_by(order_id=order.id).first()
    assert payment.status == "PROCESSING"  # NEVER FAILED on a timeout
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment.id).first()
    assert txn.status == "INITIATED"


def test_gateway_connection_error_leaves_payment_processing(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "FAIL2")
    order = _create_order(db_session, user)
    gateway.queue_initiate(GatewayConnectionError("simulated connection refused"))

    client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    )

    db_session.expire_all()
    payment = db_session.query(Payment).filter_by(order_id=order.id).first()
    assert payment.status == "PROCESSING"


def test_gateway_definitive_rejection_marks_failed(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "FAIL3")
    order = _create_order(db_session, user)
    gateway.queue_initiate(GatewayRejectedError("simulated validation error"))

    client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    )

    db_session.expire_all()
    payment = db_session.query(Payment).filter_by(order_id=order.id).first()
    assert payment.status == "FAILED"  # definitively resolved, safe to mark FAILED
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment.id).first()
    assert txn.status == "FAILED"


def test_real_pnb_gateway_initiate_and_query_are_honest_not_implemented() -> None:
    """The actual production adapter, not the fake - proves we do not
    pretend UPI works end-to-end without a real PNB integration contract.
    """
    real_gateway = PNBGateway(
        merchant_id="x", webhook_secret="x", base_url="https://example.invalid"
    )
    with pytest.raises(NotImplementedError):
        real_gateway.initiate_payment(
            reference="r", amount=Decimal("1"), currency="INR", idempotency_key="k"
        )
    with pytest.raises(NotImplementedError):
        real_gateway.query_status(gateway_order_id="x", gateway_transaction_id=None)


def test_real_pnb_gateway_webhook_signature_verification_works() -> None:
    """The placeholder HMAC scheme itself is real, testable code - not a stub."""
    real_gateway = PNBGateway(
        merchant_id="x", webhook_secret="real-secret-value", base_url="https://example.invalid"
    )
    body = b'{"event_id":"e1","event_type":"t","status":"SUCCESS"}'
    good_sig = _sign("real-secret-value", body)
    assert real_gateway.verify_webhook_signature(
        raw_body=body, headers={"X-PNB-Signature": good_sig}
    ) is True
    assert real_gateway.verify_webhook_signature(
        raw_body=body, headers={"X-PNB-Signature": "wrong"}
    ) is False
    assert real_gateway.verify_webhook_signature(raw_body=body, headers={}) is False


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_payment_initiation_exactly_one_payment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "CONC1")
    order = _create_order(db_session, user)

    def create():
        return client.post(
            "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(create)
        f2 = pool.submit(create)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    assert r1.json()["id"] == r2.json()["id"]  # both resolve to the same logical payment

    db_session.expire_all()
    assert db_session.query(Payment).filter_by(order_id=order.id).count() == 1


def test_concurrent_identical_webhook_delivery_processed_exactly_once(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "CONC2")
    order = _create_order(db_session, user, total_amount=Decimal("175.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    body = _webhook_body(
        event_id="evt-concurrent-1", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="175.00", currency="INR",
    )
    sig_headers = _webhook_headers(WEBHOOK_SECRET, body)

    def send():
        return client.post("/api/v1/payments/webhooks/pnb", content=body, headers=sig_headers)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(send) for _ in range(4)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)

    db_session.expire_all()
    assert db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-concurrent-1").count() == 1
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PAID"
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "CONFIRMED"
    # Exactly one SUCCESS transaction row - never duplicated.
    success_txns = (
        db_session.query(PaymentTransaction)
        .filter_by(payment_id=payment["id"], status="SUCCESS")
        .count()
    )
    assert success_txns == 1


def test_webhook_and_verify_race_exactly_one_confirmation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "CONC3")
    order = _create_order(db_session, user, total_amount=Decimal("220.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    gateway.queue_query(
        GatewayStatusResult(
            gateway_order_id=payment["gateway_order_id"],
            gateway_transaction_id=txn.gateway_transaction_id,
            status=TransactionStatus.SUCCESS, amount=Decimal("220.00"), currency="INR",
        )
    )
    body = _webhook_body(
        event_id="evt-race-1", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="220.00", currency="INR",
    )
    sig_headers = _webhook_headers(WEBHOOK_SECRET, body)

    def do_webhook():
        return client.post("/api/v1/payments/webhooks/pnb", content=body, headers=sig_headers)

    def do_verify():
        return client.post(f"/api/v1/payments/{payment['id']}/verify", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(do_webhook)
        f2 = pool.submit(do_verify)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200
    assert r2.status_code == 200

    db_session.expire_all()
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PAID"
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "CONFIRMED"
    success_txns = (
        db_session.query(PaymentTransaction)
        .filter_by(payment_id=payment["id"], status="SUCCESS")
        .count()
    )
    assert success_txns == 1  # never double-applied


def test_concurrent_retries_do_not_create_two_new_attempts(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    user, headers = _customer(db_session, "CONC4")
    order = _create_order(db_session, user)
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()
    body = _webhook_body(
        event_id="evt-pre-retry-fail", event_type="PAYMENT_FAILED",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="FAILED",
    )
    client.post("/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body))

    def retry():
        return client.post(f"/api/v1/payments/{payment['id']}/retry", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(retry)
        f2 = pool.submit(retry)
        r1, r2 = f1.result(), f2.result()

    statuses = {r1.status_code, r2.status_code}
    assert 200 in statuses
    assert 409 in statuses  # the second sees PROCESSING (already retried) and is rejected

    db_session.expire_all()
    all_txns = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).count()
    assert all_txns == 2  # original FAILED + exactly one new attempt, never two new ones


# ---------------------------------------------------------------------------
# Rollback (fault injection - DB state re-verified, not just HTTP response)
# ---------------------------------------------------------------------------


def test_forced_failure_during_paid_confirmation_leaves_no_partial_state(
    client: TestClient, db_session: Session, gateway: FakePNBGateway, monkeypatch
) -> None:
    import app.services.payment as payment_module

    user, headers = _customer(db_session, "ROLLBACK1")
    order = _create_order(db_session, user, total_amount=Decimal("60.00"))
    payment = client.post(
        "/api/v1/payments", json={"order_id": order.id, "payment_method": "UPI"}, headers=headers
    ).json()
    txn = db_session.query(PaymentTransaction).filter_by(payment_id=payment["id"]).first()

    original = payment_module.PaymentService._confirm_order_if_paid

    def boom(self, *args, **kwargs):
        raise RuntimeError("simulated failure confirming order")

    monkeypatch.setattr(payment_module.PaymentService, "_confirm_order_if_paid", boom)

    body = _webhook_body(
        event_id="evt-rollback-1", event_type="PAYMENT_SUCCESS",
        gateway_order_id=payment["gateway_order_id"], gateway_transaction_id=txn.gateway_transaction_id,
        status="SUCCESS", amount="60.00", currency="INR",
    )
    response = client.post(
        "/api/v1/payments/webhooks/pnb", content=body, headers=_webhook_headers(WEBHOOK_SECRET, body)
    )
    assert response.status_code == 500

    db_session.expire_all()
    # Nothing committed - payment must NOT be PAID, order must NOT be CONFIRMED,
    # and the webhook event must not be stuck claiming PROCESSED.
    refreshed_payment = db_session.get(Payment, payment["id"])
    assert refreshed_payment.status == "PROCESSING"
    refreshed_order = db_session.get(Order, order.id)
    assert refreshed_order.status == "PENDING"
    webhook_event = db_session.query(PaymentWebhookEvent).filter_by(event_id="evt-rollback-1").first()
    assert webhook_event is None  # the whole transaction (incl. the dedup row) rolled back

    monkeypatch.setattr(payment_module.PaymentService, "_confirm_order_if_paid", original)
