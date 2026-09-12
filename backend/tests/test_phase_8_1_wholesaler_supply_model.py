"""Phase 8.1 — Business Model Correction: Farmer -> Wholesaler Supply Model Tests.

Verifies:
1. Batch requires wholesaler_user_id.
2. Valid User can be assigned as Batch.wholesaler.
3. Batch.farm_id may be NULL.
4. Existing Farm -> Batch relationship remains structurally valid.
5. User can have multiple supplied batches.
6. Wholesaler user is NOT unique to one batch.
7. Batch -> Wholesaler relationship works.
8. Batch -> Farm relationship still works.
9. QualityCheck -> Batch still works.
10. Batch -> InventoryLot remains valid.
11. Batch deletion behavior remains correct.
12. User deletion is RESTRICTED when referenced by batches.
13. Farm deletion remains governed by existing FK rules.
14. The wholesaler FK uses ON DELETE RESTRICT.
15. farm_id remains nullable.
16. No wholesalers table is introduced.
17. No Farmer/Farm tables are removed.
18. No Phase 1–8 unrelated tables are changed.
19. Database schema contains the new wholesaler_user_id column.
20. Index exists on wholesaler_user_id.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.category import Category
from app.models.farm import Farm
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.quality_check import QualityCheck
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "wholesaler_user@example.com",
    phone: str = "+919811111111",
    name: str = "Agro Wholesaler Pvt Ltd",
) -> User:
    """Helper to create a user."""
    user = User(
        name=name,
        email=email,
        phone=phone,
        password_hash="argon2id_dummy_hash",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_farm(
    db_session: Session,
    owner_user_id: int,
    name: str = "Sahyadri Heritage Farm",
) -> Farm:
    """Helper to create a farm."""
    farm = Farm(
        owner_user_id=owner_user_id,
        name=name,
        address_line_1="Farm Plot 77",
        village="Narayangaon",
        city="Pune",
        state="Maharashtra",
        postal_code="410504",
        status="ACTIVE",
    )
    db_session.add(farm)
    db_session.commit()
    return farm


def _create_product(
    db_session: Session,
    name: str = "Nashik Red Onion",
    slug: str = "nashik-red-onion",
) -> Product:
    """Helper to create a product with category."""
    cat = Category(
        name="Fresh Produce",
        slug="fresh-produce",
        status="ACTIVE",
    )
    db_session.add(cat)
    db_session.flush()

    prod = Product(
        category_id=cat.id,
        name=name,
        slug=slug,
        status="ACTIVE",
    )
    db_session.add(prod)
    db_session.commit()
    return prod


# 1. Batch requires wholesaler_user_id
def test_1_batch_requires_wholesaler_user_id(db_session: Session) -> None:
    prod = _create_product(db_session)
    batch = Batch(
        wholesaler_user_id=None,  # Not provided
        batch_code="BATCH-WS-ERR-001",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 2. Valid User can be assigned as Batch.wholesaler
def test_2_valid_user_assigned_as_batch_wholesaler(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws2@example.com", phone="+919811111112"
    )
    prod = _create_product(db_session)
    batch = Batch(
        wholesaler=wholesaler,
        batch_code="BATCH-WS-002",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("200.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    assert batch.id is not None
    assert batch.wholesaler_user_id == wholesaler.id
    assert batch.wholesaler.id == wholesaler.id


# 3. Batch.farm_id may be NULL
def test_3_batch_farm_id_nullable(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws3@example.com", phone="+919811111113"
    )
    prod = _create_product(db_session)
    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        farm_id=None,  # Nullable future capability
        batch_code="BATCH-WS-003",
        product_id=prod.id,
        harvest_date=date(2026, 9, 2),
        quantity=Decimal("150.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    reloaded = db_session.get(Batch, batch.id)
    assert reloaded is not None
    assert reloaded.farm_id is None
    assert reloaded.farm is None


# 4. Existing Farm -> Batch relationship remains structurally valid
def test_4_farm_to_batch_relationship_structurally_valid(db_session: Session) -> None:
    farmer = _create_user(
        db_session, email="farmer4@example.com", phone="+919811111114"
    )
    wholesaler = _create_user(
        db_session, email="ws4@example.com", phone="+919811111115"
    )
    farm = _create_farm(db_session, owner_user_id=farmer.id)
    prod = _create_product(db_session)

    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        farm_id=farm.id,
        batch_code="BATCH-WS-004",
        product_id=prod.id,
        harvest_date=date(2026, 9, 3),
        quantity=Decimal("300.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    reloaded_farm = db_session.get(Farm, farm.id)
    assert reloaded_farm is not None
    assert len(reloaded_farm.batches) == 1
    assert reloaded_farm.batches[0].batch_code == "BATCH-WS-004"


# 5. User can have multiple supplied batches
def test_5_user_multiple_supplied_batches(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws5@example.com", phone="+919811111116"
    )
    prod = _create_product(db_session)

    b1 = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-005-A",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    b2 = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-005-B",
        product_id=prod.id,
        harvest_date=date(2026, 9, 2),
        quantity=Decimal("200.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add_all([b1, b2])
    db_session.commit()

    reloaded_user = db_session.get(User, wholesaler.id)
    assert reloaded_user is not None
    assert len(reloaded_user.batches_supplied) == 2
    codes = {b.batch_code for b in reloaded_user.batches_supplied}
    assert codes == {"BATCH-WS-005-A", "BATCH-WS-005-B"}


# 6. Wholesaler user is NOT unique to one batch
def test_6_wholesaler_user_not_unique_to_one_batch(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws6@example.com", phone="+919811111117"
    )
    prod = _create_product(db_session)

    b1 = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-006-1",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("10.000"),
        unit="KG",
        status="HARVESTED",
    )
    b2 = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-006-2",
        product_id=prod.id,
        harvest_date=date(2026, 9, 2),
        quantity=Decimal("20.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add_all([b1, b2])
    db_session.commit()
    assert b1.wholesaler_user_id == b2.wholesaler_user_id


# 7. Batch -> Wholesaler relationship works
def test_7_batch_to_wholesaler_relationship(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session,
        email="ws7@example.com",
        phone="+919811111118",
        name="Wholesaler Seven",
    )
    prod = _create_product(db_session)
    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-007",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    loaded_batch = db_session.get(Batch, batch.id)
    assert loaded_batch is not None
    assert loaded_batch.wholesaler is not None
    assert loaded_batch.wholesaler.name == "Wholesaler Seven"
    assert loaded_batch.wholesaler.email == "ws7@example.com"


# 8. Batch -> Farm relationship still works
def test_8_batch_to_farm_relationship(db_session: Session) -> None:
    farmer = _create_user(
        db_session, email="farmer8@example.com", phone="+919811111119"
    )
    wholesaler = _create_user(
        db_session, email="ws8@example.com", phone="+919811111120"
    )
    farm = _create_farm(db_session, owner_user_id=farmer.id, name="Orchard Eight")
    prod = _create_product(db_session)

    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        farm_id=farm.id,
        batch_code="BATCH-WS-008",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    loaded_batch = db_session.get(Batch, batch.id)
    assert loaded_batch is not None
    assert loaded_batch.farm is not None
    assert loaded_batch.farm.name == "Orchard Eight"


# 9. QualityCheck -> Batch still works and reaches wholesaler
def test_9_quality_check_to_batch_and_wholesaler(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws9@example.com", phone="+919811111121"
    )
    inspector = _create_user(
        db_session, email="qa9@example.com", phone="+919811111122"
    )
    prod = _create_product(db_session)

    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-009",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("500.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.flush()

    qc = QualityCheck(
        batch_id=batch.id,
        checked_by_user_id=inspector.id,
        checked_on=datetime.now(UTC),
        status="PASSED",
        remarks="Produce verified",
    )
    db_session.add(qc)
    db_session.commit()

    loaded_qc = db_session.get(QualityCheck, qc.id)
    assert loaded_qc is not None
    assert loaded_qc.batch is not None
    assert loaded_qc.batch.batch_code == "BATCH-WS-009"
    # Reach wholesaler through Batch
    assert loaded_qc.batch.wholesaler.email == "ws9@example.com"


# 10. Batch -> InventoryLot remains valid and derives wholesaler
def test_10_batch_to_inventory_lot_remains_valid(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws10@example.com", phone="+919811111123"
    )
    prod = _create_product(db_session)

    variant = ProductVariant(
        product_id=prod.id,
        sku="SKU-WS-ONION-1KG",
        name="1kg Pack",
        quantity=Decimal("1.000"),
        unit="KG",
        status="ACTIVE",
    )
    db_session.add(variant)

    location = InventoryLocation(
        name="Main Fulfillment Center",
        code="LOC-MFC-01",
        type="WAREHOUSE",
        address_line_1="Plot 10, Sector 19",
        city="Vashi",
        state="Maharashtra",
        postal_code="400703",
        status="ACTIVE",
    )
    db_session.add(location)
    db_session.flush()

    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-010",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("1000.000"),
        unit="KG",
        status="APPROVED",
    )
    db_session.add(batch)
    db_session.flush()

    lot = InventoryLot(
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=location.id,
        quantity=Decimal("500.000"),
        status="ACTIVE",
    )
    db_session.add(lot)
    db_session.commit()

    loaded_lot = db_session.get(InventoryLot, lot.id)
    assert loaded_lot is not None
    assert loaded_lot.batch is not None
    assert loaded_lot.batch.wholesaler_user_id == wholesaler.id
    assert loaded_lot.batch.wholesaler.email == "ws10@example.com"


# 11. Batch deletion behavior remains correct
def test_11_batch_deletion_behavior(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws11@example.com", phone="+919811111124"
    )
    prod = _create_product(db_session)
    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-011",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    batch_id = batch.id
    db_session.delete(batch)
    db_session.commit()

    assert db_session.get(Batch, batch_id) is None
    # Wholesaler and Product must NOT be deleted
    assert db_session.get(User, wholesaler.id) is not None
    assert db_session.get(Product, prod.id) is not None


# 12. User deletion is RESTRICTED when referenced by batches
def test_12_user_deletion_restricted_by_batches(db_session: Session) -> None:
    wholesaler = _create_user(
        db_session, email="ws12@example.com", phone="+919811111125"
    )
    prod = _create_product(db_session)
    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        batch_code="BATCH-WS-012",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    db_session.delete(wholesaler)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 13. Farm deletion remains governed by existing FK rules (ON DELETE RESTRICT)
def test_13_farm_deletion_governed_by_fk_rules(db_session: Session) -> None:
    farmer = _create_user(
        db_session, email="farmer13@example.com", phone="+919811111126"
    )
    wholesaler = _create_user(
        db_session, email="ws13@example.com", phone="+919811111127"
    )
    farm = _create_farm(db_session, owner_user_id=farmer.id)
    prod = _create_product(db_session)

    batch = Batch(
        wholesaler_user_id=wholesaler.id,
        farm_id=farm.id,
        batch_code="BATCH-WS-013",
        product_id=prod.id,
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()

    db_session.delete(farm)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 14. The wholesaler FK uses ON DELETE RESTRICT
def test_14_wholesaler_fk_on_delete_restrict(db_session: Session) -> None:
    row = db_session.execute(
        text("""
        SELECT confdeltype
        FROM pg_constraint
        WHERE conname = 'fk_batches_wholesaler_user_id_users';
    """)
    ).fetchone()
    assert row is not None
    # 'r' in PostgreSQL pg_constraint confdeltype stands for RESTRICT
    assert row[0] == "r"


# 15. farm_id remains nullable
def test_15_farm_id_is_nullable(db_session: Session) -> None:
    row = db_session.execute(
        text("""
        SELECT is_nullable
        FROM information_schema.columns
        WHERE table_name = 'batches' AND column_name = 'farm_id';
    """)
    ).fetchone()
    assert row is not None
    assert row[0] == "YES"


# 16. No wholesalers table is introduced
def test_16_no_wholesalers_table_introduced(db_session: Session) -> None:
    tables = db_session.execute(
        text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name LIKE '%wholesaler%';
    """)
    ).fetchall()
    assert len(tables) == 0


# 17. No Farmer/Farm tables are removed
def test_17_farms_table_exists(db_session: Session) -> None:
    exists = db_session.execute(
        text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'farms'
        );
    """)
    ).scalar()
    assert exists is True


# 18. No Phase 1–8 unrelated tables are changed (26 domain tables + alembic_version)
def test_18_no_unrelated_tables_changed(db_session: Session) -> None:
    expected_tables = {
        "alembic_version",
        "roles",
        "users",
        "user_roles",
        "addresses",
        "auth_sessions",
        "farms",
        "batches",
        "quality_checks",
        "categories",
        "products",
        "product_variants",
        "prices",
        "product_images",
        "inventory_locations",
        "inventory_lots",
        "stock_movements",
        "packaging_operations",
        "packaging_inputs",
        "packaging_outputs",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "order_addresses",
        "payments",
        "payment_transactions",
    }
    actual_tables = set(
        db_session.execute(
            text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        ).scalars()
    )
    assert actual_tables == expected_tables


# 19. Database schema contains the wholesaler_user_id column
def test_19_schema_contains_wholesaler_user_id(db_session: Session) -> None:
    """Phase 17 relaxed this column from NOT NULL to nullable (additive,
    safe - every pre-existing row already has a value) so a batch can be
    sourced from a `Supplier` record alone, with no `User`/wholesaler
    involved at all. `ck_batches_supplier_or_wholesaler` now guarantees at
    least one of {wholesaler_user_id, supplier_id} is always set instead.
    See ARCHITECTURE.md §21c.
    """
    row = db_session.execute(
        text("""
        SELECT data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'batches' AND column_name = 'wholesaler_user_id';
    """)
    ).fetchone()
    assert row is not None
    assert row[0] == "bigint"
    assert row[1] == "YES"


# 20. Index exists on wholesaler_user_id
def test_20_index_exists_on_wholesaler_user_id(db_session: Session) -> None:
    index_exists = db_session.execute(
        text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'batches' AND indexname = 'ix_batches_wholesaler_user_id'
        );
    """)
    ).scalar()
    assert index_exists is True
