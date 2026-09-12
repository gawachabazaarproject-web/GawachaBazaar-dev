"""Supplier domain schemas.

Suppliers are staff-managed business records, never customer-facing.
Ratings/evaluations are ADMIN-only (see app/api/v1/suppliers.py) - a
supplier never logs in and never sees its own evaluation.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100

SupplierStatus = Literal["ACTIVE", "INACTIVE"]


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class CreateSupplierRequest(BaseSchema):
    business_name: str = Field(..., min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    status: SupplierStatus = Field(default="ACTIVE")
    notes: str | None = Field(default=None)


class UpdateSupplierRequest(BaseSchema):
    business_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    status: SupplierStatus | None = Field(default=None)
    notes: str | None = Field(default=None)


class SupplierResponse(BaseSchema):
    id: int
    business_name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseSchema):
    items: list[SupplierResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Supplier <-> Product
# ---------------------------------------------------------------------------


class LinkSupplierProductRequest(BaseSchema):
    product_id: int = Field(..., gt=0)
    active: bool = Field(default=True)
    supplier_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None)


class UpdateSupplierProductRequest(BaseSchema):
    active: bool | None = Field(default=None)
    supplier_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None)


class SupplierProductResponse(BaseSchema):
    id: int
    supplier_id: int
    product_id: int
    product_name: str
    active: bool
    supplier_reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SupplierProductListResponse(BaseSchema):
    items: list[SupplierProductResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Supplier evaluations (ADMIN-only, append-only)
# ---------------------------------------------------------------------------

_RatingField = Field(..., ge=0, le=5, max_digits=2, decimal_places=1)


class CreateSupplierEvaluationRequest(BaseSchema):
    quality_rating: Decimal = _RatingField
    delivery_rating: Decimal = _RatingField
    price_rating: Decimal = _RatingField
    reliability_rating: Decimal = _RatingField
    responsiveness_rating: Decimal = _RatingField
    overall_rating: Decimal = _RatingField
    notes: str | None = Field(default=None)


class SupplierEvaluationResponse(BaseSchema):
    id: int
    supplier_id: int
    evaluated_by_user_id: int
    quality_rating: Decimal
    delivery_rating: Decimal
    price_rating: Decimal
    reliability_rating: Decimal
    responsiveness_rating: Decimal
    overall_rating: Decimal
    notes: str | None
    created_at: datetime


class SupplierEvaluationListResponse(BaseSchema):
    items: list[SupplierEvaluationResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Supplier performance dashboard data
# ---------------------------------------------------------------------------


class SupplierAverageRatings(BaseSchema):
    quality: Decimal | None
    delivery: Decimal | None
    price: Decimal | None
    reliability: Decimal | None
    responsiveness: Decimal | None
    overall: Decimal | None


class SupplierProductSupplySummary(BaseSchema):
    product_id: int
    product_name: str
    unit: str
    batch_count: int
    total_quantity_supplied: Decimal


class SupplierPerformanceResponse(BaseSchema):
    supplier: SupplierResponse
    products_supplied: list[str]
    supply_summary: list[SupplierProductSupplySummary]
    total_batches_supplied: int
    last_supply_date: date | None
    evaluation_count: int
    latest_evaluation: SupplierEvaluationResponse | None
    average_ratings: SupplierAverageRatings
