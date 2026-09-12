"""Phase 18 focused validation: order cancellation & refund approval.

Minor/lightweight validation only, per the phase's own instruction - this
is NOT a large test suite. Covers the core rules: cancel-before-delivery,
COD-no-refund, online-paid-refund-eligible-not-automatic, admin-approval-
required, delivery-vs-cancellation race safety, and fulfillment cannot
progress after cancellation. Real PostgreSQL throughout, no mocking except
the payment gateway (FakePNBGateway, same convention as test_phase_16).
"""

import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import (
    ADMIN,
    CUSTOMER,
    DELIVERY_PARTNER,
    HUB_STAFF,
    OPERATIONS,
    WHOLESALER,
)
from app.core.security import create_access_token, hash_password
from app.dependencies.payments import get_payment_gateway
from app.main import app
from app.models.address import Address
from app.models.auth_session import AuthSession
from app.models.batch import Batch
from app.models.category import Category
from app.models.fulfillment import Fulfillment
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.order import Order
from app.models.price import Price
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.refund import Refund
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.payment_gateway import GatewayInitiateResult, PNBGateway
from app.services.payment_state import TransactionStatus

WEBHOOK_SECRET = "test-webhook-secret-for-phase-18-min-32-chars"


class FakePNBGateway(PNBGateway):
    def __init__(self) -> None:
        super().__init__(
            merchant_id="fake-merchant", webhook_secret=WEBHOOK_SECRET,
            base_url="https://fake-pnb.invalid",
        )
        self._next_initiate = None
        self._counter = 0

    def queue_initiate(self, result_or_exc) -> None:
        self._next_initiate = result_or_exc

    def initiate_payment(self, **kwargs) -> GatewayInitiateResult:
        if self._next_initiate is not None:
            value = self._next_initiate
            self._next_initiate = None
            if isinstance(value, Exception):
                raise value
            return value
        self._counter += 1
        return GatewayInitiateResult(
            gateway_order_id=f"fake-order-{self._counter}",
            gateway_transaction_id=f"fake-txn-{self._counter}",
            status=TransactionStatus.PROCESSING,
        )

    def query_status(self, **kwargs):
        raise NotImplementedError


@pytest.fixture
def gateway() -> FakePNBGateway:
    fake = FakePNBGateway()
    app.dependency_overrides[get_payment_gateway] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_payment_gateway, None)


# ---------------------------------------------------------------------------
# Helpers (same conventions as test_phase_16/17)
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
        phone=f"+9197{abs(hash(email)) % 100000000:08d}",
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
        user_id=user.id, refresh_token_hash=f"dummy-hash-{user.id}-{secrets.token_hex(8)}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    token = create_access_token(user_id=user.id, session_id=session.id)
    return {"Authorization": f"Bearer {token}"}


def _customer(db_session: Session, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, CUSTOMER, f"cust18_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _staff(db_session: Session, role: str, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, role, f"{role.lower()}18_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _create_product_variant(db_session: Session, *, tag: str) -> tuple[Product, ProductVariant]:
    category = Category(name=f"Cat18-{tag}", slug=f"cat18-{tag.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod18-{tag}", slug=f"prod18-{tag.lower()}", status="ACTIVE"
    )
    db_session.add(product)
    db_session.commit()
    variant = ProductVariant(
        product_id=product.id, name="1 KG", sku=f"SKU18-{tag}", unit="KG",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return product, variant


def _create_price(db_session: Session, variant: ProductVariant, *, price: Decimal = Decimal("50.00")) -> None:
    db_session.add(
        Price(
            variant_id=variant.id, price=price, currency="INR",
            valid_from=datetime.now(UTC) - timedelta(days=1), valid_to=None, is_active=True,
        )
    )
    db_session.commit()


def _create_lot(
    db_session: Session, product: Product, variant: ProductVariant, *, tag: str, quantity: Decimal
) -> InventoryLot:
    wholesaler = _create_user_with_role(db_session, WHOLESALER, f"ws18_{tag.lower()}@example.com")
    batch = Batch(
        wholesaler_user_id=wholesaler.id, product_id=product.id, batch_code=f"BATCH18-{tag}",
        harvest_date=date(2026, 1, 1), quantity=quantity, unit="KG", status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    location = InventoryLocation(
        name=f"Hub18-{tag}", code=f"HUB18-{tag}", type="WAREHOUSE",
        address_line_1="1 Warehouse Rd", city="Nagpur", state="MH",
        postal_code="440001", status="ACTIVE",
    )
    db_session.add(location)
    db_session.commit()
    lot = InventoryLot(
        batch_id=batch.id, variant_id=variant.id, location_id=location.id,
        quantity=quantity, status="ACTIVE",
    )
    db_session.add(lot)
    db_session.commit()
    db_session.refresh(lot)
    return lot


def _create_address(db_session: Session, user: User) -> Address:
    addr = Address(
        user_id=user.id, label="Home", address_line_1="221B Test Lane",
        city="Nagpur", state="Maharashtra", postal_code="440001",
    )
    db_session.add(addr)
    db_session.commit()
    db_session.refresh(addr)
    return addr


def _ready_customer(db_session: Session, tag: str, *, stock: Decimal = Decimal("100.000")):
    user, headers = _customer(db_session, tag)
    product, variant = _create_product_variant(db_session, tag=tag)
    _create_price(db_session, variant, price=Decimal("50.00"))
    lot = _create_lot(db_session, product, variant, tag=tag, quantity=stock)
    address = _create_address(db_session, user)
    return user, headers, variant, address, lot


def _checkout(client: TestClient, headers: dict, variant: ProductVariant, address, qty: str = "1") -> dict:
    client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": qty}, headers=headers
    )
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _confirm_cod(client: TestClient, headers: dict, order_id: int) -> None:
    response = client.post(
        "/api/v1/payments", json={"order_id": order_id, "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 201, response.text


def _pay_upi(client: TestClient, headers: dict, gateway: FakePNBGateway, order_id: int) -> None:
    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id=f"go-{order_id}", gateway_transaction_id=f"gt-{order_id}",
            status=TransactionStatus.SUCCESS,
        )
    )
    response = client.post(
        "/api/v1/payments", json={"order_id": order_id, "payment_method": "UPI"}, headers=headers
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "PAID"


def _advance_to_out_for_delivery(
    client: TestClient, db_session: Session, ops_headers: dict, fulfillment_id: int, tag: str
) -> dict[str, str]:
    for target in ("PICKING", "PACKED", "READY_FOR_DELIVERY"):
        r = client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": target}, headers=ops_headers
        )
        assert r.status_code == 200, r.text
    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, tag)
    r = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=partner_headers)
    assert r.status_code == 200, r.text
    return partner_headers


# ---------------------------------------------------------------------------
# Cancellation basics (1-8)
# ---------------------------------------------------------------------------


def test_1_customer_can_cancel_pending_order_before_payment(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T1")
    order = _checkout(client, headers, variant, address)

    response = client.post(
        f"/api/v1/orders/{order['id']}/cancel", json={"reason": "changed my mind"}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancellation_reason"] == "changed my mind"
    assert body["cancelled_at"] is not None

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "RELEASED"
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")
    assert refreshed_lot.quantity == lot.quantity  # physical inventory untouched
    assert db_session.query(Refund).filter_by(order_id=order["id"]).count() == 0


def test_2_cod_cancellation_after_confirmation_releases_reservation_no_refund(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T2")
    order = _checkout(client, headers, variant, address)
    _confirm_cod(client, headers, order["id"])

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "COMMITTED"

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    db_session.expire_all()
    assert db_session.get(InventoryReservation, reservation.id).status == "RELEASED"
    assert db_session.get(InventoryLot, lot.id).reserved_quantity == Decimal("0.000")
    assert db_session.query(Refund).filter_by(order_id=order["id"]).count() == 0  # COD: no refund


def test_3_online_paid_cancellation_creates_pending_refund_not_automatic(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T3")
    order = _checkout(client, headers, variant, address)
    _pay_upi(client, headers, gateway, order["id"])

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()
    assert refund.status == "PENDING_APPROVAL"  # never auto-refunded
    assert str(refund.amount) == order["total_amount"]
    lot_after = db_session.get(InventoryLot, lot.id)
    assert lot_after.reserved_quantity == Decimal("0.000")

    refund_view = client.get(f"/api/v1/orders/{order['id']}/refund", headers=headers)
    assert refund_view.status_code == 200
    assert refund_view.json()["status"] == "PENDING_APPROVAL"


def test_4_cannot_cancel_a_delivered_order(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T4")
    order = _checkout(client, headers, variant, address)
    _confirm_cod(client, headers, order["id"])
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one()
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T4")
    partner_headers = _advance_to_out_for_delivery(client, db_session, ops_headers, fulfillment.id, "T4")
    deliver = client.post(f"/api/v1/fulfillments/{fulfillment.id}/deliver", headers=partner_headers)
    assert deliver.status_code == 200

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.get(Order, order["id"]).status == "COMPLETED"


def test_5_cancel_is_idempotent_on_already_cancelled_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T5")
    order = _checkout(client, headers, variant, address)
    first = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "CANCELLED"


def test_6_customer_cannot_cancel_another_customers_order(
    client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a, variant, address, _lot = _ready_customer(db_session, "T6A")
    order = _checkout(client, headers_a, variant, address)
    _user_b, headers_b = _customer(db_session, "T6B")

    response = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers_b)
    assert response.status_code == 404


def test_7_admin_can_cancel_any_order(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T7")
    order = _checkout(client, headers, variant, address)
    _admin, admin_headers = _staff(db_session, ADMIN, "T7")

    response = client.post(
        f"/api/v1/orders/admin/{order['id']}/cancel",
        json={"reason": "customer support request"}, headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["cancellation_reason"] == "customer support request"


def test_8_operations_role_cannot_administratively_cancel(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T8")
    order = _checkout(client, headers, variant, address)
    _ops, ops_headers = _staff(db_session, OPERATIONS, "T8")

    response = client.post(
        f"/api/v1/orders/admin/{order['id']}/cancel", json={}, headers=ops_headers
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Fulfillment must stop after cancellation (9-11)
# ---------------------------------------------------------------------------


def test_9_cannot_assign_delivery_partner_to_a_cancelled_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T9")
    order = _checkout(client, headers, variant, address)
    _confirm_cod(client, headers, order["id"])
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one()
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T9")
    for target in ("PICKING", "PACKED", "READY_FOR_DELIVERY"):
        client.post(
            f"/api/v1/fulfillments/{fulfillment.id}/status", json={"status": target}, headers=ops_headers
        )

    cancel = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert cancel.status_code == 200

    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T9")
    assign = client.post(
        f"/api/v1/fulfillments/{fulfillment.id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    assert assign.status_code == 409


def test_10_cannot_advance_warehouse_status_on_a_cancelled_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T10")
    order = _checkout(client, headers, variant, address)
    _confirm_cod(client, headers, order["id"])
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one()

    cancel = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert cancel.status_code == 200

    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T10")
    response = client.post(
        f"/api/v1/fulfillments/{fulfillment.id}/status", json={"status": "PICKING"}, headers=ops_headers
    )
    assert response.status_code == 409


def test_11_cannot_deliver_a_cancelled_order_no_inventory_consumed(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T11")
    order = _checkout(client, headers, variant, address, qty="2")
    _confirm_cod(client, headers, order["id"])
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one()
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T11")
    partner_headers = _advance_to_out_for_delivery(client, db_session, ops_headers, fulfillment.id, "T11")

    cancel = client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    assert cancel.status_code == 200

    deliver = client.post(f"/api/v1/fulfillments/{fulfillment.id}/deliver", headers=partner_headers)
    assert deliver.status_code == 409

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == lot.quantity  # never consumed
    assert refreshed_lot.reserved_quantity == Decimal("0.000")
    assert db_session.get(Order, order["id"]).status == "CANCELLED"


# ---------------------------------------------------------------------------
# Delivery vs. cancellation race (12) - the one required concurrency test
# ---------------------------------------------------------------------------


def test_concurrency_12_cancel_races_delivery_exactly_one_terminal_state(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "C12", stock=Decimal("500"))
    order = _checkout(client, headers, variant, address, qty="2")
    _confirm_cod(client, headers, order["id"])
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one()
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "C12")
    partner_headers = _advance_to_out_for_delivery(client, db_session, ops_headers, fulfillment.id, "C12")

    def cancel():
        return client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)

    def deliver():
        return client.post(f"/api/v1/fulfillments/{fulfillment.id}/deliver", headers=partner_headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(cancel)
        f2 = pool.submit(deliver)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409]  # exactly one side wins

    db_session.expire_all()
    final_order = db_session.get(Order, order["id"])
    assert final_order.status in ("CANCELLED", "COMPLETED")
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    if final_order.status == "CANCELLED":
        assert refreshed_lot.quantity == lot.quantity  # never consumed
        assert refreshed_lot.reserved_quantity == Decimal("0.000")
        assert db_session.get(Fulfillment, fulfillment.id).status != "DELIVERED"
    else:
        assert refreshed_lot.quantity == lot.quantity - Decimal("2.000")  # consumed exactly once
        assert db_session.get(Fulfillment, fulfillment.id).status == "DELIVERED"


# ---------------------------------------------------------------------------
# Refund approval workflow (13-18)
# ---------------------------------------------------------------------------


def _cancelled_paid_order(client, db_session, gateway, tag) -> tuple[dict, dict]:
    _user, headers, variant, address, _lot = _ready_customer(db_session, tag)
    order = _checkout(client, headers, variant, address)
    _pay_upi(client, headers, gateway, order["id"])
    client.post(f"/api/v1/orders/{order['id']}/cancel", json={}, headers=headers)
    return order, headers


def test_13_admin_can_approve_refund(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    order, _headers = _cancelled_paid_order(client, db_session, gateway, "T13")
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()
    _admin, admin_headers = _staff(db_session, ADMIN, "T13")

    response = client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["approved_by_user_id"] == _admin.id
    assert body["approved_at"] is not None


def test_14_admin_can_reject_refund(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    order, _headers = _cancelled_paid_order(client, db_session, gateway, "T14")
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()
    _admin, admin_headers = _staff(db_session, ADMIN, "T14")

    response = client.post(
        f"/api/v1/payments/refunds/{refund.id}/reject",
        json={"reason": "duplicate refund request"}, headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "duplicate refund request"


def test_15_double_approve_rejected_not_silently_reapplied(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    order, _headers = _cancelled_paid_order(client, db_session, gateway, "T15")
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()
    admin_a, admin_a_headers = _staff(db_session, ADMIN, "T15A")
    _admin_b, admin_b_headers = _staff(db_session, ADMIN, "T15B")

    first = client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin_a_headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin_b_headers)
    assert second.status_code == 409  # not silently re-stamped by a second admin

    db_session.expire_all()
    assert db_session.get(Refund, refund.id).approved_by_user_id == admin_a.id


def test_16_customer_cannot_approve_own_refund(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    order, headers = _cancelled_paid_order(client, db_session, gateway, "T16")
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()

    response = client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=headers)
    assert response.status_code == 403


def test_17_operations_and_hub_staff_cannot_access_refund_endpoints(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    order, _headers = _cancelled_paid_order(client, db_session, gateway, "T17")
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()
    _ops, ops_headers = _staff(db_session, OPERATIONS, "T17")
    _hub, hub_headers = _staff(db_session, HUB_STAFF, "T17")

    for headers in (ops_headers, hub_headers):
        response = client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=headers)
        assert response.status_code == 403


def test_18_process_without_real_gateway_fails_cleanly_refund_marked_failed(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    """PNBGateway.refund_payment is a structural placeholder
    (NotImplementedError) - processing must fail cleanly, never crash the
    approval state into something ambiguous.
    """
    order, _headers = _cancelled_paid_order(client, db_session, gateway, "T18")
    db_session.expire_all()
    refund = db_session.query(Refund).filter_by(order_id=order["id"]).one()
    _admin, admin_headers = _staff(db_session, ADMIN, "T18")
    client.post(f"/api/v1/payments/refunds/{refund.id}/approve", headers=admin_headers)

    response = client.post(f"/api/v1/payments/refunds/{refund.id}/process", headers=admin_headers)
    assert response.status_code == 500  # PNBGateway.refund_payment raises NotImplementedError

    db_session.expire_all()
    assert db_session.get(Refund, refund.id).status == "FAILED"
