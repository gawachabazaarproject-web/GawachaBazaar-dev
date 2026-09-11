"""Packaging domain schemas: operations, inputs, outputs."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Packaging Operation
# ---------------------------------------------------------------------------


class CreatePackagingOperationRequest(BaseSchema):
    """Status always starts DRAFT; performed_by_user_id comes from the
    authenticated user. Neither is accepted here.
    """

    packaging_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=150)
    location_id: int
    remarks: str | None = Field(default=None)


class PackagingOperationResponse(BaseSchema):
    id: int
    packaging_code: str
    name: str
    location_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    performed_by_user_id: int
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class PackagingOperationListResponse(BaseSchema):
    items: list[PackagingOperationResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Packaging Input
# ---------------------------------------------------------------------------


class CreatePackagingInputRequest(BaseSchema):
    inventory_lot_id: int
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)


class PackagingInputResponse(BaseSchema):
    id: int
    packaging_operation_id: int
    inventory_lot_id: int
    quantity: Decimal
    created_at: datetime


# ---------------------------------------------------------------------------
# Packaging Output
# ---------------------------------------------------------------------------


class CreatePackagingOutputRequest(BaseSchema):
    """The inventory lot is resolved server-side from
    (batch_id, variant_id, operation.location_id) - never client-supplied.
    """

    variant_id: int
    batch_id: int
    package_count: int = Field(..., gt=0)
    total_quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)


class PackagingOutputResponse(BaseSchema):
    id: int
    packaging_operation_id: int
    inventory_lot_id: int
    package_count: int
    total_quantity: Decimal
    created_at: datetime


# ---------------------------------------------------------------------------
# Operation Detail (with inputs/outputs)
# ---------------------------------------------------------------------------


class PackagingOperationDetailResponse(PackagingOperationResponse):
    inputs: list[PackagingInputResponse] = Field(default_factory=list)
    outputs: list[PackagingOutputResponse] = Field(default_factory=list)
