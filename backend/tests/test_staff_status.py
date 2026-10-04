"""PATCH /staff/{id}/status - an admin must not be able to lock themselves
out, because nobody could undo it from the panel afterwards."""

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.roles import ADMIN, HUB_STAFF
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from tests.firebase_fake import auth_headers_for


def _staff(db_session: Session, role_name: str, email: str, phone: str) -> User:
    role = db_session.query(Role).filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db_session.add(role)
        db_session.flush()
    user = User(name=f"{role_name.title()} User", email=email, phone=phone, status="ACTIVE")
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id, is_primary=True))
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_cannot_deactivate_or_suspend_own_account(client: TestClient, db_session: Session):
    admin = _staff(db_session, ADMIN, "self-lock@example.com", "+919800000101")
    headers = auth_headers_for(db_session, admin)

    for new_status in ("INACTIVE", "SUSPENDED"):
        response = client.patch(f"/api/v1/staff/{admin.id}/status", json={"status": new_status}, headers=headers)
        assert response.status_code == 409, response.text

    db_session.refresh(admin)
    assert admin.status == "ACTIVE"


def test_admin_can_still_deactivate_another_staff_member(client: TestClient, db_session: Session):
    admin = _staff(db_session, ADMIN, "admin-status@example.com", "+919800000102")
    other = _staff(db_session, HUB_STAFF, "hub-status@example.com", "+919800000103")

    response = client.patch(
        f"/api/v1/staff/{other.id}/status",
        json={"status": "INACTIVE"},
        headers=auth_headers_for(db_session, admin),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "INACTIVE"
