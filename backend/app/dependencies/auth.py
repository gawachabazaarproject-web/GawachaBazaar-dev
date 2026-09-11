"""Authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.models.user import User
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
    """Dependency factory boundary for Role-Based Access Control (RBAC).

    To be fully implemented in Phase 9 (Authorization / RBAC).
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> Any:
        raise AuthorizationError(
            "Authorization dependency boundary - role checking will be implemented in Phase 9."
        )

    return role_checker
