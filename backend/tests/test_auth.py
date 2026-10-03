"""Firebase-backed authentication.

Firebase itself (password checks, Google OAuth, OTP delivery/verification,
verification and reset emails) runs client-side and is not re-tested here.
These tests cover what the backend owns: ID-token verification, mapping a
verified identity to exactly one application user, the email-verification
gate, legacy-account migration, and the security properties around them.
Firebase is the in-memory fake installed by conftest.py.
"""

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.roles import ADMIN, CUSTOMER
from app.core.security import hash_password, normalize_email, normalize_phone
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from tests.firebase_fake import auth_headers_for, fake_firebase

PROTECTED = "/api/v1/addresses"  # any customer route guarded by get_current_user


@pytest.fixture(autouse=True)
def seed_roles(db_session: Session) -> None:
    for name in (CUSTOMER, ADMIN):
        if not db_session.query(Role).filter_by(name=name).first():
            db_session.add(Role(name=name, description=name))
    db_session.commit()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sync(client: TestClient, token: str, **body) -> "object":
    return client.post("/api/v1/auth/sync", json=body or None, headers=_bearer(token))


def _legacy_user(
    db: Session, *, email: str | None, phone: str | None, password: str = "OldSecret123", role: str = CUSTOMER
) -> User:
    user = User(name="Legacy User", email=email, phone=phone, password_hash=hash_password(password), status="ACTIVE")
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=db.query(Role).filter_by(name=role).one().id, is_primary=True))
    db.commit()
    db.refresh(user)
    return user


def _users(db: Session) -> list[User]:
    db.expire_all()
    return db.query(User).order_by(User.id).all()


# ---------------------------------------------------------------------------
# Backend token verification
# ---------------------------------------------------------------------------


def test_missing_token_is_401(client: TestClient) -> None:
    r = client.get(PROTECTED)
    assert r.status_code == 401
    assert r.json()["code"] == "AUTHENTICATION_ERROR"


def test_invalid_authorization_header_is_401(client: TestClient) -> None:
    token = fake_firebase.issue("fb-x", email="x@example.com")
    assert client.get(PROTECTED, headers={"Authorization": f"Basic {token}"}).status_code == 401
    assert client.get(PROTECTED, headers={"Authorization": "Bearer"}).status_code == 401
    assert client.get(PROTECTED, headers={"Authorization": token}).status_code == 401


def test_forged_or_garbled_token_is_401(client: TestClient) -> None:
    r = client.get(PROTECTED, headers=_bearer("eyJhbGciOiJub25lIn0.eyJ1aWQiOiJhZG1pbiJ9."))
    assert r.status_code == 401
    assert r.json()["code"] == "AUTHENTICATION_ERROR"


def test_expired_token_gets_distinct_code(client: TestClient, db_session: Session) -> None:
    user = _legacy_user(db_session, email="exp@example.com", phone=None)
    headers = auth_headers_for(db_session, user, expired=True)
    r = client.get(PROTECTED, headers=headers)
    assert r.status_code == 401
    assert r.json()["code"] == "TOKEN_EXPIRED"  # client refreshes and retries


def test_valid_token_for_known_user_is_accepted(client: TestClient, db_session: Session) -> None:
    user = _legacy_user(db_session, email="ok@example.com", phone=None)
    r = client.get(PROTECTED, headers=auth_headers_for(db_session, user))
    assert r.status_code == 200, r.text


def test_unknown_firebase_uid_must_sync_first(client: TestClient) -> None:
    token = fake_firebase.issue("fb-never-synced", email="new@example.com")
    r = client.get(PROTECTED, headers=_bearer(token))
    assert r.status_code == 401
    assert r.json()["code"] == "ACCOUNT_NOT_REGISTERED"


def test_firebase_outage_is_503_not_401(client: TestClient, db_session: Session) -> None:
    user = _legacy_user(db_session, email="down@example.com", phone=None)
    headers = auth_headers_for(db_session, user)
    fake_firebase.unavailable = True
    r = client.get(PROTECTED, headers=headers)
    assert r.status_code == 503
    assert r.json()["code"] == "AUTH_UNAVAILABLE"


def test_inactive_user_is_rejected(client: TestClient, db_session: Session) -> None:
    user = _legacy_user(db_session, email="sus@example.com", phone=None)
    headers = auth_headers_for(db_session, user)
    user.status = "SUSPENDED"
    db_session.commit()
    assert client.get(PROTECTED, headers=headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_forged_user_id_is_ignored(client: TestClient, db_session: Session) -> None:
    """Identity comes only from the verified token - ids/emails in headers
    or the body cannot switch the caller to another account."""
    victim = _legacy_user(db_session, email="victim@example.com", phone="+919811111111")
    attacker = _legacy_user(db_session, email="attacker@example.com", phone="+919822222222")
    headers = auth_headers_for(db_session, attacker)

    r = client.get(
        "/api/v1/auth/me",
        headers={**headers, "X-User-Id": str(victim.id), "X-Firebase-Uid": victim.firebase_uid or "x"},
    )
    assert r.json()["id"] == attacker.id

    r = client.post(
        "/api/v1/auth/sync",
        json={"first_name": "x", "uid": "whatever", "email": "victim@example.com", "user_id": victim.id},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == attacker.id
    assert r.json()["email"] == "attacker@example.com"


# ---------------------------------------------------------------------------
# Email + password
# ---------------------------------------------------------------------------


def test_email_registration_creates_one_customer(client: TestClient, db_session: Session) -> None:
    token = fake_firebase.issue("fb-arjun", email="Arjun.Sharma@Example.com", email_verified=False)
    r = _sync(client, token, first_name="  Arjun ", last_name="Sharma")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Arjun Sharma"
    assert body["email"] == "arjun.sharma@example.com"
    assert body["phone"] is None
    assert body["roles"] == [CUSTOMER]
    assert body["email_verified"] is False
    assert body["sign_in_provider"] == "password"
    assert not any("password" in key or "token" in key for key in body)

    # Idempotent: repeated sync (every app start) never duplicates.
    assert _sync(client, token).status_code == 200
    [user] = _users(db_session)
    assert user.firebase_uid == "fb-arjun"
    assert user.password_hash is None  # Firebase holds the credential


def test_unverified_email_is_gated_until_verified(client: TestClient, db_session: Session) -> None:
    unverified = fake_firebase.issue("fb-meera", email="meera@example.com", email_verified=False)
    assert _sync(client, unverified, first_name="Meera").status_code == 200

    # /auth/me stays reachable so the app can render "verify your email".
    me = client.get("/api/v1/auth/me", headers=_bearer(unverified))
    assert me.status_code == 200
    assert me.json()["email_verified"] is False

    blocked = client.get(PROTECTED, headers=_bearer(unverified))
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "EMAIL_NOT_VERIFIED"

    # After the link is clicked the client refreshes its ID token.
    verified = fake_firebase.issue("fb-meera", email="meera@example.com", email_verified=True)
    assert client.get(PROTECTED, headers=_bearer(verified)).status_code == 200


def test_duplicate_email_with_different_firebase_user_conflicts(
    client: TestClient, db_session: Session
) -> None:
    first = fake_firebase.issue("fb-one", email="dup@example.com", email_verified=True)
    assert _sync(client, first).status_code == 200

    # A second, unverified Firebase identity claiming the same address.
    second = fake_firebase.issue("fb-two", email="dup@example.com", email_verified=False)
    r = _sync(client, second)
    assert r.status_code == 409
    assert len(_users(db_session)) == 1


def test_invalid_names_are_rejected(client: TestClient) -> None:
    token = fake_firebase.issue("fb-long", email="long@example.com")
    assert _sync(client, token, first_name="x" * 76).status_code == 422


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------


def test_new_google_user(client: TestClient, db_session: Session) -> None:
    token = fake_firebase.issue(
        "fb-google-1", email="priya@gmail.com", name="Priya Nair", provider="google.com"
    )
    r = _sync(client, token)
    assert r.status_code == 200
    assert r.json()["name"] == "Priya Nair"
    assert r.json()["email_verified"] is True
    assert client.get(PROTECTED, headers=_bearer(token)).status_code == 200


def test_existing_google_user_maps_to_same_row(client: TestClient, db_session: Session) -> None:
    for _ in range(3):
        token = fake_firebase.issue("fb-google-2", email="ravi@gmail.com", provider="google.com")
        assert _sync(client, token).status_code == 200
    assert len(_users(db_session)) == 1


def test_google_links_to_existing_legacy_account_by_verified_email(
    client: TestClient, db_session: Session
) -> None:
    legacy = _legacy_user(db_session, email="old@gmail.com", phone="+919833333333")
    token = fake_firebase.issue("fb-google-3", email="old@gmail.com", provider="google.com")
    r = _sync(client, token)
    assert r.status_code == 200
    assert r.json()["id"] == legacy.id

    [user] = _users(db_session)
    assert user.firebase_uid == "fb-google-3"
    assert user.password_hash is None  # old password is no longer a way in


def test_unverified_email_never_links_to_existing_account(
    client: TestClient, db_session: Session
) -> None:
    _legacy_user(db_session, email="target@example.com", phone=None)
    token = fake_firebase.issue("fb-squatter", email="target@example.com", email_verified=False)
    r = _sync(client, token)
    assert r.status_code == 409
    assert _users(db_session)[0].firebase_uid is None


def test_same_email_on_a_different_firebase_user_is_not_duplicated(
    client: TestClient, db_session: Session
) -> None:
    """Customer registered with a phone+email identity, then tries Google
    with the same address on a separate Firebase user: the app must link
    in Firebase instead of the backend splitting the customer in two."""
    phone_first = fake_firebase.issue(
        "fb-phone-A", email="same@example.com", phone="+919844444444", provider="phone"
    )
    assert _sync(client, phone_first).status_code == 200

    google = fake_firebase.issue("fb-google-B", email="same@example.com", provider="google.com")
    r = _sync(client, google)
    assert r.status_code == 409
    assert r.json()["code"] == "ACCOUNT_EXISTS_DIFFERENT_METHOD"
    assert len(_users(db_session)) == 1


def test_linking_a_phone_in_firebase_updates_the_same_customer(
    client: TestClient, db_session: Session
) -> None:
    email_token = fake_firebase.issue("fb-link", email="link@example.com")
    assert _sync(client, email_token, first_name="Link").status_code == 200

    # Same Firebase user after linkWithCredential(phone): UID unchanged.
    linked = fake_firebase.issue("fb-link", email="link@example.com", phone="+919855555555", provider="phone")
    r = _sync(client, linked)
    assert r.status_code == 200
    [user] = _users(db_session)
    assert user.phone == "+919855555555"
    assert user.email == "link@example.com"


# ---------------------------------------------------------------------------
# Phone + OTP
# ---------------------------------------------------------------------------


def test_new_phone_user(client: TestClient, db_session: Session) -> None:
    token = fake_firebase.issue("fb-phone-1", email=None, phone="+919866666666", provider="phone")
    r = _sync(client, token)
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "+919866666666"
    assert r.json()["email"] is None
    assert r.json()["name"] == "Customer"
    # The OTP is the proof - no email verification gate for phone sign-ins.
    assert client.get(PROTECTED, headers=_bearer(token)).status_code == 200


def test_existing_phone_account_is_linked_not_duplicated(
    client: TestClient, db_session: Session
) -> None:
    legacy = _legacy_user(db_session, email="phoneuser@example.com", phone="+919877777777")
    token = fake_firebase.issue("fb-phone-2", phone="+919877777777", provider="phone")
    r = _sync(client, token)
    assert r.status_code == 200
    assert r.json()["id"] == legacy.id
    assert len(_users(db_session)) == 1


def test_email_and_phone_owned_by_different_accounts_are_never_merged(
    client: TestClient, db_session: Session
) -> None:
    _legacy_user(db_session, email="a@example.com", phone="+919800000101")
    _legacy_user(db_session, email="b@example.com", phone="+919800000102")
    token = fake_firebase.issue(
        "fb-both", email="a@example.com", phone="+919800000102", provider="phone"
    )
    r = _sync(client, token)
    assert r.status_code == 409
    assert all(u.firebase_uid is None for u in _users(db_session))


def test_sync_is_rate_limited(client: TestClient) -> None:
    token = fake_firebase.issue("fb-spam", phone="+919800000200", provider="phone")
    codes = [_sync(client, token).status_code for _ in range(21)]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429


# ---------------------------------------------------------------------------
# Legacy (pre-Firebase) account migration
# ---------------------------------------------------------------------------


def test_legacy_migration_moves_password_to_firebase_once(
    client: TestClient, db_session: Session
) -> None:
    legacy = _legacy_user(db_session, email="legacy@example.com", phone="+919800000300")
    r = client.post(
        "/api/v1/auth/legacy-migrate",
        json={"identifier": " LEGACY@example.com ", "password": "OldSecret123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "legacy@example.com"

    [user] = _users(db_session)
    fb = fake_firebase.users[user.firebase_uid]
    assert fb["email"] == "legacy@example.com"
    assert fb["password"] == "OldSecret123"
    assert fb["email_verified"] is False  # customers prove their email
    assert user.password_hash is None
    assert user.id == legacy.id

    again = client.post(
        "/api/v1/auth/legacy-migrate",
        json={"identifier": "legacy@example.com", "password": "OldSecret123"},
    )
    assert again.status_code == 401


def test_legacy_migration_by_phone_returns_the_email_to_sign_in_with(client: TestClient, db_session: Session) -> None:
    _legacy_user(db_session, email="byphone@example.com", phone="+919800000301")
    r = client.post("/api/v1/auth/legacy-migrate", json={"identifier": "98000 00301", "password": "OldSecret123"})
    assert r.status_code == 200
    assert r.json()["email"] == "byphone@example.com"


def test_legacy_staff_email_counts_as_verified(client: TestClient, db_session: Session) -> None:
    _legacy_user(db_session, email="boss@example.com", phone="+919800000302", role=ADMIN)
    r = client.post("/api/v1/auth/legacy-migrate", json={"identifier": "boss@example.com", "password": "OldSecret123"})
    assert r.status_code == 200
    [fb] = fake_firebase.users.values()
    assert fb["email_verified"] is True


def test_legacy_migration_rejects_bad_credentials_uniformly(client: TestClient, db_session: Session) -> None:
    _legacy_user(db_session, email="guard@example.com", phone=None)
    wrong = client.post("/api/v1/auth/legacy-migrate", json={"identifier": "guard@example.com", "password": "nope"})
    unknown = client.post("/api/v1/auth/legacy-migrate", json={"identifier": "ghost@example.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["message"] == unknown.json()["message"] == "Invalid credentials."
    assert fake_firebase.users == {}


def test_legacy_migration_when_firebase_account_already_exists(client: TestClient, db_session: Session) -> None:
    _legacy_user(db_session, email="taken@example.com", phone=None)
    fake_firebase.create_user(email="taken@example.com", password="whatever1", display_name=None, email_verified=False)
    r = client.post("/api/v1/auth/legacy-migrate", json={"identifier": "taken@example.com", "password": "OldSecret123"})
    assert r.status_code == 409
    assert _users(db_session)[0].password_hash is not None  # nothing changed


def test_legacy_password_rejected_by_policy_requires_reset(client: TestClient, db_session: Session) -> None:
    _legacy_user(db_session, email="weak@example.com", phone=None, password="OldSecret123")
    fake_firebase.min_password_length = 20
    r = client.post("/api/v1/auth/legacy-migrate", json={"identifier": "weak@example.com", "password": "OldSecret123"})
    assert r.status_code == 409
    assert r.json()["code"] == "PASSWORD_RESET_REQUIRED"
    [user] = _users(db_session)
    assert user.firebase_uid and user.password_hash is None
    assert fake_firebase.users[user.firebase_uid]["password"] is None


def test_legacy_migration_is_rate_limited(client: TestClient) -> None:
    codes = [
        client.post("/api/v1/auth/legacy-migrate", json={"identifier": "x@example.com", "password": "x"}).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    allowed = settings.ALLOWED_ORIGINS[0]
    ok = client.options(
        "/api/v1/auth/me",
        headers={"Origin": allowed, "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == allowed

    evil = client.options(
        "/api/v1/auth/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert evil.headers.get("access-control-allow-origin") is None


def test_removed_password_endpoints_are_gone(client: TestClient) -> None:
    for path in ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh", "/api/v1/auth/logout"):
        assert client.post(path, json={}).status_code in (404, 405)


def test_phone_and_email_normalization_utilities() -> None:
    assert normalize_email(" TEST@Example.com ") == "test@example.com"
    assert normalize_phone("9876543210") == "+919876543210"
    assert normalize_phone("09876543210") == "+919876543210"
    assert normalize_phone("919876543210") == "+919876543210"
    assert normalize_phone("+91-98765-43210") == "+919876543210"
    assert normalize_phone(" (987) 654-3210 ") == "+919876543210"
    with pytest.raises(ValueError):
        normalize_phone("123")
    with pytest.raises(ValueError):
        normalize_phone("+invalid")
