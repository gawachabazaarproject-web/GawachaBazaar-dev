"""Inventory domain schemas: locations, lots, stock movements, batches."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

LocationStatus = Literal["ACTIVE", "INACTIVE"]
LotStatus = Literal["ACTIVE", "INACTIVE", "DEPLETED"]
MovementType = Literal[
    "RECEIPT",
    "ADJUSTMENT_IN",
    "ADJUSTMENT_OUT",
    "DAMAGE",
    "WASTE",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "DISPATCH",
]
BatchStatus = Literal["HARVESTED", "COLLECTED", "SORTED", "GRADED", "APPROVED", "REJECTED", "EXPIRED"]
BatchUnit = Literal["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "CRATE"]

MAX_PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Batch - the model (app/models/batch.py) has existed since Phase 2/8.1/17
# but had no API surface at all (confirmed: no schema, service method, or
# route anywhere referenced it) until this admin-panel Inventory module,
# which needs it for stock receiving/traceability. This is additive only -
# no new table, no migration, just exposing what the domain model already
# supports. At least one of supplier_id/wholesaler_user_id is required,
# mirroring `ck_batches_supplier_or_wholesaler`.
# ---------------------------------------------------------------------------


class CreateBatchRequest(BaseSchema):
    product_id: int = Field(..., gt=0)
    batch_code: str = Field(..., min_length=1, max_length=100)
    harvest_date: date
    expiry_date: date | None = Field(default=None)
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    unit: BatchUnit
    status: BatchStatus = Field(default="HARVESTED")
    supplier_id: int | None = Field(default=None)
    wholesaler_user_id: int | None = Field(default=None)
    purchase_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    purchase_currency: str | None = Field(default=None, min_length=3, max_length=3)
    received_date: date | None = Field(default=None)
    receiving_reference: str | None = Field(default=None, max_length=100)


class BatchResponse(BaseSchema):
    id: int
    product_id: int
    product_name: str
    batch_code: str
    harvest_date: date
    expiry_date: date | None
    quantity: Decimal
    unit: str
    status: str
    supplier_id: int | None
    supplier_name: str | None
    wholesaler_user_id: int | None
    purchase_price: Decimal | None
    purchase_currency: str | None
    received_date: date | None
    receiving_reference: str | None
    created_at: datetime


class BatchListResponse(BaseSchema):
    items: list[BatchResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Inventory Location
# ---------------------------------------------------------------------------


class CreateInventoryLocationRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=50)
    type: str = Field(..., min_length=1, max_length=30)
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=1, max_length=20)
    status: LocationStatus = Field(default="ACTIVE")


class UpdateInventoryLocationRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    type: str | None = Field(default=None, min_length=1, max_length=30)
    address_line_1: str | None = Field(default=None, min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    status: LocationStatus | None = Field(default=None)


class InventoryLocationResponse(BaseSchema):
    id: int
    name: str
    code: str
    type: str
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str
    status: str
    created_at: datetime
    updated_at: datetime


class InventoryLocationListResponse(BaseSchema):
    items: list[InventoryLocationResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Inventory Lot
# ---------------------------------------------------------------------------


class CreateInventoryLotRequest(BaseSchema):
    """Status is never client-supplied - it is derived from quantity on creation."""

    batch_id: int
    variant_id: int
    location_id: int
    quantity: Decimal = Field(..., ge=0, max_digits=12, decimal_places=3)


class InventoryLotResponse(BaseSchema):
    id: int
    batch_id: int
    variant_id: int
    location_id: int
    quantity: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


class InventoryLotListResponse(BaseSchema):
    items: list[InventoryLotResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Stock Movement
# ---------------------------------------------------------------------------


class CreateStockMovementRequest(BaseSchema):
    """inventory_lot_id comes from the URL; performed_by_user_id from the authenticated user.

    Neither is accepted here.
    """

    movement_type: MovementType
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    occurred_at: datetime | None = Field(default=None)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: int | None = Field(default=None)
    remarks: str | None = Field(default=None)


class StockMovementResponse(BaseSchema):
    id: int
    inventory_lot_id: int
    movement_type: str
    quantity: Decimal
    reference_type: str | None
    reference_id: int | None
    performed_by_user_id: int
    occurred_at: datetime
    remarks: str | None
    created_at: datetime


class StockMovementListResponse(BaseSchema):
    items: list[StockMovementResponse]
    page: int
    page_size: int
    total: int
