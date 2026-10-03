"""Admin-assisted customer account changes.

With no email/SMS channel in the codebase (Resend and every verification-
code flow were removed), an ADMIN changes a customer's email/phone and
resets their password directly:

- PATCH /customers/{id}/contact   (customers.manage_contact)
- POST  /customers/{id}/password  (customers.reset_password)

Both are ADMIN-only, audit-logged, and must never be reachable by a role
lacking the permission (SUPPORT is the interesting case - it can view
customers but not change them).
"""

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, CUSTOMER, HUB_STAFF, SUPPORT
from app.core.security import hash_password, verify_password
from app.models.admin_action_log import AdminActionLog
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from tests.firebase_fake import auth_headers_for, fake_firebase

CUSTOMER_PASSWORD = "CustomerPass123"


def _role(db_session: Session, name: str) -> Role:
    role = db_session.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db_session.add(role)
        db_session.commit()
        db_session.refresh(role)
    return role


def _user(db_session: Session, role_name: str, email: str, phone: str) -> User:
    user = User(
        name=f"{role_name.title()} User",
        email=email,
        phone=phone,
        password_hash=hash_password(CUSTOMER_PASSWORD),
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=_role(db_session, role_name).id, is_primary=True))
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(db_session: Session, user: User) -> dict[str, str]:
    return auth_headers_for(db_session, user)


def _setup(db_session: Session) -> tuple[User, dict[str, str], User, dict[str, str]]:
    admin = _user(db_session, ADMIN, "admin-acct@example.com", "+919800000001")
    customer = _user(db_session, CUSTOMER, "customer-acct@example.com", "+919800000002")
    return admin, _headers(db_session, admin), customer, _headers(db_session, customer)


def _audit(db_session: Session, action: str) -> list[AdminActionLog]:
    db_session.expire_all()
    return db_session.query(AdminActionLog).filter_by(action=action).all()


# ---------------------------------------------------------------------------
# Contact details
# ---------------------------------------------------------------------------


def test_admin_changes_customer_email_directly(client: TestClient, db_session: Session) -> None:
    admin, admin_h, customer, _ = _setup(db_session)

    resp = client.patch(
        f"/api/v1/customers/{customer.id}/contact",
        json={"field": "email", "new_value": "  New.Address@Example.com ", "reason": "verified by phone"},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "new.address@example.com"

    [log] = _audit(db_session, "customer.email_changed")
    assert log.admin_user_id == admin.id
    assert log.resource_id == customer.id
    assert log.previous_state == "customer-acct@example.com"
    assert log.new_state == "new.address@example.com"
    assert log.reason == "verified by phone"


def test_admin_changes_customer_phone_normalized(client: TestClient, db_session: Session) -> None:
    _, admin_h, customer, _ = _setup(db_session)

    resp = client.patch(
        f"/api/v1/customers/{customer.id}/contact",
        json={"field": "PHONE", "new_value": "98765-11111"},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone"] == "+919876511111"
    assert len(_audit(db_session, "customer.phone_changed")) == 1


def test_contact_change_rejects_value_owned_by_another_account(
    client: TestClient, db_session: Session
) -> None:
    _, admin_h, customer, _ = _setup(db_session)
    _user(db_session, CUSTOMER, "taken@example.com", "+919800000003")

    resp = client.patch(
        f"/api/v1/customers/{customer.id}/contact",
        json={"field": "EMAIL", "new_value": "TAKEN@example.com"},
        headers=admin_h,
    )
    assert resp.status_code == 409
    db_session.expire_all()
    assert db_session.get(User, customer.id).email == "customer-acct@example.com"


def test_contact_change_validation(client: TestClient, db_session: Session) -> None:
    _, admin_h, customer, _ = _setup(db_session)
    url = f"/api/v1/customers/{customer.id}/contact"

    same = client.patch(url, json={"field": "EMAIL", "new_value": "customer-acct@example.com"}, headers=admin_h)
    assert same.status_code == 422
    bad_field = client.patch(url, json={"field": "NAME", "new_value": "Someone Else"}, headers=admin_h)
    assert bad_field.status_code == 422
    bad_phone = client.patch(url, json={"field": "PHONE", "new_value": "not-a-phone"}, headers=admin_h)
    assert bad_phone.status_code == 422
    assert _audit(db_session, "customer.email_changed") == []


def test_contact_change_forbidden_without_permission(client: TestClient, db_session: Session) -> None:
    _, _, customer, customer_h = _setup(db_session)
    support = _user(db_session, SUPPORT, "support-acct@example.com", "+919800000004")
    url = f"/api/v1/customers/{customer.id}/contact"
    body = {"field": "EMAIL", "new_value": "hijack@example.com"}

    assert client.patch(url, json=body, headers=_headers(db_session, support)).status_code == 403
    assert client.patch(url, json=body, headers=customer_h).status_code == 403
    assert client.patch(url, json=body).status_code == 401


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def test_admin_resets_customer_password_and_signs_them_out(
    client: TestClient, db_session: Session
) -> None:
    admin, admin_h, customer, customer_h = _setup(db_session)
    assert client.get("/api/v1/auth/me", headers=customer_h).status_code == 200

    resp = client.post(
        f"/api/v1/customers/{customer.id}/password",
        json={"new_password": "BrandNewPass456", "reason": "customer called support"},
        headers=admin_h,
    )
    assert resp.status_code == 204, resp.text

    # Firebase holds the new credential and every device is signed out.
    assert fake_firebase.users[customer.firebase_uid]["password"] == "BrandNewPass456"
    assert customer.firebase_uid in fake_firebase.revoked

    [log] = _audit(db_session, "customer.password_reset")
    assert log.admin_user_id == admin.id
    assert log.resource_id == customer.id
    assert log.reason == "customer called support"
    # The password itself must never land in the audit trail.
    assert "BrandNewPass456" not in f"{log.previous_state} {log.new_state} {log.reason}"


def test_password_reset_rules(client: TestClient, db_session: Session) -> None:
    _, admin_h, customer, _ = _setup(db_session)
    staff = _user(db_session, HUB_STAFF, "hub-acct@example.com", "+919800000005")

    too_short = client.post(
        f"/api/v1/customers/{customer.id}/password", json={"new_password": "short"}, headers=admin_h
    )
    assert too_short.status_code == 422
    # Only CUSTOMER accounts - staff passwords aren't reset through this route.
    not_customer = client.post(
        f"/api/v1/customers/{staff.id}/password", json={"new_password": "LongEnough123"}, headers=admin_h
    )
    assert not_customer.status_code == 404
    missing = client.post(
        "/api/v1/customers/999999/password", json={"new_password": "LongEnough123"}, headers=admin_h
    )
    assert missing.status_code == 404
    assert _audit(db_session, "customer.password_reset") == []


def test_password_reset_forbidden_without_permission(client: TestClient, db_session: Session) -> None:
    _, _, customer, customer_h = _setup(db_session)
    support = _user(db_session, SUPPORT, "support2-acct@example.com", "+919800000006")
    url = f"/api/v1/customers/{customer.id}/password"
    body = {"new_password": "TakeOver12345"}

    assert client.post(url, json=body, headers=_headers(db_session, support)).status_code == 403
    assert client.post(url, json=body, headers=customer_h).status_code == 403
    assert client.post(url, json=body).status_code == 401
    assert customer.firebase_uid not in fake_firebase.users  # credential untouched


def test_admin_reset_of_unmigrated_customer_updates_legacy_password(
    client: TestClient, db_session: Session
) -> None:
    """A customer who has not signed in since the Firebase cutover has no
    Firebase user yet - the reset sets the password their one-time
    migration will be checked against."""
    admin = _user(db_session, ADMIN, "admin-legacy@example.com", "+919800000011")
    admin_h = _headers(db_session, admin)
    customer = _user(db_session, CUSTOMER, "legacy-reset@example.com", "+919800000012")

    resp = client.post(
        f"/api/v1/customers/{customer.id}/password",
        json={"new_password": "LegacyNewPass789"},
        headers=admin_h,
    )
    assert resp.status_code == 204, resp.text
    db_session.expire_all()
    assert verify_password("LegacyNewPass789", db_session.get(User, customer.id).password_hash)

    migrated = client.post(
        "/api/v1/auth/legacy-migrate",
        json={"identifier": "legacy-reset@example.com", "password": "LegacyNewPass789"},
    )
    assert migrated.status_code == 200, migrated.text
