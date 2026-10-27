"""Inventory domain routes: internal staff only (ADMIN, HUB_STAFF, OPERATIONS).

There is no public inventory API. CUSTOMER, WHOLESALER, and DELIVERY_PARTNER
have no access to any route in this file.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, HUB_STAFF, OPERATIONS
from app.dependencies.auth import get_current_user, require_permission, require_roles
from app.dependencies.database import get_db
from app.exceptions.base import NotFoundError
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.admin_inventory import MAX_PAGE_SIZE as ADMIN_MAX_PAGE_SIZE
from app.schemas.admin_inventory import (
    AdminInventoryLotDetailResponse,
    AdminInventoryLotListItemResponse,
    AdminInventoryLotListResponse,
    InventoryDashboardResponse,
    ProductCorrectStockRequest,
    ProductMoveStockRequest,
    ProductRemoveStockRequest,
    ProductStockItemResponse,
    ProductStockListResponse,
    ProductStockOperationResponse,
    ProductStockSummaryResponse,
    ReceiveStockRequest,
    ReconcileStockRequest,
    RemoveStockRequest,
    ResolveLotBaseRequest,
    SetProductReserveRequest,
    SetStockSharesRequest,
    StockAlertsResponse,
    TransferStockRequest,
    TransferStockResponse,
)
from app.schemas.inventory import (
    MAX_PAGE_SIZE,
    BatchListResponse,
    BatchResponse,
    CreateBatchRequest,
    CreateInventoryLocationRequest,
    CreateInventoryLotRequest,
    CreateStockMovementRequest,
    InventoryLocationListResponse,
    InventoryLocationResponse,
    InventoryLotListResponse,
    InventoryLotResponse,
    StockMovementListResponse,
    StockMovementResponse,
    UpdateInventoryLocationRequest,
)
from app.schemas.inventory_reservation import (
    InventoryReservationDetailResponse,
    InventoryReservationListResponse,
    InventoryReservationResponse,
)
from app.services.inventory import InventoryService
from app.services.inventory_reservation import InventoryReservationService
from app.services.product_stock import ProductStockService

router = APIRouter(dependencies=[Depends(require_roles(ADMIN, HUB_STAFF, OPERATIONS))])


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


@router.post(
    "/locations",
    response_model=InventoryLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inventory location",
)
def create_location(
    payload: CreateInventoryLocationRequest, db: Session = Depends(get_db)
) -> InventoryLocationResponse:
    return InventoryService(db).create_location(payload)


@router.get(
    "/locations",
    response_model=InventoryLocationListResponse,
    summary="List inventory locations",
)
def list_locations(
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> InventoryLocationListResponse:
    return InventoryService(db).list_locations(status_, page, page_size)


@router.get(
    "/locations/{location_id}",
    response_model=InventoryLocationResponse,
    summary="Get an inventory location",
)
def get_location(
    location_id: int, db: Session = Depends(get_db)
) -> InventoryLocationResponse:
    return InventoryService(db).get_location_or_404(location_id)


@router.patch(
    "/locations/{location_id}",
    response_model=InventoryLocationResponse,
    summary="Update an inventory location (lifecycle status included)",
)
def update_location(
    location_id: int,
    payload: UpdateInventoryLocationRequest,
    db: Session = Depends(get_db),
) -> InventoryLocationResponse:
    return InventoryService(db).update_location(location_id, payload)


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin: delete (archive) an inventory location - refused while it holds stock",
    dependencies=[Depends(require_roles(ADMIN))],
)
def delete_location(location_id: int, db: Session = Depends(get_db)) -> None:
    InventoryService(db).delete_location(location_id)


@router.post(
    "/locations/{location_id}/packing-point",
    response_model=InventoryLocationResponse,
    summary="Admin: make this location the delivery-distance origin (packing point)",
    dependencies=[Depends(require_roles(ADMIN))],
)
def set_packing_point(
    location_id: int, db: Session = Depends(get_db)
) -> InventoryLocationResponse:
    return InventoryService(db).set_packing_point(location_id)


# ---------------------------------------------------------------------------
# Lots
# ---------------------------------------------------------------------------


@router.post(
    "/lots",
    response_model=InventoryLotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inventory lot (batch + variant + location)",
)
def create_lot(
    payload: CreateInventoryLotRequest, db: Session = Depends(get_db)
) -> InventoryLotResponse:
    return InventoryService(db).create_lot(payload)


@router.get(
    "/lots",
    response_model=InventoryLotListResponse,
    summary="List inventory lots",
)
def list_lots(
    batch_id: int | None = Query(default=None),
    variant_id: int | None = Query(default=None),
    location_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> InventoryLotListResponse:
    return InventoryService(db).list_lots(
        batch_id, variant_id, location_id, status_, page, page_size
    )


@router.get(
    "/lots/{lot_id}",
    response_model=InventoryLotResponse,
    summary="Get an inventory lot",
)
def get_lot(lot_id: int, db: Session = Depends(get_db)) -> InventoryLotResponse:
    return InventoryService(db).get_lot_or_404(lot_id)


# ---------------------------------------------------------------------------
# Stock Movements
# ---------------------------------------------------------------------------


@router.post(
    "/lots/{lot_id}/movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a stock movement (the only way quantity changes)",
)
def create_movement(
    lot_id: int,
    payload: CreateStockMovementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StockMovementResponse:
    return InventoryService(db).create_movement(lot_id, payload, current_user.id)


@router.get(
    "/lots/{lot_id}/movements",
    response_model=StockMovementListResponse,
    summary="List stock movement history for a lot (read-only, immutable)",
)
def list_movements(
    lot_id: int,
    movement_type: str | None = Query(default=None),
    performed_by_user_id: int | None = Query(default=None),
    occurred_from: datetime | None = Query(default=None),
    occurred_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> StockMovementListResponse:
    return InventoryService(db).list_movements(
        lot_id,
        movement_type,
        performed_by_user_id,
        occurred_from,
        occurred_to,
        page,
        page_size,
    )


# ---------------------------------------------------------------------------
# Reservations (ops/admin read + explicit expiry - Phase 15)
# ---------------------------------------------------------------------------


@router.get(
    "/reservations",
    response_model=InventoryReservationListResponse,
    summary="List inventory reservations",
)
def list_reservations(
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> InventoryReservationListResponse:
    return InventoryReservationService(db).list_reservations_response(
        status_, page, page_size
    )


@router.get(
    "/reservations/{reservation_id}",
    response_model=InventoryReservationDetailResponse,
    summary="Get an inventory reservation, including its FIFO lot allocation",
)
def get_reservation(
    reservation_id: int, db: Session = Depends(get_db)
) -> InventoryReservationDetailResponse:
    return InventoryReservationService(db).get_reservation_detail_response(
        reservation_id
    )


@router.post(
    "/reservations/{reservation_id}/expire",
    response_model=InventoryReservationResponse,
    summary="Manually expire an ACTIVE reservation (idempotent no-op if already terminal)",
)
def expire_reservation(
    reservation_id: int, db: Session = Depends(get_db)
) -> InventoryReservationResponse:
    return InventoryReservationService(db).expire_reservation_response(reservation_id)


# ---------------------------------------------------------------------------
# Batches (Admin Panel Inventory module) - app/models/batch.py existed with
# no API surface at all before this; additive only, no migration.
# ---------------------------------------------------------------------------


@router.post(
    "/batches",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a batch (harvest lot) for stock receiving",
)
def create_batch(
    payload: CreateBatchRequest,
    current_user: User = Depends(require_permission("inventory.receive")),
    db: Session = Depends(get_db),
) -> BatchResponse:
    return InventoryService(db).create_batch(payload, current_user.id)


@router.get(
    "/batches",
    response_model=BatchListResponse,
    summary="List batches",
)
def list_batches(
    product_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> BatchListResponse:
    return InventoryService(db).list_batches(product_id, status_, page, page_size)


@router.get(
    "/batches/{batch_id}",
    response_model=BatchResponse,
    summary="Get a batch",
)
def get_batch(
    batch_id: int,
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> BatchResponse:
    return InventoryService(db).get_batch_response(batch_id)


# ---------------------------------------------------------------------------
# Admin: enriched lot list/detail + dashboard (Admin Panel Inventory module)
# ---------------------------------------------------------------------------


@router.get(
    "/admin/dashboard",
    response_model=InventoryDashboardResponse,
    summary="Real-time inventory operational summary",
)
def admin_inventory_dashboard(
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> InventoryDashboardResponse:
    return InventoryService(db).admin_dashboard()


@router.get(
    "/admin/products",
    response_model=ProductStockListResponse,
    summary="Stock per product (shared pool total) with each size's packs and weight",
)
def admin_list_product_stock(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=ADMIN_MAX_PAGE_SIZE),
    category_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=150, description="Product name"),
    stock_status: str | None = Query(
        default=None, alias="status", pattern="^(all|low|out|expiring)$", description="Keep only products that need attention"
    ),
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> ProductStockListResponse:
    return InventoryService(db).admin_list_product_stock(page, page_size, category_id, q, stock_status)


@router.get(
    "/admin/products/summary",
    response_model=ProductStockSummaryResponse,
    summary="How many products are low, out of stock or expiring (the Inventory filter chips)",
)
def admin_product_stock_summary(
    category_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=150, description="Product name"),
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> ProductStockSummaryResponse:
    return InventoryService(db).admin_product_stock_summary(category_id, q)


@router.get(
    "/admin/products/{product_id}",
    response_model=ProductStockItemResponse,
    summary="One product's current stock (kg, warehouses, expiry) - used to refresh a card before a stock action",
)
def admin_get_product_stock(
    product_id: int,
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> ProductStockItemResponse:
    card = InventoryService(db).product_stock_card(product_id)
    if card is None:
        raise NotFoundError("Product not found.")
    return card


@router.put(
    "/admin/products/{product_id}/reserve",
    response_model=ProductStockItemResponse,
    summary="Set the stock to keep in reserve for a product, as one physical amount (same for every size)",
)
def admin_set_product_reserve(
    product_id: int,
    payload: SetProductReserveRequest,
    current_user: User = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
) -> ProductStockItemResponse:
    return InventoryService(db).set_product_reserve(product_id, payload.amount, payload.amount_unit, current_user.id)


@router.delete(
    "/admin/products/{product_id}/reserve",
    response_model=ProductStockItemResponse,
    summary="Clear the product-level reserve (the per-size reserve levels apply again)",
)
def admin_clear_product_reserve(
    product_id: int,
    current_user: User = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
) -> ProductStockItemResponse:
    return InventoryService(db).set_product_reserve(product_id, None, None, current_user.id)


@router.post(
    "/admin/lots/{lot_id}/resolve-base",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Put a lot the base-unit migration held for review back into service with the confirmed physical amount",
)
def admin_resolve_lot_base(
    lot_id: int,
    payload: ResolveLotBaseRequest,
    current_user: User = Depends(require_permission("inventory.reconcile")),
    db: Session = Depends(get_db),
) -> None:
    InventoryService(db).resolve_lot_base(lot_id, payload.quantity_base, payload.reason, current_user.id)


@router.post(
    "/admin/products/{product_id}/correct",
    response_model=ProductStockOperationResponse,
    summary="Correct a product's stock to a physical count - the server works out the difference (oldest stock first)",
)
def admin_correct_product_stock(
    product_id: int,
    payload: ProductCorrectStockRequest,
    current_user: User = Depends(require_permission("inventory.reconcile")),
    db: Session = Depends(get_db),
) -> ProductStockOperationResponse:
    return ProductStockService(db).correct_stock(product_id, payload, current_user.id)


@router.post(
    "/admin/products/{product_id}/remove",
    response_model=ProductStockOperationResponse,
    summary="Remove an amount of a product's stock with a reason (oldest first, never reserved stock)",
)
def admin_remove_product_stock(
    product_id: int,
    payload: ProductRemoveStockRequest,
    current_user: User = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
) -> ProductStockOperationResponse:
    return ProductStockService(db).remove_stock(product_id, payload, current_user.id)


@router.post(
    "/admin/products/{product_id}/move",
    response_model=ProductStockOperationResponse,
    summary="Move an amount of a product's stock to another warehouse in one atomic action",
)
def admin_move_product_stock(
    product_id: int,
    payload: ProductMoveStockRequest,
    current_user: User = Depends(require_permission("inventory.transfer")),
    db: Session = Depends(get_db),
) -> ProductStockOperationResponse:
    return ProductStockService(db).move_stock(product_id, payload, current_user.id)


@router.post(
    "/admin/stock-actions/{operation_id}/undo",
    response_model=ProductStockOperationResponse,
    summary="Undo a recent correct/remove/move with compensating movements (refused when unsafe)",
)
def admin_undo_stock_action(
    operation_id: int,
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> ProductStockOperationResponse:
    role_names = [
        name
        for (name,) in db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id)
        .all()
    ]
    return ProductStockService(db).undo(operation_id, current_user, role_names)


@router.put(
    "/admin/products/{product_id}/stock-shares",
    response_model=ProductStockItemResponse,
    summary="Assign stock of a product to specific sizes (each size's share), rest stays unassigned",
)
def admin_set_stock_shares(
    product_id: int,
    payload: SetStockSharesRequest,
    current_user: User = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
) -> ProductStockItemResponse:
    return InventoryService(db).set_stock_shares(product_id, payload, current_user.id)


@router.get(
    "/admin/lots",
    response_model=AdminInventoryLotListResponse,
    summary="List/search/filter inventory lots with product/warehouse/batch context",
)
def admin_list_lots(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=ADMIN_MAX_PAGE_SIZE),
    location_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    operational_status: str | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=150, description="Product name, SKU, or batch code"),
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> AdminInventoryLotListResponse:
    return InventoryService(db).admin_list_lots(
        page, page_size, location_id, category_id, status_, operational_status, batch_id, q
    )


@router.get(
    "/admin/lots/{lot_id}",
    response_model=AdminInventoryLotDetailResponse,
    summary="Complete operational detail for one inventory lot",
)
def admin_get_lot_detail(
    lot_id: int,
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> AdminInventoryLotDetailResponse:
    return InventoryService(db).admin_get_lot_detail(lot_id)


# ---------------------------------------------------------------------------
# Admin: transactional stock actions - each is one domain action, not a raw
# PATCH quantity, and each goes through the same locked apply_movement()
# core the raw POST /lots/{id}/movements endpoint uses.
# ---------------------------------------------------------------------------


@router.post(
    "/admin/receive",
    response_model=AdminInventoryLotListItemResponse,
    summary="Receive stock into a (batch, variant, location) lot - creates the lot if needed",
)
def admin_receive_stock(
    payload: ReceiveStockRequest,
    current_user: User = Depends(require_permission("inventory.receive")),
    db: Session = Depends(get_db),
) -> AdminInventoryLotListItemResponse:
    return InventoryService(db).receive_stock(payload, current_user.id)


@router.post(
    "/admin/lots/{lot_id}/remove",
    response_model=AdminInventoryLotListItemResponse,
    summary="Remove stock from a lot (all available, or a quantity) with a reason",
)
def admin_remove_stock(
    lot_id: int,
    payload: RemoveStockRequest,
    current_user: User = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
) -> AdminInventoryLotListItemResponse:
    return InventoryService(db).remove_stock(lot_id, payload, current_user.id)


@router.get(
    "/admin/stock-alerts",
    response_model=StockAlertsResponse,
    summary="Items out of stock, at/below their reserve level, or close to it",
)
def admin_stock_alerts(
    limit: int = Query(default=20, ge=1, le=1000, description="Most urgent N items to list"),
    current_user: User = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
) -> StockAlertsResponse:
    return InventoryService(db).stock_alerts(limit)


@router.post(
    "/admin/lots/{lot_id}/reconcile",
    response_model=AdminInventoryLotListItemResponse,
    summary="Reconcile a lot against a physical count - computes and applies the difference",
)
def admin_reconcile_stock(
    lot_id: int,
    payload: ReconcileStockRequest,
    current_user: User = Depends(require_permission("inventory.reconcile")),
    db: Session = Depends(get_db),
) -> AdminInventoryLotListItemResponse:
    return InventoryService(db).reconcile_stock(lot_id, payload, current_user.id)


@router.post(
    "/admin/transfer",
    response_model=TransferStockResponse,
    summary="Atomically transfer stock from one lot to a different warehouse",
)
def admin_transfer_stock(
    payload: TransferStockRequest,
    current_user: User = Depends(require_permission("inventory.transfer")),
    db: Session = Depends(get_db),
) -> TransferStockResponse:
    return InventoryService(db).transfer_stock(payload, current_user.id)
