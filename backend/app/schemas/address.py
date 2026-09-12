"""Address domain schemas.

Client never supplies user_id - always the authenticated caller. A
customer's own address book is naturally small, so this list is
unpaginated (same convention as GET /cart).
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class CreateAddressRequest(BaseSchema):
    label: str = Field(..., min_length=1, max_length=50)
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=1, max_length=20)
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    is_default: bool = False


class UpdateAddressRequest(BaseSchema):
    """All fields optional - PATCH semantics, only supplied fields change."""

    label: str | None = Field(default=None, min_length=1, max_length=50)
    address_line_1: str | None = Field(default=None, min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    is_default: bool | None = None


class AddressResponse(BaseSchema):
    id: int
    label: str
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str
    latitude: Decimal | None
    longitude: Decimal | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AddressListResponse(BaseSchema):
    items: list[AddressResponse]
