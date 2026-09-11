from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.security import normalize_email, normalize_phone
from app.schemas.base import BaseSchema


class RegisterRequest(BaseSchema):
    """User registration payload."""

    name: str = Field(..., min_length=2, max_length=150, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    phone: str = Field(..., min_length=10, max_length=20, description="Mobile number")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )

    @field_validator("email", mode="after")
    @classmethod
    def validate_and_normalize_email(cls, v: EmailStr) -> str:
        return normalize_email(str(v))

    @field_validator("phone", mode="after")
    @classmethod
    def validate_and_normalize_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


class LoginRequest(BaseSchema):
    """User login payload accepting email or phone as identifier."""

    identifier: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email address or phone number",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Plaintext password",
    )


class RefreshTokenRequest(BaseSchema):
    """Refresh token payload."""

    refresh_token: str = Field(
        ...,
        min_length=20,
        description="Cryptographically secure opaque refresh token",
    )


class UserResponse(BaseSchema):
    """Sanitized user profile response (no passwords, hashes, or credentials)."""

    id: int
    name: str
    email: str
    phone: str
    status: str
    created_at: datetime


class TokenResponse(BaseSchema):
    """Authentication token response on successful registration and login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenResponse(BaseSchema):
    """Token rotation response on successful refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutResponse(BaseSchema):
    """Confirmation message upon session revocation."""

    message: str = "Logged out successfully."
