"""Phase 11 focused validation: inventory locations, lots, and atomic stock movements.

Fast-development-mode focused validation only. Beyond asserting HTTP responses,
mutation tests re-read the database afterward (per project testing principle) to
catch transaction bugs where the API reports success but a write was rolled back
- exactly the class of bug found in Phase 10's image primary-swap logic.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, CUSTOMER, HUB_STAFF, OPERATIONS, WHOLESALER
from app.core.security import create_access_token, hash_password
from app.models.auth_session import AuthSession
from app.models.batch import Batch
from app.models.category import Category
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.role import Role
from app.models.stock_movement import StockMovement
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
        phone=f"+9197{abs(hash(email)) % 100000000:08d}",
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


def _create_category_product_variant(
    db_session: Session, *, sku: str = "TOMATO-1KG"
) -> tuple[Product, ProductVariant]:
    category = Category(name=f"Cat-{sku}", slug=f"cat-{sku.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod-{sku}", slug=f"prod-{sku.lower()}", status="ACTIVE"
    )
    db_session.add(product)
    db_session.commit()
    variant = ProductVariant(
        product_id=product.id, name="1 KG", sku=sku, unit="KG",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return product, variant


def _create_batch(
    db_session: Session, product: Product, *, batch_code: str
) -> Batch:
    wholesaler = _create_user_with_role(
        db_session, WHOLESALER, f"ws_{batch_code.lower()}@example.com"
    )
    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        product_id=product.id,
        batch_code=batch_code,
        harvest_date=date(2026, 1, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    return batch


def _create_location(
    db_session: Session, *, code: str = "HUB-01", status: str = "ACTIVE"
) -> InventoryLocation:
    location = InventoryLocation(
        name=f"Hub {code}", code=code, type="WAREHOUSE",
        address_line_1="123 Main St", city="Nagpur", state="MH", postal_code="440001",
        status=status,
    )
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


def _create_lot(
    db_session: Session,
    batch: Batch,
    variant: ProductVariant,
    location: InventoryLocation,
    *,
    quantity: Decimal = Decimal("10.000"),
    status: str = "ACTIVE",
) -> InventoryLot:
    lot = InventoryLot(
        batch_id=batch.id, variant_id=variant.id, location_id=location.id,
        quantity=quantity, status=status,
    )
    db_session.add(lot)
    db_session.commit()
    db_session.refresh(lot)
    return lot


def _full_fixture(
    db_session: Session, *, sku: str, lot_quantity: Decimal = Decimal("10.000")
) -> tuple[Batch, ProductVariant, InventoryLocation, InventoryLot]:
    product, variant = _create_category_product_variant(db_session, sku=sku)
    batch = _create_batch(db_session, product, batch_code=f"BATCH-{sku}")
    location = _create_location(db_session, code=f"LOC-{sku}")
    lot = _create_lot(db_session, batch, variant, location, quantity=lot_quantity)
    return batch, variant, location, lot


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def test_1_create_location(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_loc1@example.com")
    headers = _auth_headers(db_session, admin)

    response = client.post(
        "/api/v1/inventory/locations",
        json={
            "name": "Central Hub", "code": "CENTRAL-01", "type": "WAREHOUSE",
            "address_line_1": "1 Hub Rd", "city": "Nagpur", "state": "MH", "postal_code": "440001",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["code"] == "CENTRAL-01"
    assert response.json()["status"] == "ACTIVE"


def test_2_duplicate_location_code_returns_409(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_loc2@example.com")
    headers = _auth_headers(db_session, admin)
    payload = {
        "name": "Dup Hub", "code": "DUP-01", "type": "WAREHOUSE",
        "address_line_1": "1 Rd", "city": "Nagpur", "state": "MH", "postal_code": "440001",
    }
    first = client.post("/api/v1/inventory/locations", json=payload, headers=headers)
    assert first.status_code == 201

    second = client.post("/api/v1/inventory/locations", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["code"] == "CONFLICT_ERROR"


def test_3_list_and_update_location(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_loc3@example.com")
    headers = _auth_headers(db_session, admin)
    location = _create_location(db_session, code="LIST-01")

    listing = client.get("/api/v1/inventory/locations", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    updated = client.patch(
        f"/api/v1/inventory/locations/{location.id}",
        json={"status": "INACTIVE"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "INACTIVE"
    assert updated.json()["code"] == "LIST-01"  # unrelated fields untouched


def test_4_invalid_location_data_rejected(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_loc4@example.com")
    headers = _auth_headers(db_session, admin)

    response = client.post(
        "/api/v1/inventory/locations",
        json={"name": "Bad", "code": "BAD-01", "type": "WAREHOUSE", "status": "DELETED"},
        headers=headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Lots
# ---------------------------------------------------------------------------


def test_5_create_valid_lot(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_lot5@example.com")
    headers = _auth_headers(db_session, admin)
    product, variant = _create_category_product_variant(db_session, sku="LOT5-SKU")
    batch = _create_batch(db_session, product, batch_code="BATCH-LOT5")
    location = _create_location(db_session, code="LOC-LOT5")

    response = client.post(
        "/api/v1/inventory/lots",
        json={
            "batch_id": batch.id, "variant_id": variant.id,
            "location_id": location.id, "quantity": "25.000",
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == "25.000"
    assert body["status"] == "ACTIVE"


def test_6_lot_creation_missing_references_returns_404(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_lot6@example.com")
    headers = _auth_headers(db_session, admin)
    product, variant = _create_category_product_variant(db_session, sku="LOT6-SKU")
    batch = _create_batch(db_session, product, batch_code="BATCH-LOT6")
    location = _create_location(db_session, code="LOC-LOT6")

    missing_batch = client.post(
        "/api/v1/inventory/lots",
        json={"batch_id": 999999, "variant_id": variant.id, "location_id": location.id, "quantity": "1"},
        headers=headers,
    )
    assert missing_batch.status_code == 404

    missing_variant = client.post(
        "/api/v1/inventory/lots",
        json={"batch_id": batch.id, "variant_id": 999999, "location_id": location.id, "quantity": "1"},
        headers=headers,
    )
    assert missing_variant.status_code == 404

    missing_location = client.post(
        "/api/v1/inventory/lots",
        json={"batch_id": batch.id, "variant_id": variant.id, "location_id": 999999, "quantity": "1"},
        headers=headers,
    )
    assert missing_location.status_code == 404


def test_7_lot_creation_product_mismatch_rejected(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_lot7@example.com")
    headers = _auth_headers(db_session, admin)
    product_a, variant_a = _create_category_product_variant(db_session, sku="LOT7-A")
    _product_b, variant_b = _create_category_product_variant(db_session, sku="LOT7-B")
    batch = _create_batch(db_session, product_a, batch_code="BATCH-LOT7")
    location = _create_location(db_session, code="LOC-LOT7")

    response = client.post(
        "/api/v1/inventory/lots",
        json={
            "batch_id": batch.id, "variant_id": variant_b.id,  # belongs to product_b, batch belongs to product_a
            "location_id": location.id, "quantity": "1",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "BUSINESS_VALIDATION_ERROR"


def test_8_duplicate_lot_returns_409(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_lot8@example.com")
    headers = _auth_headers(db_session, admin)
    batch, variant, location, _lot = _full_fixture(db_session, sku="LOT8-SKU")

    response = client.post(
        "/api/v1/inventory/lots",
        json={
            "batch_id": batch.id, "variant_id": variant.id,
            "location_id": location.id, "quantity": "5",
        },
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT_ERROR"


def test_9_list_filter_and_get_lot(client: TestClient, db_session: Session) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_lot9@example.com")
    headers = _auth_headers(db_session, admin)
    _batch, variant, _location, lot = _full_fixture(db_session, sku="LOT9-SKU")

    get_resp = client.get(f"/api/v1/inventory/lots/{lot.id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == lot.id

    filtered = client.get(
        f"/api/v1/inventory/lots?variant_id={variant.id}", headers=headers
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


# ---------------------------------------------------------------------------
# Movements
# ---------------------------------------------------------------------------


def _movement(
    client: TestClient, headers: dict, lot_id: int, movement_type: str, quantity: str, **extra
):
    payload = {"movement_type": movement_type, "quantity": quantity, **extra}
    return client.post(
        f"/api/v1/inventory/lots/{lot_id}/movements", json=payload, headers=headers
    )


def test_10_receipt_increases_quantity_and_persists(
    client: TestClient, db_session: Session
) -> None:
    ops = _create_user_with_role(db_session, OPERATIONS, "ops10@example.com")
    headers = _auth_headers(db_session, ops)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV10-SKU", lot_quantity=Decimal("10.000"))

    response = _movement(client, headers, lot.id, "RECEIPT", "15", remarks="restock")
    assert response.status_code == 201
    body = response.json()
    assert body["performed_by_user_id"] == ops.id
    assert body["movement_type"] == "RECEIPT"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == Decimal("25.000")
    assert refreshed_lot.status == "ACTIVE"
    movements = (
        db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).all()
    )
    assert len(movements) == 1
    assert movements[0].quantity == Decimal("15.000")
    assert movements[0].performed_by_user_id == ops.id


def test_11_dispatch_and_damage_decrease_quantity(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov11@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV11-SKU", lot_quantity=Decimal("20.000"))

    dispatch = _movement(client, headers, lot.id, "DISPATCH", "5")
    assert dispatch.status_code == 201

    damage = _movement(client, headers, lot.id, "DAMAGE", "3")
    assert damage.status_code == 201

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == Decimal("12.000")


def test_12_non_positive_quantity_rejected(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov12@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV12-SKU")

    zero = _movement(client, headers, lot.id, "RECEIPT", "0")
    assert zero.status_code == 422

    negative = _movement(client, headers, lot.id, "RECEIPT", "-5")
    assert negative.status_code == 422


def test_13_insufficient_stock_rejected_and_quantity_unchanged(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov13@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV13-SKU", lot_quantity=Decimal("5.000"))

    response = _movement(client, headers, lot.id, "DISPATCH", "10")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT_ERROR"

    db_session.expire_all()
    refreshed_lot = db_session.get(InventoryLot, lot.id)
    assert refreshed_lot.quantity == Decimal("5.000")
    assert (
        db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).count() == 0
    )


def test_14_zero_quantity_transitions_to_depleted_then_reactivates(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov14@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV14-SKU", lot_quantity=Decimal("5.000"))

    deplete = _movement(client, headers, lot.id, "DISPATCH", "5")
    assert deplete.status_code == 201
    assert deplete.json() is not None

    db_session.expire_all()
    depleted_lot = db_session.get(InventoryLot, lot.id)
    assert depleted_lot.quantity == Decimal("0.000")
    assert depleted_lot.status == "DEPLETED"

    reactivate = _movement(client, headers, lot.id, "RECEIPT", "8")
    assert reactivate.status_code == 201

    db_session.expire_all()
    reactivated_lot = db_session.get(InventoryLot, lot.id)
    assert reactivated_lot.quantity == Decimal("8.000")
    assert reactivated_lot.status == "ACTIVE"


def test_15_inactive_lot_rejects_movement(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov15@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(
        db_session, sku="MOV15-SKU", lot_quantity=Decimal("5.000")
    )
    lot.status = "INACTIVE"
    db_session.commit()

    response = _movement(client, headers, lot.id, "RECEIPT", "5")
    assert response.status_code == 422
    assert response.json()["code"] == "BUSINESS_VALIDATION_ERROR"

    db_session.expire_all()
    unchanged_lot = db_session.get(InventoryLot, lot.id)
    assert unchanged_lot.quantity == Decimal("5.000")
    assert unchanged_lot.status == "INACTIVE"


def test_16_movement_history_retrievable_and_filterable(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov16@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(
        db_session, sku="MOV16-SKU", lot_quantity=Decimal("20.000")
    )
    _movement(client, headers, lot.id, "DISPATCH", "3")
    _movement(client, headers, lot.id, "DAMAGE", "2")

    history = client.get(f"/api/v1/inventory/lots/{lot.id}/movements", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == 2

    filtered = client.get(
        f"/api/v1/inventory/lots/{lot.id}/movements?movement_type=DAMAGE", headers=headers
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["movement_type"] == "DAMAGE"


def test_17_movement_cannot_be_modified_or_deleted(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov17@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV17-SKU")
    created = _movement(client, headers, lot.id, "DISPATCH", "1")
    movement_id = created.json()["id"]

    patch_attempt = client.patch(
        f"/api/v1/inventory/movements/{movement_id}",
        json={"quantity": "999"},
        headers=headers,
    )
    assert patch_attempt.status_code in (404, 405)

    delete_attempt = client.delete(
        f"/api/v1/inventory/movements/{movement_id}", headers=headers
    )
    assert delete_attempt.status_code in (404, 405)


def test_18_client_cannot_override_performed_by_user(
    client: TestClient, db_session: Session
) -> None:
    admin = _create_user_with_role(db_session, ADMIN, "admin_mov18@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(db_session, sku="MOV18-SKU")

    response = client.post(
        f"/api/v1/inventory/lots/{lot.id}/movements",
        json={
            "movement_type": "RECEIPT", "quantity": "1",
            "performed_by_user_id": 999999,  # must be ignored
            "inventory_lot_id": 999999,  # must be ignored
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["performed_by_user_id"] == admin.id
    assert response.json()["inventory_lot_id"] == lot.id


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_19_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/inventory/locations")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_ERROR"


def test_20_customer_and_wholesaler_forbidden(
    client: TestClient, db_session: Session
) -> None:
    customer = _create_user_with_role(db_session, CUSTOMER, "cust_inv@example.com")
    wholesaler = _create_user_with_role(db_session, WHOLESALER, "ws_inv@example.com")

    cust_resp = client.get(
        "/api/v1/inventory/locations", headers=_auth_headers(db_session, customer)
    )
    assert cust_resp.status_code == 403

    ws_resp = client.get(
        "/api/v1/inventory/locations", headers=_auth_headers(db_session, wholesaler)
    )
    assert ws_resp.status_code == 403


def test_21_hub_staff_and_operations_allowed(
    client: TestClient, db_session: Session
) -> None:
    hub_staff = _create_user_with_role(db_session, HUB_STAFF, "hub21@example.com")
    operations = _create_user_with_role(db_session, OPERATIONS, "ops21@example.com")

    hub_resp = client.get(
        "/api/v1/inventory/locations", headers=_auth_headers(db_session, hub_staff)
    )
    assert hub_resp.status_code == 200

    ops_resp = client.get(
        "/api/v1/inventory/locations", headers=_auth_headers(db_session, operations)
    )
    assert ops_resp.status_code == 200


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_22_concurrent_dispatch_cannot_oversell(
    client: TestClient, db_session: Session
) -> None:
    """Starting quantity 10; concurrent DISPATCH 8 and DISPATCH 7.

    Exactly one must succeed. Final quantity must never be negative and must
    equal whichever single movement won the row lock.
    """
    admin = _create_user_with_role(db_session, ADMIN, "admin_concurrency@example.com")
    headers = _auth_headers(db_session, admin)
    _b, _v, _loc, lot = _full_fixture(
        db_session, sku="CONC-SKU", lot_quantity=Decimal("10.000")
    )

    def dispatch(quantity: str):
        return _movement(client, headers, lot.id, "DISPATCH", quantity)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(dispatch, "8")
        future_b = pool.submit(dispatch, "7")
        result_a = future_a.result()
        result_b = future_b.result()

    statuses = {result_a.status_code, result_b.status_code}
    assert 201 in statuses
    assert 409 in statuses  # the other must have been rejected, not silently succeeded

    db_session.expire_all()
    final_lot = db_session.get(InventoryLot, lot.id)
    assert final_lot.quantity >= Decimal("0.000")
    assert final_lot.quantity in (Decimal("2.000"), Decimal("3.000"))

    movements = (
        db_session.query(StockMovement).filter_by(inventory_lot_id=lot.id).all()
    )
    assert len(movements) == 1  # only the winning movement was recorded
