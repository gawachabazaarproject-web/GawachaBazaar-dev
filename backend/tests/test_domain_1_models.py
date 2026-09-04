from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.address import Address
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


def test_1_role_persistence(db_session: Session) -> None:
    """Verify that a Role can be successfully persisted."""
    role = Role(name="CUSTOMER", description="Retail customer")
    db_session.add(role)
    db_session.commit()

    saved = db_session.query(Role).filter_by(name="CUSTOMER").first()
    assert saved is not None
    assert saved.id is not None
    assert saved.name == "CUSTOMER"
    assert saved.created_at is not None
    assert saved.updated_at is not None


def test_2_role_uniqueness(db_session: Session) -> None:
    """Verify that duplicate role names are rejected."""
    r1 = Role(name="FARMER", description="Farmer role")
    db_session.add(r1)
    db_session.commit()

    r2 = Role(name="FARMER", description="Duplicate farmer role")
    db_session.add(r2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_3_user_persistence(db_session: Session) -> None:
    """Verify that a User can be successfully persisted."""
    user = User(
        name="Ramesh Kumar",
        email="ramesh@example.com",
        phone="+919876543210",
        password_hash=hash_password("SecurePass123!"),
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()

    saved = db_session.query(User).filter_by(email="ramesh@example.com").first()
    assert saved is not None
    assert saved.id is not None
    assert saved.name == "Ramesh Kumar"
    assert saved.status == "ACTIVE"


def test_4_user_email_uniqueness(db_session: Session) -> None:
    """Verify that duplicate email addresses are rejected."""
    u1 = User(
        name="User One",
        email="duplicate@example.com",
        phone="+919876543201",
        password_hash="hashed_pw_1",
    )
    db_session.add(u1)
    db_session.commit()

    u2 = User(
        name="User Two",
        email="duplicate@example.com",
        phone="+919876543202",
        password_hash="hashed_pw_2",
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_5_user_phone_uniqueness(db_session: Session) -> None:
    """Verify that duplicate phone numbers are rejected."""
    u1 = User(
        name="User One",
        email="user1@example.com",
        phone="+919876543299",
        password_hash="hashed_pw_1",
    )
    db_session.add(u1)
    db_session.commit()

    u2 = User(
        name="User Two",
        email="user2@example.com",
        phone="+919876543299",
        password_hash="hashed_pw_2",
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_6_user_valid_status(db_session: Session) -> None:
    """Verify all valid user statuses (ACTIVE, INACTIVE, SUSPENDED)."""
    for idx, valid_status in enumerate(["ACTIVE", "INACTIVE", "SUSPENDED"]):
        user = User(
            name=f"Status User {idx}",
            email=f"status{idx}@example.com",
            phone=f"+91980000000{idx}",
            password_hash="hash",
            status=valid_status,
        )
        db_session.add(user)
    db_session.commit()

    count = db_session.query(User).count()
    assert count == 3


def test_7_user_invalid_status_rejected(db_session: Session) -> None:
    """Verify that invalid user status values are rejected by check constraint."""
    user = User(
        name="Bad Status User",
        email="badstatus@example.com",
        phone="+919876543288",
        password_hash="hash",
        status="PENDING_APPROVAL",  # Not in ('ACTIVE', 'INACTIVE', 'SUSPENDED')
    )
    db_session.add(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_8_user_role_persistence(db_session: Session) -> None:
    """Verify that UserRole links a user and a role."""
    user = User(
        name="Test User",
        email="testur@example.com",
        phone="+919876543255",
        password_hash="hash",
    )
    role = Role(name="DELIVERY_PARTNER")
    db_session.add_all([user, role])
    db_session.commit()

    user_role = UserRole(user_id=user.id, role_id=role.id, is_primary=True)
    db_session.add(user_role)
    db_session.commit()

    saved = (
        db_session.query(UserRole).filter_by(user_id=user.id, role_id=role.id).first()
    )
    assert saved is not None
    assert saved.is_primary is True


def test_9_user_multiple_roles_allowed(db_session: Session) -> None:
    """Verify a user can hold multiple distinct roles."""
    user = User(
        name="Multi Role User",
        email="multirole@example.com",
        phone="+919876543244",
        password_hash="hash",
    )
    r1 = Role(name="CUSTOMER")
    r2 = Role(name="FARMER")
    db_session.add_all([user, r1, r2])
    db_session.commit()

    ur1 = UserRole(user_id=user.id, role_id=r1.id, is_primary=True)
    ur2 = UserRole(user_id=user.id, role_id=r2.id, is_primary=False)
    db_session.add_all([ur1, ur2])
    db_session.commit()

    roles_assigned = db_session.query(UserRole).filter_by(user_id=user.id).all()
    assert len(roles_assigned) == 2


def test_10_duplicate_user_role_rejected(db_session: Session) -> None:
    """Verify duplicate assignment of same role to same user is rejected."""
    user = User(
        name="User Duplicate Role",
        email="dup_ur@example.com",
        phone="+919876543233",
        password_hash="hash",
    )
    role = Role(name="ADMIN")
    db_session.add_all([user, role])
    db_session.commit()

    ur1 = UserRole(user_id=user.id, role_id=role.id, is_primary=False)
    db_session.add(ur1)
    db_session.commit()

    ur2 = UserRole(user_id=user.id, role_id=role.id, is_primary=False)
    db_session.add(ur2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_11_multiple_primary_roles_rejected(db_session: Session) -> None:
    """Verify database partial unique index rejects multiple primary roles for one user."""
    user = User(
        name="Primary Role Test",
        email="prim_role@example.com",
        phone="+919876543222",
        password_hash="hash",
    )
    r1 = Role(name="ROLE_A")
    r2 = Role(name="ROLE_B")
    db_session.add_all([user, r1, r2])
    db_session.commit()

    ur1 = UserRole(user_id=user.id, role_id=r1.id, is_primary=True)
    db_session.add(ur1)
    db_session.commit()

    # Second role also marked is_primary=True for the same user -> violates partial index
    ur2 = UserRole(user_id=user.id, role_id=r2.id, is_primary=True)
    db_session.add(ur2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_12_user_multiple_addresses_allowed(db_session: Session) -> None:
    """Verify a user can have multiple physical addresses."""
    user = User(
        name="Address User",
        email="addr_user@example.com",
        phone="+919876543211",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()

    a1 = Address(
        user_id=user.id,
        label="Home",
        address_line_1="123 Farm Road",
        city="Pune",
        state="Maharashtra",
        postal_code="411001",
        is_default=True,
    )
    a2 = Address(
        user_id=user.id,
        label="Farm Office",
        address_line_1="Plot 45 Green Valley",
        city="Pune",
        state="Maharashtra",
        postal_code="411002",
        is_default=False,
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    addresses = db_session.query(Address).filter_by(user_id=user.id).all()
    assert len(addresses) == 2


def test_13_multiple_default_addresses_rejected(db_session: Session) -> None:
    """Verify partial unique index rejects multiple default addresses for one user."""
    user = User(
        name="Default Address Test",
        email="def_addr@example.com",
        phone="+919876543200",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()

    a1 = Address(
        user_id=user.id,
        label="Address 1",
        address_line_1="10 Market St",
        city="Pune",
        state="Maharashtra",
        postal_code="411001",
        is_default=True,
    )
    db_session.add(a1)
    db_session.commit()

    # Second address also marked is_default=True -> violates partial index
    a2 = Address(
        user_id=user.id,
        label="Address 2",
        address_line_1="20 Bazaar Lane",
        city="Pune",
        state="Maharashtra",
        postal_code="411001",
        is_default=True,
    )
    db_session.add(a2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_14_address_foreign_key_constraint(db_session: Session) -> None:
    """Verify address cannot be created with non-existent user_id."""
    invalid_address = Address(
        user_id=9999999,  # Non-existent user ID
        label="Ghost Address",
        address_line_1="Nowhere Street",
        city="Pune",
        state="Maharashtra",
        postal_code="411001",
    )
    db_session.add(invalid_address)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_15_users_table_does_not_contain_role_id() -> None:
    """Verify critical architectural invariant: users table MUST NOT have role_id."""
    columns = [c.name for c in User.__table__.columns]
    assert "role_id" not in columns, (
        "Critical error: role_id must NOT exist on users table!"
    )
    assert "id" in columns
    assert "name" in columns
    assert "email" in columns
    assert "phone" in columns
    assert "password_hash" in columns
    assert "status" in columns


def test_16_password_hash_stored_not_plaintext(db_session: Session) -> None:
    """Verify that password is saved strictly as an Argon2 hash, never plaintext."""
    plaintext = "SuperSecretPassword123"
    hashed = hash_password(plaintext)

    user = User(
        name="Crypto User",
        email="crypto@example.com",
        phone="+919876543111",
        password_hash=hashed,
    )
    db_session.add(user)
    db_session.commit()

    saved = db_session.query(User).filter_by(email="crypto@example.com").first()
    assert saved is not None
    assert saved.password_hash != plaintext
    assert saved.password_hash.startswith("$argon2")


def test_17_orm_relationships(db_session: Session) -> None:
    """Verify that SQLAlchemy 2 ORM relationships navigate accurately."""
    user = User(
        name="Relationship User",
        email="rel@example.com",
        phone="+919876543122",
        password_hash="hash",
    )
    role = Role(name="SUPPLIER", description="Supply partner")
    db_session.add_all([user, role])
    db_session.commit()

    # Link role and add address
    user_role = UserRole(user=user, role=role, is_primary=True)
    address = Address(
        user=user,
        label="Warehouse 1",
        address_line_1="Highway 48",
        city="Pune",
        state="Maharashtra",
        postal_code="411038",
        latitude=Decimal("18.520430"),
        longitude=Decimal("73.856744"),
        is_default=True,
    )
    db_session.add_all([user_role, address])
    db_session.commit()

    # Re-query user
    queried_user = db_session.query(User).filter_by(email="rel@example.com").first()
    assert queried_user is not None
    assert len(queried_user.user_roles) == 1
    assert queried_user.user_roles[0].role.name == "SUPPLIER"
    assert len(queried_user.addresses) == 1
    assert queried_user.addresses[0].city == "Pune"
    assert queried_user.addresses[0].latitude == Decimal("18.520430")

    # Navigate from user_role to user and role
    queried_ur = queried_user.user_roles[0]
    assert queried_ur.user.email == "rel@example.com"
    assert queried_ur.role.name == "SUPPLIER"

    # Navigate from address to user
    queried_addr = queried_user.addresses[0]
    assert queried_addr.user.name == "Relationship User"
