"""Firebase-backed authentication.

Firebase Auth owns every credential and sign-in method (email/password,
Google, phone OTP, verification, password reset). This service:

1. verifies the Firebase ID token on each request (`resolve_*`),
2. keeps the PostgreSQL application user in step with the verified
   Firebase identity (`sync_user`), linking instead of duplicating when
   the same person arrives through a second sign-in method, and
3. moves accounts created before the cutover into Firebase on their
   first sign-in (`migrate_legacy_account`).

Nothing here reads a user id, email, or phone from the request body as
identity - only from a token that passed Firebase verification.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.firebase import (
    FirebaseEmailExistsError,
    FirebaseGateway,
    FirebaseIdentity,
    FirebasePasswordRejectedError,
    FirebaseTokenError,
    FirebaseUnavailableError,
    get_firebase,
)
from app.core.logging import logger
from app.core.roles import CUSTOMER, STAFF_ROLES
from app.core.security import (
    hash_password,
    normalize_email,
    normalize_phone,
    verify_password,
)
from app.exceptions.base import (
    AppException,
    AuthenticationError,
    ConflictError,
)
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.auth import (
    AuthUserResponse,
    LegacyMigrationRequest,
    LegacyMigrationResponse,
    SyncUserRequest,
)

# Verified against when no legacy account matches, so "no such account" and
# "wrong password" take the same time (no account enumeration by timing).
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


@contextmanager
def _transaction(db: Session):
    """Run the block, then commit; rollback on any exception.

    Deliberately does not branch on `db.in_transaction()` - SQLAlchemy
    autobegins on the first query, so that check is true even when no
    caller owns a transaction; a plain commit/rollback is correct either way.
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def token_expired_error() -> AppException:
    # Distinct code so clients refresh the Firebase ID token and retry
    # instead of signing the user out.
    return AppException("Your session has expired.", status_code=401, code="TOKEN_EXPIRED")


def auth_unavailable_error() -> AppException:
    return AppException(
        "Sign-in is temporarily unavailable. Please try again shortly.",
        status_code=503,
        code="AUTH_UNAVAILABLE",
    )


def account_not_registered_error() -> AppException:
    # Valid Firebase user with no application account yet - the client
    # calls POST /auth/sync and retries.
    return AppException(
        "Finish setting up your account to continue.",
        status_code=401,
        code="ACCOUNT_NOT_REGISTERED",
    )


def email_not_verified_error() -> AppException:
    return AppException(
        "Please verify your email address to continue.",
        status_code=403,
        code="EMAIL_NOT_VERIFIED",
    )


def requires_email_verification(identity: FirebaseIdentity) -> bool:
    """Email/password sign-ins must prove the address first. Google emails
    arrive verified, and a phone sign-in's OTP is itself the proof."""
    return identity.sign_in_provider == "password" and not identity.email_verified


@dataclass(frozen=True)
class AuthContext:
    user: User
    identity: FirebaseIdentity


class AuthService:
    def __init__(self, db: Session, firebase: FirebaseGateway | None = None) -> None:
        self.db = db
        self.firebase = firebase or get_firebase()

    def get_role_names(self, user_id: int) -> list[str]:
        """Current role names for a user, read live from `user_roles`/`roles`
        on every call - a role change takes effect on the next request."""
        rows = (
            self.db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id)
            .all()
        )
        return sorted(name for (name,) in rows)

    # ------------------------------------------------------------------
    # Per-request authentication
    # ------------------------------------------------------------------

    def verify_token(self, token: str) -> FirebaseIdentity:
        try:
            return self.firebase.verify_id_token(token)
        except FirebaseTokenError as exc:
            logger.info("AUTH_INVALID_TOKEN: firebase token rejected (%s)", exc.reason)
            if exc.reason == "expired":
                raise token_expired_error() from exc
            raise AuthenticationError("Could not validate credentials.") from exc
        except FirebaseUnavailableError as exc:
            raise auth_unavailable_error() from exc

    def resolve(self, token: str) -> AuthContext:
        """Verified identity + its ACTIVE application user. Does not enforce
        email verification (see resolve_current_user)."""
        identity = self.verify_token(token)
        user = self.db.query(User).filter(User.firebase_uid == identity.uid).first()
        if user is None:
            logger.info("AUTH_UNKNOWN_FIREBASE_UID: no application user for verified token")
            raise account_not_registered_error()
        self._require_active(user)
        return AuthContext(user=user, identity=identity)

    def resolve_current_user(self, token: str) -> User:
        """The gate every protected route goes through: valid token, known
        ACTIVE user, and a verified email for email/password sign-ins."""
        ctx = self.resolve(token)
        if requires_email_verification(ctx.identity):
            raise email_not_verified_error()
        return ctx.user

    def _require_active(self, user: User) -> None:
        if user.status != "ACTIVE":
            logger.warning("AUTH_USER_NOT_ACTIVE: user_id=%s status is %s", user.id, user.status)
            raise AuthenticationError("User account is inactive or suspended.")

    def to_auth_user_response(self, ctx: AuthContext) -> AuthUserResponse:
        user = ctx.user
        return AuthUserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            status=user.status,
            created_at=user.created_at,
            roles=self.get_role_names(user.id),
            email_verified=ctx.identity.email_verified,
            sign_in_provider=ctx.identity.sign_in_provider,
        )

    # ------------------------------------------------------------------
    # Firebase -> PostgreSQL synchronization
    # ------------------------------------------------------------------

    def sync_user(self, token: str, data: SyncUserRequest) -> AuthUserResponse:
        """Find, link, or create the application user for a verified
        Firebase identity. Idempotent - clients call it after every sign-in.

        Lookup order, so one person never becomes two customers:
        1. `firebase_uid` - the normal case after the first sign-in.
        2. A *verified* identifier on an existing row with no Firebase link
           (legacy account, or the same person's earlier row): verified
           email (Google, or email/password after verification), or phone
           (a phone claim only exists after Firebase OTP verification).
        3. Otherwise create a new CUSTOMER.

        Multiple sign-in methods on one Firebase user (account linking done
        client-side) share one UID, so they already map to one row here.
        """
        identity = self.verify_token(token)
        email = normalize_email(identity.email) if identity.email else None
        phone = self._normalize_phone_claim(identity.phone)
        email_is_verified = bool(email) and identity.email_verified

        try:
            with _transaction(self.db):
                user = self.db.query(User).filter(User.firebase_uid == identity.uid).first()
                if user is None:
                    user = self._link_existing(identity, email if email_is_verified else None, phone)
                if user is None:
                    user = self._create_customer(identity, email, phone, data)
                else:
                    self._refresh_contact_details(user, email if email_is_verified else None, phone)
        except IntegrityError as exc:
            # Lost a race with a concurrent sync for the same UID (first
            # sign-in fired twice) - the other request created the row.
            self.db.rollback()
            user = self.db.query(User).filter(User.firebase_uid == identity.uid).first()
            if user is None:
                logger.info("AUTH_SYNC_CONFLICT: email or phone already belongs to another account")
                raise ConflictError(
                    "This email or mobile number is already linked to another account."
                ) from exc

        self._require_active(user)
        self.db.refresh(user)
        return self.to_auth_user_response(AuthContext(user=user, identity=identity))

    @staticmethod
    def _normalize_phone_claim(phone: str | None) -> str | None:
        if not phone:
            return None
        try:
            return normalize_phone(phone)
        except ValueError:
            return None

    def _link_existing(
        self, identity: FirebaseIdentity, verified_email: str | None, phone: str | None
    ) -> User | None:
        candidates: list[User] = []
        if verified_email:
            candidates += self.db.query(User).filter(User.email == verified_email).all()
        if phone:
            candidates += self.db.query(User).filter(User.phone == phone).all()
        if not candidates:
            return None

        target = candidates[0]
        if any(c.id != target.id for c in candidates):
            # Verified email is one account, verified phone another: never
            # merge two customers' orders/addresses automatically.
            raise ConflictError(
                "Your email and mobile number belong to different accounts. Please contact support."
            )
        if target.firebase_uid and target.firebase_uid != identity.uid:
            # Same person, different Firebase user (e.g. phone account vs
            # Google account). Firebase-side linking merges them; creating a
            # second row would split their data.
            raise AppException(
                "An account already exists with these details. Sign in with your "
                "original method, then add this one from your account.",
                status_code=409,
                code="ACCOUNT_EXISTS_DIFFERENT_METHOD",
            )

        target.firebase_uid = identity.uid
        # Firebase now proves ownership; the legacy hash must not remain a
        # second way into the account.
        target.password_hash = None
        logger.info("AUTH_ACCOUNT_LINKED: user_id=%s linked to firebase identity", target.id)
        return target

    def _create_customer(
        self,
        identity: FirebaseIdentity,
        email: str | None,
        phone: str | None,
        data: SyncUserRequest,
    ) -> User:
        if email and self.db.query(User.id).filter(User.email == email).first():
            # Unverified email that already belongs to someone - do not link
            # (unproven ownership) and do not duplicate.
            raise ConflictError("An account with this email already exists.")
        if not email and not phone:
            raise AuthenticationError("Your sign-in has no email or phone number.")

        customer_role = self.db.query(Role).filter_by(name=CUSTOMER).first()
        if not customer_role:
            logger.error("AUTH_ROLE_NOT_FOUND: Baseline CUSTOMER role is missing in database.")
            raise AppException("System role configuration error.", status_code=500)

        user = User(
            firebase_uid=identity.uid,
            name=self._display_name(identity, email, data),
            email=email,
            phone=phone,
            status="ACTIVE",
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserRole(user_id=user.id, role_id=customer_role.id, is_primary=True))
        logger.info("AUTH_USER_CREATED: user_id=%s via %s", user.id, identity.sign_in_provider)
        return user

    @staticmethod
    def _display_name(identity: FirebaseIdentity, email: str | None, data: SyncUserRequest) -> str:
        given = " ".join(p for p in (data.first_name, data.last_name) if p)
        name = given or (identity.name or "").strip() or (email.split("@")[0] if email else "")
        return (name or "Customer")[:150]

    def _refresh_contact_details(self, user: User, verified_email: str | None, phone: str | None) -> None:
        # Keep copies in step with Firebase when the customer adds/changes
        # a verified email or phone there. Unique violations surface as
        # IntegrityError -> ConflictError in sync_user.
        if verified_email and user.email != verified_email:
            user.email = verified_email
        if phone and user.phone != phone:
            user.phone = phone

    # ------------------------------------------------------------------
    # One-time migration of pre-Firebase accounts
    # ------------------------------------------------------------------

    def migrate_legacy_account(self, data: LegacyMigrationRequest) -> LegacyMigrationResponse:
        """Move a pre-Firebase account into Firebase using its old password.

        The client calls this only after Firebase rejected an email/password
        sign-in. On success the Firebase user exists with the same password,
        the row is linked, and the legacy hash is erased - so this endpoint
        can succeed at most once per account.
        """
        user = self._find_legacy_user(data.identifier)
        password_ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
        if not user or not password_ok or user.status != "ACTIVE" or not user.email:
            logger.info("AUTH_LEGACY_MIGRATION_REJECTED: invalid credentials")
            raise AuthenticationError("Invalid credentials.")

        # Staff emails were entered by an admin; customers must prove theirs.
        is_staff = bool(STAFF_ROLES.intersection(self.get_role_names(user.id)))
        reset_required = False
        try:
            try:
                uid = self.firebase.create_user(
                    email=user.email,
                    password=data.password,
                    display_name=user.name,
                    email_verified=is_staff,
                )
            except FirebasePasswordRejectedError:
                # Old password fails the project's password policy: create the
                # account without one and have the owner set a new password.
                uid = self.firebase.create_user(
                    email=user.email,
                    password=None,
                    display_name=user.name,
                    email_verified=is_staff,
                )
                reset_required = True
        except FirebaseEmailExistsError as exc:
            raise ConflictError(
                "This account has already been upgraded. Sign in with your email, "
                "or use Forgot password."
            ) from exc
        except FirebaseUnavailableError as exc:
            raise auth_unavailable_error() from exc

        try:
            with _transaction(self.db):
                user.firebase_uid = uid
                user.password_hash = None
        except Exception:
            self.firebase.delete_user(uid)
            raise

        logger.info("AUTH_LEGACY_MIGRATED: user_id=%s moved to firebase", user.id)
        if reset_required:
            raise AppException(
                "Your account was upgraded. Please set a new password using the link we send you.",
                status_code=409,
                code="PASSWORD_RESET_REQUIRED",
                details={"email": user.email},
            )
        return LegacyMigrationResponse(email=user.email)

    def _find_legacy_user(self, identifier: str) -> User | None:
        identifier = identifier.strip()
        query = self.db.query(User).filter(
            User.firebase_uid.is_(None), User.password_hash.is_not(None)
        )
        if "@" in identifier:
            return query.filter(User.email == normalize_email(identifier)).first()
        try:
            return query.filter(User.phone == normalize_phone(identifier)).first()
        except ValueError:
            return None
