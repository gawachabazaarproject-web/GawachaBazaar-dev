import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    try:
        return _ph.verify(hashed_password, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def normalize_email(email: str) -> str:
    """Normalize email consistently by trimming whitespace and lowercasing.

    Does not perform provider-specific transformations (e.g. Gmail dot removal).
    """
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    """Normalize phone number to canonical international E.164 representation.

    Accepts standard 10-digit Indian numbers (e.g. 9876543210), numbers with leading zero,
    or with country code prefix (+91 or 91). Strips whitespace, hyphens, and brackets.
    """
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if cleaned.startswith("+"):
        if not re.match(r"^\+[1-9]\d{9,14}$", cleaned):
            raise ValueError("Invalid international phone format.")
        return cleaned
    if len(cleaned) == 11 and cleaned.startswith("0"):
        cleaned = cleaned[1:]
    if len(cleaned) == 10 and cleaned.isdigit():
        return f"+91{cleaned}"
    if len(cleaned) == 12 and cleaned.startswith("91") and cleaned.isdigit():
        return f"+{cleaned}"
    raise ValueError("Invalid phone number format.")


def generate_refresh_token() -> str:
    """Generate cryptographically secure, high-entropy opaque refresh token.

    Uses secrets.token_urlsafe(48) providing ~384 bits of entropy.
    Raw tokens are returned only to the client and never stored server-side.
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Compute SHA-256 digest of opaque refresh token for server-side persistence.

    SHA-256 is appropriate because the raw token has ~384 bits of entropy (unlike human
    passwords which require slow, memory-hard Argon2id).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    data: dict[str, Any] | None = None,
    *,
    user_id: int | None = None,
    session_id: int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token adhering to Phase 8 claims architecture.

    Claims: sub, sid, iat, exp, jti, type, iss, aud.
    """
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: dict[str, Any] = {
        "iat": now,
        "exp": expire,
        "jti": uuid.uuid4().hex,
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    if data:
        to_encode.update(data)
    if user_id is not None:
        to_encode["sub"] = str(user_id)
    if session_id is not None:
        to_encode["sid"] = session_id

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(
    token: str,
    *,
    verify_aud: bool = True,
    verify_iss: bool = True,
) -> dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Validates cryptographic signature, expiration, issuer, and audience.
    """
    options: dict[str, Any] = {}
    if not verify_aud:
        options["verify_aud"] = False
    if not verify_iss:
        options["verify_iss"] = False

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER if verify_iss else None,
        audience=settings.JWT_AUDIENCE if verify_aud else None,
        options=options,
    )
