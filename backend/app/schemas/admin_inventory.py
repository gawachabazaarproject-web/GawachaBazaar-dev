"""Admin-facing inventory schemas.

Separate module for the same reason admin_order.py/admin_catalog.py are:
these enrich the bare InventoryLotResponse (raw foreign keys only) with the
joined product/variant/category/warehouse/batch names an admin table
actually needs to be usable, without risking a circular import as this
surface grows. `on_hand`/`reserved`/`available` are always `quantity`,
`reserved_quantity`, and `quantity - reserved_quantity` read straight off
InventoryLot - never recomputed differently or cached separately (see the
"AVAILABLE = ON_HAND - RESERVED" rule in the admin-panel Inventory spec).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.inventory import BatchResponse, StockMovementResponse

MAX_PAGE_SIZE = 100

# UI-facing status computed from real data (lot.status, quantity vs
# reserved_quantity, batch.expiry_date) - never a fabricated field. See
# InventoryService.admin_list_lots for exactly how each value is derived.
LotOperationalStatus = str  # IN_STOCK | LOW_STOCK | OUT_OF_STOCK | EXPIRING | EXPIRED | INACTIVE


class AdminInventoryLotListItemResponse(BaseSchema):
    id: int
    product_id: int
    product_name: str
    variant_id: int
    variant_name: str
    sku: str
    category_id: int
    category_name: str
    location_id: int
    location_name: str
    location_code: str
    batch_id: int
    batch_code: str
    batch_expiry_date: date | None
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    lot_status: str
    operational_status: LotOperationalStatus
    last_movement_at: datetime | None
    updated_at: datetime


class AdminInventoryLotListResponse(BaseSchema):
    items: list[AdminInventoryLotListItemResponse]
    page: int
    page_size: int
    total: int


class RelatedOrderResponse(BaseSchema):
    """One order that has reserved/consumed stock from this lot, via
    InventoryReservationItem - never a duplicated/derived order concept."""

    order_id: int
    order_number: str
    reserved_quantity: Decimal
    reservation_status: str


class AdminInventoryLotDetailResponse(BaseSchema):
    id: int
    product_id: int
    product_name: str
    product_image_url: str | None
    category_id: int
    category_name: str
    variant_id: int
    variant_name: str
    sku: str
    unit: str
    location_id: int
    location_name: str
    location_code: str
    location_city: str
    location_status: str
    batch: BatchResponse
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    lot_status: str
    operational_status: LotOperationalStatus
    created_at: datetime
    updated_at: datetime
    recent_movements: list[StockMovementResponse]
    related_orders: list[RelatedOrderResponse]


class InventoryDashboardResponse(BaseSchema):
    """Every figure here is a real aggregate query result - see
    InventoryService.admin_dashboard. Nothing is a placeholder; a count
    that is genuinely zero is returned as 0, never omitted or faked.
    """

    total_skus: int
    total_on_hand: Decimal
    total_reserved: Decimal
    total_available: Decimal
    low_stock_count: int
    out_of_stock_count: int
    expiring_batches_count: int
    expired_batches_count: int
    recent_movements: list[StockMovementResponse]
    warehouses_requiring_attention: int


class ReceiveStockRequest(BaseSchema):
    """Get-or-create the (batch, variant, location) lot and apply one
    RECEIPT movement, atomically - see InventoryService.receive_stock.
    This is the "Stock Receiving" convenience the raw POST /lots + POST
    /lots/{id}/movements two-step doesn't offer as a single admin action.

    `batch_id` is optional - every InventoryLot still requires a real
    Batch row (traceability - Packaging/QualityCheck both reference lots
    by batch), but an admin just adding stock with no existing batch to
    pick shouldn't have to think about harvest dates or batch codes to do
    it. Omitting it makes receive_stock create a minimal batch
    automatically (see its docstring) - the traceability row still
    exists, it's just server-generated instead of admin-authored.
    """

    batch_id: int | None = Field(default=None, gt=0)
    variant_id: int = Field(..., gt=0)
    location_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    remarks: str | None = Field(default=None)


class ReconcileStockRequest(BaseSchema):
    """Physical-count reconciliation - computes the ADJUSTMENT_IN/OUT
    movement from the difference server-side (never client-supplied
    direction/quantity), so the admin only ever states what they counted
    and why, never the raw signed delta.
    """

    physical_count: Decimal = Field(..., ge=0, max_digits=12, decimal_places=3)
    reason: str = Field(..., min_length=1, max_length=200)
    notes: str | None = Field(default=None)


class TransferStockRequest(BaseSchema):
    """Atomically moves quantity from one lot to the same batch+variant at
    a different location: TRANSFER_OUT on the source (blocked if it would
    go negative, same as any other movement) then TRANSFER_IN on a
    get-or-created destination lot. No in-transit intermediate state
    exists in the backend (no transfer-request entity), so this is an
    immediate, atomic transfer - not a multi-step approval workflow the
    schema has no state machine for.
    """

    source_lot_id: int = Field(..., gt=0)
    destination_location_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    remarks: str | None = Field(default=None)


class TransferStockResponse(BaseSchema):
    source_lot: AdminInventoryLotListItemResponse
    destination_lot: AdminInventoryLotListItemResponse
