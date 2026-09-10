from datetime import UTC, date, datetime, timedelta
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
from app.models.packaging_input import PackagingInput
from app.models.packaging_operation import PackagingOperation
from app.models.packaging_output import PackagingOutput
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "pack.operator@example.com",
    phone: str = "+919876555001",
) -> User:
    """Helper to create a user for testing."""
    user = User(
        name="Sunita Patil",
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
    name: str = "Wardha Organic Orchards",
) -> Farm:
    """Helper to create a farm for testing."""
    farm = Farm(
        owner_user_id=owner_user_id,
        name=name,
        address_line_1="Farm Plot 108",
        village="Seloo",
        city="Wardha",
        state="Maharashtra",
        postal_code="442104",
        latitude=Decimal("20.835000"),
        longitude=Decimal("78.705000"),
        contact_number="+919876555002",
        status="ACTIVE",
    )
    db_session.add(farm)
    db_session.commit()
    return farm


def _create_category(
    db_session: Session,
    name: str = "Fresh Citrus Fruits",
    slug: str = "fresh-citrus-fruits",
) -> Category:
    """Helper to create a category for testing."""
    category = Category(
        name=name,
        slug=slug,
        status="ACTIVE",
        description="Naturally ripened citrus",
    )
    db_session.add(category)
    db_session.commit()
    return category


def _create_product(
    db_session: Session,
    category_id: int,
    name: str = "Nagpur Orange",
    slug: str = "nagpur-orange",
) -> Product:
    """Helper to create a product for testing."""
    product = Product(
        category_id=category_id,
        name=name,
        slug=slug,
        status="ACTIVE",
        description="Juicy GI-tagged Nagpur oranges",
    )
    db_session.add(product)
    db_session.commit()
    return product


def _create_variant(
    db_session: Session,
    product_id: int,
    name: str = "2 KG Gift Box",
    sku: str = "ORANGE-NAG-2KG",
    unit: str = "KG",
    quantity: Decimal = Decimal("2.000"),
) -> ProductVariant:
    """Helper to create a product variant for testing."""
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
    batch_code: str = "BATCH-ORANGE-2026-01",
    quantity: Decimal = Decimal("1000.000"),
) -> Batch:
    """Helper to create a harvest batch for testing."""
    batch = Batch(
        farm_id=farm_id,
        product_id=product_id,
        batch_code=batch_code,
        harvest_date=date(2026, 9, 1),
        expiry_date=date(2026, 10, 1),
        quantity=quantity,
        unit="KG",
        status="APPROVED",
    )
    db_session.add(batch)
    db_session.commit()
    return batch


def _create_location(
    db_session: Session,
    name: str = "Nagpur Central Hub",
    code: str = "NGP-HUB-01",
    location_type: str = "PACKING_FACILITY",
    status: str = "ACTIVE",
) -> InventoryLocation:
    """Helper to create an inventory location for testing."""
    location = InventoryLocation(
        name=name,
        code=code,
        type=location_type,
        address_line_1="MIDC Butibori Industrial Area",
        city="Nagpur",
        state="Maharashtra",
        postal_code="441122",
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
    quantity: Decimal = Decimal("500.000"),
    status: str = "ACTIVE",
) -> InventoryLot:
    """Helper to create an inventory lot for testing."""
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


def _create_operation(
    db_session: Session,
    location_id: int,
    performed_by_user_id: int,
    packaging_code: str = "PKG-2026-0001",
    name: str = "Orange Festive Gift Packaging",
    status: str = "DRAFT",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    remarks: str | None = "Commercial packaging for festive dispatch",
) -> PackagingOperation:
    """Helper to create a packaging operation for testing."""
    if started_at is None:
        started_at = datetime.now(UTC)
    operation = PackagingOperation(
        packaging_code=packaging_code,
        name=name,
        location_id=location_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        performed_by_user_id=performed_by_user_id,
        remarks=remarks,
    )
    db_session.add(operation)
    db_session.commit()
    return operation


def _create_input(
    db_session: Session,
    packaging_operation_id: int,
    inventory_lot_id: int,
    quantity: Decimal = Decimal("50.000"),
) -> PackagingInput:
    """Helper to create a packaging input record."""
    inp = PackagingInput(
        packaging_operation_id=packaging_operation_id,
        inventory_lot_id=inventory_lot_id,
        quantity=quantity,
    )
    db_session.add(inp)
    db_session.commit()
    return inp


def _create_output(
    db_session: Session,
    packaging_operation_id: int,
    inventory_lot_id: int,
    package_count: int = 25,
    total_quantity: Decimal = Decimal("50.000"),
) -> PackagingOutput:
    """Helper to create a packaging output record."""
    out = PackagingOutput(
        packaging_operation_id=packaging_operation_id,
        inventory_lot_id=inventory_lot_id,
        package_count=package_count,
        total_quantity=total_quantity,
    )
    db_session.add(out)
    db_session.commit()
    return out


# ==============================================================================
# 1. PACKAGING OPERATIONS TESTS
# ==============================================================================


def test_01_packaging_operations_table_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    assert "packaging_operations" in inspector.get_table_names()


def test_02_packaging_operations_pk_is_bigint_identity(test_engine) -> None:
    inspector = inspect(test_engine)
    pk = inspector.get_pk_constraint("packaging_operations")
    assert pk["constrained_columns"] == ["id"]
    cols = {col["name"]: col for col in inspector.get_columns("packaging_operations")}
    assert cols["id"]["type"].python_type is int
    assert cols["id"]["identity"] is not None


def test_03_packaging_code_is_unique(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    _create_operation(db_session, loc.id, user.id, packaging_code="PKG-UNIQUE-01")

    dup = PackagingOperation(
        packaging_code="PKG-UNIQUE-01",
        name="Duplicate Packaging Code Operation",
        location_id=loc.id,
        status="DRAFT",
        started_at=datetime.now(UTC),
        performed_by_user_id=user.id,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_04_packaging_operation_name_is_required(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = PackagingOperation(
        packaging_code="PKG-NAME-REQ",
        name=None,  # type: ignore[arg-type]
        location_id=loc.id,
        status="DRAFT",
        started_at=datetime.now(UTC),
        performed_by_user_id=user.id,
    )
    db_session.add(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_05_packaging_operation_location_fk_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    op = PackagingOperation(
        packaging_code="PKG-LOC-FK",
        name="Missing Location Op",
        location_id=999999,
        status="DRAFT",
        started_at=datetime.now(UTC),
        performed_by_user_id=user.id,
    )
    db_session.add(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_06_packaging_operation_performed_by_user_fk_exists(
    db_session: Session,
) -> None:
    loc = _create_location(db_session)
    op = PackagingOperation(
        packaging_code="PKG-USER-FK",
        name="Missing User Op",
        location_id=loc.id,
        status="DRAFT",
        started_at=datetime.now(UTC),
        performed_by_user_id=999999,
    )
    db_session.add(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_07_all_four_operation_statuses_are_accepted(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    statuses = ["DRAFT", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
    for idx, st in enumerate(statuses):
        op = _create_operation(
            db_session,
            loc.id,
            user.id,
            packaging_code=f"PKG-ST-{idx}",
            status=st,
        )
        assert op.status == st


def test_08_invalid_operation_status_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = PackagingOperation(
        packaging_code="PKG-INV-ST",
        name="Invalid Status Op",
        location_id=loc.id,
        status="PACKAGED",  # Invalid status
        started_at=datetime.now(UTC),
        performed_by_user_id=user.id,
    )
    db_session.add(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_09_started_at_is_required(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = PackagingOperation(
        packaging_code="PKG-START-REQ",
        name="Missing started_at Op",
        location_id=loc.id,
        status="DRAFT",
        started_at=None,  # type: ignore[arg-type]
        performed_by_user_id=user.id,
    )
    db_session.add(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_10_completed_at_is_nullable(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = _create_operation(
        db_session,
        loc.id,
        user.id,
        packaging_code="PKG-COMP-NULL",
        completed_at=None,
    )
    assert op.completed_at is None


def test_11_completed_at_greater_or_equal_started_at_enforced(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    start_time = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)

    # Equal is valid
    op_eq = _create_operation(
        db_session,
        loc.id,
        user.id,
        packaging_code="PKG-DATE-EQ",
        started_at=start_time,
        completed_at=start_time,
    )
    assert op_eq.completed_at == start_time

    # Greater is valid
    op_gt = _create_operation(
        db_session,
        loc.id,
        user.id,
        packaging_code="PKG-DATE-GT",
        started_at=start_time,
        completed_at=start_time + timedelta(hours=2),
    )
    assert op_gt.completed_at > op_gt.started_at

    # Earlier is rejected
    op_invalid = PackagingOperation(
        packaging_code="PKG-DATE-INV",
        name="Invalid Completion Time Op",
        location_id=loc.id,
        status="COMPLETED",
        started_at=start_time,
        completed_at=start_time - timedelta(hours=1),
        performed_by_user_id=user.id,
    )
    db_session.add(op_invalid)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_12_created_at_and_updated_at_exist(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = _create_operation(db_session, loc.id, user.id, packaging_code="PKG-TIME-01")
    assert op.created_at is not None
    assert op.updated_at is not None


def test_13_packaging_operations_indexes_exist(test_engine) -> None:
    inspector = inspect(test_engine)
    idx_names = {idx["name"] for idx in inspector.get_indexes("packaging_operations")}
    assert "ix_packaging_operations_location_id" in idx_names
    assert "ix_packaging_operations_status" in idx_names
    assert "ix_packaging_operations_started_at" in idx_names


# ==============================================================================
# 2. PACKAGING INPUTS TESTS
# ==============================================================================


def test_14_packaging_inputs_table_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    assert "packaging_inputs" in inspector.get_table_names()


def test_15_packaging_inputs_pk_is_bigint_identity(test_engine) -> None:
    inspector = inspect(test_engine)
    pk = inspector.get_pk_constraint("packaging_inputs")
    assert pk["constrained_columns"] == ["id"]
    cols = {col["name"]: col for col in inspector.get_columns("packaging_inputs")}
    assert cols["id"]["type"].python_type is int
    assert cols["id"]["identity"] is not None


def test_16_packaging_input_operation_fk_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    inp = PackagingInput(
        packaging_operation_id=999999,
        inventory_lot_id=lot.id,
        quantity=Decimal("10.000"),
    )
    db_session.add(inp)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_17_packaging_input_lot_fk_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = _create_operation(db_session, loc.id, user.id)

    inp = PackagingInput(
        packaging_operation_id=op.id,
        inventory_lot_id=999999,
        quantity=Decimal("10.000"),
    )
    db_session.add(inp)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_18_packaging_input_quantity_required(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    inp = PackagingInput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        quantity=None,  # type: ignore[arg-type]
    )
    db_session.add(inp)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_19_packaging_input_positive_quantity_accepted(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    inp = _create_input(db_session, op.id, lot.id, quantity=Decimal("0.001"))
    assert inp.quantity == Decimal("0.001")


def test_20_packaging_input_zero_quantity_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    inp = PackagingInput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        quantity=Decimal("0.000"),
    )
    db_session.add(inp)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_21_packaging_input_negative_quantity_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    inp = PackagingInput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        quantity=Decimal("-5.000"),
    )
    db_session.add(inp)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_22_packaging_input_created_at_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    inp = _create_input(db_session, op.id, lot.id)
    assert inp.created_at is not None


def test_23_packaging_inputs_indexes_exist(test_engine) -> None:
    inspector = inspect(test_engine)
    idx_names = {idx["name"] for idx in inspector.get_indexes("packaging_inputs")}
    assert "ix_packaging_inputs_packaging_operation_id" in idx_names
    assert "ix_packaging_inputs_inventory_lot_id" in idx_names


# ==============================================================================
# 3. PACKAGING OUTPUTS TESTS
# ==============================================================================


def test_24_packaging_outputs_table_exists(test_engine) -> None:
    inspector = inspect(test_engine)
    assert "packaging_outputs" in inspector.get_table_names()


def test_25_packaging_outputs_pk_is_bigint_identity(test_engine) -> None:
    inspector = inspect(test_engine)
    pk = inspector.get_pk_constraint("packaging_outputs")
    assert pk["constrained_columns"] == ["id"]
    cols = {col["name"]: col for col in inspector.get_columns("packaging_outputs")}
    assert cols["id"]["type"].python_type is int
    assert cols["id"]["identity"] is not None


def test_26_packaging_output_operation_fk_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    out = PackagingOutput(
        packaging_operation_id=999999,
        inventory_lot_id=lot.id,
        package_count=10,
        total_quantity=Decimal("20.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_27_packaging_output_lot_fk_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=999999,
        package_count=10,
        total_quantity=Decimal("20.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_28_packaging_output_package_count_required(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        package_count=None,  # type: ignore[arg-type]
        total_quantity=Decimal("20.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_29_packaging_output_package_count_positive_accepted(
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
    op = _create_operation(db_session, loc.id, user.id)

    out = _create_output(db_session, op.id, lot.id, package_count=1)
    assert out.package_count == 1


def test_30_packaging_output_package_count_zero_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        package_count=0,
        total_quantity=Decimal("20.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_31_packaging_output_package_count_negative_rejected(
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
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        package_count=-5,
        total_quantity=Decimal("20.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_32_packaging_output_total_quantity_required(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        package_count=10,
        total_quantity=None,  # type: ignore[arg-type]
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_33_packaging_output_total_quantity_positive_accepted(
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
    op = _create_operation(db_session, loc.id, user.id)

    out = _create_output(
        db_session, op.id, lot.id, package_count=1, total_quantity=Decimal("0.500")
    )
    assert out.total_quantity == Decimal("0.500")


def test_34_packaging_output_total_quantity_zero_rejected(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        package_count=10,
        total_quantity=Decimal("0.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_35_packaging_output_total_quantity_negative_rejected(
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
    op = _create_operation(db_session, loc.id, user.id)

    out = PackagingOutput(
        packaging_operation_id=op.id,
        inventory_lot_id=lot.id,
        package_count=10,
        total_quantity=Decimal("-10.000"),
    )
    db_session.add(out)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_36_packaging_output_created_at_exists(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)
    op = _create_operation(db_session, loc.id, user.id)

    out = _create_output(db_session, op.id, lot.id)
    assert out.created_at is not None


def test_37_packaging_outputs_indexes_exist(test_engine) -> None:
    inspector = inspect(test_engine)
    idx_names = {idx["name"] for idx in inspector.get_indexes("packaging_outputs")}
    assert "ix_packaging_outputs_packaging_operation_id" in idx_names
    assert "ix_packaging_outputs_inventory_lot_id" in idx_names


# ==============================================================================
# 4. RELATIONSHIP TESTS
# ==============================================================================


def test_38_relationship_inventory_location_to_packaging_operations(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = _create_operation(db_session, loc.id, user.id)

    db_session.refresh(loc)
    op_ids = [o.id for o in loc.packaging_operations]
    assert op.id in op_ids


def test_39_relationship_user_to_packaging_operations(db_session: Session) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    op = _create_operation(db_session, loc.id, user.id)

    db_session.refresh(user)
    op_ids = [o.id for o in user.packaging_operations]
    assert op.id in op_ids


def test_40_relationship_packaging_operation_to_inputs_and_outputs(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    v_bulk = _create_variant(db_session, prod.id, sku="BULK-VAR")
    v_retail = _create_variant(db_session, prod.id, sku="RETAIL-VAR")
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot_in = _create_lot(
        db_session, batch.id, v_bulk.id, loc.id, quantity=Decimal("100.000")
    )
    lot_out = _create_lot(
        db_session, batch.id, v_retail.id, loc.id, quantity=Decimal("0.000")
    )

    op = _create_operation(db_session, loc.id, user.id)
    inp = _create_input(db_session, op.id, lot_in.id, quantity=Decimal("40.000"))
    out = _create_output(
        db_session, op.id, lot_out.id, package_count=20, total_quantity=Decimal("40.000")
    )

    db_session.refresh(op)
    assert len(op.inputs) == 1
    assert op.inputs[0].id == inp.id
    assert len(op.outputs) == 1
    assert op.outputs[0].id == out.id
    assert op.location.id == loc.id
    assert op.performed_by.id == user.id


def test_41_relationship_packaging_input_and_output_to_lot(
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
    op = _create_operation(db_session, loc.id, user.id)

    inp = _create_input(db_session, op.id, lot.id)
    out = _create_output(db_session, op.id, lot.id)

    assert inp.operation.id == op.id
    assert inp.inventory_lot.id == lot.id
    assert out.operation.id == op.id
    assert out.inventory_lot.id == lot.id


# ==============================================================================
# 5. DELETE BEHAVIOR (ON DELETE RESTRICT)
# ==============================================================================


def test_42_deleting_location_referenced_by_operation_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    _create_operation(db_session, loc.id, user.id)

    db_session.delete(loc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_43_deleting_user_referenced_by_operation_is_restricted(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    loc = _create_location(db_session)
    _create_operation(db_session, loc.id, user.id)

    db_session.delete(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_44_deleting_operation_referenced_by_inputs_is_restricted(
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
    op = _create_operation(db_session, loc.id, user.id)
    _create_input(db_session, op.id, lot.id)

    db_session.delete(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_45_deleting_operation_referenced_by_outputs_is_restricted(
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
    op = _create_operation(db_session, loc.id, user.id)
    _create_output(db_session, op.id, lot.id)

    db_session.delete(op)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_46_deleting_lot_referenced_by_packaging_inputs_is_restricted(
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
    op = _create_operation(db_session, loc.id, user.id)
    _create_input(db_session, op.id, lot.id)

    db_session.delete(lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_47_deleting_lot_referenced_by_packaging_outputs_is_restricted(
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
    op = _create_operation(db_session, loc.id, user.id)
    _create_output(db_session, op.id, lot.id)

    db_session.delete(lot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# 6. BUSINESS INVARIANTS & INTEGRATION
# ==============================================================================


def test_48_one_operation_can_consume_multiple_inventory_lots(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    v1 = _create_variant(db_session, prod.id, sku="SKU-MULTI-1")
    v2 = _create_variant(db_session, prod.id, sku="SKU-MULTI-2")
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot1 = _create_lot(db_session, batch.id, v1.id, loc.id)
    lot2 = _create_lot(db_session, batch.id, v2.id, loc.id)

    op = _create_operation(db_session, loc.id, user.id)
    _create_input(db_session, op.id, lot1.id, quantity=Decimal("15.000"))
    _create_input(db_session, op.id, lot2.id, quantity=Decimal("25.000"))

    db_session.refresh(op)
    assert len(op.inputs) == 2


def test_49_one_operation_can_produce_multiple_packaged_outputs(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    v_1kg = _create_variant(db_session, prod.id, sku="SKU-PACK-1KG")
    v_2kg = _create_variant(db_session, prod.id, sku="SKU-PACK-2KG")
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot_1kg = _create_lot(db_session, batch.id, v_1kg.id, loc.id)
    lot_2kg = _create_lot(db_session, batch.id, v_2kg.id, loc.id)

    op = _create_operation(db_session, loc.id, user.id)
    _create_output(
        db_session, op.id, lot_1kg.id, package_count=10, total_quantity=Decimal("10.000")
    )
    _create_output(
        db_session, op.id, lot_2kg.id, package_count=5, total_quantity=Decimal("10.000")
    )

    db_session.refresh(op)
    assert len(op.outputs) == 2


def test_50_multiple_input_records_allowed_for_same_lot(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    variant = _create_variant(db_session, prod.id)
    batch = _create_batch(db_session, farm.id, prod.id)
    loc = _create_location(db_session)
    lot = _create_lot(db_session, batch.id, variant.id, loc.id)

    op = _create_operation(db_session, loc.id, user.id)
    inp1 = _create_input(db_session, op.id, lot.id, quantity=Decimal("10.000"))
    inp2 = _create_input(db_session, op.id, lot.id, quantity=Decimal("15.000"))
    assert inp1.id != inp2.id
    assert inp1.inventory_lot_id == inp2.inventory_lot_id


def test_51_inventory_lot_preserves_batch_traceability(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    cat = _create_category(db_session)
    prod = _create_product(db_session, cat.id)
    v_out = _create_variant(db_session, prod.id, sku="PACKAGED-SKU")
    batch_a = _create_batch(db_session, farm.id, prod.id, batch_code="BATCH-A-ORIGIN")
    batch_b = _create_batch(db_session, farm.id, prod.id, batch_code="BATCH-B-ORIGIN")
    loc = _create_location(db_session)

    # 1 output lot = exactly 1 batch
    lot_a = _create_lot(db_session, batch_a.id, v_out.id, loc.id)
    lot_b = _create_lot(db_session, batch_b.id, v_out.id, loc.id)

    op = _create_operation(db_session, loc.id, user.id)
    out_a = _create_output(
        db_session, op.id, lot_a.id, package_count=5, total_quantity=Decimal("10.000")
    )
    out_b = _create_output(
        db_session, op.id, lot_b.id, package_count=5, total_quantity=Decimal("10.000")
    )

    assert out_a.inventory_lot.batch_id == batch_a.id
    assert out_b.inventory_lot.batch_id == batch_b.id
    assert out_a.inventory_lot.batch_id != out_b.inventory_lot.batch_id


# ==============================================================================
# 7. SCHEMA SAFETY & COLUMN SAFETY
# ==============================================================================


def test_52_no_postgresql_enums_introduced(test_engine) -> None:
    with test_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT t.typname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typtype = 'e' AND n.nspname = 'public';"
            )
        ).fetchall()
        assert len(result) == 0, f"Found unexpected PostgreSQL ENUM types: {result}"


def test_53_no_database_triggers_exist(test_engine) -> None:
    with test_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT tgname, relname FROM pg_trigger tg "
                "JOIN pg_class c ON c.oid = tg.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND NOT tg.tgisinternal;"
            )
        ).fetchall()
        assert len(result) == 0, f"Found unexpected non-internal triggers: {result}"


def test_54_column_safety_no_prohibited_columns(test_engine) -> None:
    inspector = inspect(test_engine)

    # packaging_inputs columns
    inp_cols = {col["name"] for col in inspector.get_columns("packaging_inputs")}
    assert "quantity_per_package" not in inp_cols
    assert "unit" not in inp_cols

    # packaging_outputs columns
    out_cols = {col["name"] for col in inspector.get_columns("packaging_outputs")}
    assert "quantity_per_package" not in out_cols
    assert "unit" not in out_cols
    assert "batch_id" not in out_cols
    assert "product_id" not in out_cols
    assert "variant_id" not in out_cols

    # packaging_operations columns
    op_cols = {col["name"] for col in inspector.get_columns("packaging_operations")}
    assert "label_reference" not in op_cols
    assert "recipe_id" not in op_cols
    assert "bom_id" not in op_cols


def test_55_inventory_lots_schema_and_uniqueness_unchanged(test_engine) -> None:
    inspector = inspect(test_engine)
    lot_cols = {col["name"] for col in inspector.get_columns("inventory_lots")}
    assert "packaging_operation_id" not in lot_cols

    uqs = inspector.get_unique_constraints("inventory_lots")
    lot_uq = next(
        (
            uq
            for uq in uqs
            if set(uq["column_names"]) == {"batch_id", "variant_id", "location_id"}
        ),
        None,
    )
    assert lot_uq is not None
    assert lot_uq["name"] == "uq_inventory_lots_batch_variant_location"


def test_56_no_unwanted_tables_introduced(test_engine) -> None:
    inspector = inspect(test_engine)
    all_tables = set(inspector.get_table_names())

    unwanted_tables = {
        "labels",
        "label_templates",
        "label_versions",
        "label_fields",
        "label_print_jobs",
        "recipes",
        "boms",
        "bill_of_materials",
        "production_batches",
        "manufacturing",
        "processing",
        "package_sizes",
        "package_serials",
        "packages",
        "individual_packages",
        "reservations",
        "delivery",
        "promotions",
        "coupons",
        "reviews",
        "suppliers",
        "procurement",
        "warehouses",
    }
    found_unwanted = unwanted_tables.intersection(all_tables)
    assert not found_unwanted, f"Unwanted tables detected in database: {found_unwanted}"
