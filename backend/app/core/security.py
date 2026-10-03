"""Password (legacy only) and identifier normalization helpers.

Authentication credentials live in Firebase. `hash_password` /
`verify_password` exist solely so accounts created before the Firebase
cutover can be migrated on their first sign-in (AuthService.migrate_legacy_account).
"""

import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

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
