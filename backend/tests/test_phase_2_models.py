from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.category import Category
from app.models.farm import Farm
from app.models.product import Product
from app.models.quality_check import QualityCheck
from app.models.user import User


def _create_user(
    db_session: Session,
    email: str = "farmer@example.com",
    phone: str = "+919876543200",
) -> User:
    """Helper to create a valid user for testing."""
    user = User(
        name="Kisan Rao",
        email=email,
        phone=phone,
        password_hash="hash",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_farm(
    db_session: Session,
    owner_user_id: int,
    name: str = "Green Valley Farm",
) -> Farm:
    """Helper to create a valid farm for testing."""
    farm = Farm(
        owner_user_id=owner_user_id,
        name=name,
        address_line_1="Farm Plot 101",
        village="Khed",
        city="Pune",
        state="Maharashtra",
        postal_code="410501",
        latitude=Decimal("18.845600"),
        longitude=Decimal("73.912300"),
        contact_number="+919876543210",
        status="ACTIVE",
    )
    db_session.add(farm)
    db_session.commit()
    return farm


def _create_product(db_session: Session) -> Product:
    """Helper to create a valid product for batch testing."""
    cat = db_session.query(Category).first()
    if not cat:
        cat = Category(name="Test Produce", slug="test-produce", status="ACTIVE")
        db_session.add(cat)
        db_session.flush()
    prod = db_session.query(Product).first()
    if not prod:
        prod = Product(
            category_id=cat.id,
            name="Test Tomato",
            slug="test-tomato",
            status="ACTIVE",
        )
        db_session.add(prod)
        db_session.flush()
    return prod


def _create_batch(
    db_session: Session,
    farm_id: int,
    batch_code: str = "BATCH-2026-001",
    product_id: int | None = None,
) -> Batch:
    """Helper to create a valid batch for testing."""
    if product_id is None:
        product_id = _create_product(db_session).id
    batch = Batch(
        farm_id=farm_id,
        product_id=product_id,
        batch_code=batch_code,
        harvest_date=date(2026, 9, 1),
        expiry_date=date(2026, 9, 10),
        quantity=Decimal("250.500"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(batch)
    db_session.commit()
    return batch


# 1. Farm can be created for an existing user
def test_1_farm_creation(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)

    assert farm.id is not None
    assert farm.owner_user_id == user.id
    assert farm.name == "Green Valley Farm"
    assert farm.status == "ACTIVE"
    assert farm.created_at is not None
    assert farm.updated_at is not None


# 2. Multiple farms can belong to one user
def test_2_multiple_farms_per_user(db_session: Session) -> None:
    user = _create_user(db_session)
    f1 = _create_farm(db_session, user.id, name="North Farm")
    f2 = _create_farm(db_session, user.id, name="South Farm")

    farms = db_session.query(Farm).filter_by(owner_user_id=user.id).all()
    assert len(farms) == 2
    assert {f.id for f in farms} == {f1.id, f2.id}


# 3. Farm requires owner_user_id (non-nullable / FK)
def test_3_farm_requires_owner(db_session: Session) -> None:
    farm = Farm(
        owner_user_id=999999,  # Non-existent owner
        name="Ghost Farm",
        address_line_1="Nowhere",
        village="Ghost Village",
        city="Pune",
        state="Maharashtra",
        postal_code="410501",
        status="ACTIVE",
    )
    db_session.add(farm)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 4. Farm status CHECK works
def test_4_farm_status_check(db_session: Session) -> None:
    user = _create_user(db_session)

    # Valid statuses
    for s in ["ACTIVE", "INACTIVE", "SUSPENDED"]:
        farm = Farm(
            owner_user_id=user.id,
            name=f"Farm {s}",
            address_line_1="Line 1",
            village="Village",
            city="City",
            state="State",
            postal_code="410501",
            status=s,
        )
        db_session.add(farm)
    db_session.commit()
    assert db_session.query(Farm).count() == 3

    # Invalid status
    invalid_farm = Farm(
        owner_user_id=user.id,
        name="Invalid Status Farm",
        address_line_1="Line 1",
        village="Village",
        city="City",
        state="State",
        postal_code="410501",
        status="PENDING_APPROVAL",
    )
    db_session.add(invalid_farm)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 5. Farm latitude validation works (-90 to 90)
def test_5_farm_latitude_bounds(db_session: Session) -> None:
    user = _create_user(db_session)

    invalid_lat_farm = Farm(
        owner_user_id=user.id,
        name="Bad Latitude Farm",
        address_line_1="Line 1",
        village="Village",
        city="City",
        state="State",
        postal_code="410501",
        latitude=Decimal("95.123456"),  # Out of range (> 90)
        longitude=Decimal("73.123456"),
        status="ACTIVE",
    )
    db_session.add(invalid_lat_farm)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 6. Farm longitude validation works (-180 to 180)
def test_6_farm_longitude_bounds(db_session: Session) -> None:
    user = _create_user(db_session)

    invalid_lng_farm = Farm(
        owner_user_id=user.id,
        name="Bad Longitude Farm",
        address_line_1="Line 1",
        village="Village",
        city="City",
        state="State",
        postal_code="410501",
        latitude=Decimal("18.123456"),
        longitude=Decimal("-185.000000"),  # Out of range (< -180)
        status="ACTIVE",
    )
    db_session.add(invalid_lng_farm)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 7. Batch can be created for an existing farm
def test_7_batch_creation(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    batch = _create_batch(db_session, farm.id)

    assert batch.id is not None
    assert batch.farm_id == farm.id
    assert batch.batch_code == "BATCH-2026-001"
    assert batch.quantity == Decimal("250.500")
    assert batch.unit == "KG"
    assert batch.status == "HARVESTED"
    assert batch.created_at is not None
    assert batch.updated_at is not None


# 8. Batch_code must be unique
def test_8_batch_code_uniqueness(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    _create_batch(db_session, farm.id, batch_code="UNIQUE-001")

    prod = _create_product(db_session)
    duplicate_batch = Batch(
        farm_id=farm.id,
        product_id=prod.id,
        batch_code="UNIQUE-001",
        harvest_date=date(2026, 9, 2),
        quantity=Decimal("100.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(duplicate_batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 9. Batch quantity must be greater than zero
def test_9_batch_quantity_positive(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)

    prod = _create_product(db_session)
    # Zero quantity
    zero_batch = Batch(
        farm_id=farm.id,
        product_id=prod.id,
        batch_code="ZERO-001",
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("0.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(zero_batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Negative quantity
    neg_batch = Batch(
        farm_id=farm.id,
        product_id=prod.id,
        batch_code="NEG-001",
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("-10.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(neg_batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 10. Batch expiry_date cannot precede harvest_date
def test_10_batch_expiry_after_harvest(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)

    prod = _create_product(db_session)
    invalid_expiry_batch = Batch(
        farm_id=farm.id,
        product_id=prod.id,
        batch_code="EXP-INVALID",
        harvest_date=date(2026, 9, 10),
        expiry_date=date(2026, 9, 5),  # Expiry earlier than harvest!
        quantity=Decimal("50.000"),
        unit="KG",
        status="HARVESTED",
    )
    db_session.add(invalid_expiry_batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 11. Batch status CHECK works
def test_11_batch_status_check(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)

    valid_statuses = [
        "HARVESTED",
        "COLLECTED",
        "SORTED",
        "GRADED",
        "APPROVED",
        "REJECTED",
        "EXPIRED",
    ]
    prod = _create_product(db_session)
    for idx, s in enumerate(valid_statuses):
        b = Batch(
            farm_id=farm.id,
            product_id=prod.id,
            batch_code=f"BATCH-STATUS-{idx}",
            harvest_date=date(2026, 9, 1),
            quantity=Decimal("10.000"),
            unit="KG",
            status=s,
        )
        db_session.add(b)
    db_session.commit()
    assert db_session.query(Batch).count() == 7

    invalid_b = Batch(
        farm_id=farm.id,
        product_id=prod.id,
        batch_code="BATCH-INVALID-STATUS",
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("10.000"),
        unit="KG",
        status="IN_TRANSIT",  # Not in allowed lifecycle values
    )
    db_session.add(invalid_b)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 12. Batch unit CHECK works
def test_12_batch_unit_check(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)

    valid_units = ["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "CRATE"]
    prod = _create_product(db_session)
    for idx, u in enumerate(valid_units):
        b = Batch(
            farm_id=farm.id,
            product_id=prod.id,
            batch_code=f"BATCH-UNIT-{idx}",
            harvest_date=date(2026, 9, 1),
            quantity=Decimal("1.000"),
            unit=u,
            status="HARVESTED",
        )
        db_session.add(b)
    db_session.commit()
    assert db_session.query(Batch).count() == len(valid_units)

    invalid_u = Batch(
        farm_id=farm.id,
        product_id=prod.id,
        batch_code="BATCH-INVALID-UNIT",
        harvest_date=date(2026, 9, 1),
        quantity=Decimal("10.000"),
        unit="POUND",  # Not in allowed units
        status="HARVESTED",
    )
    db_session.add(invalid_u)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 13. Quality check can be created for a batch
# 14. Quality check references the checking user
# 15. Quality check status CHECK works
def test_13_14_15_quality_check(db_session: Session) -> None:
    farmer = _create_user(
        db_session, email="farmer1@example.com", phone="+919876543001"
    )
    inspector = _create_user(
        db_session, email="inspector@example.com", phone="+919876543002"
    )
    farm = _create_farm(db_session, farmer.id)
    batch = _create_batch(db_session, farm.id)

    now = datetime.now(UTC)
    qc = QualityCheck(
        batch_id=batch.id,
        checked_by_user_id=inspector.id,
        checked_on=now,
        status="PASSED",
        remarks="Grade A fresh produce, zero defects",
    )
    db_session.add(qc)
    db_session.commit()

    saved_qc = db_session.query(QualityCheck).filter_by(batch_id=batch.id).first()
    assert saved_qc is not None
    assert saved_qc.id is not None
    assert saved_qc.checked_by_user_id == inspector.id
    assert saved_qc.status == "PASSED"
    assert saved_qc.remarks == "Grade A fresh produce, zero defects"
    assert saved_qc.created_at is not None

    # Invalid status
    bad_qc = QualityCheck(
        batch_id=batch.id,
        checked_by_user_id=inspector.id,
        checked_on=now,
        status="VERIFIED",  # Not in ('PENDING', 'PASSED', 'FAILED')
    )
    db_session.add(bad_qc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 16. Foreign-key relationships work
def test_16_orm_relationships(db_session: Session) -> None:
    farmer = _create_user(db_session, email="kisan@example.com", phone="+919876543003")
    inspector = _create_user(db_session, email="qa@example.com", phone="+919876543004")
    farm = _create_farm(db_session, farmer.id, name="Sunset Orchards")
    batch = _create_batch(db_session, farm.id, batch_code="ORCHARD-B1")
    qc = QualityCheck(
        batch=batch,
        checked_by_user=inspector,
        checked_on=datetime.now(UTC),
        status="PASSED",
        remarks="Excellent quality",
    )
    db_session.add(qc)
    db_session.commit()

    # Verify farmer -> farms
    f = db_session.query(User).filter_by(email="kisan@example.com").first()
    assert f is not None
    assert len(f.farms) == 1
    assert f.farms[0].name == "Sunset Orchards"

    # Verify farm -> batches and batch -> farm
    assert len(f.farms[0].batches) == 1
    assert f.farms[0].batches[0].batch_code == "ORCHARD-B1"
    assert f.farms[0].batches[0].farm.name == "Sunset Orchards"

    # Verify batch -> quality_checks and quality_check -> batch
    b = f.farms[0].batches[0]
    assert len(b.quality_checks) == 1
    assert b.quality_checks[0].status == "PASSED"
    assert b.quality_checks[0].batch.batch_code == "ORCHARD-B1"

    # Verify quality_check -> checked_by_user and user -> quality_checks_performed
    assert b.quality_checks[0].checked_by_user.email == "qa@example.com"
    qa_user = db_session.query(User).filter_by(email="qa@example.com").first()
    assert qa_user is not None
    assert len(qa_user.quality_checks_performed) == 1
    assert qa_user.quality_checks_performed[0].status == "PASSED"


# 17. Deleting a farm referenced by a batch is rejected (ON DELETE RESTRICT)
def test_17_restrict_farm_deletion_with_batches(db_session: Session) -> None:
    user = _create_user(db_session)
    farm = _create_farm(db_session, user.id)
    _create_batch(db_session, farm.id)

    db_session.delete(farm)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 18. Deleting a batch referenced by a quality check is rejected (ON DELETE RESTRICT)
def test_18_restrict_batch_deletion_with_quality_checks(db_session: Session) -> None:
    farmer = _create_user(db_session, email="f_del@example.com", phone="+919876543005")
    inspector = _create_user(
        db_session, email="qa_del@example.com", phone="+919876543006"
    )
    farm = _create_farm(db_session, farmer.id)
    batch = _create_batch(db_session, farm.id)
    qc = QualityCheck(
        batch_id=batch.id,
        checked_by_user_id=inspector.id,
        checked_on=datetime.now(UTC),
        status="PENDING",
    )
    db_session.add(qc)
    db_session.commit()

    db_session.delete(batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 19. Deleting a user referenced as farm owner is rejected (ON DELETE RESTRICT)
def test_19_restrict_user_deletion_with_farms(db_session: Session) -> None:
    user = _create_user(
        db_session, email="owner_del@example.com", phone="+919876543007"
    )
    _create_farm(db_session, user.id)

    db_session.delete(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 20. Deleting a user referenced as quality checker is rejected (ON DELETE RESTRICT)
def test_20_restrict_user_deletion_with_quality_checks(db_session: Session) -> None:
    farmer = _create_user(db_session, email="f_qc@example.com", phone="+919876543008")
    inspector = _create_user(
        db_session, email="qa_del2@example.com", phone="+919876543009"
    )
    farm = _create_farm(db_session, farmer.id)
    batch = _create_batch(db_session, farm.id)
    qc = QualityCheck(
        batch_id=batch.id,
        checked_by_user_id=inspector.id,
        checked_on=datetime.now(UTC),
        status="PASSED",
    )
    db_session.add(qc)
    db_session.commit()

    db_session.delete(inspector)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
