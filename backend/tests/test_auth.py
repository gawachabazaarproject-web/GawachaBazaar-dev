import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    normalize_phone,
)
from app.models.auth_session import AuthSession
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


@pytest.fixture(autouse=True)
def seed_customer_role(db_session: Session) -> None:
    """Ensure baseline CUSTOMER role exists in test database."""
    role = db_session.query(Role).filter_by(name="CUSTOMER").first()
    if not role:
        role = Role(name="CUSTOMER", description="Retail customer")
        db_session.add(role)
        db_session.commit()


def test_registration_flow_and_default_customer_role(
    client: TestClient, db_session: Session
) -> None:
    """Verify registration creates user, assigns CUSTOMER role, creates auth_session, and returns tokens."""
    payload = {
        "name": "Arjun Sharma",
        "email": "Arjun.Sharma@Example.Com ",
        "phone": "9876543210",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    # Verify response schema
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    user_data = data["user"]
    assert user_data["name"] == "Arjun Sharma"
    assert user_data["email"] == "arjun.sharma@example.com"
    assert user_data["phone"] == "+919876543210"
    assert user_data["status"] == "ACTIVE"

    # Verify no password or hash in response
    assert "password" not in response.text
    assert "password_hash" not in response.text

    # Verify database state
    user = db_session.query(User).filter_by(email="arjun.sharma@example.com").first()
    assert user is not None
    assert user.phone == "+919876543210"

    # Verify CUSTOMER role was assigned with is_primary=True
    user_roles = db_session.query(UserRole).filter_by(user_id=user.id).all()
    assert len(user_roles) == 1
    role = db_session.query(Role).filter_by(id=user_roles[0].role_id).first()
    assert role.name == "CUSTOMER"
    assert user_roles[0].is_primary is True

    # Verify raw refresh token is NOT in database, only SHA-256 hash
    raw_rt = data["refresh_token"]
    stored_session = db_session.query(AuthSession).filter_by(user_id=user.id).first()
    assert stored_session is not None
    assert stored_session.refresh_token_hash == hash_refresh_token(raw_rt)
    assert stored_session.refresh_token_hash != raw_rt


def test_registration_duplicate_email_and_phone_conflict(client: TestClient) -> None:
    """Verify duplicate email or phone returns HTTP 409 ConflictError without server leak."""
    payload1 = {
        "name": "User One",
        "email": "duplicate@example.com",
        "phone": "9876543211",
        "password": "Password123!",
    }
    r1 = client.post("/api/v1/auth/register", json=payload1)
    assert r1.status_code == 201

    # Duplicate email
    payload_dup_email = {
        "name": "User Two",
        "email": "DUPLICATE@example.com",
        "phone": "9876543212",
        "password": "Password123!",
    }
    r2 = client.post("/api/v1/auth/register", json=payload_dup_email)
    assert r2.status_code == 409
    assert r2.json()["code"] == "CONFLICT_ERROR"

    # Duplicate phone (normalized)
    payload_dup_phone = {
        "name": "User Three",
        "email": "unique@example.com",
        "phone": "+91 9876543211",
        "password": "Password123!",
    }
    r3 = client.post("/api/v1/auth/register", json=payload_dup_phone)
    assert r3.status_code == 409
    assert r3.json()["code"] == "CONFLICT_ERROR"


def test_phone_and_email_normalization_utilities() -> None:
    """Verify phone and email normalization logic."""
    assert normalize_email(" TEST@Example.com ") == "test@example.com"

    # 10 digits
    assert normalize_phone("9876543210") == "+919876543210"
    # Leading zero 11 digits
    assert normalize_phone("09876543210") == "+919876543210"
    # Country code 91
    assert normalize_phone("919876543210") == "+919876543210"
    # Hyphens and spaces
    assert normalize_phone("+91-98765-43210") == "+919876543210"
    assert normalize_phone(" (987) 654-3210 ") == "+919876543210"

    with pytest.raises(ValueError):
        normalize_phone("123")
    with pytest.raises(ValueError):
        normalize_phone("+invalid")


def test_login_by_email_and_by_phone(client: TestClient) -> None:
    """Verify user can authenticate using either normalized email or phone."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Meera Patel",
            "email": "meera@example.com",
            "phone": "9876543220",
            "password": "MeeraSecretPass1!",
        },
    )
    assert reg.status_code == 201

    # Login by email
    l_email = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": " MEERA@example.com ",
            "password": "MeeraSecretPass1!",
        },
    )
    assert l_email.status_code == 200
    assert "access_token" in l_email.json()
    assert l_email.json()["user"]["email"] == "meera@example.com"

    # Login by phone
    l_phone = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "+91-98765-43220",
            "password": "MeeraSecretPass1!",
        },
    )
    assert l_phone.status_code == 200
    assert "access_token" in l_phone.json()
    assert l_phone.json()["user"]["phone"] == "+919876543220"


def test_login_enumeration_protection_generic_error(client: TestClient) -> None:
    """Verify unknown email, unknown phone, and wrong password return identical generic error."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Secret User",
            "email": "secret@example.com",
            "phone": "9876543230",
            "password": "CorrectPassword123!",
        },
    )
    assert reg.status_code == 201

    expected_error = {
        "code": "AUTHENTICATION_ERROR",
        "message": "Invalid credentials.",
        "details": None,
    }

    # Unknown email
    r_unknown_email = client.post(
        "/api/v1/auth/login",
        json={"identifier": "nonexistent@example.com", "password": "AnyPassword"},
    )
    assert r_unknown_email.status_code == 401
    assert r_unknown_email.json() == expected_error

    # Unknown phone
    r_unknown_phone = client.post(
        "/api/v1/auth/login",
        json={"identifier": "9999999999", "password": "AnyPassword"},
    )
    assert r_unknown_phone.status_code == 401
    assert r_unknown_phone.json() == expected_error

    # Wrong password for existing user
    r_wrong_pwd = client.post(
        "/api/v1/auth/login",
        json={"identifier": "secret@example.com", "password": "WrongPassword!"},
    )
    assert r_wrong_pwd.status_code == 401
    assert r_wrong_pwd.json() == expected_error


def test_account_status_enforcement(client: TestClient, db_session: Session) -> None:
    """Verify INACTIVE and SUSPENDED accounts cannot login, refresh, or access /me."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Status User",
            "email": "status_user@example.com",
            "phone": "9876543240",
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201
    tokens = reg.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    user = db_session.query(User).filter_by(email="status_user@example.com").first()

    # 1. Test SUSPENDED user
    user.status = "SUSPENDED"
    db_session.commit()

    # Login rejected with generic message
    l_resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "status_user@example.com", "password": "Password123!"},
    )
    assert l_resp.status_code == 401
    assert l_resp.json()["message"] == "Invalid credentials."

    # /me rejected
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 401

    # Refresh rejected
    ref_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_resp.status_code == 401

    # 2. Test INACTIVE user
    user.status = "INACTIVE"
    db_session.commit()

    l_resp2 = client.post(
        "/api/v1/auth/login",
        json={"identifier": "status_user@example.com", "password": "Password123!"},
    )
    assert l_resp2.status_code == 401
    assert l_resp2.json()["message"] == "Invalid credentials."


def test_jwt_claims_and_validation(client: TestClient, db_session: Session) -> None:
    """Verify JWT access token contains sub, sid, iat, exp, jti, type=access, iss, aud."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Claims User",
            "email": "claims@example.com",
            "phone": "9876543250",
            "password": "Password123!",
        },
    )
    token = reg.json()["access_token"]
    decoded = decode_access_token(token)

    assert decoded["type"] == "access"
    assert decoded["iss"] == "gawachabazaar"
    assert decoded["aud"] == "gawachabazaar:api"
    assert "sub" in decoded
    assert "sid" in decoded
    assert "jti" in decoded
    assert "iat" in decoded
    assert "exp" in decoded

    # No sensitive fields in claims
    assert "password" not in decoded
    assert "password_hash" not in decoded
    assert "refresh_token" not in decoded


def test_jwt_invalid_type_and_iss_aud_rejected(
    client: TestClient, db_session: Session
) -> None:
    """Verify token validation fails if type != 'access' or wrong iss/aud."""
    # Create user and session
    user = User(
        name="Direct User",
        email="direct@example.com",
        phone="+919876543260",
        password_hash=hash_password("Pass123!"),
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()

    session = AuthSession(
        user_id=user.id,
        refresh_token_hash="dummy-hash",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()

    # Wrong token type (e.g. refresh)
    wrong_type_token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": session.id,
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
            "jti": uuid.uuid4().hex,
            "type": "refresh",
            "iss": "gawachabazaar",
            "aud": "gawachabazaar:api",
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    r1 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_type_token}"},
    )
    assert r1.status_code == 401

    # Wrong issuer
    wrong_iss_token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": session.id,
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
            "jti": uuid.uuid4().hex,
            "type": "access",
            "iss": "malicious-issuer",
            "aud": "gawachabazaar:api",
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    r2 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_iss_token}"},
    )
    assert r2.status_code == 401

    # Expired access token
    expired_token = create_access_token(
        user_id=user.id,
        session_id=session.id,
        expires_delta=timedelta(seconds=-5),
    )
    r3 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert r3.status_code == 401


def test_random_invalid_refresh_token_does_not_revoke_valid_session(
    client: TestClient, db_session: Session
) -> None:
    """Verify an arbitrary invalid refresh token does NOT revoke or invalidate legitimate sessions."""
    from app.core.security import generate_refresh_token

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Negative Test User",
            "email": "negative@example.com",
            "phone": "9876543201",
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201
    valid_rt1 = reg.json()["refresh_token"]

    # Generate a completely random invalid refresh token
    random_invalid_rt = generate_refresh_token()

    # Attempt refresh with invalid token -> fails with 401
    bad_resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": random_invalid_rt}
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["code"] == "AUTHENTICATION_ERROR"

    # Crucial: verify valid_rt1 session was NOT revoked and remains fully functional
    good_resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": valid_rt1}
    )
    assert good_resp.status_code == 200
    new_data = good_resp.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["refresh_token"] != valid_rt1


def test_refresh_token_rotation_and_old_token_invalidation(
    client: TestClient, db_session: Session
) -> None:
    """Verify refresh rotates token: RT1 -> RT2, RT1 fails, RT2 succeeds, session expires_at NOT extended."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Rotate User",
            "email": "rotate@example.com",
            "phone": "9876543270",
            "password": "Password123!",
        },
    )
    data = reg.json()
    rt1 = data["refresh_token"]

    user = db_session.query(User).filter_by(email="rotate@example.com").first()
    session_before = db_session.query(AuthSession).filter_by(user_id=user.id).first()
    original_expires_at = session_before.expires_at

    # 1. Rotate RT1 -> RT2
    ref_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert ref_resp.status_code == 200
    ref_data = ref_resp.json()
    rt2 = ref_data["refresh_token"]
    at2 = ref_data["access_token"]
    assert rt2 != rt1

    # Access /me with new access token succeeds
    me_resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {at2}"}
    )
    assert me_resp.status_code == 200

    # ABSOLUTE SESSION LIFETIME: verify session.expires_at was NOT extended!
    db_session.refresh(session_before)
    assert session_before.expires_at == original_expires_at
    assert session_before.last_used_at is not None

    # 2. Reusing old rotated RT1 must fail safely!
    reuse_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["code"] == "AUTHENTICATION_ERROR"

    # 3. Rotating with valid RT2 must succeed!
    ref2_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": rt2})
    assert ref2_resp.status_code == 200
    ref2_data = ref2_resp.json()
    rt3 = ref2_data["refresh_token"]
    assert rt3 != rt2

    # Verify session state after second rotation
    db_session.refresh(session_before)
    assert session_before.refresh_token_hash == hash_refresh_token(rt3)
    assert session_before.expires_at == original_expires_at


def test_logout_session_revocation_and_idempotency(client: TestClient) -> None:
    """Verify logout revokes session, prevents refresh, and is idempotent."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Logout User",
            "email": "logout@example.com",
            "phone": "9876543280",
            "password": "Password123!",
        },
    )
    tokens = reg.json()
    rt = tokens["refresh_token"]
    at = tokens["access_token"]

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", json={"refresh_token": rt})
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"message": "Logged out successfully."}

    # Repeated logout is safe (idempotent)
    repeat_logout = client.post("/api/v1/auth/logout", json={"refresh_token": rt})
    assert repeat_logout.status_code == 200

    # Refresh after logout fails
    ref_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert ref_resp.status_code == 401

    # Access /me after session revoked fails
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {at}"})
    assert me_resp.status_code == 401
    assert "revoked" in me_resp.json()["message"].lower()


def test_concurrent_refresh_row_locking(test_engine) -> None:
    """Verify row locking prevents concurrent refreshes from double-rotating the same session.

    Simulates two threads attempting to refresh the exact same token simultaneously using real DB connections.
    Also verifies the losing request does not invalidate the winner's new token.
    """
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    setup_session = SessionLocal()

    # Create user and role
    customer_role = setup_session.query(Role).filter_by(name="CUSTOMER").first()
    if not customer_role:
        customer_role = Role(name="CUSTOMER", description="Retail customer")
        setup_session.add(customer_role)
        setup_session.commit()

    user = User(
        name="Concurrent User",
        email="concurrent@example.com",
        phone="+919876543290",
        password_hash=hash_password("Pass123!"),
        status="ACTIVE",
    )
    setup_session.add(user)
    setup_session.commit()
    user_id = user.id

    from app.core.security import generate_refresh_token
    from app.services.auth import AuthService

    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    auth_session = AuthSession(
        user_id=user_id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    setup_session.add(auth_session)
    setup_session.commit()
    setup_session.close()

    results: list[Any] = []
    errors: list[Any] = []

    def perform_refresh() -> None:
        thread_db = SessionLocal()
        service = AuthService(thread_db)
        try:
            res = service.refresh_session(raw_token)
            results.append(res)
        except Exception as e:
            errors.append(e)
        finally:
            thread_db.close()

    t1 = threading.Thread(target=perform_refresh)
    t2 = threading.Thread(target=perform_refresh)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    # Exactly one thread succeeds, and the other thread fails with AuthenticationError
    assert len(results) == 1
    assert len(errors) == 1
    from app.exceptions.base import AuthenticationError

    assert isinstance(errors[0], AuthenticationError)

    # Verify winning request's rotated token remains fully valid and session is unrevoked
    check_session = SessionLocal()
    refreshed_session = (
        check_session.query(AuthSession).filter_by(user_id=user_id).first()
    )
    assert refreshed_session is not None
    assert refreshed_session.revoked_at is None
    assert refreshed_session.refresh_token_hash == hash_refresh_token(
        results[0].refresh_token
    )

    # Prove the winning rotated token can refresh again cleanly
    winner_service = AuthService(check_session)
    second_refresh = winner_service.refresh_session(results[0].refresh_token)
    assert second_refresh is not None
    assert second_refresh.refresh_token != results[0].refresh_token
    check_session.close()
