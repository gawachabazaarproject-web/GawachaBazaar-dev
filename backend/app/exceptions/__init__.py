"""Application exceptions package."""

from app.exceptions.base import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.exceptions.handlers import register_exception_handlers

__all__ = [
    "AppException",
    "AuthenticationError",
    "AuthorizationError",
    "BusinessValidationError",
    "ConflictError",
    "NotFoundError",
    "register_exception_handlers",
]
