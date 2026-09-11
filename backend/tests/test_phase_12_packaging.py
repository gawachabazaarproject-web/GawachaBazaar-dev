"""Phase 12 focused validation: packaging operations and atomic completion.

Fast-development-mode focused validation only. Mutation tests re-read the
database afterward (not just the HTTP response) per established project
testing principle, to catch transaction bugs where the API reports success
but a write was rolled back.
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
from app.models.packaging_operation import PackagingOperation
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
        phone=f"+9196{abs(hash(email)) % 100000000:08d}",
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


def _create_location(db_session: Session, *, code: str) -> InventoryLocation:
    location = InventoryLocation(
        name=f"Hub {code}", code=code, type="WAREHOUSE",
        address_line_1="123 Main St", city="Nagpur", state="MH", postal_code="440001",
        status="ACTIVE",
    )
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


def _create_product_and_variants(
    db_session: Session, *, tag: str
) -> tuple[Product, ProductVariant, ProductVariant]:
    """Returns (product, bulk_variant, pack_variant) - two variants of one product."""
    category = Category(name=f"Cat-{tag}", slug=f"cat-{tag.lower()}", status="ACTIVE")
    db_session.add(category)
    db_session.commit()
    product = Product(
        category_id=category.id, name=f"Prod-{tag}", slug=f"prod-{tag.lower()}", status="ACTIVE"
    )
    db_session.add(product)
    db_session.commit()
    bulk = ProductVariant(
        product_id=product.id, name="Bulk Crate", sku=f"BULK-{tag}", unit="BOX",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    pack = ProductVariant(
        product_id=product.id, name="1 KG Pack", sku=f"PACK-{tag}", unit="KG",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add_all([bulk, pack])
    db_session.commit()
    db_session.refresh(bulk)
    db_session.refresh(pack)
    return product, bulk, pack


def _create_batch(db_session: Session, product: Product, *, batch_code: str) -> Batch:
    wholesaler = _create_user_with_role(
        db_session, WHOLESALER, f"ws_{batch_code.lower()}@example.com"
    )
    batch = Batch(
        wholesaler_user_id=wholesaler.id, product_id=product.id, batch_code=batch_code,
        harvest_date=date(2026, 1, 1), quantity=Decimal("100.000"), unit="KG",
        status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    return batch


def _create_lot(
    db_session: Session, batch: Batch, variant: ProductVariant, location: InventoryLocation,
    *, quantity: Decimal,
) -> InventoryLot:
    lot = InventoryLot(
        batch_id=batch.id, variant_id=variant.id, location_id=location.id,
        quantity=quantity, status="ACTIVE" if quantity > 0 else "DEPLETED",
    )
    db_session.add(lot)
    db_session.commit()
    db_session.refresh(lot)
    return lot


def _scenario(db_session: Session, *, tag: str, input_qty: Decimal = Decimal("20.000")):
    """Full scenario: location, product/bulk/pack variants, batch, and an input lot."""
    location = _create_location(db_session, code=f"LOC-{tag}")
    product, bulk, pack = _create_product_and_variants(db_session, tag=tag)
    batch = _create_batch(db_session, product, batch_code=f"BATCH-{tag}")
    input_lot = _create_lot(db_session, batch, bulk, location, quantity=input_qty)
    return location, batch, bulk, pack, input_lot


def _headers(db_session: Session, tag: str, role: str = ADMIN) -> dict[str, str]:
    user = _create_user_with_role(db_session, role, f"user_{tag.lower()}@example.com")
    return _auth_headers(db_session, user), user


# ---------------------------------------------------------------------------
# Operation CRUD + lifecycle
# ---------------------------------------------------------------------------


def test_1_create_operation(client: TestClient, db_session: Session) -> None:
    headers, _user = _headers(db_session, "OP1")
    location = _create_location(db_session, code="LOC-OP1")

    response = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-001", "name": "Tomato Repack", "location_id": location.id},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["packaging_code"] == "PKG-001"
    assert body["completed_at"] is None


def test_2_start_operation(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP2")
    location = _create_location(db_session, code="LOC-OP2")
    created = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-002", "name": "Op2", "location_id": location.id},
        headers=headers,
    ).json()

    started = client.post(
        f"/api/v1/packaging/operations/{created['id']}/start", headers=headers
    )
    assert started.status_code == 200
    assert started.json()["status"] == "IN_PROGRESS"

    # DRAFT -> IN_PROGRESS again is invalid (already IN_PROGRESS)
    invalid = client.post(
        f"/api/v1/packaging/operations/{created['id']}/start", headers=headers
    )
    assert invalid.status_code == 409


def test_3_cancel_operation(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP3")
    location = _create_location(db_session, code="LOC-OP3")
    created = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-003", "name": "Op3", "location_id": location.id},
        headers=headers,
    ).json()

    cancelled = client.post(
        f"/api/v1/packaging/operations/{created['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    # CANCELLED -> anything is invalid
    invalid = client.post(
        f"/api/v1/packaging/operations/{created['id']}/start", headers=headers
    )
    assert invalid.status_code == 409


# ---------------------------------------------------------------------------
# Inputs / Outputs
# ---------------------------------------------------------------------------


def test_4_add_input(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP4")
    location, _batch, _bulk, _pack, input_lot = _scenario(db_session, tag="OP4")
    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-004", "name": "Op4", "location_id": location.id},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": "5"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["quantity"] == "5.000"


def test_5_add_output(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP5")
    location, batch, _bulk, pack, input_lot = _scenario(db_session, tag="OP5")
    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-005", "name": "Op5", "location_id": location.id},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": "5"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/outputs",
        json={
            "variant_id": pack.id, "batch_id": batch.id,
            "package_count": 5, "total_quantity": "5",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["package_count"] == 5
    assert response.json()["total_quantity"] == "5.000"


# ---------------------------------------------------------------------------
# Completion: the core atomic transaction
# ---------------------------------------------------------------------------


def _build_ready_operation(
    client: TestClient, db_session: Session, headers: dict, *, tag: str,
    input_qty: Decimal = Decimal("20.000"), consume_qty: str = "15",
    output_qty: str = "15", package_count: int = 15,
) -> tuple[dict, InventoryLot, InventoryLot]:
    location, batch, bulk, pack, input_lot = _scenario(
        db_session, tag=tag, input_qty=input_qty
    )
    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": f"PKG-{tag}", "name": f"Op {tag}", "location_id": location.id},
        headers=headers,
    ).json()
    client.post(f"/api/v1/packaging/operations/{op['id']}/start", headers=headers)
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": consume_qty},
        headers=headers,
    )
    output_resp = client.post(
        f"/api/v1/packaging/operations/{op['id']}/outputs",
        json={
            "variant_id": pack.id, "batch_id": batch.id,
            "package_count": package_count, "total_quantity": output_qty,
        },
        headers=headers,
    )
    output_lot_id = output_resp.json()["inventory_lot_id"]
    output_lot = db_session.get(InventoryLot, output_lot_id)
    return op, input_lot, output_lot


def test_6_complete_operation_happy_path(client: TestClient, db_session: Session) -> None:
    headers, user = _headers(db_session, "OP6")
    op, input_lot, output_lot = _build_ready_operation(client, db_session, headers, tag="OP6")

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["completed_at"] is not None
    assert len(body["inputs"]) == 1
    assert len(body["outputs"]) == 1


def test_7_input_stock_decreases(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP7")
    op, input_lot, _output_lot = _build_ready_operation(
        client, db_session, headers, tag="OP7", input_qty=Decimal("20.000"), consume_qty="15"
    )
    client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)

    db_session.expire_all()
    refreshed = db_session.get(InventoryLot, input_lot.id)
    assert refreshed.quantity == Decimal("5.000")
    assert refreshed.status == "ACTIVE"


def test_8_output_stock_increases(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP8")
    op, _input_lot, output_lot = _build_ready_operation(
        client, db_session, headers, tag="OP8", output_qty="15", package_count=15
    )
    assert output_lot.quantity == Decimal("0.000")  # not yet applied before completion

    client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)

    db_session.expire_all()
    refreshed = db_session.get(InventoryLot, output_lot.id)
    assert refreshed.quantity == Decimal("15.000")
    assert refreshed.status == "ACTIVE"


def test_9_stock_movements_created_with_reference(
    client: TestClient, db_session: Session
) -> None:
    headers, user = _headers(db_session, "OP9")
    op, input_lot, output_lot = _build_ready_operation(client, db_session, headers, tag="OP9")
    client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)

    db_session.expire_all()
    input_movements = (
        db_session.query(StockMovement).filter_by(inventory_lot_id=input_lot.id).all()
    )
    output_movements = (
        db_session.query(StockMovement).filter_by(inventory_lot_id=output_lot.id).all()
    )
    assert len(input_movements) == 1
    assert input_movements[0].movement_type == "ADJUSTMENT_OUT"
    assert input_movements[0].reference_type == "PACKAGING_OPERATION"
    assert input_movements[0].reference_id == op["id"]
    assert input_movements[0].performed_by_user_id == user.id

    assert len(output_movements) == 1
    assert output_movements[0].movement_type == "RECEIPT"
    assert output_movements[0].reference_type == "PACKAGING_OPERATION"
    assert output_movements[0].reference_id == op["id"]


def test_10_operation_becomes_completed(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP10")
    op, _il, _ol = _build_ready_operation(client, db_session, headers, tag="OP10")
    client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)

    db_session.expire_all()
    refreshed = db_session.get(PackagingOperation, op["id"])
    assert refreshed.status == "COMPLETED"
    assert refreshed.completed_at is not None


def test_11_completed_operation_cannot_be_modified(
    client: TestClient, db_session: Session
) -> None:
    headers, _ = _headers(db_session, "OP11")
    op, input_lot, _ol = _build_ready_operation(client, db_session, headers, tag="OP11")
    client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)

    assert client.post(f"/api/v1/packaging/operations/{op['id']}/start", headers=headers).status_code == 409
    assert client.post(f"/api/v1/packaging/operations/{op['id']}/cancel", headers=headers).status_code == 409
    assert client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": "1"},
        headers=headers,
    ).status_code == 409


def test_12_insufficient_stock_returns_409(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP12")
    location, batch, bulk, pack, input_lot = _scenario(
        db_session, tag="OP12", input_qty=Decimal("5.000")
    )
    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-OP12", "name": "Op12", "location_id": location.id},
        headers=headers,
    ).json()
    client.post(f"/api/v1/packaging/operations/{op['id']}/start", headers=headers)
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": "5"},
        headers=headers,
    )
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/outputs",
        json={"variant_id": pack.id, "batch_id": batch.id, "package_count": 5, "total_quantity": "5"},
        headers=headers,
    )
    # Drain the lot below the declared input quantity between add_input and complete.
    input_lot.quantity = Decimal("2.000")
    db_session.commit()

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers
    )
    assert response.status_code == 409


def test_13_no_negative_stock_after_failed_completion(
    client: TestClient, db_session: Session
) -> None:
    headers, _ = _headers(db_session, "OP13")
    location, batch, bulk, pack, input_lot = _scenario(
        db_session, tag="OP13", input_qty=Decimal("5.000")
    )
    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-OP13", "name": "Op13", "location_id": location.id},
        headers=headers,
    ).json()
    client.post(f"/api/v1/packaging/operations/{op['id']}/start", headers=headers)
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": "5"},
        headers=headers,
    )
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/outputs",
        json={"variant_id": pack.id, "batch_id": batch.id, "package_count": 5, "total_quantity": "5"},
        headers=headers,
    )
    input_lot.quantity = Decimal("2.000")
    db_session.commit()

    client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)

    db_session.expire_all()
    refreshed = db_session.get(InventoryLot, input_lot.id)
    assert refreshed.quantity == Decimal("2.000")
    assert refreshed.quantity >= Decimal("0")


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_14_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/packaging/operations")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_ERROR"


def test_15_customer_forbidden(client: TestClient, db_session: Session) -> None:
    customer = _create_user_with_role(db_session, CUSTOMER, "cust_pkg@example.com")
    response = client.get(
        "/api/v1/packaging/operations", headers=_auth_headers(db_session, customer)
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTHORIZATION_ERROR"


def test_15b_hub_staff_and_operations_allowed(
    client: TestClient, db_session: Session
) -> None:
    for role in (HUB_STAFF, OPERATIONS):
        user = _create_user_with_role(db_session, role, f"staff_{role.lower()}@example.com")
        response = client.get(
            "/api/v1/packaging/operations", headers=_auth_headers(db_session, user)
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Duplicate / concurrent completion
# ---------------------------------------------------------------------------


def test_16_duplicate_completion_does_not_duplicate_movements(
    client: TestClient, db_session: Session
) -> None:
    headers, _ = _headers(db_session, "OP16")
    op, input_lot, output_lot = _build_ready_operation(client, db_session, headers, tag="OP16")

    first = client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers)
    assert second.status_code == 409

    db_session.expire_all()
    total_movements = (
        db_session.query(StockMovement)
        .filter(StockMovement.inventory_lot_id.in_([input_lot.id, output_lot.id]))
        .count()
    )
    assert total_movements == 2  # exactly one ADJUSTMENT_OUT + one RECEIPT, never duplicated


def test_17_concurrent_completion_exactly_one_succeeds(
    client: TestClient, db_session: Session
) -> None:
    headers, _ = _headers(db_session, "OP17")
    op, input_lot, output_lot = _build_ready_operation(client, db_session, headers, tag="OP17")

    def complete():
        return client.post(
            f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(complete)
        f2 = pool.submit(complete)
        r1, r2 = f1.result(), f2.result()

    statuses = {r1.status_code, r2.status_code}
    assert 200 in statuses
    assert 409 in statuses

    db_session.expire_all()
    refreshed_op = db_session.get(PackagingOperation, op["id"])
    assert refreshed_op.status == "COMPLETED"

    total_movements = (
        db_session.query(StockMovement)
        .filter(StockMovement.inventory_lot_id.in_([input_lot.id, output_lot.id]))
        .count()
    )
    assert total_movements == 2


# ---------------------------------------------------------------------------
# Traceability & location
# ---------------------------------------------------------------------------


def test_18_output_batch_traceability_rejected(
    client: TestClient, db_session: Session
) -> None:
    headers, _ = _headers(db_session, "OP18")
    location, batch, bulk, pack, input_lot = _scenario(db_session, tag="OP18")
    other_product, _b2, _p2 = _create_product_and_variants(db_session, tag="OP18OTHER")
    other_batch = _create_batch(db_session, other_product, batch_code="BATCH-OP18OTHER")

    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-OP18", "name": "Op18", "location_id": location.id},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": input_lot.id, "quantity": "5"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/outputs",
        json={
            "variant_id": pack.id, "batch_id": other_batch.id,  # never an input batch
            "package_count": 5, "total_quantity": "5",
        },
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT_ERROR"


def test_19_location_mismatch_rejected(client: TestClient, db_session: Session) -> None:
    headers, _ = _headers(db_session, "OP19")
    op_location = _create_location(db_session, code="LOC-OP19-OP")
    other_location = _create_location(db_session, code="LOC-OP19-OTHER")
    product, bulk, _pack = _create_product_and_variants(db_session, tag="OP19")
    batch = _create_batch(db_session, product, batch_code="BATCH-OP19")
    wrong_location_lot = _create_lot(
        db_session, batch, bulk, other_location, quantity=Decimal("10.000")
    )

    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-OP19", "name": "Op19", "location_id": op_location.id},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": wrong_location_lot.id, "quantity": "5"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT_ERROR"


# ---------------------------------------------------------------------------
# Atomic rollback
# ---------------------------------------------------------------------------


def test_20_transaction_rollback_when_completion_fails(
    client: TestClient, db_session: Session
) -> None:
    """Two inputs; the second is starved below its declared quantity right
    before completion. Completion must fail entirely - including rolling
    back the first input's (in-memory, pre-commit) quantity change.
    """
    headers, _ = _headers(db_session, "OP20")
    location = _create_location(db_session, code="LOC-OP20")
    product, bulk, pack = _create_product_and_variants(db_session, tag="OP20")
    batch = _create_batch(db_session, product, batch_code="BATCH-OP20")
    lot_a = _create_lot(db_session, batch, bulk, location, quantity=Decimal("20.000"))
    # A second bulk-ish variant sharing the same product for lot_b's SKU distinctness.
    lot_b_variant = ProductVariant(
        product_id=product.id, name="Bulk Crate B", sku="BULK-OP20-B", unit="BOX",
        quantity=Decimal("1.000"), status="ACTIVE",
    )
    db_session.add(lot_b_variant)
    db_session.commit()
    lot_b = _create_lot(db_session, batch, lot_b_variant, location, quantity=Decimal("20.000"))

    op = client.post(
        "/api/v1/packaging/operations",
        json={"packaging_code": "PKG-OP20", "name": "Op20", "location_id": location.id},
        headers=headers,
    ).json()
    client.post(f"/api/v1/packaging/operations/{op['id']}/start", headers=headers)
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": lot_a.id, "quantity": "5"},
        headers=headers,
    )
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/inputs",
        json={"inventory_lot_id": lot_b.id, "quantity": "5"},
        headers=headers,
    )
    client.post(
        f"/api/v1/packaging/operations/{op['id']}/outputs",
        json={"variant_id": pack.id, "batch_id": batch.id, "package_count": 10, "total_quantity": "10"},
        headers=headers,
    )

    # Starve lot_b below its declared 5 right before completion.
    lot_b.quantity = Decimal("1.000")
    db_session.commit()

    response = client.post(
        f"/api/v1/packaging/operations/{op['id']}/complete", headers=headers
    )
    assert response.status_code == 409

    db_session.expire_all()
    refreshed_a = db_session.get(InventoryLot, lot_a.id)
    refreshed_b = db_session.get(InventoryLot, lot_b.id)
    refreshed_op = db_session.get(PackagingOperation, op["id"])
    assert refreshed_a.quantity == Decimal("20.000")  # untouched despite processing before lot_b
    assert refreshed_b.quantity == Decimal("1.000")
    assert refreshed_op.status == "IN_PROGRESS"  # never marked COMPLETED

    movements = (
        db_session.query(StockMovement)
        .filter(StockMovement.inventory_lot_id.in_([lot_a.id, lot_b.id]))
        .count()
    )
    assert movements == 0
