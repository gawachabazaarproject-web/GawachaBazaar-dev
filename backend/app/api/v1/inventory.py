"""Inventory domain routes: internal staff only (ADMIN, HUB_STAFF, OPERATIONS).

There is no public inventory API. CUSTOMER, WHOLESALER, and DELIVERY_PARTNER
have no access to any route in this file.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, HUB_STAFF, OPERATIONS
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.inventory import (
    MAX_PAGE_SIZE,
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
from app.services.inventory import InventoryService

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
