"""Phase 15 focused validation: inventory reservation, order expiry, and
fulfillment foundation.

Fast-development-mode focused validation against real PostgreSQL.
Mutation tests re-read the database afterward, never trusting an HTTP
response alone. Concurrency tests use real threads against real Postgres
row locks (ThreadPoolExecutor), never mocked - consistent with every
concurrency test in Phase 11/13/14.
"""

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
from app.models.auth_session import AuthSession
from app.models.batch import Batch
from app.models.category import Category
from app.models.fulfillment import Fulfillment
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.models.payment import Payment
from app.models.price import Price
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.role import Role
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.user_role import UserRole
from app.services.payment_gateway import (
    GatewayInitiateResult,
    GatewayStatusResult,
    PNBGateway,
)
from app.services.payment_state import TransactionStatus

WEBHOOK_SECRET = "test-webhook-secret-for-phase-15-min-32-chars"


class FakePNBGateway(PNBGateway):
    def __init__(self, *, webhook_secret: str = WEBHOOK_SECRET) -> None:
        super().__init__(
            merchant_id="fake-merchant", webhook_secret=webhook_secret,
            base_url="https://fake-pnb.invalid",
        )
        self._next_initiate = None
        self._next_query = None
        self._counter = 0

    def queue_initiate(self, result_or_exc) -> None:
        self._next_initiate = result_or_exc

    def queue_query(self, result_or_exc) -> None:
        self._next_query = result_or_exc

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

    def query_status(self, **kwargs) -> GatewayStatusResult:
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
        phone=f"+9196{abs(hash(email)) % 100000000:08d}",
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


def _staff(db_session: Session, role: str, tag: str) -> dict[str, str]:
    user = _create_user_with_role(db_session, role, f"{role.lower()}_{tag.lower()}@example.com")
    return _auth_headers(db_session, user)


def _create_product_variant(
    db_session: Session, *, tag: str
) -> tuple[Product, ProductVariant]:
    category = Category(name=f"Cat-{tag}", slug=f"cat-{tag.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod-{tag}", slug=f"prod-{tag.lower()}", status="ACTIVE"
    )
    db_session.add(product)
    db_session.commit()
    variant = ProductVariant(
        product_id=product.id, name="1 KG", sku=f"SKU-{tag}", unit="KG",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return product, variant


def _create_price(
    db_session: Session, variant: ProductVariant, *, price: Decimal = Decimal("50.00")
) -> Price:
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
    wholesaler = _create_user_with_role(db_session, WHOLESALER, f"ws_{tag.lower()}@example.com")
    batch = Batch(
        wholesaler_user_id=wholesaler.id, product_id=product.id, batch_code=f"BATCH-{tag}",
        harvest_date=date(2026, 1, 1), quantity=quantity, unit="KG", status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    location = InventoryLocation(
        name=f"Hub-{tag}", code=f"HUB-{tag}", type="WAREHOUSE",
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


def _create_address(db_session: Session, user: User):
    from app.models.address import Address

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
    """Customer + priced/stocked variant + address, ready to check out."""
    user, headers = _customer(db_session, tag)
    product, variant = _create_product_variant(db_session, tag=tag)
    _create_price(db_session, variant, price=price)
    lot = _create_lot(db_session, product, variant, tag=tag, quantity=stock)
    address = _create_address(db_session, user)
    return user, headers, variant, address, lot


def _checkout(client: TestClient, headers: dict, variant: ProductVariant, address, qty: str = "1"):
    client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": qty}, headers=headers
    )
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Reservation creation at checkout (1-8)
# ---------------------------------------------------------------------------


def test_1_checkout_creates_active_reservation(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T1")
    original_quantity = lot.quantity  # snapshot: `lot` is refreshed in place below

    order = _checkout(client, headers, variant, address, qty="3")

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "ACTIVE"
    assert reservation.expires_at > datetime.now(UTC)

    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("3.000")
    assert refreshed_lot.quantity == original_quantity  # physical stock untouched


def test_2_reservation_item_allocation_matches_order_item(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T2")
    order = _checkout(client, headers, variant, address, qty="4")

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    items = (
        db_session.query(InventoryReservationItem)
        .filter_by(reservation_id=reservation.id)
        .all()
    )
    assert len(items) == 1
    assert items[0].inventory_lot_id == lot.id
    assert items[0].quantity == Decimal("4.000")
    assert items[0].order_item_id == order["items"][0]["id"]


def test_3_insufficient_stock_rejects_checkout_and_rolls_back_everything(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T3", stock=Decimal("2.000"))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "5"}, headers=headers)

    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.query(Order).count() == 0
    assert db_session.query(InventoryReservation).count() == 0
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")  # nothing partially applied


def test_4_fifo_allocation_uses_oldest_lot_first(client: TestClient, db_session: Session) -> None:
    user, headers = _customer(db_session, "T4")
    product, variant = _create_product_variant(db_session, tag="T4")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    old_lot = _create_lot(
        db_session, product, variant, tag="T4OLD", quantity=Decimal("3.000"),
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    new_lot = _create_lot(
        db_session, product, variant, tag="T4NEW", quantity=Decimal("10.000"),
        created_at=datetime.now(UTC),
    )

    order = _checkout(client, headers, variant, address, qty="5")

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    items = {
        i.inventory_lot_id: i.quantity
        for i in db_session.query(InventoryReservationItem).filter_by(reservation_id=reservation.id).all()
    }
    assert items[old_lot.id] == Decimal("3.000")  # oldest fully drained first
    assert items[new_lot.id] == Decimal("2.000")  # remainder spills to the newer lot


def test_5_fifo_ties_broken_by_id_when_created_at_equal(
    client: TestClient, db_session: Session
) -> None:
    user, headers = _customer(db_session, "T5")
    product, variant = _create_product_variant(db_session, tag="T5")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    same_time = datetime.now(UTC)
    lot_a = _create_lot(
        db_session, product, variant, tag="T5A", quantity=Decimal("2.000"), created_at=same_time
    )
    lot_b = _create_lot(
        db_session, product, variant, tag="T5B", quantity=Decimal("10.000"), created_at=same_time
    )
    assert lot_a.id < lot_b.id

    order = _checkout(client, headers, variant, address, qty="3")

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    items = {
        i.inventory_lot_id: i.quantity
        for i in db_session.query(InventoryReservationItem).filter_by(reservation_id=reservation.id).all()
    }
    assert items[lot_a.id] == Decimal("2.000")
    assert items.get(lot_b.id, Decimal("0")) == Decimal("1.000")


def test_6_depleted_and_inactive_lots_skipped_by_fifo(
    client: TestClient, db_session: Session
) -> None:
    user, headers = _customer(db_session, "T6")
    product, variant = _create_product_variant(db_session, tag="T6")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    depleted = _create_lot(
        db_session, product, variant, tag="T6DEP", quantity=Decimal("5.000"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    depleted.status = "DEPLETED"
    depleted.quantity = Decimal("0.000")
    db_session.commit()

    usable = _create_lot(
        db_session, product, variant, tag="T6OK", quantity=Decimal("5.000"), created_at=datetime.now(UTC)
    )

    order = _checkout(client, headers, variant, address, qty="2")

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    items = db_session.query(InventoryReservationItem).filter_by(reservation_id=reservation.id).all()
    assert len(items) == 1
    assert items[0].inventory_lot_id == usable.id


def test_7_multi_lot_reservation_spans_two_lots_for_one_order_item(
    client: TestClient, db_session: Session
) -> None:
    user, headers = _customer(db_session, "T7")
    product, variant = _create_product_variant(db_session, tag="T7")
    _create_price(db_session, variant, price=Decimal("10.00"))
    address = _create_address(db_session, user)

    lot1 = _create_lot(
        db_session, product, variant, tag="T7A", quantity=Decimal("2.000"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    lot2 = _create_lot(
        db_session, product, variant, tag="T7B", quantity=Decimal("2.000"), created_at=datetime.now(UTC)
    )

    order = _checkout(client, headers, variant, address, qty="4")

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    items = db_session.query(InventoryReservationItem).filter_by(reservation_id=reservation.id).all()
    assert len(items) == 2
    assert {i.inventory_lot_id for i in items} == {lot1.id, lot2.id}
    assert sum((i.quantity for i in items), Decimal("0")) == Decimal("4.000")


def test_8_customer_can_read_own_reservation(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T8")
    order = _checkout(client, headers, variant, address)

    response = client.get(f"/api/v1/orders/{order['id']}/reservation", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["order_id"] == order["id"]
    assert "items" not in body  # customer-facing shape never leaks lot allocation


def test_9_customer_cannot_read_another_users_reservation(
    client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a, variant_a, address_a, _lot_a = _ready_customer(db_session, "T9A")
    order = _checkout(client, headers_a, variant_a, address_a)

    _user_b, headers_b = _customer(db_session, "T9B")
    response = client.get(f"/api/v1/orders/{order['id']}/reservation", headers=headers_b)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# COD (10-11)
# ---------------------------------------------------------------------------


def test_10_cod_commits_reservation_and_creates_fulfillment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T10")
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty="2")

    response = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 201

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "COMMITTED"
    refreshed_order = db_session.get(Order, order["id"])
    assert refreshed_order.status == "CONFIRMED"
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order["id"]).one()
    assert fulfillment.status == "PENDING"
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("2.000")
    assert refreshed_lot.quantity == original_quantity  # still not physically consumed


def test_11_cod_after_reservation_expired_is_rejected_and_leaves_no_payment(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T11")
    order = _checkout(client, headers, variant, address)

    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.query(Payment).filter_by(order_id=order["id"]).count() == 0
    refreshed_order = db_session.get(Order, order["id"])
    assert refreshed_order.status == "PENDING"


# ---------------------------------------------------------------------------
# UPI (12-14)
# ---------------------------------------------------------------------------


def test_12_upi_synchronous_success_commits_reservation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T12")
    order = _checkout(client, headers, variant, address, qty="1")

    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id="go-t12", gateway_transaction_id="gt-t12",
            status=TransactionStatus.SUCCESS,
        )
    )
    response = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "UPI"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PAID"

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "COMMITTED"
    assert db_session.get(Order, order["id"]).status == "CONFIRMED"
    assert db_session.query(Fulfillment).filter_by(order_id=order["id"]).count() == 1


def test_13_upi_failure_keeps_reservation_active_and_retry_still_succeeds(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    """Documented Phase 15 deviation: definitive UPI failure does NOT
    release the reservation (see app/services/inventory_reservation.py) -
    it stays ACTIVE so the existing, unmodified retry flow can still
    commit it on a later successful attempt.
    """
    from app.services.payment_gateway import GatewayRejectedError

    _user, headers, variant, address, lot = _ready_customer(db_session, "T13")
    order = _checkout(client, headers, variant, address, qty="1")

    # Matches the established Phase 14 test pattern (test_phase_14_payments.py):
    # create_payment re-raises GatewayRejectedError after marking the
    # payment/transaction FAILED, which surfaces as an unhandled 500 - the
    # payment id is read back from the DB, not the HTTP response.
    gateway.queue_initiate(GatewayRejectedError("card declined"))
    client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "UPI"}, headers=headers
    )

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "ACTIVE"
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("1.000")  # still held
    payment = db_session.query(Payment).filter_by(order_id=order["id"]).one()
    assert payment.status == "FAILED"

    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id="go-t13-retry", gateway_transaction_id="gt-t13-retry",
            status=TransactionStatus.SUCCESS,
        )
    )
    retry = client.post(f"/api/v1/payments/{payment.id}/retry", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["status"] == "PAID"

    db_session.expire_all()
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert reservation.status == "COMMITTED"
    assert db_session.get(Order, order["id"]).status == "CONFIRMED"


def test_14_late_payment_after_expiry_does_not_resurrect_reservation(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T14")
    order = _checkout(client, headers, variant, address, qty="1")

    gateway.queue_initiate(
        GatewayInitiateResult(
            gateway_order_id="go-t14", gateway_transaction_id="gt-t14",
            status=TransactionStatus.PROCESSING,
        )
    )
    created = client.post(
        "/api/v1/payments", json={"order_id": order["id"], "payment_method": "UPI"}, headers=headers
    ).json()
    assert created["status"] == "PROCESSING"

    # Simulate the 30-minute window having elapsed before the gateway's
    # (late) success confirmation arrives.
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    gateway.queue_query(
        GatewayStatusResult(
            gateway_order_id="go-t14", gateway_transaction_id="gt-t14",
            status=TransactionStatus.SUCCESS,
        )
    )
    verify = client.post(f"/api/v1/payments/{created['id']}/verify", headers=headers)
    assert verify.status_code == 200
    assert verify.json()["status"] == "PAID"  # the money genuinely arrived

    db_session.expire_all()
    refreshed_order = db_session.get(Order, order["id"])
    # NOT auto-confirmed to CONFIRMED - instead the order itself is moved
    # to the explicit terminal EXPIRED status (its reservation's own
    # expiry, detected during this verify call, carries the order with it).
    assert refreshed_order.status == "EXPIRED"
    refreshed_reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    assert refreshed_reservation.status == "EXPIRED"  # not resurrected to COMMITTED
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")  # inventory was released


# ---------------------------------------------------------------------------
# Expiry (15-17)
# ---------------------------------------------------------------------------


def test_15_lazy_expiry_on_customer_get_releases_inventory(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T15")
    order = _checkout(client, headers, variant, address, qty="2")

    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()
    reservation.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    response = client.get(f"/api/v1/orders/{order['id']}/reservation", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "EXPIRED"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")
    assert db_session.get(Order, order["id"]).status == "EXPIRED"


def test_16_ops_can_manually_expire_and_it_is_idempotent(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T16")
    order = _checkout(client, headers, variant, address, qty="1")
    ops_headers = _staff(db_session, OPERATIONS, "T16")

    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()

    first = client.post(
        f"/api/v1/inventory/reservations/{reservation.id}/expire", headers=ops_headers
    )
    assert first.status_code == 200
    assert first.json()["status"] == "EXPIRED"

    second = client.post(
        f"/api/v1/inventory/reservations/{reservation.id}/expire", headers=ops_headers
    )
    assert second.status_code == 200
    assert second.json()["status"] == "EXPIRED"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")  # released exactly once
    assert db_session.get(Order, order["id"]).status == "EXPIRED"


def test_17_customer_cannot_access_ops_reservation_endpoints(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T17")
    order = _checkout(client, headers, variant, address)
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()

    assert client.get("/api/v1/inventory/reservations", headers=headers).status_code == 403
    assert (
        client.get(f"/api/v1/inventory/reservations/{reservation.id}", headers=headers).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/inventory/reservations/{reservation.id}/expire", headers=headers
        ).status_code
        == 403
    )


def test_ops_detail_view_exposes_lot_allocation(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T17D")
    order = _checkout(client, headers, variant, address, qty="1")
    ops_headers = _staff(db_session, ADMIN, "T17D")
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()

    response = client.get(
        f"/api/v1/inventory/reservations/{reservation.id}", headers=ops_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["inventory_lot_id"] == lot.id


# ---------------------------------------------------------------------------
# Fulfillment (18-22)
# ---------------------------------------------------------------------------


def _confirm_cod_and_get_fulfillment_id(
    client: TestClient, db_session: Session, headers: dict, order_id: int
) -> int:
    response = client.post(
        "/api/v1/payments", json={"order_id": order_id, "payment_method": "COD"}, headers=headers
    )
    assert response.status_code == 201
    db_session.expire_all()
    fulfillment = db_session.query(Fulfillment).filter_by(order_id=order_id).one()
    return fulfillment.id


def _advance_to_out_for_delivery(
    client: TestClient, db_session: Session, ops_headers: dict, fulfillment_id: int, tag: str
) -> dict[str, str]:
    """Phase 16 extended the chain with a mandatory ASSIGNED step and
    delivery-partner ownership enforcement - advances a fulfillment all
    the way to OUT_FOR_DELIVERY via the correctly assigned partner, and
    returns that partner's auth headers for the caller's subsequent
    /deliver call.
    """
    for target in ("PICKING", "PACKED", "READY_FOR_DELIVERY"):
        response = client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": target}, headers=ops_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target

    partner = _create_user_with_role(
        db_session, DELIVERY_PARTNER, f"partner_{tag.lower()}@example.com"
    )
    partner_headers = _auth_headers(db_session, partner)

    assign_response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/assign",
        json={"delivery_partner_user_id": partner.id},
        headers=ops_headers,
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json()["status"] == "ASSIGNED"
    assert assign_response.json()["delivery_partner_user_id"] == partner.id

    out_response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/out-for-delivery", headers=partner_headers
    )
    assert out_response.status_code == 200, out_response.text
    assert out_response.json()["status"] == "OUT_FOR_DELIVERY"

    return partner_headers


def test_18_full_fulfillment_lifecycle_consumes_physical_inventory(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T18")
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty="3")
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    ops_headers = _staff(db_session, HUB_STAFF, "T18")

    deliver_headers = _advance_to_out_for_delivery(
        client, db_session, ops_headers, fulfillment_id, "T18"
    )
    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=deliver_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "DELIVERED"
    assert response.json()["delivered_at"] is not None

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == original_quantity - Decimal("3.000")  # physically consumed
    assert refreshed_lot.reserved_quantity == Decimal("0.000")
    assert db_session.get(Order, order["id"]).status == "COMPLETED"

    movements = db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).all()
    assert len(movements) == 1
    assert movements[0].movement_type == "DISPATCH"
    assert movements[0].quantity == Decimal("3.000")


def test_19_cannot_deliver_before_out_for_delivery(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    """Uses ADMIN (which bypasses the Phase 16 delivery-partner ownership
    check) to isolate the pure state-machine rejection - an arbitrary
    unassigned DELIVERY_PARTNER would now fail ownership (403) before
    ever reaching this state check, which is covered separately in the
    Phase 16 test suite.
    """
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T19")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    admin_headers = _staff(db_session, ADMIN, "T19")

    response = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=admin_headers)
    assert response.status_code == 409

    db_session.expire_all()
    assert db_session.query(StockMovement).count() == 0


def test_20_duplicate_delivery_confirmation_does_not_double_consume(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "T20")
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty="2")
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    ops_headers = _staff(db_session, HUB_STAFF, "T20")
    deliver_headers = _advance_to_out_for_delivery(
        client, db_session, ops_headers, fulfillment_id, "T20"
    )

    first = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=deliver_headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=deliver_headers)
    assert second.status_code == 200
    assert second.json()["status"] == "DELIVERED"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == original_quantity - Decimal("2.000")  # consumed exactly once
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 1


def test_21_update_status_rejects_delivered_target(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T21")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    ops_headers = _staff(db_session, HUB_STAFF, "T21")

    response = client.post(
        f"/api/v1/fulfillments/{fulfillment_id}/status",
        json={"status": "DELIVERED"}, headers=ops_headers,
    )
    assert response.status_code in (409, 422)  # rejected either at schema or service level


def test_22_customer_gets_403_on_fulfillment_endpoints(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "T22")
    order = _checkout(client, headers, variant, address)
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])

    assert client.get(f"/api/v1/fulfillments/{fulfillment_id}", headers=headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/fulfillments/{fulfillment_id}/status",
            json={"status": "PICKING"}, headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=headers).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# Concurrency (A-F) - real threads, real PostgreSQL row locks
# ---------------------------------------------------------------------------


def test_concurrency_a_two_customers_racing_last_unit_exactly_one_wins(
    client: TestClient, db_session: Session
) -> None:
    user_a, headers_a = _customer(db_session, "CCA")
    user_b, headers_b = _customer(db_session, "CCB")
    product, variant = _create_product_variant(db_session, tag="CCA")
    _create_price(db_session, variant, price=Decimal("10.00"))
    lot = _create_lot(db_session, product, variant, tag="CCA", quantity=Decimal("1.000"))
    address_a = _create_address(db_session, user_a)
    address_b = _create_address(db_session, user_b)

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers_a)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers_b)

    def checkout(headers, address):
        return client.post(
            "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(checkout, headers_a, address_a)
        f2 = pool.submit(checkout, headers_b, address_b)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409]  # exactly one wins, the other is rejected cleanly

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("1.000")  # never exceeds physical quantity
    assert db_session.query(Order).count() == 1
    assert db_session.query(InventoryReservation).count() == 1


def test_concurrency_b_concurrent_multi_lot_fifo_no_oversell(
    client: TestClient, db_session: Session
) -> None:
    user_a, headers_a = _customer(db_session, "CCB1")
    user_b, headers_b = _customer(db_session, "CCB2")
    product, variant = _create_product_variant(db_session, tag="CCB")
    _create_price(db_session, variant, price=Decimal("10.00"))
    lot1 = _create_lot(
        db_session, product, variant, tag="CCB1", quantity=Decimal("1.000"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    lot2 = _create_lot(
        db_session, product, variant, tag="CCB2", quantity=Decimal("1.000"), created_at=datetime.now(UTC)
    )
    address_a = _create_address(db_session, user_a)
    address_b = _create_address(db_session, user_b)

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers_a)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers_b)

    def checkout(headers, address):
        return client.post(
            "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(checkout, headers_a, address_a)
        f2 = pool.submit(checkout, headers_b, address_b)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 201 and r2.status_code == 201  # exactly enough for both

    db_session.expire_all()
    total_reserved = (
        db_session.get(InventoryLot, lot1.id).reserved_quantity
        + db_session.get(InventoryLot, lot2.id).reserved_quantity
    )
    assert total_reserved == Decimal("2.000")  # both units allocated, none doubled/lost
    assert db_session.get(InventoryLot, lot1.id).reserved_quantity <= Decimal("1.000")
    assert db_session.get(InventoryLot, lot2.id).reserved_quantity <= Decimal("1.000")


def test_concurrency_c_concurrent_expiry_releases_exactly_once(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "CCC", stock=Decimal("5.000"))
    order = _checkout(client, headers, variant, address, qty="4")
    ops_headers = _staff(db_session, OPERATIONS, "CCC")
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()

    def expire():
        return client.post(
            f"/api/v1/inventory/reservations/{reservation.id}/expire", headers=ops_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(expire)
        f2 = pool.submit(expire)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200 and r2.status_code == 200  # idempotent - neither errors
    assert r1.json()["status"] == "EXPIRED" and r2.json()["status"] == "EXPIRED"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("0.000")  # released exactly once, never negative


def test_concurrency_d_payment_success_vs_expiry_exactly_one_winner(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, _lot = _ready_customer(db_session, "CCD")
    order = _checkout(client, headers, variant, address, qty="1")
    ops_headers = _staff(db_session, OPERATIONS, "CCD")
    reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()

    def confirm_cod():
        return client.post(
            "/api/v1/payments", json={"order_id": order["id"], "payment_method": "COD"}, headers=headers
        )

    def expire():
        return client.post(
            f"/api/v1/inventory/reservations/{reservation.id}/expire", headers=ops_headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(confirm_cod)
        f2 = pool.submit(expire)
        cod_resp, expire_resp = f1.result(), f2.result()

    assert expire_resp.status_code == 200  # the expire endpoint is always a safe no-op or a real expiry

    db_session.expire_all()
    refreshed_order = db_session.get(Order, order["id"])
    refreshed_reservation = db_session.query(InventoryReservation).filter_by(order_id=order["id"]).one()

    committed_won = (
        cod_resp.status_code == 201
        and refreshed_reservation.status == "COMMITTED"
        and refreshed_order.status == "CONFIRMED"
    )
    expiry_won = (
        cod_resp.status_code == 409
        and refreshed_reservation.status == "EXPIRED"
        and refreshed_order.status == "EXPIRED"  # order carried to EXPIRED with its reservation
    )
    assert committed_won or expiry_won  # exactly one outcome, never a mixed/corrupted state
    assert not (committed_won and expiry_won)


def test_concurrency_e_concurrent_delivery_confirmation_no_double_consumption(
    client: TestClient, db_session: Session, gateway: FakePNBGateway
) -> None:
    _user, headers, variant, address, lot = _ready_customer(db_session, "CCE", stock=Decimal("10.000"))
    original_quantity = lot.quantity
    order = _checkout(client, headers, variant, address, qty="3")
    fulfillment_id = _confirm_cod_and_get_fulfillment_id(client, db_session, headers, order["id"])
    ops_headers = _staff(db_session, HUB_STAFF, "CCE")
    deliver_headers = _advance_to_out_for_delivery(
        client, db_session, ops_headers, fulfillment_id, "CCE"
    )

    def deliver():
        return client.post(f"/api/v1/fulfillments/{fulfillment_id}/deliver", headers=deliver_headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(deliver)
        f2 = pool.submit(deliver)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200 and r2.status_code == 200  # idempotent - neither errors

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == original_quantity - Decimal("3.000")  # consumed exactly once
    assert db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 1


def test_concurrency_f_concurrent_checkout_across_customers_never_oversells(
    client: TestClient, db_session: Session
) -> None:
    user_a, headers_a = _customer(db_session, "CCF1")
    user_b, headers_b = _customer(db_session, "CCF2")
    product, variant = _create_product_variant(db_session, tag="CCF")
    _create_price(db_session, variant, price=Decimal("10.00"))
    lot = _create_lot(db_session, product, variant, tag="CCF", quantity=Decimal("3.000"))
    address_a = _create_address(db_session, user_a)
    address_b = _create_address(db_session, user_b)

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers_a)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers_b)

    def checkout(headers, address):
        return client.post(
            "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(checkout, headers_a, address_a)
        f2 = pool.submit(checkout, headers_b, address_b)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409]  # combined demand (4) exceeds supply (3) - only one can fit

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.reserved_quantity == Decimal("2.000")  # never exceeds physical quantity (3)
    assert refreshed_lot.reserved_quantity <= refreshed_lot.quantity
