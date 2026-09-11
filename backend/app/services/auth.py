from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    normalize_phone,
    verify_password,
)
from app.exceptions.base import (
    AppException,
    AuthenticationError,
    ConflictError,
)
from app.models.auth_session import AuthSession
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshTokenResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


@contextmanager
def _transaction(db: Session):
    """Context manager executing block in transaction or nested savepoint if transaction already active."""
    if db.in_transaction():
        with db.begin_nested():
            yield
    else:
        with db.begin():
            yield


class AuthService:
    """Production authentication service managing user registration, sessions, and token lifecycles."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def register_user(
        self,
        data: RegisterRequest,
        client_meta: dict[str, Any] | None = None,
    ) -> TokenResponse:
        """Atomically register a new user, assign the default CUSTOMER role, and create an auth session.

        Concurrency & Race Conditions:
        If duplicate email or phone is attempted concurrently, PostgreSQL unique constraints
        trigger IntegrityError, which is translated to ConflictError.
        """
        meta = client_meta or {}
        now = datetime.now(UTC)

        try:
            with _transaction(self.db):
                # Verify baseline CUSTOMER role exists
                customer_role = self.db.query(Role).filter_by(name="CUSTOMER").first()
                if not customer_role:
                    logger.error(
                        "AUTH_ROLE_NOT_FOUND: Baseline CUSTOMER role is missing in database."
                    )
                    raise AppException(
                        "System role configuration error.",
                        status_code=500,
                        code="INTERNAL_SERVER_ERROR",
                    )

                # Create active User account
                user = User(
                    name=data.name,
                    email=data.email,
                    phone=data.phone,
                    password_hash=hash_password(data.password),
                    status="ACTIVE",
                )
                self.db.add(user)
                self.db.flush()

                # Assign default CUSTOMER role (is_primary=True)
                user_role = UserRole(
                    user_id=user.id,
                    role_id=customer_role.id,
                    is_primary=True,
                )
                self.db.add(user_role)

                # Generate opaque refresh token and store only its SHA-256 hash
                raw_refresh_token = generate_refresh_token()
                refresh_hash = hash_refresh_token(raw_refresh_token)
                expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

                session = AuthSession(
                    user_id=user.id,
                    refresh_token_hash=refresh_hash,
                    expires_at=expires_at,
                    device_name=meta.get("device_name"),
                    ip_address=meta.get("ip_address"),
                    user_agent=meta.get("user_agent"),
                )
                self.db.add(session)
                self.db.flush()

                # Issue short-lived access JWT bound to user and session id
                access_token = create_access_token(
                    user_id=user.id,
                    session_id=session.id,
                )

                logger.info("AUTH_REGISTER_SUCCESS: user_id=%s registered", user.id)

        except IntegrityError as exc:
            self.db.rollback()
            logger.info(
                "AUTH_REGISTRATION_CONFLICT: duplicate email or phone attempted"
            )
            raise ConflictError(
                "User with this email or phone already exists."
            ) from exc

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                phone=user.phone,
                status=user.status,
                created_at=user.created_at,
            ),
        )

    def authenticate(
        self,
        data: LoginRequest,
        client_meta: dict[str, Any] | None = None,
    ) -> TokenResponse:
        """Authenticate user by email or phone with enumeration protection and issue a session.

        Enumeration Protection:
        Unknown email, unknown phone, wrong password, inactive status, and suspended status
        all return the identical generic AuthenticationError("Invalid credentials.").
        """
        meta = client_meta or {}
        identifier = data.identifier.strip()
        now = datetime.now(UTC)

        # Normalize and look up user by email or phone
        if "@" in identifier:
            norm_email = normalize_email(identifier)
            user = self.db.query(User).filter(User.email == norm_email).first()
        else:
            try:
                norm_phone = normalize_phone(identifier)
                user = self.db.query(User).filter(User.phone == norm_phone).first()
            except ValueError:
                user = None

        if not user or not verify_password(data.password, user.password_hash):
            logger.info("AUTH_INVALID_CREDENTIALS: login failed for identifier")
            raise AuthenticationError("Invalid credentials.")

        if user.status != "ACTIVE":
            if user.status == "INACTIVE":
                logger.warning("AUTH_ACCOUNT_INACTIVE: user_id=%s is inactive", user.id)
            elif user.status == "SUSPENDED":
                logger.warning(
                    "AUTH_ACCOUNT_SUSPENDED: user_id=%s is suspended", user.id
                )
            raise AuthenticationError("Invalid credentials.")

        with _transaction(self.db):
            raw_refresh_token = generate_refresh_token()
            refresh_hash = hash_refresh_token(raw_refresh_token)
            expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

            session = AuthSession(
                user_id=user.id,
                refresh_token_hash=refresh_hash,
                expires_at=expires_at,
                device_name=meta.get("device_name"),
                ip_address=meta.get("ip_address"),
                user_agent=meta.get("user_agent"),
            )
            self.db.add(session)
            self.db.flush()

            access_token = create_access_token(
                user_id=user.id,
                session_id=session.id,
            )

            logger.info(
                "AUTH_LOGIN_SUCCESS: user_id=%s session_id=%s", user.id, session.id
            )

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                phone=user.phone,
                status=user.status,
                created_at=user.created_at,
            ),
        )

    def refresh_session(
        self,
        raw_refresh_token: str,
        client_meta: dict[str, Any] | None = None,
    ) -> RefreshTokenResponse:
        """Rotate refresh token and issue a new access token under row-level database lock.

        Concurrency & Replay Safety:
        Phase 8 provides secure refresh-token rotation, old-token invalidation, PostgreSQL
        concurrency protection (via `SELECT ... FOR UPDATE`), and bounded replay protection
        within the single-session-row design. Full token-family historical replay detection
        is intentionally deferred because it requires persistent token lineage.

        When two concurrent refresh requests arrive with the same refresh token, the first
        request acquires the lock, rotates the token hash, updates last_used_at, and commits.
        The second request unblocks, finds that the original hash is no longer present,
        and safely fails with AuthenticationError("Invalid or expired refresh token.") without
        affecting the newly rotated token.

        Absolute Session Lifetime:
        The session's `expires_at` is NOT extended on rotation. It preserves the 30-day absolute
        lifetime established at login/registration.
        """
        meta = client_meta or {}
        token_hash = hash_refresh_token(raw_refresh_token)
        now_utc = datetime.now(UTC)

        with _transaction(self.db):
            # Acquire row lock
            session = (
                self.db.query(AuthSession)
                .filter(AuthSession.refresh_token_hash == token_hash)
                .with_for_update()
                .first()
            )

            if not session:
                logger.warning(
                    "AUTH_REFRESH_INVALID: refresh token hash not found in active sessions"
                )
                raise AuthenticationError("Invalid or expired refresh token.")

            if session.revoked_at is not None:
                logger.warning(
                    "AUTH_REFRESH_REVOKED: attempt to refresh revoked session_id=%s",
                    session.id,
                )
                raise AuthenticationError("Invalid or expired refresh token.")

            if session.expires_at <= now_utc:
                logger.info(
                    "AUTH_REFRESH_EXPIRED: session_id=%s reached absolute expiration",
                    session.id,
                )
                raise AuthenticationError("Invalid or expired refresh token.")

            user = self.db.query(User).filter(User.id == session.user_id).first()
            if not user or user.status != "ACTIVE":
                session.revoked_at = now_utc
                logger.warning(
                    "AUTH_REFRESH_INACTIVE_USER: user_id=%s inactive/suspended; session revoked",
                    session.user_id,
                )
                raise AuthenticationError("Invalid or expired refresh token.")

            # Rotate: generate new token and replace hash in place
            new_raw_refresh_token = generate_refresh_token()
            session.refresh_token_hash = hash_refresh_token(new_raw_refresh_token)
            session.last_used_at = now_utc

            if meta.get("ip_address"):
                session.ip_address = meta["ip_address"]
            if meta.get("user_agent"):
                session.user_agent = meta["user_agent"]

            # Issue new access token bound to user and session
            access_token = create_access_token(
                user_id=user.id,
                session_id=session.id,
            )

            logger.info("AUTH_REFRESH_SUCCESS: session_id=%s rotated", session.id)

        return RefreshTokenResponse(
            access_token=access_token,
            refresh_token=new_raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def logout(self, raw_refresh_token: str) -> LogoutResponse:
        """Revoke authentication session by refresh token hash.

        Safe and idempotent: repeated logouts succeed gracefully without raising errors.
        """
        token_hash = hash_refresh_token(raw_refresh_token)
        now_utc = datetime.now(UTC)

        with _transaction(self.db):
            session = (
                self.db.query(AuthSession)
                .filter(AuthSession.refresh_token_hash == token_hash)
                .first()
            )
            if session and session.revoked_at is None:
                session.revoked_at = now_utc
                logger.info("AUTH_LOGOUT_SUCCESS: session_id=%s revoked", session.id)

        return LogoutResponse(message="Logged out successfully.")

    def resolve_current_user(self, token: str) -> User:
        """Resolve, validate, and return the authenticated user from a Bearer JWT.

        Validates:
        1. JWT cryptographic signature, expiration, issuer, audience.
        2. Token type must be 'access'.
        3. Subject must correspond to a valid, ACTIVE user in PostgreSQL.
        4. Associated AuthSession must exist, not be revoked, and not be expired.
        """
        try:
            payload = decode_access_token(token)
        except Exception as exc:
            logger.info(
                "AUTH_INVALID_TOKEN: JWT validation failed: %s", type(exc).__name__
            )
            raise AuthenticationError("Could not validate credentials.") from exc

        token_type = payload.get("type")
        if token_type != "access":
            logger.warning(
                "AUTH_INVALID_TOKEN_TYPE: received '%s', expected 'access'", token_type
            )
            raise AuthenticationError("Could not validate credentials.")

        sub = payload.get("sub")
        if not sub or not str(sub).isdigit():
            logger.warning("AUTH_INVALID_SUBJECT: invalid or missing sub claim")
            raise AuthenticationError("Could not validate credentials.")

        session_id = payload.get("sid")
        if not session_id or not isinstance(session_id, int):
            logger.warning("AUTH_INVALID_SESSION_ID: invalid or missing sid claim")
            raise AuthenticationError("Could not validate credentials.")

        user_id = int(sub)
        now_utc = datetime.now(UTC)

        # Check server-side session state
        session = (
            self.db.query(AuthSession)
            .filter(AuthSession.id == session_id, AuthSession.user_id == user_id)
            .first()
        )
        if (
            not session
            or session.revoked_at is not None
            or session.expires_at <= now_utc
        ):
            logger.warning(
                "AUTH_SESSION_INVALID: session_id=%s invalid, expired, or revoked",
                session_id,
            )
            raise AuthenticationError("Session has expired or been revoked.")

        # Check user account status in database
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("AUTH_USER_NOT_FOUND: user_id=%s not found", user_id)
            raise AuthenticationError("User not found.")

        if user.status != "ACTIVE":
            logger.warning(
                "AUTH_USER_NOT_ACTIVE: user_id=%s status is %s", user_id, user.status
            )
            raise AuthenticationError("User account is inactive or suspended.")

        return user
