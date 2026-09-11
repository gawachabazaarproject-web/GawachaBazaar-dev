"""Inventory domain service: locations, lots, and atomic stock movements.

TRANSACTION DESIGN NOTE (read before touching create_movement):
Every route in this domain is protected by `require_roles`, which composes
`get_current_user`. `get_current_user` always issues SELECTs on the shared
request-scoped `db` session before any service method runs, so by the time
`create_movement` executes, SQLAlchemy 2.0's autobegin has ALREADY opened a
transaction on this session. Calling `db.begin()` explicitly at that point
raises "A transaction is already begun on this Session." This is exactly
the bug found and fixed in Phase 10's image primary-swap logic - see
docs/api/PHASE_10_CATALOG_API.md. The fix here is the same: never call
`db.begin()`. Perform the locking SELECT, validation, and writes directly
against the already-open (autobegun) transaction, then call `db.commit()`
exactly once at the end. This still gives one atomic transaction - what
matters for atomicity is "no commit happens until everything succeeds",
not whether the transaction was opened explicitly or implicitly.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.batch import Batch
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from app.schemas.inventory import (
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

_ACTIVE = "ACTIVE"
_INACTIVE = "INACTIVE"
_DEPLETED = "DEPLETED"

# Movement direction: centralizes the ONE place quantity sign is decided.
# Client always supplies a positive quantity; direction comes from type.
_MOVEMENT_DIRECTION: dict[str, int] = {
    "RECEIPT": 1,
    "ADJUSTMENT_IN": 1,
    "TRANSFER_IN": 1,
    "ADJUSTMENT_OUT": -1,
    "DAMAGE": -1,
    "WASTE": -1,
    "TRANSFER_OUT": -1,
    "DISPATCH": -1,
}


class InventoryService:
    """Location/Lot/StockMovement business logic and queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def get_location_or_404(self, location_id: int) -> InventoryLocation:
        location = (
            self.db.query(InventoryLocation)
            .filter(InventoryLocation.id == location_id)
            .first()
        )
        if not location:
            raise NotFoundError("Inventory location not found.")
        return location

    def create_location(
        self, data: CreateInventoryLocationRequest
    ) -> InventoryLocationResponse:
        location = InventoryLocation(
            name=data.name,
            code=data.code,
            type=data.type,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            status=data.status,
        )
        self.db.add(location)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "An inventory location with this code already exists."
            ) from exc
        self.db.refresh(location)
        return InventoryLocationResponse.model_validate(location)

    def update_location(
        self, location_id: int, data: UpdateInventoryLocationRequest
    ) -> InventoryLocationResponse:
        location = self.get_location_or_404(location_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(location, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "An inventory location with this code already exists."
            ) from exc
        self.db.refresh(location)
        return InventoryLocationResponse.model_validate(location)

    def list_locations(
        self, status: str | None, page: int, page_size: int
    ) -> InventoryLocationListResponse:
        query = self.db.query(InventoryLocation)
        if status is not None:
            query = query.filter(InventoryLocation.status == status)

        total = query.count()
        items = (
            query.order_by(InventoryLocation.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return InventoryLocationListResponse(
            items=[InventoryLocationResponse.model_validate(loc) for loc in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    # ------------------------------------------------------------------
    # Lots
    # ------------------------------------------------------------------

    def get_lot_or_404(self, lot_id: int) -> InventoryLot:
        lot = self.db.query(InventoryLot).filter(InventoryLot.id == lot_id).first()
        if not lot:
            raise NotFoundError("Inventory lot not found.")
        return lot

    def create_lot(self, data: CreateInventoryLotRequest) -> InventoryLotResponse:
        batch = self.db.query(Batch).filter(Batch.id == data.batch_id).first()
        if not batch:
            raise NotFoundError("Batch not found.")

        variant = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.id == data.variant_id)
            .first()
        )
        if not variant:
            raise NotFoundError("Product variant not found.")

        self.get_location_or_404(data.location_id)

        # The database does not enforce batch.product_id == variant.product_id -
        # this must be checked here (see INVARIANT 9 / Phase 11 doc).
        if batch.product_id != variant.product_id:
            raise BusinessValidationError(
                "Batch and variant belong to different products."
            )

        status = _ACTIVE if data.quantity > 0 else _DEPLETED
        lot = InventoryLot(
            batch_id=data.batch_id,
            variant_id=data.variant_id,
            location_id=data.location_id,
            quantity=data.quantity,
            status=status,
        )
        self.db.add(lot)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "An inventory lot for this batch, variant, and location "
                "already exists. Use the stock movement endpoint to adjust it."
            ) from exc
        self.db.refresh(lot)
        return InventoryLotResponse.model_validate(lot)

    def list_lots(
        self,
        batch_id: int | None,
        variant_id: int | None,
        location_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> InventoryLotListResponse:
        query = self.db.query(InventoryLot)
        if batch_id is not None:
            query = query.filter(InventoryLot.batch_id == batch_id)
        if variant_id is not None:
            query = query.filter(InventoryLot.variant_id == variant_id)
        if location_id is not None:
            query = query.filter(InventoryLot.location_id == location_id)
        if status is not None:
            query = query.filter(InventoryLot.status == status)

        total = query.count()
        items = (
            query.order_by(InventoryLot.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return InventoryLotListResponse(
            items=[InventoryLotResponse.model_validate(lot) for lot in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    # ------------------------------------------------------------------
    # Stock Movements
    # ------------------------------------------------------------------

    def create_movement(
        self,
        lot_id: int,
        data: CreateStockMovementRequest,
        performed_by_user_id: int,
    ) -> StockMovementResponse:
        """Atomically lock the lot, validate, update quantity/status, and record
        the movement. See the module docstring for why no explicit db.begin()
        is used here.
        """
        lot = (
            self.db.query(InventoryLot)
            .filter(InventoryLot.id == lot_id)
            .with_for_update()
            .first()
        )
        if not lot:
            raise NotFoundError("Inventory lot not found.")

        if lot.status == _INACTIVE:
            raise BusinessValidationError(
                "Cannot record a movement against an INACTIVE inventory lot."
            )

        direction = _MOVEMENT_DIRECTION[data.movement_type]
        delta: Decimal = direction * data.quantity
        new_quantity = lot.quantity + delta

        if new_quantity < 0:
            raise ConflictError(
                "Insufficient stock: this movement would result in negative quantity."
            )

        lot.quantity = new_quantity
        if new_quantity == 0:
            lot.status = _DEPLETED
        elif direction > 0 and lot.status == _DEPLETED:
            # A positive movement reactivates a DEPLETED lot. INACTIVE lots
            # are rejected above and never auto-activate.
            lot.status = _ACTIVE

        movement = StockMovement(
            inventory_lot_id=lot.id,
            movement_type=data.movement_type,
            quantity=data.quantity,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            performed_by_user_id=performed_by_user_id,
            occurred_at=data.occurred_at or datetime.now(UTC),
            remarks=data.remarks,
        )
        self.db.add(movement)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not record stock movement due to a conflicting update."
            ) from exc

        self.db.refresh(lot)
        self.db.refresh(movement)
        return StockMovementResponse.model_validate(movement)

    def list_movements(
        self,
        lot_id: int,
        movement_type: str | None,
        performed_by_user_id: int | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        page: int,
        page_size: int,
    ) -> StockMovementListResponse:
        self.get_lot_or_404(lot_id)

        query = self.db.query(StockMovement).filter(
            StockMovement.inventory_lot_id == lot_id
        )
        if movement_type is not None:
            query = query.filter(StockMovement.movement_type == movement_type)
        if performed_by_user_id is not None:
            query = query.filter(
                StockMovement.performed_by_user_id == performed_by_user_id
            )
        if occurred_from is not None:
            query = query.filter(StockMovement.occurred_at >= occurred_from)
        if occurred_to is not None:
            query = query.filter(StockMovement.occurred_at <= occurred_to)

        total = query.count()
        items = (
            query.order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return StockMovementListResponse(
            items=[StockMovementResponse.model_validate(m) for m in items],
            page=page,
            page_size=page_size,
            total=total,
        )
