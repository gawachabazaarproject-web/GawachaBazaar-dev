"""Bulk & custom commerce domain schemas.

Client never supplies status, pricing totals, snapshot fields, or which
quote version is "current" - all server-derived. A request is priced
only via the separate admin quoting action; the customer only ever
accepts or cancels.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100

BusinessType = Literal[
    "RESTAURANT", "HOTEL", "CATERER", "RETAILER", "OFFICE", "INSTITUTION", "EVENT", "OTHER"
]
RequestUnit = Literal["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "CRATE"]
AdminRequestStatus = Literal["UNDER_REVIEW", "REJECTED", "CANCELLED", "EXPIRED"]


# ---------------------------------------------------------------------------
# Bulk customer profile
# ---------------------------------------------------------------------------


class UpsertBulkCustomerProfileRequest(BaseSchema):
    business_name: str = Field(..., min_length=1, max_length=200)
    business_type: BusinessType
    contact_person: str | None = Field(default=None, max_length=150)


class BulkCustomerProfileResponse(BaseSchema):
    id: int
    user_id: int
    business_name: str
    business_type: str
    contact_person: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Bulk order request + items
# ---------------------------------------------------------------------------


class CreateBulkOrderRequestItemRequest(BaseSchema):
    """Exactly one of product_id / custom_item_name must be set - Mode A
    (existing catalog product) vs Mode B (fully custom ask)."""

    product_id: int | None = Field(default=None, gt=0)
    custom_item_name: str | None = Field(default=None, min_length=1, max_length=150)
    requested_quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    unit: RequestUnit
    customer_notes: str | None = Field(default=None)

    @model_validator(mode="after")
    def _exactly_one_of_product_or_custom(self) -> "CreateBulkOrderRequestItemRequest":
        if (self.product_id is None) == (self.custom_item_name is None):
            raise ValueError(
                "Exactly one of product_id or custom_item_name must be provided."
            )
        return self


class CreateBulkOrderRequestRequest(BaseSchema):
    address_id: int | None = Field(default=None, gt=0)
    requested_delivery_date: date | None = Field(default=None)
    customer_notes: str | None = Field(default=None)
    items: list[CreateBulkOrderRequestItemRequest] = Field(..., min_length=1)


class BulkOrderRequestItemResponse(BaseSchema):
    id: int
    product_id: int | None
    product_name: str | None
    custom_item_name: str | None
    requested_quantity: Decimal
    unit: str
    customer_notes: str | None
    created_at: datetime


class BulkOrderRequestAddressResponse(BaseSchema):
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str


class BulkOrderRequestResponse(BaseSchema):
    id: int
    status: str
    requested_delivery_date: date | None
    customer_notes: str | None
    address: BulkOrderRequestAddressResponse | None
    items: list[BulkOrderRequestItemResponse]
    created_at: datetime
    updated_at: datetime


class BulkOrderRequestListResponse(BaseSchema):
    items: list[BulkOrderRequestResponse]
    page: int
    page_size: int
    total: int


class AdminBulkOrderRequestResponse(BulkOrderRequestResponse):
    """Ops-facing: adds internal fields never shown to the customer."""

    customer_user_id: int
    admin_notes: str | None


class AdminBulkOrderRequestListResponse(BaseSchema):
    items: list[AdminBulkOrderRequestResponse]
    page: int
    page_size: int
    total: int


class ReviewBulkOrderRequestRequest(BaseSchema):
    admin_notes: str | None = Field(default=None)


class UpdateBulkOrderRequestStatusRequest(BaseSchema):
    status: AdminRequestStatus
    admin_notes: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


class QuoteVersionItemRequest(BaseSchema):
    request_item_id: int = Field(..., gt=0)
    variant_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)


class CreateQuoteVersionRequest(BaseSchema):
    currency: str = Field(default="INR", min_length=3, max_length=3)
    valid_until: date | None = Field(default=None)
    admin_notes: str | None = Field(default=None)
    items: list[QuoteVersionItemRequest] = Field(..., min_length=1)


class QuoteItemResponse(BaseSchema):
    id: int
    request_item_id: int
    variant_id: int
    variant_name: str
    sku: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal


class QuoteVersionResponse(BaseSchema):
    id: int
    version_number: int
    status: str
    currency: str
    valid_until: date | None
    admin_notes: str | None
    items: list[QuoteItemResponse]
    created_at: datetime


class QuoteResponse(BaseSchema):
    id: int
    request_id: int
    versions: list[QuoteVersionResponse]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Inventory availability (read-only, for admin quoting - never reserves)
# ---------------------------------------------------------------------------


class VariantAvailabilityResponse(BaseSchema):
    variant_id: int
    total_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
