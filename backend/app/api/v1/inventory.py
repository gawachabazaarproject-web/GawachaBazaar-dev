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
from app.models.user import User
from app.schemas.admin_inventory import (
    AdminInventoryLotDetailResponse,
    AdminInventoryLotListItemResponse,
    AdminInventoryLotListResponse,
    InventoryDashboardResponse,
    ReceiveStockRequest,
    ReconcileStockRequest,
    TransferStockRequest,
    TransferStockResponse,
)
from app.schemas.admin_inventory import MAX_PAGE_SIZE as ADMIN_MAX_PAGE_SIZE
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
