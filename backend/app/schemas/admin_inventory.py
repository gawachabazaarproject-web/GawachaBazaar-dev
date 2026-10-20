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

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema
from app.schemas.inventory import (
    AmountUnit,
    BatchResponse,
    StockMovementResponse,
    check_packs_or_amount,
)

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
    # One pack of this variant is `variant_quantity` x `variant_unit`;
    # on_hand/reserved/available count packs, not that unit.
    variant_unit: str
    variant_quantity: Decimal
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
    # Stock to keep in reserve for this item (None = default) and the value in force.
    reserve_level: Decimal | None = None
    effective_reserve: Decimal | None = None
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
    variant_quantity: Decimal
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
    reserve_level: Decimal | None = None
    effective_reserve: Decimal | None = None
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
    # Either a number of packs, or the weight/volume received (e.g. 1 KG),
    # which the server converts into packs of this variant.
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    amount_unit: AmountUnit | None = None
    remarks: str | None = Field(default=None)

    @model_validator(mode="after")
    def _packs_or_amount(self) -> "ReceiveStockRequest":
        check_packs_or_amount(self.quantity, self.amount, self.amount_unit)
        return self


class RemoveStockRequest(BaseSchema):
    """Take stock out of a lot. Leave `quantity` out to remove all available
    stock; a reason is always required (it goes on the movement + audit log)."""

    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    reason: str = Field(..., min_length=1, max_length=200)


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


class StockAlertItemResponse(BaseSchema):
    product_id: int
    variant_id: int
    product_name: str
    variant_name: str
    unit: str
    pack_quantity: Decimal = Decimal("1")
    available: Decimal
    reserve_level: Decimal
    level: str  # OUT / BELOW / NEAR


class StockAlertsResponse(BaseSchema):
    """Light summary for the Admin's header alerts (polled every minute)."""

    count: int
    out_count: int
    below_count: int
    near_count: int
    items: list[StockAlertItemResponse]


class ProductStockVariantResponse(BaseSchema):
    variant_id: int
    variant_name: str
    sku: str
    status: str
    pack_quantity: Decimal
    pack_unit: str
    # Whole packs this size can sell: its own share plus the unassigned stock.
    available_packs: Decimal
    # What those packs add up to, in kg / L / pcs (`amount_unit`).
    available_amount: Decimal
    amount_unit: str
    # Stock assigned to this size alone (in `amount_unit`) and the whole packs
    # that makes.
    share_amount: Decimal = Decimal("0")
    share_packs: Decimal = Decimal("0")


class ProductStockTotalResponse(BaseSchema):
    """Stock of one unit family of a product ("34 kg", of which 10 kg is
    still unassigned and shared by every size)."""

    family: str
    amount: Decimal
    amount_unit: str
    unassigned_amount: Decimal


class ProductStockItemResponse(BaseSchema):
    product_id: int
    product_name: str
    category_name: str
    totals: list[ProductStockTotalResponse]
    variants: list[ProductStockVariantResponse]


class StockShare(BaseSchema):
    variant_id: int = Field(..., gt=0)
    # The size's TOTAL assigned share (not an increment); 0 releases it.
    amount: Decimal = Field(..., ge=0, max_digits=12, decimal_places=3)
    amount_unit: AmountUnit


class SetStockSharesRequest(BaseSchema):
    """Assign stock of a product to specific sizes. Each entry sets that
    size's whole share; sizes not listed keep theirs."""

    shares: list[StockShare] = Field(..., min_length=1, max_length=50)


class ProductStockListResponse(BaseSchema):
    items: list[ProductStockItemResponse]
    page: int
    page_size: int
    total: int
