from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


def _clean_name_part(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class SyncUserRequest(BaseSchema):
    """Optional profile details sent right after a Firebase sign-in/sign-up.

    Identity (uid, email, phone, verification) is NEVER read from this body -
    only from the verified Firebase ID token. These fields only name a
    newly created application user (email registration collects first and
    last name; Google supplies a display name in the token; phone sign-up
    may send neither).
    """

    first_name: str | None = Field(None, max_length=75)
    last_name: str | None = Field(None, max_length=75)

    _clean = field_validator("first_name", "last_name", mode="after")(_clean_name_part)


class LegacyMigrationRequest(BaseSchema):
    """Credentials of an account created before the Firebase cutover."""

    identifier: str = Field(..., min_length=3, max_length=255, description="Email address or phone number")
    password: str = Field(..., min_length=1, max_length=128)


class LegacyMigrationResponse(BaseSchema):
    """The account now exists in Firebase with the same password; the
    client signs in to Firebase with this email."""

    email: str
    message: str = "Account upgraded. Signing you in."


class UserResponse(BaseSchema):
    """Sanitized user profile response (no passwords, hashes, or credentials)."""

    id: int
    name: str
    email: str | None
    phone: str | None
    status: str
    created_at: datetime
    roles: list[str] = Field(
        default_factory=list,
        description="Role names currently assigned to this user (from user_roles), "
        "e.g. ['ADMIN']. Read from the database on every request, never from "
        "the token, so a role change takes effect immediately.",
    )


class AuthUserResponse(UserResponse):
    """UserResponse plus facts about the current Firebase sign-in."""

    email_verified: bool = Field(description="From the verified Firebase ID token.")
    sign_in_provider: str | None = Field(
        None, description='"password", "google.com", or "phone".'
    )
