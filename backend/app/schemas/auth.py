from datetime import datetime
from typing import Literal

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
    roles: list[str] = Field(
        default_factory=list,
        description="Role names currently assigned to this user (from user_roles), "
        "e.g. ['ADMIN']. Read from the database on every auth response, never from "
        "the JWT, so a role change takes effect on the user's next login/refresh.",
    )


class TokenResponse(BaseSchema):
    """Authentication token response on successful registration and login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class OtpChallengeResponse(BaseSchema):
    """Returned from POST /auth/login instead of TokenResponse when the
    account requires the email-OTP second factor (every CUSTOMER/
    WHOLESALER login - see app/core/roles.py STAFF_ROLES). No token is
    issued yet; the client must call POST /auth/login/verify-otp with
    `challenge_token` and the 6-digit code emailed to `masked_email`.
    """

    otp_required: Literal[True] = True
    challenge_token: str
    masked_email: str
    expires_in_seconds: int


class VerifyLoginOtpRequest(BaseSchema):
    """Completes a login OTP challenge. `challenge_token` is the opaque
    reference from OtpChallengeResponse, not a credential by itself - the
    6-digit `code` is what actually proves control of the account's email.
    """

    challenge_token: str = Field(..., min_length=10, max_length=64)
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class RefreshTokenResponse(BaseSchema):
    """Token rotation response on successful refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutResponse(BaseSchema):
    """Confirmation message upon session revocation."""

    message: str = "Logged out successfully."
