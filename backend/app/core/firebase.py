"""Firebase Admin SDK boundary.

The only module that talks to Firebase. Everything else depends on the
`FirebaseGateway` interface and gets the process-wide instance from
`get_firebase()` - tests swap in a fake with `set_firebase()` so the suite
never needs network access or a real service account.

Firebase is the identity provider (passwords, Google OAuth, phone OTP,
email verification, password reset). The backend never sees a credential:
it verifies the Firebase ID token the client sends on every request and
trusts only the claims inside a token that passed verification.
"""

import json
import os
import threading
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import logger


@dataclass(frozen=True)
class FirebaseIdentity:
    """Claims from a verified Firebase ID token - the only source of truth
    for who the caller is. Never populated from request bodies/headers."""

    uid: str
    email: str | None
    email_verified: bool
    phone: str | None
    name: str | None
    # "password", "google.com", "phone", ... - the method used for THIS sign-in.
    sign_in_provider: str | None


class FirebaseTokenError(Exception):
    """ID token missing, malformed, forged, expired, or for another project.

    `reason` is a short machine code ("expired", "revoked", "invalid") safe
    to log; the token itself is never logged.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class FirebaseUnavailableError(Exception):
    """Firebase is not configured, or could not be reached (e.g. the
    public-key fetch failed). Callers answer 503, not 401 - the caller's
    token may be perfectly valid."""


class FirebaseEmailExistsError(Exception):
    """A Firebase user with this email already exists."""


class FirebasePasswordRejectedError(Exception):
    """The Firebase project's password policy refused the password."""


class FirebaseGateway:
    """Interface. Methods raise FirebaseUnavailableError when the Admin SDK
    is not configured/reachable."""

    def verify_id_token(self, token: str) -> FirebaseIdentity:
        raise NotImplementedError

    def create_user(
        self, *, email: str, password: str | None, display_name: str | None, email_verified: bool
    ) -> str:
        """Create an email/password Firebase user and return its UID.

        password=None creates the account without one (the owner sets it via
        a password-reset email). Raises FirebaseEmailExistsError, or
        FirebasePasswordRejectedError when the project's password policy
        refuses `password`.
        """
        raise NotImplementedError

    def update_password(self, uid: str, password: str) -> None:
        raise NotImplementedError

    def set_disabled(self, uid: str, disabled: bool) -> None:
        raise NotImplementedError

    def revoke_sessions(self, uid: str) -> None:
        """Invalidate the user's Firebase refresh tokens (signs out every
        device once its current ID token - max 1h - expires)."""
        raise NotImplementedError

    def delete_user(self, uid: str) -> None:
        raise NotImplementedError


def _anonymous_credential():
    """A firebase_admin credential that carries no identity (see _get_app)."""
    from firebase_admin import credentials
    from google.auth.credentials import AnonymousCredentials

    class _Anonymous(credentials.Base):
        def get_credential(self):
            return AnonymousCredentials()

    return _Anonymous()


class FirebaseAdminGateway(FirebaseGateway):
    """Real implementation backed by the `firebase_admin` package."""

    def __init__(self) -> None:
        self._app = None
        self._lock = threading.Lock()

    def _get_app(self):
        if self._app is not None:
            return self._app
        with self._lock:
            if self._app is not None:
                return self._app
            if not settings.FIREBASE_PROJECT_ID:
                raise FirebaseUnavailableError("FIREBASE_PROJECT_ID is not configured.")

            import firebase_admin
            from firebase_admin import credentials

            try:
                self._app = firebase_admin.get_app("gawachabazaar")
                return self._app
            except ValueError:
                pass

            credential = None
            raw_cred = (settings.FIREBASE_SERVICE_ACCOUNT_JSON or "").strip()
            if raw_cred:
                if os.path.isfile(raw_cred):
                    try:
                        credential = credentials.Certificate(raw_cred)
                    except Exception as exc:
                        logger.error("FIREBASE_CREDENTIAL_FILE_LOAD_FAILED: %s", type(exc).__name__)
                        raise FirebaseUnavailableError(
                            "FIREBASE_SERVICE_ACCOUNT_JSON file could not be read."
                        ) from exc
                else:
                    try:
                        info = json.loads(raw_cred)
                    except ValueError as exc:
                        raise FirebaseUnavailableError(
                            "FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON."
                        ) from exc
                    try:
                        credential = credentials.Certificate(info)
                    except Exception as exc:
                        logger.error("FIREBASE_CERTIFICATE_INIT_FAILED: %s", type(exc).__name__)
                        raise FirebaseUnavailableError(
                            "FIREBASE_SERVICE_ACCOUNT_JSON certificate is invalid."
                        ) from exc

            # No service account: firebase_admin would fall back to
            # Application Default Credentials and raise DefaultCredentialsError
            # on the first verify_id_token when none exist (any host that is
            # not Google Cloud). Token verification only needs Google's public
            # certificates, so use anonymous credentials instead - sign-in
            # keeps working and admin operations fail as "unavailable".
            if credential is None and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                logger.warning(
                    "FIREBASE_SERVICE_ACCOUNT_JSON is not set: ID tokens are verified, "
                    "but staff creation, password resets and legacy migration are unavailable."
                )
                credential = _anonymous_credential()

            try:
                self._app = firebase_admin.initialize_app(
                    credential,
                    options={"projectId": settings.FIREBASE_PROJECT_ID},
                    name="gawachabazaar",
                )
            except ValueError:
                self._app = firebase_admin.get_app("gawachabazaar")
            return self._app

    def verify_id_token(self, token: str) -> FirebaseIdentity:
        from firebase_admin import auth
        from google.auth import exceptions as google_auth_exceptions

        app = self._get_app()
        try:
            claims = auth.verify_id_token(token, app=app, clock_skew_seconds=10)
        except auth.ExpiredIdTokenError as exc:
            raise FirebaseTokenError("expired") from exc
        except auth.RevokedIdTokenError as exc:
            raise FirebaseTokenError("revoked") from exc
        except auth.CertificateFetchError as exc:
            logger.error("FIREBASE_CERT_FETCH_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError("Could not reach Firebase.") from exc
        except (auth.InvalidIdTokenError, ValueError) as exc:
            raise FirebaseTokenError("invalid") from exc
        except google_auth_exceptions.GoogleAuthError as exc:
            logger.error("FIREBASE_VERIFY_CREDENTIALS_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError("Firebase credentials are not configured.") from exc

        firebase_claims = claims.get("firebase") or {}
        return FirebaseIdentity(
            uid=claims["uid"],
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
            phone=claims.get("phone_number"),
            name=claims.get("name"),
            sign_in_provider=firebase_claims.get("sign_in_provider"),
        )

    def create_user(
        self, *, email: str, password: str | None, display_name: str | None, email_verified: bool
    ) -> str:
        from firebase_admin import auth, exceptions
        from google.auth import exceptions as google_auth_exceptions

        kwargs = {"email": email, "email_verified": email_verified}
        if password is not None:
            kwargs["password"] = password
        if display_name:
            kwargs["display_name"] = display_name
        try:
            record = auth.create_user(app=self._get_app(), **kwargs)
        except auth.EmailAlreadyExistsError as exc:
            raise FirebaseEmailExistsError(email) from exc
        except (ValueError, exceptions.InvalidArgumentError) as exc:
            if password is not None:
                raise FirebasePasswordRejectedError() from exc
            raise
        except (google_auth_exceptions.GoogleAuthError, exceptions.FirebaseError) as exc:
            logger.error("FIREBASE_CREATE_USER_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError(
                "Could not reach Firebase or credentials are not configured."
            ) from exc
        return record.uid

    def update_password(self, uid: str, password: str) -> None:
        from firebase_admin import auth, exceptions
        from google.auth import exceptions as google_auth_exceptions

        try:
            auth.update_user(uid, password=password, app=self._get_app())
        except (google_auth_exceptions.GoogleAuthError, exceptions.FirebaseError) as exc:
            logger.error("FIREBASE_UPDATE_PASSWORD_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError(
                "Could not reach Firebase or credentials are not configured."
            ) from exc

    def set_disabled(self, uid: str, disabled: bool) -> None:
        from firebase_admin import auth, exceptions
        from google.auth import exceptions as google_auth_exceptions

        try:
            auth.update_user(uid, disabled=disabled, app=self._get_app())
        except (google_auth_exceptions.GoogleAuthError, exceptions.FirebaseError) as exc:
            logger.error("FIREBASE_SET_DISABLED_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError(
                "Could not reach Firebase or credentials are not configured."
            ) from exc

    def revoke_sessions(self, uid: str) -> None:
        from firebase_admin import auth, exceptions
        from google.auth import exceptions as google_auth_exceptions

        try:
            auth.revoke_refresh_tokens(uid, app=self._get_app())
        except (google_auth_exceptions.GoogleAuthError, exceptions.FirebaseError) as exc:
            logger.error("FIREBASE_REVOKE_SESSIONS_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError(
                "Could not reach Firebase or credentials are not configured."
            ) from exc

    def delete_user(self, uid: str) -> None:
        from firebase_admin import auth, exceptions
        from google.auth import exceptions as google_auth_exceptions

        try:
            auth.delete_user(uid, app=self._get_app())
        except auth.UserNotFoundError:
            pass
        except (google_auth_exceptions.GoogleAuthError, exceptions.FirebaseError) as exc:
            logger.error("FIREBASE_DELETE_USER_FAILED: %s", type(exc).__name__)
            raise FirebaseUnavailableError(
                "Could not reach Firebase or credentials are not configured."
            ) from exc


_gateway: FirebaseGateway | None = None


def get_firebase() -> FirebaseGateway:
    global _gateway
    if _gateway is None:
        _gateway = FirebaseAdminGateway()
    return _gateway


def set_firebase(gateway: FirebaseGateway | None) -> None:
    """Replace the process-wide gateway (tests only)."""
    global _gateway
    _gateway = gateway
