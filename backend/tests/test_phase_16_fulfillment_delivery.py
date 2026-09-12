"""Phase 16 focused validation: fulfillment & delivery operations.

Fast-development-mode focused validation against real PostgreSQL. Builds
directly on the Phase 15 reservation/fulfillment foundation - this file
exercises the NEW Phase 16 surface (ASSIGNED state, delivery-partner
assignment + ownership, ops/customer RBAC scoping) rather than
re-testing what Phase 15's own suite already covers (FIFO allocation,
reservation lifecycle, expiry). Mutation tests re-read the database
afterward, never trusting an HTTP response alone. Concurrency tests use
real threads against real Postgres row locks (ThreadPoolExecutor), never
mocked.
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
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.models.price import Price
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.user_role import UserRole
from app.services.payment_gateway import GatewayInitiateResult, PNBGateway
from app.services.payment_state import TransactionStatus

WEBHOOK_SECRET = "test-webhook-secret-for-phase-16-min-32-chars"


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
# Helpers
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
        phone=f"+9198{abs(hash(email)) % 100000000:08d}",
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
    """Each call creates a fresh session (a real user can be logged in on
    multiple devices) - the hash must be unique per call, not just per
    user, so calling this twice for the same user (a legitimate pattern
    in several tests below) never collides on refresh_token_hash.
    """
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=f"dummy-hash-{user.id}-{secrets.token_hex(8)}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    token = create_access_token(user_id=user.id, session_id=session.id)
    return {"Authorization": f"Bearer {token}"}


def _customer(db_session: Session, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, CUSTOMER, f"cust16_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _staff(db_session: Session, role: str, tag: str) -> tuple[User, dict[str, str]]:
    user = _create_user_with_role(db_session, role, f"{role.lower()}16_{tag.lower()}@example.com")
    return user, _auth_headers(db_session, user)


def _create_product_variant(db_session: Session, *, tag: str) -> tuple[Product, ProductVariant]:
    category = Category(name=f"Cat16-{tag}", slug=f"cat16-{tag.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod16-{tag}", slug=f"prod16-{tag.lower()}", status="ACTIVE"
    )
    db_session.add(product)
    db_session.commit()
    variant = ProductVariant(
        product_id=product.id, name="1 KG", sku=f"SKU16-{tag}", unit="KG",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return product, variant


def _create_price(db_session: Session, variant: ProductVariant, *, price: Decimal = Decimal("50.00")) -> Price:
    row = Price(
        variant_id=variant.id, price=price, currency="INR",
        valid_from=datetime.now(UTC) - timedelta(days=1), valid_to=None, is_active=True,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _create_lot(
    db_session: Session, product: Product, variant: ProductVariant, *,
    tag: str, quantity: Decimal, created_at: datetime | None = None,
) -> InventoryLot:
    wholesaler = _create_user_with_role(db_session, WHOLESALER, f"ws16_{tag.lower()}@example.com")
    batch = Batch(
        wholesaler_user_id=wholesaler.id, product_id=product.id, batch_code=f"BATCH16-{tag}",
        harvest_date=date(2026, 1, 1), quantity=quantity, unit="KG", status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    location = InventoryLocation(
        name=f"Hub16-{tag}", code=f"HUB16-{tag}", type="WAREHOUSE",
        address_line_1="1 Warehouse Rd", city="Nagpur", state="MH",
        postal_code="440001", status="ACTIVE",
    )
    db_session.add(location)
    db_session.commit()
    lot = InventoryLot(
        batch_id=batch.id, variant_id=variant.id, location_id=location.id,
        quantity=quantity, status="ACTIVE",
    )
    if created_at is not None:
        lot.created_at = created_at
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


def _ready_customer(
    db_session: Session, tag: str, *, stock: Decimal = Decimal("100.000"),
    price: Decimal = Decimal("50.00"),
):
    user, headers = _customer(db_session, tag)
    product, variant = _create_product_variant(db_session, tag=tag)
    _create_price(db_session, variant, price=price)
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


def _confirm_cod_and_get_fulfillment_id(
    client: TestClient, db_session: Session, headers: dict, order_id: int
) -> int:
    response = client.post(
        "/api/v1/payments", json={"order_id": order_id, "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 201, response.text
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order_id).one()
    return fulfillment.id


def _advance_to_ready(client: TestClient, ops_headers: dict, fulfillment_id: int) -> None:
    for target in ("PICKING", "PACKED", "READY_FOR_DELIVERY"):
        response = client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": target}, headers=ops_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target


def _assign_and_dispatch(
    client: TestClient, db_session: Session, ops_headers: dict, fulfillment_id: int, tag: str
) -> tuple[User, dict[str, str]]:
    """Advances READY_FOR_DELIVERY -> ASSIGNED -> OUT_FOR_DELIVERY, returns
    the assigned partner (user, headers).
    """
    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, tag)
    assign = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["status"] == "ASSIGNED"
    out = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=partner_headers
    )
    assert out.status_code == 200, out.text
    assert out.json()["status"] == "OUT_FOR_DELIVERY"
    return partner, partner_headers


def _full_cod_ready_for_delivery(
    client: TestClient, db_session: Session, tag: str, *, qty: str = "3", stock: Decimal = Decimal("100.000")
):
    """Full happy-path setup: checkout -> COD confirm -> fulfillment
    advanced through PICKING/PACKED/READY_FOR_DELIVERY. Returns
    (order, fulfillment_id, ops_headers, lot, original_quantity).
    """
    _user, headers, variant, address, lot = _ready_customer(db_session, tag, stock=stock)
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty=qty)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, tag)
    _advance_to_ready(client, ops_headers, fulfillment_id)
    return order, fulfillment_id, ops_headers, lot, original_quantity


# ---------------------------------------------------------------------------
# Fulfillment creation gating (1-4)
# ---------------------------------------------------------------------------


def test_1_pending_order_has_no_fulfillment(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T1")
    order = _checkout(client, headers, variant, address)
    assert order["status"] == "PENDING"

    response = client.get(f"/api/v1/orders/{order['id']}/fulfillment", headers=headers)
    assert response.status_code == 404

    db_session.expire_all()
    assert db_session.query(Fulfillment).filter_by(order_id=order["id"]).count() == 0


def test_2_cod_confirmation_creates_fulfillment(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T2")
    order = _checkout(client, headers, variant, address)
    client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers
    )

    response = client.get(f"/api/v1/orders/{order['id']}/fulfillment", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"


def test_3_expired_order_never_gets_a_fulfillment(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T3")
    order = _checkout(client, headers, variant, address)

    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    # Lazily trigger expiry via the customer's own reservation read.
    client.get(f"/api/v1/orders/{order['id']}/reservation", headers=headers)

    db_session.expire_all()
    assert db_session.get(Order, order["id"]).status == "EXPIRED"
    assert db_session.query(Fulfillment).filter_by(order_id=order["id"]).count() == 0

    # A COD attempt against the now-expired order must not create one either.
    response = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.query(Fulfillment).filter_by(order_id=order["id"]).count() == 0


def test_4_upi_fulfillment_requires_paid_payment_and_committed_reservation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T4")
    order = _checkout(client, headers, variant, address)

    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id="go-t4", gateway_transaction_id="gt-t4",
            status=TransactionStatus.PROCESSING,
        )
    )
    client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "UPI"}, headers=headers
    )

    # Payment PROCESSING (not yet PAID) - no fulfillment must exist.
    still_pending = client.get(f"/api/v1/orders/{order['id']}/fulfillment", headers=headers)
    assert still_pending.status_code == 404
    db_session.expire_all()
    assert db_session.query(Fulfillment).filter_by(order_id=order["id"]).count() == 0

    # Now let the payment succeed via a fresh PAID UPI order (synchronous
    # success at initiation) and confirm fulfillment appears immediately.
    order2 = _checkout(client, headers, variant, address, qty="1")
    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id="go-t4b", gateway_transaction_id="gt-t4b",
            status=TransactionStatus.SUCCESS,
        )
    )
    paid = client.post(
        "/api/v1/payments", json={"order_id": order2["id"], "payment_method": "UPI"}, headers=headers
    )
    assert paid.json()["status"] == "PAID"

    response = client.get(f"/api/v1/orders/{order2['id']}/fulfillment", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"

    db_session.expire_all()
    reservation2 = db_session.query(InventoryReservation).filter_by(order_id=order2["id"]).one()
    assert reservation2.status == "COMMITTED"


# ---------------------------------------------------------------------------
# State machine (5-16)
# ---------------------------------------------------------------------------


def test_5_valid_chain_pending_through_ready(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T5")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, OPERATIONS, "T5")

    for target in ("PICKING", "PACKED", "READY_FOR_DELIVERY"):
        response = client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": target}, headers=ops_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target


def test_6_valid_chain_ready_through_delivered(client: TestClient, db_session: Session) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(db_session=db_session, client=client, tag="T6")
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T6")

    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "DELIVERED"


@pytest.mark.parametrize(
    "start,target",
    [
        ("PENDING", "DELIVERED"),
        ("PENDING", "PACKED"),  # skip-ahead
        ("PENDING", "READY_FOR_DELIVERY"),
        ("PACKED", "DELIVERED"),
        ("PICKING", "READY_FOR_DELIVERY"),  # skip ASSIGNED/OUT_FOR_DELIVERY too but this alone should fail
    ],
)
def test_7_invalid_forward_transitions_rejected(
    client: TestClient, db_session: Session, start: str, target: str
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, f"T7{start}{target}")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, f"T7{start}{target}")

    # Walk up to and including `start` (PENDING requires no steps).
    chain = ["PICKING", "PACKED", "READY_FOR_DELIVERY"]
    if start != "PENDING":
        for step in chain[: chain.index(start) + 1]:
            walk = client.post(
                f"/api/v1/fulfillments/{fulfillment_id}/status",
                json={"status": step}, headers=ops_headers,
            )
            assert walk.status_code == 200, walk.text

    if target == "DELIVERED":
        response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=ops_headers)
    else:
        response = client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": target}, headers=ops_headers
        )
    assert response.status_code in (403, 409)  # ops lacks /deliver access OR illegal transition


def test_8_ready_for_delivery_to_out_for_delivery_directly_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    """Phase 16 makes ASSIGNED mandatory - the old Phase 15
    READY_FOR_DELIVERY -> OUT_FOR_DELIVERY single step no longer exists.
    """
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T8"
    )
    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T8")
    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=partner_headers
    )
    # Unassigned partner: ownership fails before the state check even runs.
    assert response.status_code == 403


def test_9_delivered_to_picking_is_rejected(client: TestClient, db_session: Session) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T9"
    )
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T9")
    deliver = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    assert deliver.status_code == 200

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": "PICKING"}, headers=ops_headers
    )
    assert response.status_code == 409


def test_10_same_state_picking_transition_is_idempotent_not_corrupting(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T10")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T10")

    client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": "PICKING"}, headers=ops_headers
    )
    second = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": "PICKING"}, headers=ops_headers
    )
    assert second.status_code == 200
    assert second.json()["status"] == "PICKING"

    db_session.expire_all()
    assert db_session.query(Fulfillment).filter_by(id=fulfillment_id).one().status == "PICKING"


def test_11_status_endpoint_rejects_assigned_out_for_delivery_delivered_targets(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T11")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T11")

    for forbidden in ("ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED"):
        response = client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": forbidden}, headers=ops_headers,
        )
        assert response.status_code in (409, 422)


# ---------------------------------------------------------------------------
# Assignment rules (12-19)
# ---------------------------------------------------------------------------


def test_12_assignment_requires_ready_for_delivery_state(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T12")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, OPERATIONS, "T12")
    partner, _partner_headers = _staff(db_session, DELIVERY_PARTNER, "T12")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    assert response.status_code == 409  # still PENDING, not READY_FOR_DELIVERY


def test_13_assignment_rejects_nonexistent_user(client: TestClient, db_session: Session) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T13"
    )
    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": 999999}, headers=ops_headers,
    )
    assert response.status_code == 404


def test_14_assignment_rejects_user_without_delivery_partner_role(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T14"
    )
    not_a_partner, _headers = _staff(db_session, HUB_STAFF, "T14NOTPARTNER")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": not_a_partner.id}, headers=ops_headers,
    )
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.get(Fulfillment, fulfillment_id).delivery_partner_user_id is None


def test_15_successful_assignment_sets_partner_and_timestamp(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T15"
    )
    partner, _partner_headers = _staff(db_session, DELIVERY_PARTNER, "T15")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ASSIGNED"
    assert body["delivery_partner_user_id"] == partner.id
    assert body["assigned_at"] is not None


def test_16_cannot_reassign_already_assigned_fulfillment(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T16"
    )
    partner_a, _ = _staff(db_session, DELIVERY_PARTNER, "T16A")
    partner_b, _ = _staff(db_session, DELIVERY_PARTNER, "T16B")

    first = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner_a.id}, headers=ops_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner_b.id}, headers=ops_headers,
    )
    assert second.status_code == 409

    db_session.expire_all()
    assert db_session.get(Fulfillment, fulfillment_id).delivery_partner_user_id == partner_a.id


def test_17_customer_cannot_assign_delivery_partner(client: TestClient, db_session: Session) -> None:
    order, fulfillment_id, _ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T17"
    )
    customer_user = db_session.query(Order).filter_by(id=order["id"]).one().user_id
    customer_headers = _auth_headers(db_session, db_session.get(User, customer_user))
    partner, _ = _staff(db_session, DELIVERY_PARTNER, "T17")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=customer_headers,
    )
    assert response.status_code == 403


def test_18_delivery_partner_cannot_assign_delivery_partner(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, _ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T18ASSIGN"
    )
    _requester, requester_headers = _staff(db_session, DELIVERY_PARTNER, "T18REQ")
    target, _ = _staff(db_session, DELIVERY_PARTNER, "T18TARGET")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": target.id}, headers=requester_headers,
    )
    assert response.status_code == 403


def test_19_client_cannot_supply_arbitrary_fields_to_assign(
    client: TestClient, db_session: Session
) -> None:
    """The assign schema only ever accepts delivery_partner_user_id -
    status/timestamps are always server-derived."""
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T19"
    )
    partner, _ = _staff(db_session, DELIVERY_PARTNER, "T19")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={
            "delivery_partner_user_id": partner.id,
            "status": "DELIVERED",
            "assigned_at": "2000-01-01T00:00:00Z",
        },
        headers=ops_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ASSIGNED"  # extra fields silently ignored, not honored
    assert body["assigned_at"] != "2000-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Inventory invariants at each warehouse step (20-21)
# ---------------------------------------------------------------------------


def test_20_no_inventory_change_through_picking_packing_ready_assigned_out_for_delivery(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T20")
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty="4")
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T20")

    def assert_unchanged(expected_status: str) -> None:
        db_session.expire_all()
        refreshed = db_session.get(InventoryLot, lot.id)
        assert refreshed.quantity == original_quantity, expected_status
        assert refreshed.reserved_quantity == Decimal("4.000"), expected_status

    for target in ("PICKING", "PACKED", "READY_FOR_DELIVERY"):
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": target}, headers=ops_headers
        )
        assert_unchanged(target)

    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T20")
    client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    assert_unchanged("ASSIGNED")

    client.post(f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=partner_headers)
    assert_unchanged("OUT_FOR_DELIVERY")

    # Only now, at DELIVERED, may inventory actually change.
    client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    db_session.expire_all()
    delivered_lot = db_session.get(InventoryLot, lot.id)
    assert delivered_lot.quantity == original_quantity - Decimal("4.000")
    assert delivered_lot.reserved_quantity == Decimal("0.000")


def test_21_no_stock_movement_until_delivered(client: TestClient, db_session: Session) -> None:
    order, fulfillment_id, ops_headers, lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T21"
    )
    db_session.expire_all()
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 0

    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T21")
    db_session.expire_all()
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 0

    client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    db_session.expire_all()
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 1


# ---------------------------------------------------------------------------
# FIFO allocation reuse at delivery - never recomputed (22-23)
# ---------------------------------------------------------------------------


def test_22_delivery_consumes_exact_multi_lot_reservation_allocation(
    client: TestClient, db_session: Session
) -> None:
    user, headers = _customer(db_session, "T22")
    product, variant = _create_product_variant(db_session, tag="T22")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    lot_a = _create_lot(
        db_session, product, variant, tag="T22A", quantity=Decimal("5.000"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    lot_b = _create_lot(
        db_session, product, variant, tag="T22B", quantity=Decimal("7.000"), created_at=datetime.now(UTC)
    )
    original_a, original_b = lot_a.quantity, lot_b.quantity

    order = _checkout(client, headers, variant, address, qty="12")  # exactly drains both lots
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    allocation = {
        i.inventory_lot_id: i.quantity
        for i in db_session.query(InventoryReservationItem).filter_by(reservation_id=reservation.id).all()
    }
    assert allocation == {lot_a.id: Decimal("5.000"), lot_b.id: Decimal("7.000")}

    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T22")
    _advance_to_ready(client, ops_headers, fulfillment_id)
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T22")

    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    assert response.status_code == 200

    db_session.expire_all()
    refreshed_a = db_session.get(InventoryLot, lot_a.id)
    refreshed_b = db_session.get(InventoryLot, lot_b.id)
    assert refreshed_a.quantity == original_a - Decimal("5.000")  # exact allocation, not recomputed
    assert refreshed_b.quantity == original_b - Decimal("7.000")
    assert refreshed_a.reserved_quantity == Decimal("0.000")
    assert refreshed_b.reserved_quantity == Decimal("0.000")

    movements = db_session.query(StockMovement).filter(
        StockMovement.inventory_lot_id.in_([lot_a.id, lot_b.id])
    ).all()
    assert len(movements) == 2  # one per lot - auditability preserved, not merged
    by_lot = {m.inventory_lot_id: m.quantity for m in movements}
    assert by_lot == {lot_a.id: Decimal("5.000"), lot_b.id: Decimal("7.000")}


def test_23_new_lot_added_after_reservation_is_never_touched_at_delivery(
    client: TestClient, db_session: Session
) -> None:
    """A lot that becomes available AFTER the reservation was made must
    never be consumed at delivery, even if it would be FIFO-preferred.
    """
    user, headers = _customer(db_session, "T23")
    product, variant = _create_product_variant(db_session, tag="T23")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    lot = _create_lot(db_session, product, variant, tag="T23", quantity=Decimal("5.000"))
    order = _checkout(client, headers, variant, address, qty="5")

    # A brand-new, older-dated lot appears after the reservation was made -
    # FIFO would prefer it if ever recomputed, but it must be ignored.
    newer_but_older_dated_lot = _create_lot(
        db_session, product, variant, tag="T23LATE", quantity=Decimal("50.000"),
        created_at=datetime.now(UTC) - timedelta(days=30),
    )

    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T23")
    _advance_to_ready(client, ops_headers, fulfillment_id)
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T23")
    client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)

    db_session.expire_all()
    assert db_session.get(InventoryLot, lot.id).quantity == Decimal("0.000")
    assert db_session.get(InventoryLot, newer_but_older_dated_lot.id).quantity == Decimal("50.000")
    assert db_session.query(StockMovement).filter_by(
        inventory_lot_id=newer_but_older_dated_lot.id
    ).count() == 0


# ---------------------------------------------------------------------------
# Rollback: no partial consumption (24)
# ---------------------------------------------------------------------------


def test_24_mid_delivery_failure_on_second_lot_rolls_back_the_first_too(
    client: TestClient, db_session: Session
) -> None:
    """Corrupts the second (higher-id, processed-later) lot's
    reserved_quantity below its allocation so the delivery transaction
    fails partway through. The first lot must show NO consumption -
    everything rolls back together, never a partial commit.
    """
    user, headers = _customer(db_session, "T24")
    product, variant = _create_product_variant(db_session, tag="T24")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    lot_a = _create_lot(
        db_session, product, variant, tag="T24A", quantity=Decimal("3.000"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    lot_b = _create_lot(
        db_session, product, variant, tag="T24B", quantity=Decimal("3.000"), created_at=datetime.now(UTC)
    )
    assert lot_a.id < lot_b.id  # processed in this order at delivery
    original_a, original_b = lot_a.quantity, lot_b.quantity

    order = _checkout(client, headers, variant, address, qty="6")
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T24")
    _advance_to_ready(client, ops_headers, fulfillment_id)
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T24")

    # Corrupt lot_b's bookkeeping directly (simulating an inconsistency
    # that must never be trusted blindly) so its consumption fails.
    db_session.query(InventoryLot).filter_by(id=lot_b.id).update({"reserved_quantity": Decimal("1.000")})
    db_session.commit()

    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.get(InventoryLot, lot_a.id).quantity == original_a  # NOT consumed either
    assert db_session.get(InventoryLot, lot_b.id).quantity == original_b
    assert db_session.query(StockMovement).filter(
        StockMovement.inventory_lot_id.in_([lot_a.id, lot_b.id])
    ).count() == 0
    assert db_session.get(Fulfillment, fulfillment_id).status == "OUT_FOR_DELIVERY"  # not DELIVERED
    assert db_session.get(Order, order["id"]).status == "CONFIRMED"  # not COMPLETED


# ---------------------------------------------------------------------------
# Security / ownership (25-31)
# ---------------------------------------------------------------------------


def test_25_customer_cannot_see_another_customers_fulfillment(
    client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a, variant_a, address_a, _lot_a = _ready_customer(db_session, "T25A")
    order = _checkout(client, headers_a, variant_a, address_a)
    client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers_a
    )

    _user_b, headers_b = _customer(db_session, "T25B")
    response = client.get(f"/api/v1/orders/{order['id']}/fulfillment", headers=headers_b)
    assert response.status_code == 404


def test_26_customer_forbidden_from_all_fulfillment_mutations(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T26"
    )
    customer_user_id = db_session.query(Order).filter_by(id=order["id"]).one().user_id
    customer_headers = _auth_headers(db_session, db_session.get(User, customer_user_id))

    assert client.get(f"/api/v1/fulfillments/{fulfillment_id}", headers=customer_headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": "PICKING"}, headers=customer_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=customer_headers
        ).status_code
        == 403
    )
    assert (
        client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=customer_headers).status_code
        == 403
    )


def test_27_delivery_partner_a_cannot_touch_partner_bs_fulfillment(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T27"
    )
    _partner_a, headers_a = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T27A")
    _partner_b, headers_b = _staff(db_session, DELIVERY_PARTNER, "T27B")

    assert client.get(f"/api/v1/fulfillments/{fulfillment_id}", headers=headers_b).status_code == 404
    assert (
        client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=headers_b).status_code == 403
    )

    # The actually-assigned partner still succeeds.
    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=headers_a)
    assert response.status_code == 200


def test_28_hub_staff_cannot_perform_delivery_partner_actions(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T28"
    )
    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T28")
    client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )

    assert (
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=ops_headers
        ).status_code
        == 403
    )


def test_29_delivery_partner_cannot_perform_warehouse_actions(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T29")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T29")

    assert (
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": "PICKING"}, headers=partner_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/assign",
            json={"delivery_partner_user_id": _partner.id}, headers=partner_headers,
        ).status_code
        == 403
    )


def test_30_admin_override_can_deliver_unassigned_fulfillment(
    client: TestClient, db_session: Session
) -> None:
    """ADMIN is the one deliberate ownership override, per
    FulfillmentService._assert_can_act_as_delivery_partner."""
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T30"
    )
    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T30")
    client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    client.post(f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=partner_headers)

    admin_user, admin_headers = _staff(db_session, ADMIN, "T30")
    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "DELIVERED"


def test_31_unauthenticated_gets_401(client: TestClient, db_session: Session) -> None:
    response = client.get("/api/v1/fulfillments")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List scoping (32)
# ---------------------------------------------------------------------------


def test_32_delivery_partner_list_is_scoped_to_own_assignments(
    client: TestClient, db_session: Session
) -> None:
    order_a, fulfillment_a, ops_headers, _lot_a, _oq_a = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T32A"
    )
    order_b, fulfillment_b, _ops_b, _lot_b, _oq_b = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T32B"
    )
    partner, partner_headers = _staff(db_session, DELIVERY_PARTNER, "T32")
    client.post(
        f"/api/v1/fulfillments/{fulfillment_a}/assign",
        json={"delivery_partner_user_id": partner.id}, headers=ops_headers,
    )
    # fulfillment_b is left unassigned.

    response = client.get("/api/v1/fulfillments", headers=partner_headers)
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {fulfillment_a}  # never sees fulfillment_b, unassigned to them

    # A client-supplied delivery_partner_user_id filter is ignored for a
    # non-privileged caller - they can never enumerate another partner's load.
    other_partner, _ = _staff(db_session, DELIVERY_PARTNER, "T32OTHER")
    scoped = client.get(
        "/api/v1/fulfillments",
        params={"delivery_partner_user_id": other_partner.id}, headers=partner_headers,
    )
    assert {item["id"] for item in scoped.json()["items"]} == {fulfillment_a}

    ops_view = client.get("/api/v1/fulfillments", headers=ops_headers)
    ops_ids = {item["id"] for item in ops_view.json()["items"]}
    assert {fulfillment_a, fulfillment_b}.issubset(ops_ids)  # staff sees everything


# ---------------------------------------------------------------------------
# COD / UPI fulfillment eligibility (33-34)
# ---------------------------------------------------------------------------


def test_33_cod_can_be_delivered_while_payment_still_pending(
    client: TestClient, db_session: Session
) -> None:
    from app.models.payment import Payment

    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="T33"
    )
    payment = db_session.query(Payment).filter_by(order_id=order["id"]).one()
    assert payment.status == "PENDING"  # COD payment collected later, never required PAID

    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T33")
    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "DELIVERED"

    db_session.expire_all()
    assert db_session.get(Order, order["id"]).status == "COMPLETED"
    # Payment is untouched by delivery - COD collection/reconciliation is
    # explicitly out of scope for both Phase 14 and Phase 16.
    assert db_session.get(Payment, payment.id).status == "PENDING"


def test_34_upi_order_completes_normally_after_paid_confirmation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T34")
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty="2")

    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id="go-t34", gateway_transaction_id="gt-t34",
            status=TransactionStatus.SUCCESS,
        )
    )
    paid = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "UPI"}, headers=headers
    )
    assert paid.json()["status"] == "PAID"

    db_session.expire_all()
    fulfillment_id = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one().id
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "T34")
    _advance_to_ready(client, ops_headers, fulfillment_id)
    _partner, partner_headers = _assign_and_dispatch(client, db_session, ops_headers, fulfillment_id, "T34")

    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)
    assert response.status_code == 200

    db_session.expire_all()
    assert db_session.get(Order, order["id"]).status == "COMPLETED"
    assert db_session.get(InventoryLot, lot.id).quantity == original_quantity - Decimal("2.000")


# ---------------------------------------------------------------------------
# Concurrency - real threads, real PostgreSQL row locks (35-39)
# ---------------------------------------------------------------------------


def test_concurrency_35_two_ops_racing_assignment_exactly_one_wins(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, _lot, _oq = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="C35"
    )
    partner_a, _ = _staff(db_session, DELIVERY_PARTNER, "C35A")
    partner_b, _ = _staff(db_session, DELIVERY_PARTNER, "C35B")

    def assign(partner_id: int):
        return client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/assign",
            json={"delivery_partner_user_id": partner_id}, headers=ops_headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(assign, partner_a.id)
        f2 = pool.submit(assign, partner_b.id)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409]  # exactly one assignment wins

    db_session.expire_all()
    fulfillment = db_session.get(Fulfillment, fulfillment_id)
    assert fulfillment.status == "ASSIGNED"
    assert fulfillment.delivery_partner_user_id in (partner_a.id, partner_b.id)  # never null, never mixed


def test_concurrency_36_two_deliver_requests_from_same_partner_no_double_consumption(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, lot, original_quantity = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="C36", qty="4"
    )
    _partner, partner_headers = _assign_and_dispatch(
        client, db_session, ops_headers, fulfillment_id, "C36"
    )

    def deliver():
        return client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(deliver)
        f2 = pool.submit(deliver)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200 and r2.status_code == 200  # idempotent - neither errors

    db_session.expire_all()
    assert db_session.get(InventoryLot, lot.id).quantity == original_quantity - Decimal("4.000")
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 1
    assert db_session.get(Order, order["id"]).status == "COMPLETED"


def test_concurrency_37_racing_valid_and_invalid_status_transition_no_corrupt_state(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "C37")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    _ops_user, ops_headers = _staff(db_session, HUB_STAFF, "C37")
    _admin_user, admin_headers = _staff(db_session, ADMIN, "C37")

    def to_picking():
        return client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status", json={"status": "PICKING"}, headers=ops_headers
        )

    def to_delivered_always_illegal():
        # DELIVERED is unreachable from PENDING/PICKING regardless of
        # ordering (unlike a PACKED race, which could legally "chase"
        # PICKING if the two happen to serialize that way) - this makes
        # the race outcome deterministic to assert on. Uses ADMIN (which
        # bypasses delivery-partner ownership) so this isolates the pure
        # state-machine rejection rather than an RBAC one.
        return client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=admin_headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(to_picking)
        f2 = pool.submit(to_delivered_always_illegal)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200  # PICKING always legal from PENDING
    assert r2.status_code == 409  # DELIVERED always illegal from PENDING/PICKING

    db_session.expire_all()
    assert db_session.get(Fulfillment, fulfillment_id).status == "PICKING"


def test_concurrency_38_delivery_races_a_concurrent_reassignment_attempt_safely(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, lot, original_quantity = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="C38"
    )
    _partner, partner_headers = _assign_and_dispatch(
        client, db_session, ops_headers, fulfillment_id, "C38"
    )
    other_partner, _ = _staff(db_session, DELIVERY_PARTNER, "C38OTHER")

    def deliver():
        return client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)

    def reassign():
        return client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/assign",
            json={"delivery_partner_user_id": other_partner.id}, headers=ops_headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(deliver)
        f2 = pool.submit(reassign)
        deliver_resp, reassign_resp = f1.result(), f2.result()

    assert deliver_resp.status_code == 200  # always legal from OUT_FOR_DELIVERY
    assert reassign_resp.status_code == 409  # never legal once past READY_FOR_DELIVERY

    db_session.expire_all()
    assert db_session.get(InventoryLot, lot.id).quantity == original_quantity - Decimal("3.000")
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 1


def test_concurrency_39_committed_reservation_survives_concurrent_expire_attempt(
    client: TestClient, db_session: Session
) -> None:
    order, fulfillment_id, ops_headers, lot, original_quantity = _full_cod_ready_for_delivery(
        db_session=db_session, client=client, tag="C39"
    )
    _partner, partner_headers = _assign_and_dispatch(
        client, db_session, ops_headers, fulfillment_id, "C39"
    )
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "COMMITTED"

    def deliver():
        return client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=partner_headers)

    def try_expire():
        return client.post(
            f"/api/v1/inventory/reservations/{reservation.id}/expire", headers=ops_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(deliver)
        f2 = pool.submit(try_expire)
        deliver_resp, expire_resp = f1.result(), f2.result()

    assert deliver_resp.status_code == 200
    assert expire_resp.status_code == 200  # always a safe no-op on a COMMITTED reservation

    db_session.expire_all()
    refreshed_reservation = db_session.get(InventoryReservation, reservation.id)
    assert refreshed_reservation.status == "COMMITTED"  # never resurrected to/through EXPIRED
    assert db_session.get(InventoryLot, lot.id).quantity == original_quantity - Decimal("3.000")
    assert db_session.get(Order, order["id"]).status == "COMPLETED"
