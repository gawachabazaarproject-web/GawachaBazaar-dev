"""Centralized application exception hierarchy.

Provides explicit, predictable domain and operational exceptions.
All exceptions translate to the standard API error contract:
{
    "code": "...",
    "message": "...",
    "details": null
}
"""

from typing import Any

from fastapi import status


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str = "An internal application error occurred",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(
        self, message: str = "Resource not found", details: Any = None
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            details=details,
        )


class AuthenticationError(AppException):
    """Raised when credentials are invalid or missing."""

    def __init__(
        self, message: str = "Authentication failed", details: Any = None
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_ERROR",
            details=details,
        )


class AuthorizationError(AppException):
    """Raised when an authenticated user lacks permission for an action."""

    def __init__(
        self, message: str = "Permission denied", details: Any = None
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="AUTHORIZATION_ERROR",
            details=details,
        )


class ConflictError(AppException):
    """Raised when an action conflicts with existing state (e.g. duplicate resource)."""

    def __init__(
        self, message: str = "Resource conflict", details: Any = None
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT_ERROR",
            details=details,
        )


class BusinessValidationError(AppException):
    """Raised when business logic constraints are violated."""

    def __init__(
        self, message: str = "Business validation failed", details: Any = None
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="BUSINESS_VALIDATION_ERROR",
            details=details,
        )
