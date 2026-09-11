"""Phase 9 focused validation: baseline role initialization and RBAC.

Per project policy this is focused validation only, not full regression.
Two independent concerns are covered:

1. Role initialization (migration 37bbdf459894): baseline roles exist and
   the seeding mechanism is idempotent. These tests use `test_engine`
   directly (no `db_session`) because `db_session` truncates `roles` before
   each test - that truncation is intentional per-test isolation and is
   orthogonal to verifying what the migration itself seeds.

2. RBAC (`require_roles` in app.dependencies.auth): authentication vs.
   authorization separation, 401 vs 403 behavior, and any-of-multiple-roles
   semantics. These tests use `db_session` and construct their own
   Users/Roles/UserRoles directly, consistent with the existing test_auth.py
   pattern.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import (
    ADMIN,
    BASELINE_ROLES,
    CUSTOMER,
    DELIVERY_PARTNER,
    HUB_STAFF,
    OPERATIONS,
    WHOLESALER,
)
from app.core.security import hash_password
from app.dependencies.auth import require_roles
from app.exceptions.base import AuthorizationError
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

# ---------------------------------------------------------------------------
# Part 1: Role initialization (migration-seeded reference data)
# ---------------------------------------------------------------------------


def test_1_baseline_roles_seeded_by_migration(test_engine) -> None:
    """All six active roles exist after `alembic upgrade head`."""
    with test_engine.connect() as conn:
        names = {
            row[0]
            for row in conn.execute(text("SELECT name FROM roles")).fetchall()
        }

    assert BASELINE_ROLES == (
        CUSTOMER,
        WHOLESALER,
        ADMIN,
        HUB_STAFF,
        OPERATIONS,
        DELIVERY_PARTNER,
    )
    for role_name in BASELINE_ROLES:
        assert role_name in names, f"{role_name} role missing after migration"

    # Farmer is a future capability, not an active role.
    assert "FARMER" not in names


def test_2_role_seeding_is_idempotent(test_engine) -> None:
    """Re-running the seed INSERT does not duplicate rows or error."""
    with test_engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM roles")).scalar()

        conn.execute(
            text(
                "INSERT INTO roles (name, description) VALUES "
                "('CUSTOMER', 'Retail customer.'), "
                "('WHOLESALER', 'Supply partner.'), "
                "('ADMIN', 'Superuser.'), "
                "('HUB_STAFF', 'Hub staff.'), "
                "('OPERATIONS', 'Operations staff.'), "
                "('DELIVERY_PARTNER', 'Delivery partner.') "
                "ON CONFLICT (name) DO NOTHING"
            )
        )
        conn.commit()

        after = conn.execute(text("SELECT COUNT(*) FROM roles")).scalar()

    assert before == after, "Re-seeding must not create duplicate role rows"


# ---------------------------------------------------------------------------
# Part 2: RBAC (require_roles)
# ---------------------------------------------------------------------------


def _create_role(db_session: Session, name: str) -> Role:
    role = db_session.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db_session.add(role)
        db_session.commit()
        db_session.refresh(role)
    return role


def _create_user_with_roles(
    db_session: Session, *role_names: str, email: str = "rbac_user@example.com"
) -> User:
    user = User(
        name="RBAC Test User",
        email=email,
        phone=f"+9198{abs(hash(email)) % 100000000:08d}",
        password_hash=hash_password("SecurePass123"),
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()

    for idx, role_name in enumerate(role_names):
        role = _create_role(db_session, role_name)
        db_session.add(
            UserRole(user_id=user.id, role_id=role.id, is_primary=(idx == 0))
        )
    db_session.commit()
    db_session.refresh(user)
    return user


def test_3_user_with_required_role_is_authorized(db_session: Session) -> None:
    user = _create_user_with_roles(db_session, ADMIN, email="admin1@example.com")
    checker = require_roles(ADMIN)

    result = checker(current_user=user, db=db_session)

    assert result is user


def test_4_user_without_required_role_is_forbidden(db_session: Session) -> None:
    user = _create_user_with_roles(db_session, CUSTOMER, email="cust1@example.com")
    checker = require_roles(ADMIN)

    try:
        checker(current_user=user, db=db_session)
        raised = False
    except AuthorizationError as exc:
        raised = True
        assert exc.status_code == 403
        assert exc.code == "AUTHORIZATION_ERROR"

    assert raised, "Expected AuthorizationError (403) for missing role"


def test_5_any_of_multiple_required_roles_is_sufficient(db_session: Session) -> None:
    user = _create_user_with_roles(
        db_session, OPERATIONS, email="ops1@example.com"
    )
    checker = require_roles(ADMIN, OPERATIONS)

    result = checker(current_user=user, db=db_session)

    assert result is user


def test_6_user_with_multiple_roles_satisfies_either_requirement(
    db_session: Session,
) -> None:
    user = _create_user_with_roles(
        db_session, WHOLESALER, OPERATIONS, email="multi1@example.com"
    )

    assert require_roles(WHOLESALER)(current_user=user, db=db_session) is user
    assert require_roles(OPERATIONS)(current_user=user, db=db_session) is user
    assert require_roles(ADMIN, OPERATIONS)(current_user=user, db=db_session) is user

    try:
        require_roles(ADMIN, DELIVERY_PARTNER)(current_user=user, db=db_session)
        raised = False
    except AuthorizationError:
        raised = True
    assert raised, "User has neither ADMIN nor DELIVERY_PARTNER role"


def test_7_unauthenticated_request_receives_401(client: TestClient) -> None:
    """Reuses the existing protected /auth/me endpoint (get_current_user)."""
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_ERROR"


# ---------------------------------------------------------------------------
# Part 3: Public registration remains CUSTOMER-only
# ---------------------------------------------------------------------------


def test_8_public_registration_ignores_client_supplied_role(
    client: TestClient, db_session: Session
) -> None:
    _create_role(db_session, CUSTOMER)
    _create_role(db_session, ADMIN)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Attempted Elevation",
            "email": "elevate@example.com",
            "phone": "9876543210",
            "password": "SecurePass123",
            "role": "ADMIN",
        },
    )

    assert response.status_code == 201
    user_id = response.json()["user"]["id"]

    assigned_roles = (
        db_session.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .all()
    )
    role_names = {r[0] for r in assigned_roles}

    assert role_names == {CUSTOMER}, (
        f"Expected registration to assign only CUSTOMER, got {role_names}"
    )
