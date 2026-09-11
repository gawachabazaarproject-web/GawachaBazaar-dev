"""Phase 13 focused validation: cart, checkout, and orders.

Fast-development-mode focused validation only, against real PostgreSQL.
Mutation tests re-read the database afterward (not just the HTTP response)
per established project testing principle - a 500/409 response alone is
never treated as sufficient proof of rollback; the DB state is verified.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, CUSTOMER, WHOLESALER
from app.core.security import create_access_token, hash_password
from app.models.address import Address
from app.models.auth_session import AuthSession
from app.models.batch import Batch
from app.models.cart import Cart
from app.models.category import Category
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.price import Price
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

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
        name="Test User",
        email=email,
        phone=f"+9195{abs(hash(email)) % 100000000:08d}",
        password_hash=hash_password("SecurePass123"),
        status="ACTIVE",
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
        user_id=user.id,
        refresh_token_hash=f"dummy-hash-{user.id}-{user.email}",
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


def _create_product_variant(
    db_session: Session, *, tag: str, product_status: str = "ACTIVE", variant_status: str = "ACTIVE"
) -> tuple[Product, ProductVariant]:
    category = Category(name=f"Cat-{tag}", slug=f"cat-{tag.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod-{tag}", slug=f"prod-{tag.lower()}",
        status=product_status,
    )
    db_session.add(product)
    db_session.commit()
    variant = ProductVariant(
        product_id=product.id, name="1 KG", sku=f"SKU-{tag}", unit="KG",
        quantity=Decimal("1.000"), status=variant_status,
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return product, variant


def _create_price(
    db_session: Session, variant: ProductVariant, *, price: Decimal = Decimal("50.00"),
    currency: str = "INR", valid_from: datetime | None = None, valid_to: datetime | None = None,
    is_active: bool = True,
) -> Price:
    row = Price(
        variant_id=variant.id, price=price, currency=currency,
        valid_from=valid_from or (datetime.now(UTC) - timedelta(days=1)),
        valid_to=valid_to, is_active=is_active,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _create_address(db_session: Session, user: User, *, label: str = "Home") -> Address:
    addr = Address(
        user_id=user.id, label=label, address_line_1="221B Test Lane",
        city="Nagpur", state="Maharashtra", postal_code="440001",
    )
    db_session.add(addr)
    db_session.commit()
    db_session.refresh(addr)
    return addr


def _stock_variant(
    db_session: Session, product: Product, variant: ProductVariant, *,
    tag: str, quantity: Decimal = Decimal("1000.000"),
) -> InventoryLot:
    """Gives a variant abundant available inventory so checkout's Phase 15
    reservation step succeeds transparently - this file tests cart/checkout
    behavior, not inventory allocation, so stock is never the limiting
    factor unless a test explicitly says otherwise.
    """
    wholesaler = _create_user_with_role(
        db_session, WHOLESALER, f"ws_{tag.lower()}@example.com"
    )
    batch = Batch(
        wholesaler_user_id=wholesaler.id, product_id=product.id,
        batch_code=f"BATCH-{tag}", harvest_date=date(2026, 1, 1),
        quantity=quantity, unit="KG", status="APPROVED",
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
    db_session.add(lot)
    db_session.commit()
    db_session.refresh(lot)
    return lot


def _ready_customer(db_session: Session, tag: str, *, price: Decimal = Decimal("50.00")):
    """Customer + priced ACTIVE product/variant (with abundant inventory) +
    address, ready to shop and check out.
    """
    user, headers = _customer(db_session, tag)
    product, variant = _create_product_variant(db_session, tag=tag)
    _create_price(db_session, variant, price=price)
    _stock_variant(db_session, product, variant, tag=tag)
    address = _create_address(db_session, user)
    return user, headers, variant, address


# ---------------------------------------------------------------------------
# Cart: basic CRUD (1-11)
# ---------------------------------------------------------------------------


def test_1_get_current_cart_empty(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T1")
    response = client.get("/api/v1/cart", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] is None
    assert body["items"] == []


def test_2_create_cart(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T2")
    response = client.post("/api/v1/cart", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] is not None
    assert body["status"] == "ACTIVE"


def test_3_add_item(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T3")
    response = client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == "2.000"
    assert body["unit_price"] == "50.00"
    assert body["line_total"] == "100.00"


def test_4_add_same_variant_twice_merges_quantity(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T4")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    second = client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "3"}, headers=headers
    )
    assert second.status_code == 201
    assert second.json()["quantity"] == "5.000"

    cart = client.get("/api/v1/cart", headers=headers).json()
    assert len(cart["items"]) == 1  # merged into one row, not two


def test_5_update_quantity(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T5")
    item = client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers
    ).json()

    updated = client.patch(
        f"/api/v1/cart/items/{item['id']}", json={"quantity": "7"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == "7.000"


def test_6_remove_item(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T6")
    item = client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers
    ).json()

    deleted = client.delete(f"/api/v1/cart/items/{item['id']}", headers=headers)
    assert deleted.status_code == 204

    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"] == []


def test_7_clear_cart(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T7")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)

    cleared = client.delete("/api/v1/cart/items", headers=headers)
    assert cleared.status_code == 204

    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"] == []
    assert cart["status"] == "ACTIVE"  # cart itself remains ACTIVE, not deleted


def test_8_inactive_variant_rejected(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T8")
    _product, variant = _create_product_variant(db_session, tag="T8", variant_status="INACTIVE")
    _create_price(db_session, variant)

    response = client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers
    )
    assert response.status_code == 409


def test_9_inactive_product_rejected(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T9")
    _product, variant = _create_product_variant(db_session, tag="T9", product_status="DRAFT")
    _create_price(db_session, variant)

    response = client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers
    )
    assert response.status_code == 409


def test_10_non_customer_rejected(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_cart@example.com")
    response = client.get("/api/v1/cart", headers=_auth_headers(db_session, admin))
    assert response.status_code == 403
    assert response.json()["code"] == "AUTHORIZATION_ERROR"


def test_11_unauthenticated_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/cart")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_ERROR"


# ---------------------------------------------------------------------------
# Pricing (12-18)
# ---------------------------------------------------------------------------


def test_12_current_price_resolved_correctly(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T12", price=Decimal("42.50"))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"][0]["unit_price"] == "42.50"


def test_13_expired_price_ignored(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T13")
    _product, variant = _create_product_variant(db_session, tag="T13")
    now = datetime.now(UTC)
    _create_price(
        db_session, variant, price=Decimal("99.00"),
        valid_from=now - timedelta(days=10), valid_to=now - timedelta(days=1),
    )
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"][0]["unit_price"] is None


def test_14_future_price_ignored(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T14")
    _product, variant = _create_product_variant(db_session, tag="T14")
    now = datetime.now(UTC)
    _create_price(db_session, variant, price=Decimal("99.00"), valid_from=now + timedelta(days=10))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"][0]["unit_price"] is None


def test_15_latest_valid_from_selected(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T15")
    _product, variant = _create_product_variant(db_session, tag="T15")
    now = datetime.now(UTC)
    _create_price(db_session, variant, price=Decimal("30.00"), valid_from=now - timedelta(days=5))
    _create_price(db_session, variant, price=Decimal("35.00"), valid_from=now - timedelta(days=1))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart = client.get("/api/v1/cart", headers=headers).json()
    assert cart["items"][0]["unit_price"] == "35.00"


def test_16_id_tie_break_deterministic(client: TestClient, db_session: Session) -> None:
    _user, headers = _customer(db_session, "T16")
    _product, variant = _create_product_variant(db_session, tag="T16")
    same_time = datetime.now(UTC) - timedelta(hours=1)
    _create_price(db_session, variant, price=Decimal("10.00"), valid_from=same_time)
    newest = _create_price(db_session, variant, price=Decimal("20.00"), valid_from=same_time)
    assert newest.id > 0

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart = client.get("/api/v1/cart", headers=headers).json()
    # Same valid_from -> highest id (the later-inserted row) must win, deterministically.
    assert cart["items"][0]["unit_price"] == "20.00"


def test_17_no_valid_price_rejected_at_checkout(client: TestClient, db_session: Session) -> None:
    user, headers = _customer(db_session, "T17")
    _product, variant = _create_product_variant(db_session, tag="T17")  # no price at all
    address = _create_address(db_session, user)
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)

    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 409


def test_18_mixed_currency_rejected(client: TestClient, db_session: Session) -> None:
    user, headers = _customer(db_session, "T18")
    _p1, variant_inr = _create_product_variant(db_session, tag="T18INR")
    _create_price(db_session, variant_inr, price=Decimal("10.00"), currency="INR")
    _p2, variant_usd = _create_product_variant(db_session, tag="T18USD")
    _create_price(db_session, variant_usd, price=Decimal("10.00"), currency="USD")
    address = _create_address(db_session, user)

    client.post("/api/v1/cart/items", json={"variant_id": variant_inr.id, "quantity": "1"}, headers=headers)
    client.post("/api/v1/cart/items", json={"variant_id": variant_usd.id, "quantity": "1"}, headers=headers)

    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Address (19-21)
# ---------------------------------------------------------------------------


def test_19_checkout_with_own_address_succeeds(client: TestClient, db_session: Session) -> None:
    user, headers, variant, address = _ready_customer(db_session, "T19")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 201


def test_20_nonexistent_address_rejected(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T20")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": 999999}, headers=headers
    )
    assert response.status_code == 404


def test_21_another_users_address_rejected(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, _addr = _ready_customer(db_session, "T21")
    other_user, _other_headers = _customer(db_session, "T21OTHER")
    other_address = _create_address(db_session, other_user)

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": other_address.id}, headers=headers
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Checkout (22-30)
# ---------------------------------------------------------------------------


def test_22_successful_checkout(client: TestClient, db_session: Session) -> None:
    user, headers, variant, address = _ready_customer(db_session, "T22", price=Decimal("25.00"))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "3"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["total_amount"] == "75.00"
    assert len(body["items"]) == 1


def test_23_empty_cart_rejected(client: TestClient, db_session: Session) -> None:
    user, headers = _customer(db_session, "T23")
    address = _create_address(db_session, user)
    client.post("/api/v1/cart", headers=headers)  # create cart with no items

    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 409


def test_24_order_status_pending(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T24")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.json()["status"] == "PENDING"


def test_25_cart_status_checked_out(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T25")
    client.post(
        "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers
    )
    cart_id = client.get("/api/v1/cart", headers=headers).json()["id"]
    client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)

    db_session.expire_all()
    refreshed_cart = db_session.get(Cart, cart_id)
    assert refreshed_cart.status == "CHECKED_OUT"


def test_26_correct_order_total(client: TestClient, db_session: Session) -> None:
    user, headers = _customer(db_session, "T26")
    address = _create_address(db_session, user)
    p1, v1 = _create_product_variant(db_session, tag="T26A")
    _create_price(db_session, v1, price=Decimal("10.55"))
    _stock_variant(db_session, p1, v1, tag="T26A")
    p2, v2 = _create_product_variant(db_session, tag="T26B")
    _create_price(db_session, v2, price=Decimal("3.20"))
    _stock_variant(db_session, p2, v2, tag="T26B")

    client.post("/api/v1/cart/items", json={"variant_id": v1.id, "quantity": "2"}, headers=headers)
    client.post("/api/v1/cart/items", json={"variant_id": v2.id, "quantity": "5"}, headers=headers)

    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    body = response.json()
    # 2*10.55 + 5*3.20 = 21.10 + 16.00 = 37.10
    assert body["total_amount"] == "37.10"

    db_session.expire_all()
    order = db_session.query(Order).filter_by(id=body["id"]).first()
    items_sum = sum(
        (i.total_price for i in db_session.query(OrderItem).filter_by(order_id=order.id).all()),
        Decimal("0"),
    )
    assert order.total_amount == items_sum


def test_27_order_item_snapshots_correct(client: TestClient, db_session: Session) -> None:
    user, headers, variant, address = _ready_customer(db_session, "T27", price=Decimal("60.00"))
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    item = response.json()["items"][0]
    assert item["sku"] == variant.sku
    assert item["variant_name"] == variant.name
    assert item["unit"] == variant.unit
    assert item["unit_price"] == "60.00"
    assert item["total_price"] == "120.00"
    assert item["quantity"] == "2.000"


def test_28_address_snapshot_correct(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T28")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    snapshot = response.json()["address"]
    assert snapshot["address_line_1"] == address.address_line_1
    assert snapshot["city"] == address.city
    assert snapshot["postal_code"] == address.postal_code


def test_29_physical_inventory_unchanged_but_reserved_after_checkout(
    client: TestClient, db_session: Session
) -> None:
    """Phase 15 superseded this test's original premise (checkout touches
    no inventory at all): checkout now reserves inventory as part of the
    same atomic transaction. What Phase 13 actually guaranteed - physical
    `quantity` never moves and no StockMovement is ever created by
    checkout - still holds exactly as before; only the newly-added
    `reserved_quantity` bookkeeping changes.
    """
    from app.models.stock_movement import StockMovement

    _user, headers, variant, address = _ready_customer(db_session, "T29")
    lot = db_session.query(InventoryLot).filter_by(variant_id=variant.id).one()
    original_quantity = lot.quantity

    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == original_quantity  # physical stock untouched
    assert refreshed_lot.reserved_quantity == Decimal("1.000")  # reservation applied
    assert db_session.query(StockMovement).count() == 0  # consumption is delivery-only


def test_30_order_references_cart(client: TestClient, db_session: Session) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T30")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart_id = client.get("/api/v1/cart", headers=headers).json()["id"]
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )

    db_session.expire_all()
    order = db_session.query(Order).filter_by(id=response.json()["id"]).first()
    assert order.cart_id == cart_id


# ---------------------------------------------------------------------------
# Retry / Concurrency (31-35)
# ---------------------------------------------------------------------------


def test_31_checkout_same_cart_twice_returns_existing_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T31")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)

    first = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    db_session.expire_all()
    assert db_session.query(Order).count() == 1


def test_32_33_34_concurrent_checkout_exactly_one_order(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T3234")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart_id = client.get("/api/v1/cart", headers=headers).json()["id"]

    def do_checkout():
        return client.post(
            "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(do_checkout)
        f2 = pool.submit(do_checkout)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    statuses = {r1.status_code, r2.status_code}
    assert 201 in statuses  # exactly one created it
    # #34: both requests resolve to the SAME order
    assert r1.json()["id"] == r2.json()["id"]

    db_session.expire_all()
    order_count = db_session.query(Order).filter_by(cart_id=cart_id).count()
    assert order_count == 1  # #33: exactly one order row


def test_35_concurrent_cart_mutation_vs_checkout(
    client: TestClient, db_session: Session
) -> None:
    _user, headers, variant, address = _ready_customer(db_session, "T35")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "2"}, headers=headers)
    cart_id = client.get("/api/v1/cart", headers=headers).json()["id"]

    def do_checkout():
        return client.post(
            "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
        )

    def do_mutate():
        return client.post(
            "/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "99"}, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(do_checkout)
        f2 = pool.submit(do_mutate)
        checkout_resp, mutate_resp = f1.result(), f2.result()

    assert checkout_resp.status_code in (200, 201)
    # The mutation either lost the race entirely (409, cart already
    # CHECKED_OUT) or - if it happened to run first - succeeded against the
    # still-ACTIVE cart before checkout locked it. Either is fine; what must
    # NEVER happen is the order reflecting a quantity mutated after the
    # order was already created.
    db_session.expire_all()
    order = db_session.query(Order).filter_by(cart_id=cart_id).first()
    order_item = order.items[0]
    if mutate_resp.status_code == 409:
        assert order_item.quantity == Decimal("2.000")
    # If the mutation won the race and ran first, order correctly reflects
    # the merged quantity (2+99) - either way there is exactly one order.
    assert db_session.query(Order).filter_by(cart_id=cart_id).count() == 1


# ---------------------------------------------------------------------------
# Rollback (36-40)
# ---------------------------------------------------------------------------


def test_36_forced_order_item_failure_leaves_no_order(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    import app.services.order as order_module

    _user, headers, variant, address = _ready_customer(db_session, "T36")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart_id = client.get("/api/v1/cart", headers=headers).json()["id"]

    def boom(*args, **kwargs):
        raise RuntimeError("simulated order_item failure")

    monkeypatch.setattr(order_module, "OrderItem", boom)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 500

    db_session.expire_all()
    assert db_session.query(Order).filter_by(cart_id=cart_id).first() is None  # #39 no orphan order
    refreshed_cart = db_session.get(Cart, cart_id)
    assert refreshed_cart.status == "ACTIVE"  # #38


def test_37_forced_address_snapshot_failure_leaves_no_order(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    import app.services.order as order_module

    _user, headers, variant, address = _ready_customer(db_session, "T37")
    client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": "1"}, headers=headers)
    cart_id = client.get("/api/v1/cart", headers=headers).json()["id"]

    def boom(*args, **kwargs):
        raise RuntimeError("simulated order_address failure")

    monkeypatch.setattr(order_module, "OrderAddress", boom)
    response = client.post(
        "/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers
    )
    assert response.status_code == 500

    db_session.expire_all()
    assert db_session.query(Order).filter_by(cart_id=cart_id).first() is None
    refreshed_cart = db_session.get(Cart, cart_id)
    assert refreshed_cart.status == "ACTIVE"

    # #40: no orphan order_addresses - none exist at all since no order exists.
    assert db_session.query(OrderAddress).count() == 0
    # #39 (again, for this failure point): no orphan order_items either.
    assert db_session.query(OrderItem).count() == 0


# ---------------------------------------------------------------------------
# Security (41-44)
# ---------------------------------------------------------------------------


def test_41_customer_cannot_access_another_users_cart(
    client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a, variant_a, _addr_a = _ready_customer(db_session, "T41A")
    client.post("/api/v1/cart/items", json={"variant_id": variant_a.id, "quantity": "5"}, headers=headers_a)

    _user_b, headers_b = _customer(db_session, "T41B")
    cart_b = client.get("/api/v1/cart", headers=headers_b).json()
    assert cart_b["items"] == []  # never sees A's items
    assert cart_b["id"] is None


def test_42_customer_cannot_access_another_users_order(
    client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a, variant_a, address_a = _ready_customer(db_session, "T42A")
    client.post("/api/v1/cart/items", json={"variant_id": variant_a.id, "quantity": "1"}, headers=headers_a)
    order = client.post(
        "/api/v1/cart/checkout", json={"address_id": address_a.id}, headers=headers_a
    ).json()

    _user_b, headers_b = _customer(db_session, "T42B")
    response = client.get(f"/api/v1/orders/{order['id']}", headers=headers_b)
    assert response.status_code == 404


def test_43_non_customer_role_gets_403_on_orders(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_orders@example.com")
    response = client.get("/api/v1/orders", headers=_auth_headers(db_session, admin))
    assert response.status_code == 403


def test_44_unauthenticated_gets_401_on_orders(client: TestClient) -> None:
    response = client.get("/api/v1/orders")
    assert response.status_code == 401
