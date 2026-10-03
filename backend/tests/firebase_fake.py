"""In-memory stand-in for the Firebase Admin SDK.

Installed for every test by conftest.py (`set_firebase(fake_firebase)`), so
no test touches the network or needs a service account. Tokens are opaque
strings minted by `issue()`; anything else is rejected exactly like a
forged/garbled token would be by the real SDK.
"""

import itertools
import secrets

from sqlalchemy.orm import Session

from app.core.firebase import (
    FirebaseEmailExistsError,
    FirebaseGateway,
    FirebaseIdentity,
    FirebasePasswordRejectedError,
    FirebaseTokenError,
    FirebaseUnavailableError,
)
from app.models.user import User


class FakeFirebase(FirebaseGateway):
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._tokens: dict[str, FirebaseIdentity] = {}
        self._expired: set[str] = set()
        self.users: dict[str, dict] = {}  # uid -> {email, password, disabled, email_verified}
        self.revoked: list[str] = []
        self.unavailable = False
        self.min_password_length = 6
        self._uids = itertools.count(1)

    # --- test helpers ---------------------------------------------------

    def issue(
        self,
        uid: str,
        *,
        email: str | None = None,
        email_verified: bool = True,
        phone: str | None = None,
        name: str | None = None,
        provider: str = "password",
        expired: bool = False,
    ) -> str:
        token = f"fake-id-token.{secrets.token_urlsafe(12)}"
        self._tokens[token] = FirebaseIdentity(
            uid=uid,
            email=email,
            email_verified=email_verified,
            phone=phone,
            name=name,
            sign_in_provider=provider,
        )
        if expired:
            self._expired.add(token)
        return token

    # --- FirebaseGateway --------------------------------------------------

    def verify_id_token(self, token: str) -> FirebaseIdentity:
        if self.unavailable:
            raise FirebaseUnavailableError("down")
        if token in self._expired:
            raise FirebaseTokenError("expired")
        identity = self._tokens.get(token)
        if identity is None:
            raise FirebaseTokenError("invalid")
        return identity

    def create_user(self, *, email, password, display_name, email_verified) -> str:
        if self.unavailable:
            raise FirebaseUnavailableError("down")
        if any(u["email"] == email for u in self.users.values()):
            raise FirebaseEmailExistsError(email)
        if password is not None and len(password) < self.min_password_length:
            raise FirebasePasswordRejectedError()
        uid = f"fb-created-{next(self._uids)}"
        self.users[uid] = {
            "email": email,
            "password": password,
            "display_name": display_name,
            "email_verified": email_verified,
            "disabled": False,
        }
        return uid

    def update_password(self, uid: str, password: str) -> None:
        if self.unavailable:
            raise FirebaseUnavailableError("down")
        self.users.setdefault(uid, {"email": None, "disabled": False})["password"] = password

    def set_disabled(self, uid: str, disabled: bool) -> None:
        self.users.setdefault(uid, {"email": None})["disabled"] = disabled

    def revoke_sessions(self, uid: str) -> None:
        self.revoked.append(uid)

    def delete_user(self, uid: str) -> None:
        self.users.pop(uid, None)


fake_firebase = FakeFirebase()


def auth_headers_for(db: Session, user: User, **claims) -> dict[str, str]:
    """Bearer header for `user`, linking it to a fake Firebase UID first.

    Defaults to a verified email/password sign-in with the user's email.
    """
    if not user.firebase_uid:
        user.firebase_uid = f"fb-uid-{user.id}"
        db.commit()
        db.refresh(user)
    claims.setdefault("email", user.email)
    token = fake_firebase.issue(user.firebase_uid, **claims)
    return {"Authorization": f"Bearer {token}"}
