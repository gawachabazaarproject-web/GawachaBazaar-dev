"""Authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.auth import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve and validate the authenticated user from the Bearer JWT access token.

    Verifies signature, expiration, issuer, audience, token type ('access'),
    and ensures the server-side session and user account in the database remain active.
    """
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Not authenticated.")

    if credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Invalid authentication scheme.")

    auth_service = AuthService(db)
    return auth_service.resolve_current_user(credentials.credentials)


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
