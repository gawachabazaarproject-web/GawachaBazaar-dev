"""Authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.permissions import role_has_permission
from app.core.roles import ADMIN, CUSTOMER
from app.dependencies.database import get_db
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.auth import AuthContext, AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Not authenticated.")
    if credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Invalid authentication scheme.")
    return credentials.credentials


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    """Verified Firebase identity + ACTIVE application user, WITHOUT the
    email-verification gate. Only for endpoints an unverified user must
    reach (GET /auth/me, so the app can show the verify-email screen)."""
    return AuthService(db).resolve(bearer_token(credentials))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the `Authorization: Bearer
    <Firebase ID token>` header.

    The token is verified with the Firebase Admin SDK (signature, expiry,
    audience = this Firebase project); the user is looked up by the
    verified UID only - never by an id/email/phone the client sends. The
    user must be ACTIVE, and email/password sign-ins must have a verified
    email.
    """
    return AuthService(db).resolve_current_user(bearer_token(credentials))


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    """Dependency factory enforcing Role-Based Access Control (RBAC).

    Composes on top of `get_current_user` (authentication: "who is this user?")
    to answer authorization ("does this user have one of the required roles?").

    Role membership is checked against current database state (`user_roles`)
    on every request, not against JWT claims - so a role change takes effect
    immediately rather than waiting for access-token expiration.

    ANY of the given role names is sufficient (no role hierarchy in Phase 9).
    An unauthenticated caller fails in `get_current_user` with 401. An
    authenticated caller lacking every required role fails here with 403.
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        has_required_role = (
            db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(
                UserRole.user_id == current_user.id,
                Role.name.in_(allowed_roles),
            )
            .first()
            is not None
        )
        if not has_required_role:
            raise AuthorizationError(
                "You do not have permission to perform this action."
            )
        return current_user

    return role_checker


def require_permission(permission: str) -> Callable[..., Any]:
    """Dependency factory enforcing a granular admin-panel permission.

    Layered on top of `require_roles`, not a replacement for it: this reads
    the same live `user_roles` state and checks it against the static
    `ROLE_PERMISSIONS` map in `app/core/permissions.py`. A role's granted
    permissions are code, not data - changing what a role can do here is a
    backend deploy, not a runtime toggle, which is deliberate for anything
    this sensitive.
    """

    def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role_names = [
            name
            for (name,) in (
                db.query(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .filter(UserRole.user_id == current_user.id)
                .all()
            )
        ]
        if not role_has_permission(role_names, permission):
            raise AuthorizationError(
                "You do not have permission to perform this action."
            )
        return current_user

    return permission_checker


# Convenience dependencies for the two most common audiences.
get_current_customer = require_roles(CUSTOMER)
get_current_admin = require_roles(ADMIN)
