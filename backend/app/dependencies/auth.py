"""Authentication and authorization dependency boundaries.

Architecture foundation for upcoming Phase 8 (Authentication) and Phase 9 (Authorization / RBAC).
These dependency boundaries are intentionally not wired into active routes in this checkpoint.
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.exceptions.base import AuthenticationError, AuthorizationError


def get_current_user(
    db: Session = Depends(get_db),
) -> Any:
    """Dependency boundary for resolving the authenticated user from request credentials.

    To be fully implemented in Phase 8 (Authentication).
    """
    raise AuthenticationError(
        "Authentication dependency boundary - active resolution will be implemented in Phase 8."
    )


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    """Dependency factory boundary for Role-Based Access Control (RBAC).

    To be fully implemented in Phase 9 (Authorization / RBAC).
    """

    def role_checker(
        current_user: Any = Depends(get_current_user),
    ) -> Any:
        raise AuthorizationError(
            "Authorization dependency boundary - role checking will be implemented in Phase 9."
        )

    return role_checker
