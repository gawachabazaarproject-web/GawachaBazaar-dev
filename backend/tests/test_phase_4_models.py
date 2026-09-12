from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.category import Category
from app.models.farm import Farm
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "warehouse.mgr@example.com",
    phone: str = "+919876544001",
) -> User:
    """Helper to create a valid user for testing."""
    user = User(
        name="Suresh Shinde",
        email=email,
        phone=phone,
        password_hash="hashed_pw",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_farm(
    db_session: Session,
    owner_user_id: int,
    name: str = "Sahyadri Valley Farm",
) -> Farm:
    """Helper to create a valid farm for testing."""
    farm = Farm(
        owner_user_id=owner_user_id,
        name=name,
        address_line_1="Survey No 102",
        village="Otur",
        city="Junnar",
        state="Maharashtra",
        postal_code="412409",
        latitude=Decimal("19.245000"),
        longitude=Decimal("73.912000"),
        contact_number="+919876544002",
        status="ACTIVE",
    )
    db_session.add(farm)
    db_session.commit()
    return farm


def _create_category(
    db_session: Session,
    name: str = "Fresh Organic Vegetables",
    slug: str = "fresh-organic-vegetables",
) -> Category:
    """Helper to create a valid category for testing."""
    category = Category(
        name=name,
        slug=slug,
        status="ACTIVE",
        description="Organic certified fresh produce",
    )
    db_session.add(category)
    db_session.commit()
    return category


def _create_product(
    db_session: Session,
    category_id: int,
    name: str = "Nashik Red Onion",
    slug: str = "nashik-red-onion",
) -> Product:
    """Helper to create a valid product for testing."""
    product = Product(
        category_id=category_id,
        name=name,
        slug=slug,
        status="ACTIVE",
        description="Premium Nashik red onions",
    )
    db_session.add(product)
    db_session.commit()
    return product


def _create_variant(
    db_session: Session,
    product_id: int,
    name: str = "5 KG Mesh Bag",
    sku: str = "ONION-RED-5KG",
    unit: str = "KG",
    quantity: Decimal = Decimal("5.000"),
) -> ProductVariant:
    """Helper to create a valid product variant for testing."""
    variant = ProductVariant(
        product_id=product_id,
        name=name,
        sku=sku,
        unit=unit,
        quantity=quantity,
        status="ACTIVE",
    )
    db_session.add(variant)
    db_session.commit()
    return variant


def _create_batch(
    db_session: Session,
    farm_id: int,
    product_id: int,
    batch_code: str = "BATCH-ONION-2026-01",
    quantity: Decimal = Decimal("500.000"),
    wholesaler_user_id: int | None = None,
) -> Batch:
    """Helper to create a valid batch for testing."""
    if wholesaler_user_id is None:
        wholesaler = _create_user(
            db_session,
            email=f"ws_{batch_code.lower().replace('-', '_')}@example.com",
            phone=f"+9194{abs(hash(batch_code)) % 100000000:08d}",
        )
        wholesaler_user_id = wholesaler.id
    batch = Batch(
        wholesaler_user_id=wholesaler_user_id,
        farm_id=farm_id,
        product_id=product_id,
        batch_code=batch_code,
        harvest_date=date(2026, 9, 1),
        expiry_date=date(2026, 9, 30),
        quantity=quantity,
        unit="KG",
        status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    return batch


def _create_location(
    db_session: Session,
    name: str = "Gawacha Bazaar Main Hub",
    code: str = "GB-HUB-01",
    location_type: str = "WAREHOUSE",
    status: str = "ACTIVE",
) -> InventoryLocation:
    """Helper to create a valid inventory location for testing."""
    location = InventoryLocation(
        name=name,
        code=code,
        type=location_type,
        address_line_1="Plot 12, APMC Market Yard",
        address_line_2="Sector 4",
        city="Vashi",
        state="Maharashtra",
        postal_code="400703",
        status=status,
    )
    db_session.add(location)
    db_session.commit()
    return location


def _create_lot(
    db_session: Session,
    batch_id: int,
    variant_id: int,
    location_id: int,
    quantity: Decimal = Decimal("100.000"),
    status: str = "ACTIVE",
) -> InventoryLot:
    """Helper to create a valid inventory lot for testing."""
    lot = InventoryLot(
        batch_id=batch_id,
        variant_id=variant_id,
        location_id=location_id,
        quantity=quantity,
        status=status,
    )
    db_session.add(lot)
    db_session.commit()
    return lot


def _create_movement(
    db_session: Session,
    inventory_lot_id: int,
    performed_by_user_id: int,
    movement_type: str = "RECEIPT",
    quantity: Decimal = Decimal("100.000"),
    reference_type: str | None = "PURCHASE_RECEIPT",
    reference_id: int | None = 1001,
    remarks: str | None = "Initial stock intake",
    occurred_at: datetime | None = None,
) -> StockMovement:
    """Helper to create a valid stock movement for testing."""
    if occurred_at is None:
        occurred_at = datetime.now(UTC)
    movement = StockMovement(
        inventory_lot_id=inventory_lot_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        performed_by_user_id=performed_by_user_id,
        occurred_at=occurred_at,
        remarks=remarks,
    )
    db_session.add(movement)
    db_session.commit()
    return movement


# ==============================================================================
# INVENTORY LOCATIONS
# ==============================================================================


# 1. location can be created
def test_01_location_can_be_created(db_session: Session) -> None:
    loc = _create_location(
        db_session,
        name="Cold Storage Unit A",
        code="CS-UNIT-A",
        location_type="COLD_STORAGE",
        status="ACTIVE",
    )
    assert loc.id is not None
    assert loc.name == "Cold Storage Unit A"
    assert loc.code == "CS-UNIT-A"
    assert loc.type == "COLD_STORAGE"
    assert loc.status == "ACTIVE"
    assert loc.created_at is not None
    assert loc.updated_at is not None


# 2. location code is unique
def test_02_location_code_is_unique(db_session: Session) -> None:
    _create_location(db_session, code="DUP-LOC-CODE")
    dup_loc = InventoryLocation(
        name="Duplicate Location",
        code="DUP-LOC-CODE",
        type="WAREHOUSE",
        address_line_1="Addr 1",
        city="Pune",
        state="Maharashtra",
        postal_code="411001",
        status="ACTIVE",
    )
    db_session.add(dup_loc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 3. location type is stored correctly
def test_03_location_type_is_stored_correctly(db_session: Session) -> None:
    types = ["COLD_STORAGE", "PACKING_AREA", "DISPATCH_AREA", "MAIN_HUB"]
    for idx, t in enumerate(types):
        loc = _create_location(
            db_session,
            name=f"Location {t}",
            code=f"LOC-TYPE-{idx}",
            location_type=t,
        )
        assert loc.type == t


# 4. location status accepts ACTIVE/INACTIVE
def test_04_location_status_accepts_active_inactive(db_session: Session) -> None:
    loc1 = _create_location(db_session, code="STATUS-ACT", status="ACTIVE")
    loc2 = _create_location(db_session, code="STATUS-INACT", status="INACTIVE")
    assert loc1.status == "ACTIVE"
    assert loc2.status == "INACTIVE"


# 5. invalid location status is rejected
def test_05_invalid_location_status_is_rejected(db_session: Session) -> None:
    loc = InventoryLocation(
        name="Invalid Status Loc",
        code="LOC-INV-STATUS",
        type="WAREHOUSE",
        address_line_1="Line 1",
        city="Pune",
        state="Maharashtra",
        postal_code="411001",
        status="PENDING",
    )
    db_session.add(loc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 6. location can have multiple inventory lots
def test_06_location_can_have_multiple_inventory_lots(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    v1 = _create_variant(db_session, prod.id, sku="SKU-LOC-1")
    v2 = _create_variant(db_session, prod.id, sku="SKU-LOC-2")
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    lot1 = _create_lot(db_session, batch.id, v1.id, loc.id, quantity=Decimal("50.000"))
    lot2 = _create_lot(db_session, batch.id, v2.id, loc.id, quantity=Decimal("80.000"))

    db_session.refresh(loc)
    lot_ids = {item.id for item in loc.lots}
    assert lot1.id in lot_ids
    assert lot2.id in lot_ids


# ==============================================================================
# INVENTORY LOTS
# ==============================================================================


# 7. inventory lot can be created
def test_07_inventory_lot_can_be_created(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    lot = _create_lot(
        db_session,
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=loc.id,
        quantity=Decimal("120.500"),
        status="ACTIVE",
    )
    assert lot.id is not None
    assert lot.batch_id == batch.id
    assert lot.variant_id == variant.id
    assert lot.location_id == loc.id
    assert lot.quantity == Decimal("120.500")
    assert lot.status == "ACTIVE"
    assert lot.created_at is not None
    assert lot.updated_at is not None


# 8. inventory lot requires valid batch
def test_08_inventory_lot_requires_valid_batch(db_session: Session) -> None:
    user = _create_user(db_session)
    _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    loc = _create_location(db_session)

    invalid_lot = InventoryLot(
        batch_id=999999,
        variant_id=variant.id,
        location_id=loc.id,
        quantity=Decimal("10.000"),
        status="ACTIVE",
    )
    db_session.add(invalid_lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 9. inventory lot requires valid variant
def test_09_inventory_lot_requires_valid_variant(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    invalid_lot = InventoryLot(
        batch_id=batch.id,
        variant_id=999999,
        location_id=loc.id,
        quantity=Decimal("10.000"),
        status="ACTIVE",
    )
    db_session.add(invalid_lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 10. inventory lot requires valid location
def test_10_inventory_lot_requires_valid_location(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)

    invalid_lot = InventoryLot(
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=999999,
        quantity=Decimal("10.000"),
        status="ACTIVE",
    )
    db_session.add(invalid_lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 11. quantity can be zero
def test_11_inventory_lot_quantity_can_be_zero(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    zero_lot = _create_lot(
        db_session,
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=loc.id,
        quantity=Decimal("0.000"),
        status="DEPLETED",
    )
    assert zero_lot.quantity == Decimal("0.000")
    assert zero_lot.status == "DEPLETED"


# 12. negative quantity is rejected
def test_12_inventory_lot_negative_quantity_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    neg_lot = InventoryLot(
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=loc.id,
        quantity=Decimal("-0.001"),
        status="ACTIVE",
    )
    db_session.add(neg_lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 13. valid status values work
def test_13_inventory_lot_valid_status_values(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    batch = _create_batch(db_session, farm.id, prod.id)

    statuses = ["ACTIVE", "INACTIVE", "DEPLETED"]
    for idx, st in enumerate(statuses):
        v = _create_variant(db_session, prod.id, sku=f"SKU-STATUS-{idx}")
        loc = _create_location(db_session, code=f"LOC-STATUS-{idx}")
        lot = _create_lot(
            db_session,
            batch_id=batch.id,
            variant_id=v.id,
            location_id=loc.id,
            status=st,
        )
        assert lot.status == st


# 14. invalid status is rejected
def test_14_inventory_lot_invalid_status_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    inv_lot = InventoryLot(
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=loc.id,
        quantity=Decimal("10.000"),
        status="ARCHIVED",
    )
    db_session.add(inv_lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 15. batch + variant + location combination is unique
def test_15_batch_variant_location_combination_is_unique(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    assert lot.id is not None


# 16. duplicate batch + variant + location is rejected
def test_16_duplicate_batch_variant_location_is_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    _create_lot(db_session, batch.id, variant.id, loc.id)

    dup_lot = InventoryLot(
        batch_id=batch.id,
        variant_id=variant.id,
        location_id=loc.id,
        quantity=Decimal("20.000"),
        status="ACTIVE",
    )
    db_session.add(dup_lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 17. batch can have multiple inventory lots across locations
def test_17_batch_can_have_multiple_inventory_lots_across_locations(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc1 = _create_location(db_session, code="LOC-CROSS-1")
    loc2 = _create_location(db_session, code="LOC-CROSS-2")

    lot1 = _create_lot(db_session, batch.id, variant.id, loc1.id)
    lot2 = _create_lot(db_session, batch.id, variant.id, loc2.id)
    assert lot1.id != lot2.id
    assert lot1.batch_id == lot2.batch_id


# 18. variant can have multiple inventory lots
def test_18_variant_can_have_multiple_inventory_lots(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    b1 = _create_batch(db_session, farm.id, prod.id, batch_code="BATCH-V-1")
    b2 = _create_batch(db_session, farm.id, prod.id, batch_code="BATCH-V-2")
    loc = _create_location(db_session)

    lot1 = _create_lot(db_session, b1.id, variant.id, loc.id)
    lot2 = _create_lot(db_session, b2.id, variant.id, loc.id)
    assert lot1.id != lot2.id
    assert lot1.variant_id == lot2.variant_id


# 19. location can have multiple inventory lots
def test_19_location_can_have_multiple_inventory_lots(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    v1 = _create_variant(db_session, prod.id, sku="SKU-L-1")
    v2 = _create_variant(db_session, prod.id, sku="SKU-L-2")
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)

    lot1 = _create_lot(db_session, batch.id, v1.id, loc.id)
    lot2 = _create_lot(db_session, batch.id, v2.id, loc.id)
    assert lot1.location_id == loc.id
    assert lot2.location_id == loc.id


# ==============================================================================
# STOCK MOVEMENTS
# ==============================================================================


# 20. movement can be created
def test_20_stock_movement_can_be_created(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    movement = _create_movement(
        db_session,
        inventory_lot_id=lot.id,
        performed_by_user_id=user.id,
        movement_type="RECEIPT",
        quantity=Decimal("75.000"),
        reference_type="INWARD_DELIVERY",
        reference_id=456,
        remarks="Produce received from Otur farm",
    )
    assert movement.id is not None
    assert movement.inventory_lot_id == lot.id
    assert movement.performed_by_user_id == user.id
    assert movement.movement_type == "RECEIPT"
    assert movement.quantity == Decimal("75.000")
    assert movement.reference_type == "INWARD_DELIVERY"
    assert movement.reference_id == 456
    assert movement.remarks == "Produce received from Otur farm"
    assert movement.occurred_at is not None
    assert movement.created_at is not None


# 21. movement requires valid inventory lot
def test_21_stock_movement_requires_valid_inventory_lot(db_session: Session) -> None:
    user = _create_user(db_session)
    inv_mov = StockMovement(
        inventory_lot_id=999999,
        movement_type="RECEIPT",
        quantity=Decimal("10.000"),
        performed_by_user_id=user.id,
        occurred_at=datetime.now(UTC),
    )
    db_session.add(inv_mov)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 22. movement requires valid performing user
def test_22_stock_movement_requires_valid_performing_user(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    inv_mov = StockMovement(
        inventory_lot_id=lot.id,
        movement_type="RECEIPT",
        quantity=Decimal("10.000"),
        performed_by_user_id=999999,
        occurred_at=datetime.now(UTC),
    )
    db_session.add(inv_mov)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 23. positive quantity is accepted
def test_23_stock_movement_positive_quantity_accepted(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    m1 = _create_movement(
        db_session, lot.id, user.id, quantity=Decimal("0.001"), movement_type="ADJUSTMENT_IN"
    )
    m2 = _create_movement(
        db_session, lot.id, user.id, quantity=Decimal("999999.999"), movement_type="RECEIPT"
    )
    assert m1.quantity == Decimal("0.001")
    assert m2.quantity == Decimal("999999.999")


# 24. zero quantity is rejected
def test_24_stock_movement_zero_quantity_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    zero_mov = StockMovement(
        inventory_lot_id=lot.id,
        movement_type="RECEIPT",
        quantity=Decimal("0.000"),
        performed_by_user_id=user.id,
        occurred_at=datetime.now(UTC),
    )
    db_session.add(zero_mov)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 25. negative quantity is rejected
def test_25_stock_movement_negative_quantity_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    neg_mov = StockMovement(
        inventory_lot_id=lot.id,
        movement_type="DAMAGE",
        quantity=Decimal("-10.000"),
        performed_by_user_id=user.id,
        occurred_at=datetime.now(UTC),
    )
    db_session.add(neg_mov)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 26. valid movement types are accepted
def test_26_valid_stock_movement_types(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    valid_types = [
        "RECEIPT",
        "ADJUSTMENT_IN",
        "ADJUSTMENT_OUT",
        "DAMAGE",
        "WASTE",
        "TRANSFER_IN",
        "TRANSFER_OUT",
        "DISPATCH",
    ]
    for m_type in valid_types:
        m = _create_movement(
            db_session,
            inventory_lot_id=lot.id,
            performed_by_user_id=user.id,
            movement_type=m_type,
            quantity=Decimal("5.000"),
        )
        assert m.movement_type == m_type


# 27. invalid movement type is rejected
def test_27_invalid_stock_movement_type_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    invalid_mov = StockMovement(
        inventory_lot_id=lot.id,
        movement_type="RETURN",
        quantity=Decimal("5.000"),
        performed_by_user_id=user.id,
        occurred_at=datetime.now(UTC),
    )
    db_session.add(invalid_mov)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 28. reference_type is optional
def test_28_stock_movement_reference_type_is_optional(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    m = _create_movement(
        db_session,
        lot.id,
        user.id,
        reference_type=None,
        reference_id=123,
    )
    assert m.reference_type is None
    assert m.reference_id == 123


# 29. reference_id is optional
def test_29_stock_movement_reference_id_is_optional(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    m = _create_movement(
        db_session,
        lot.id,
        user.id,
        reference_type="ADHOC_AUDIT",
        reference_id=None,
    )
    assert m.reference_type == "ADHOC_AUDIT"
    assert m.reference_id is None


# 30. occurred_at is stored correctly
def test_30_stock_movement_occurred_at_stored_correctly(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    event_time = datetime(2026, 9, 8, 14, 30, 0, tzinfo=UTC)
    m = _create_movement(db_session, lot.id, user.id, occurred_at=event_time)
    assert m.occurred_at == event_time


# 31. remarks are optional
def test_31_stock_movement_remarks_are_optional(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    m = _create_movement(db_session, lot.id, user.id, remarks=None)
    assert m.remarks is None


# 32. stock movement does NOT have updated_at
def test_32_stock_movement_does_not_have_updated_at(test_engine) -> None:
    inspector = inspect(test_engine)
    columns = {col["name"] for col in inspector.get_columns("stock_movements")}
    assert "updated_at" not in columns
    assert not hasattr(StockMovement, "updated_at")


# ==============================================================================
# RELATIONSHIPS
# ==============================================================================


# 33. InventoryLocation -> InventoryLot
def test_33_relationship_inventory_location_to_lots(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    db_session.refresh(loc)
    assert len(loc.lots) == 1
    assert loc.lots[0].id == lot.id


# 34. InventoryLot -> Batch
def test_34_relationship_inventory_lot_to_batch(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    assert lot.batch is not None
    assert lot.batch.id == batch.id
    assert lot.batch.batch_code == batch.batch_code


# 35. InventoryLot -> ProductVariant
def test_35_relationship_inventory_lot_to_variant(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    assert lot.variant is not None
    assert lot.variant.id == variant.id
    assert lot.variant.sku == variant.sku


# 36. InventoryLot -> Location
def test_36_relationship_inventory_lot_to_location(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    assert lot.location is not None
    assert lot.location.id == loc.id
    assert lot.location.code == loc.code


# 37. InventoryLot -> StockMovement
def test_37_relationship_inventory_lot_to_movements(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    m1 = _create_movement(db_session, lot.id, user.id, movement_type="RECEIPT")
    m2 = _create_movement(db_session, lot.id, user.id, movement_type="DAMAGE")

    db_session.refresh(lot)
    movement_ids = {m.id for m in lot.movements}
    assert m1.id in movement_ids
    assert m2.id in movement_ids


# 38. StockMovement -> InventoryLot
def test_38_relationship_stock_movement_to_inventory_lot(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    movement = _create_movement(db_session, lot.id, user.id)

    assert movement.inventory_lot is not None
    assert movement.inventory_lot.id == lot.id


# 39. StockMovement -> User
def test_39_relationship_stock_movement_to_user(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    movement = _create_movement(db_session, lot.id, user.id)

    assert movement.performed_by_user is not None
    assert movement.performed_by_user.id == user.id
    assert movement.performed_by_user.email == user.email


# ==============================================================================
# DELETE BEHAVIOR (ON DELETE RESTRICT)
# ==============================================================================


# 40. deleting a batch referenced by inventory is restricted
def test_40_deleting_batch_referenced_by_inventory_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    _create_lot(db_session, batch.id, variant.id, loc.id)

    db_session.delete(batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 41. deleting a variant referenced by inventory is restricted
def test_41_deleting_variant_referenced_by_inventory_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    _create_lot(db_session, batch.id, variant.id, loc.id)

    db_session.delete(variant)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 42. deleting a location referenced by inventory is restricted
def test_42_deleting_location_referenced_by_inventory_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    _create_lot(db_session, batch.id, variant.id, loc.id)

    db_session.delete(loc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 43. deleting an inventory lot referenced by movements is restricted
def test_43_deleting_inventory_lot_referenced_by_movements_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    _create_movement(db_session, lot.id, user.id)

    db_session.delete(lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 44. deleting a user referenced by stock movements is restricted
def test_44_deleting_user_referenced_by_stock_movements_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    _create_movement(db_session, lot.id, user.id)

    db_session.delete(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# SCHEMA INTROSPECTION & SAFETY
# ==============================================================================


# 45. inventory_locations table exists
def test_45_inventory_locations_table_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    assert "inventory_locations" in inspector.get_table_names()


# 46. inventory_lots table exists
def test_46_inventory_lots_table_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    assert "inventory_lots" in inspector.get_table_names()


# 47. stock_movements table exists
def test_47_stock_movements_table_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    assert "stock_movements" in inspector.get_table_names()


# 48. expected foreign keys exist
def test_48_expected_foreign_keys_exist(test_engine) -> None:
    inspector = inspect(test_engine)

    # inventory_lots FKs
    lot_fks = inspector.get_foreign_keys("inventory_lots")
    batch_fk = next(
        (fk for fk in lot_fks if fk["constrained_columns"] == ["batch_id"]), None
    )
    assert batch_fk is not None
    assert batch_fk["referred_table"] == "batches"
    assert batch_fk["referred_columns"] == ["id"]
    assert batch_fk["options"].get("ondelete") == "RESTRICT"

    variant_fk = next(
        (fk for fk in lot_fks if fk["constrained_columns"] == ["variant_id"]), None
    )
    assert variant_fk is not None
    assert variant_fk["referred_table"] == "product_variants"
    assert variant_fk["referred_columns"] == ["id"]
    assert variant_fk["options"].get("ondelete") == "RESTRICT"

    loc_fk = next(
        (fk for fk in lot_fks if fk["constrained_columns"] == ["location_id"]), None
    )
    assert loc_fk is not None
    assert loc_fk["referred_table"] == "inventory_locations"
    assert loc_fk["referred_columns"] == ["id"]
    assert loc_fk["options"].get("ondelete") == "RESTRICT"

    # stock_movements FKs
    sm_fks = inspector.get_foreign_keys("stock_movements")
    lot_mov_fk = next(
        (fk for fk in sm_fks if fk["constrained_columns"] == ["inventory_lot_id"]), None
    )
    assert lot_mov_fk is not None
    assert lot_mov_fk["referred_table"] == "inventory_lots"
    assert lot_mov_fk["referred_columns"] == ["id"]
    assert lot_mov_fk["options"].get("ondelete") == "RESTRICT"

    user_mov_fk = next(
        (fk for fk in sm_fks if fk["constrained_columns"] == ["performed_by_user_id"]),
        None,
    )
    assert user_mov_fk is not None
    assert user_mov_fk["referred_table"] == "users"
    assert user_mov_fk["referred_columns"] == ["id"]
    assert user_mov_fk["options"].get("ondelete") == "RESTRICT"


# 49. expected indexes exist
def test_49_expected_indexes_exist(test_engine) -> None:
    inspector = inspect(test_engine)

    def get_index_names(table: str) -> set[str]:
        return {idx["name"] for idx in inspector.get_indexes(table)}

    loc_indexes = get_index_names("inventory_locations")
    assert "ix_inventory_locations_type" in loc_indexes
    assert "ix_inventory_locations_status" in loc_indexes

    lot_indexes = get_index_names("inventory_lots")
    assert "ix_inventory_lots_batch_id" in lot_indexes
    assert "ix_inventory_lots_variant_id" in lot_indexes
    assert "ix_inventory_lots_location_id" in lot_indexes
    assert "ix_inventory_lots_status" in lot_indexes

    sm_indexes = get_index_names("stock_movements")
    assert "ix_stock_movements_inventory_lot_id" in sm_indexes
    assert "ix_stock_movements_performed_by_user_id" in sm_indexes
    assert "ix_stock_movements_movement_type" in sm_indexes
    assert "ix_stock_movements_occurred_at" in sm_indexes


# 50. unique batch/variant/location constraint exists
def test_50_unique_batch_variant_location_constraint_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    unique_constraints = inspector.get_unique_constraints("inventory_lots")
    lot_uq = next(
        (
            uq
            for uq in unique_constraints
            if set(uq["column_names"]) == {"batch_id", "variant_id", "location_id"}
        ),
        None,
    )
    assert lot_uq is not None
    assert lot_uq["name"] == "uq_inventory_lots_batch_variant_location"


# 51. movement quantity CHECK exists
def test_51_movement_quantity_check_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    checks = inspector.get_check_constraints("stock_movements")
    qty_check = next((ck for ck in checks if "quantity > 0" in ck["sqltext"]), None)
    assert qty_check is not None
    assert qty_check["name"] == "ck_stock_movements_quantity"


# 52. inventory quantity CHECK exists
def test_52_inventory_quantity_check_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    checks = inspector.get_check_constraints("inventory_lots")
    qty_check = next((ck for ck in checks if "quantity >= 0" in ck["sqltext"]), None)
    assert qty_check is not None
    assert qty_check["name"] == "ck_inventory_lots_quantity"


# 53. movement type CHECK exists
def test_53_movement_type_check_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    checks = inspector.get_check_constraints("stock_movements")
    type_check = next(
        (ck for ck in checks if ck["name"] == "ck_stock_movements_movement_type"), None
    )
    assert type_check is not None
    for expected_type in [
        "RECEIPT",
        "ADJUSTMENT_IN",
        "ADJUSTMENT_OUT",
        "DAMAGE",
        "WASTE",
        "TRANSFER_IN",
        "TRANSFER_OUT",
        "DISPATCH",
    ]:
        assert expected_type in type_check["sqltext"]


# 54. inventory status CHECK exists
def test_54_inventory_status_check_exists(test_engine) -> None:
    inspector = inspect(test_engine)

    # inventory_locations status
    loc_checks = inspector.get_check_constraints("inventory_locations")
    loc_status_check = next(
        (ck for ck in loc_checks if ck["name"] == "ck_inventory_locations_status"),
        None,
    )
    assert loc_status_check is not None
    assert "ACTIVE" in loc_status_check["sqltext"]
    assert "INACTIVE" in loc_status_check["sqltext"]

    # inventory_lots status
    lot_checks = inspector.get_check_constraints("inventory_lots")
    lot_status_check = next(
        (ck for ck in lot_checks if ck["name"] == "ck_inventory_lots_status"),
        None,
    )
    assert lot_status_check is not None
    assert "ACTIVE" in lot_status_check["sqltext"]
    assert "INACTIVE" in lot_status_check["sqltext"]
    assert "DEPLETED" in lot_status_check["sqltext"]


# 55. no PostgreSQL ENUMs were created
def test_55_no_postgresql_enums_created(test_engine) -> None:
    with test_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT t.typname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typtype = 'e' AND n.nspname = 'public';"
            )
        ).fetchall()
        assert len(result) == 0, f"Found unexpected PostgreSQL ENUM types: {result}"


# 56. no future-domain tables were accidentally introduced
def test_56_no_future_domain_tables_accidentally_introduced(test_engine) -> None:
    inspector = inspect(test_engine)
    all_tables = set(inspector.get_table_names())

    unwanted_tables = {
        "processing",
        "packing",
        "preparation",
        "reservations",
        "delivery",
        "promotions",
        "coupons",
        "reviews",
        # "suppliers" removed from this blocklist in Phase 17 - see
        # test_phase_3_models.py's equivalent note.
        "procurement",
        "warehouses",
        "stock_snapshots",
        "stock_reservations",
    }
    found_unwanted = unwanted_tables.intersection(all_tables)
    assert not found_unwanted, f"Unwanted future tables found: {found_unwanted}"
