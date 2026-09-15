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

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.batch import Batch
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.schemas.admin_inventory import (
    AdminInventoryLotDetailResponse,
    AdminInventoryLotListItemResponse,
    AdminInventoryLotListResponse,
    InventoryDashboardResponse,
    ReceiveStockRequest,
    ReconcileStockRequest,
    RelatedOrderResponse,
    TransferStockRequest,
    TransferStockResponse,
)
from app.schemas.inventory import (
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
from app.services.admin_audit import AdminAuditService

_ACTIVE = "ACTIVE"
_INACTIVE = "INACTIVE"
_DEPLETED = "DEPLETED"

# No `reorder_level` column exists anywhere in the schema (Product,
# ProductVariant, InventoryLot) - there is no real configured business
# threshold to read. This constant is an explicit, honestly-labeled
# stand-in so the dashboard/list can still surface "getting low" as a
# useful signal, NOT a claim that 10 units is Gawacha's actual reorder
# policy. A genuine implementation needs a real reorder_level field added
# to the domain model first - flagged, not silently worked around.
DEFAULT_LOW_STOCK_THRESHOLD = Decimal("10")
EXPIRING_SOON_DAYS = 7

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
    # Batches (Admin Panel Inventory module) - app/models/batch.py existed
    # since Phase 2/8.1/17 but had zero API surface before this. Additive
    # only: no migration, just exposing the existing table.
    # ------------------------------------------------------------------

    def get_batch_or_404(self, batch_id: int) -> Batch:
        batch = self.db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise NotFoundError("Batch not found.")
        return batch

    def get_batch_response(self, batch_id: int) -> BatchResponse:
        return self._to_batch_response(self.get_batch_or_404(batch_id))

    def create_batch(self, data: CreateBatchRequest, admin_user_id: int) -> BatchResponse:
        product = self.db.query(Product).filter(Product.id == data.product_id).first()
        if not product:
            raise NotFoundError("Product not found.")
        if data.supplier_id is None and data.wholesaler_user_id is None:
            raise BusinessValidationError(
                "A batch requires either a supplier or a wholesaler as its origin."
            )
        if data.supplier_id is not None:
            supplier = self.db.query(Supplier).filter(Supplier.id == data.supplier_id).first()
            if not supplier:
                raise NotFoundError("Supplier not found.")

        batch = Batch(
            product_id=data.product_id,
            batch_code=data.batch_code,
            harvest_date=data.harvest_date,
            expiry_date=data.expiry_date,
            quantity=data.quantity,
            unit=data.unit,
            status=data.status,
            supplier_id=data.supplier_id,
            wholesaler_user_id=data.wholesaler_user_id,
            purchase_price=data.purchase_price,
            purchase_currency=data.purchase_currency,
            received_date=data.received_date,
            receiving_reference=data.receiving_reference,
        )
        self.db.add(batch)
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="inventory.batch.create",
            resource_type="batch",
            resource_id=batch.id,
            new_state=batch.status,
            reason=f"product_id={data.product_id} batch_code={data.batch_code}",
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A batch with this batch_code already exists.") from exc
        self.db.refresh(batch)
        return self._to_batch_response(batch)

    def list_batches(
        self,
        product_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> BatchListResponse:
        query = self.db.query(Batch).options(
            joinedload(Batch.product), joinedload(Batch.supplier)
        )
        if product_id is not None:
            query = query.filter(Batch.product_id == product_id)
        if status is not None:
            query = query.filter(Batch.status == status)

        total = query.count()
        items = (
            query.order_by(Batch.harvest_date.desc(), Batch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return BatchListResponse(
            items=[self._to_batch_response(b) for b in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def _to_batch_response(self, batch: Batch) -> BatchResponse:
        product = batch.product or self.db.query(Product).filter(Product.id == batch.product_id).first()
        supplier = (
            batch.supplier
            if batch.supplier_id and batch.supplier
            else (
                self.db.query(Supplier).filter(Supplier.id == batch.supplier_id).first()
                if batch.supplier_id
                else None
            )
        )
        return BatchResponse(
            id=batch.id,
            product_id=batch.product_id,
            product_name=product.name if product else "",
            batch_code=batch.batch_code,
            harvest_date=batch.harvest_date,
            expiry_date=batch.expiry_date,
            quantity=batch.quantity,
            unit=batch.unit,
            status=batch.status,
            supplier_id=batch.supplier_id,
            supplier_name=supplier.business_name if supplier else None,
            wholesaler_user_id=batch.wholesaler_user_id,
            purchase_price=batch.purchase_price,
            purchase_currency=batch.purchase_currency,
            received_date=batch.received_date,
            receiving_reference=batch.receiving_reference,
            created_at=batch.created_at,
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

    def apply_movement(
        self,
        lot: InventoryLot,
        movement_type: str,
        quantity: Decimal,
        performed_by_user_id: int,
        *,
        reference_type: str | None = None,
        reference_id: int | None = None,
        occurred_at: datetime | None = None,
        remarks: str | None = None,
    ) -> StockMovement:
        """Validate and apply one movement against an already row-locked lot.

        Does NOT commit - the caller owns the transaction boundary and must
        have already locked `lot` via `.with_for_update()` in the same
        transaction. This is the shared core other services (e.g. Packaging
        completion) reuse to participate in a larger atomic transaction
        instead of each movement committing independently.
        """
        if lot.status == _INACTIVE:
            raise BusinessValidationError(
                "Cannot record a movement against an INACTIVE inventory lot."
            )

        direction = _MOVEMENT_DIRECTION[movement_type]
        new_quantity = lot.quantity + (direction * quantity)

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
            movement_type=movement_type,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            performed_by_user_id=performed_by_user_id,
            occurred_at=occurred_at or datetime.now(UTC),
            remarks=remarks,
        )
        self.db.add(movement)
        return movement

    def get_or_create_lot_no_commit(
        self, batch_id: int, variant_id: int, location_id: int
    ) -> InventoryLot:
        """Get-or-create the lot for (batch, variant, location) without committing.

        Caller owns the transaction boundary (used by Packaging output
        resolution, which must not commit until the whole completion
        transaction succeeds). Applies the same batch/variant product-match
        validation as create_lot() (INVARIANT 9).
        """
        existing = (
            self.db.query(InventoryLot)
            .filter(
                InventoryLot.batch_id == batch_id,
                InventoryLot.variant_id == variant_id,
                InventoryLot.location_id == location_id,
            )
            .first()
        )
        if existing:
            return existing

        batch = self.db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise NotFoundError("Batch not found.")
        variant = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.id == variant_id)
            .first()
        )
        if not variant:
            raise NotFoundError("Product variant not found.")
        if batch.product_id != variant.product_id:
            raise BusinessValidationError(
                "Batch and variant belong to different products."
            )

        lot = InventoryLot(
            batch_id=batch_id,
            variant_id=variant_id,
            location_id=location_id,
            quantity=Decimal("0"),
            status=_DEPLETED,
        )
        self.db.add(lot)
        self.db.flush()
        return lot

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

        movement = self.apply_movement(
            lot,
            data.movement_type,
            data.quantity,
            performed_by_user_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            occurred_at=data.occurred_at,
            remarks=data.remarks,
        )

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

    # ------------------------------------------------------------------
    # Admin: enriched list/detail/dashboard + domain actions (Admin Panel
    # Inventory module). Every mutation here (receive/reconcile/transfer)
    # goes through `apply_movement` above - the same row-locked,
    # negative-quantity-rejecting core the raw movements endpoint uses -
    # never a second stock-mutation code path.
    # ------------------------------------------------------------------

    def _operational_status(self, lot_status: str, on_hand: Decimal, reserved: Decimal, expiry: date | None) -> str:
        if lot_status == _INACTIVE:
            return "INACTIVE"
        available = on_hand - reserved
        today = datetime.now(UTC).date()
        if expiry is not None:
            if expiry < today:
                return "EXPIRED"
            if (expiry - today).days <= EXPIRING_SOON_DAYS:
                return "EXPIRING"
        if available <= 0:
            return "OUT_OF_STOCK"
        if available < DEFAULT_LOW_STOCK_THRESHOLD:
            return "LOW_STOCK"
        return "IN_STOCK"

    def _enrich_lot(self, lot: InventoryLot, last_movement: datetime | None) -> AdminInventoryLotListItemResponse:
        variant = lot.variant
        product = variant.product
        batch = lot.batch
        location = lot.location
        return AdminInventoryLotListItemResponse(
            id=lot.id,
            product_id=product.id,
            product_name=product.name,
            variant_id=variant.id,
            variant_name=variant.name,
            sku=variant.sku,
            category_id=product.category_id,
            category_name=product.category.name,
            location_id=location.id,
            location_name=location.name,
            location_code=location.code,
            batch_id=batch.id,
            batch_code=batch.batch_code,
            batch_expiry_date=batch.expiry_date,
            on_hand=lot.quantity,
            reserved=lot.reserved_quantity,
            available=lot.quantity - lot.reserved_quantity,
            lot_status=lot.status,
            operational_status=self._operational_status(
                lot.status, lot.quantity, lot.reserved_quantity, batch.expiry_date
            ),
            last_movement_at=last_movement,
            updated_at=lot.updated_at,
        )

    def admin_list_lots(
        self,
        page: int,
        page_size: int,
        location_id: int | None = None,
        category_id: int | None = None,
        lot_status: str | None = None,
        operational_status: str | None = None,
        batch_id: int | None = None,
        q: str | None = None,
    ) -> AdminInventoryLotListResponse:
        query = (
            self.db.query(InventoryLot)
            .join(ProductVariant, InventoryLot.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Batch, InventoryLot.batch_id == Batch.id)
            .options(
                joinedload(InventoryLot.variant).joinedload(ProductVariant.product).joinedload(Product.category),
                joinedload(InventoryLot.batch),
                joinedload(InventoryLot.location),
            )
        )
        if location_id is not None:
            query = query.filter(InventoryLot.location_id == location_id)
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)
        if lot_status is not None:
            query = query.filter(InventoryLot.status == lot_status)
        if batch_id is not None:
            query = query.filter(InventoryLot.batch_id == batch_id)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(Product.name.ilike(like), ProductVariant.sku.ilike(like), Batch.batch_code.ilike(like))
            )

        if operational_status:
            # Computed status (blends lot state, reservation math, and
            # batch expiry) can't be expressed as a single SQL predicate -
            # evaluate it in Python over the filtered set, same approach
            # already used for Products' price-range filter. Bounded to a
            # generous cap; a grocery catalog's lot count is in the
            # hundreds, not millions.
            candidates = query.order_by(InventoryLot.updated_at.desc(), InventoryLot.id.desc()).limit(2000).all()
            last_movements = self._last_movement_by_lot([c.id for c in candidates])
            enriched = [self._enrich_lot(lot, last_movements.get(lot.id)) for lot in candidates]
            matching = [item for item in enriched if item.operational_status == operational_status]
            total = len(matching)
            page_items = matching[(page - 1) * page_size : (page - 1) * page_size + page_size]
            return AdminInventoryLotListResponse(items=page_items, page=page, page_size=page_size, total=total)

        total = query.count()
        lots = (
            query.order_by(InventoryLot.updated_at.desc(), InventoryLot.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        last_movements = self._last_movement_by_lot([lot.id for lot in lots])
        items = [self._enrich_lot(lot, last_movements.get(lot.id)) for lot in lots]
        return AdminInventoryLotListResponse(items=items, page=page, page_size=page_size, total=total)

    def _last_movement_by_lot(self, lot_ids: list[int]) -> dict[int, datetime]:
        if not lot_ids:
            return {}
        rows = (
            self.db.query(StockMovement.inventory_lot_id, func.max(StockMovement.occurred_at))
            .filter(StockMovement.inventory_lot_id.in_(lot_ids))
            .group_by(StockMovement.inventory_lot_id)
            .all()
        )
        return dict(rows)

    def admin_get_lot_detail(self, lot_id: int) -> AdminInventoryLotDetailResponse:
        lot = (
            self.db.query(InventoryLot)
            .options(
                joinedload(InventoryLot.variant).joinedload(ProductVariant.product).joinedload(Product.category),
                joinedload(InventoryLot.batch),
                joinedload(InventoryLot.location),
            )
            .filter(InventoryLot.id == lot_id)
            .first()
        )
        if not lot:
            raise NotFoundError("Inventory lot not found.")

        variant = lot.variant
        product = variant.product
        batch = lot.batch
        location = lot.location
        image_url = None
        if product.images:
            primary = next((i for i in product.images if i.is_primary), None)
            image_url = primary.image_url if primary else product.images[0].image_url

        recent_movements = (
            self.db.query(StockMovement)
            .filter(StockMovement.inventory_lot_id == lot_id)
            .order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
            .limit(20)
            .all()
        )

        related = (
            self.db.query(
                Order.id,
                Order.order_number,
                InventoryReservationItem.quantity,
                InventoryReservation.status,
            )
            .join(InventoryReservation, InventoryReservationItem.reservation_id == InventoryReservation.id)
            .join(Order, InventoryReservation.order_id == Order.id)
            .filter(InventoryReservationItem.inventory_lot_id == lot_id)
            .order_by(Order.id.desc())
            .limit(20)
            .all()
        )

        return AdminInventoryLotDetailResponse(
            id=lot.id,
            product_id=product.id,
            product_name=product.name,
            product_image_url=image_url,
            category_id=product.category_id,
            category_name=product.category.name,
            variant_id=variant.id,
            variant_name=variant.name,
            sku=variant.sku,
            unit=variant.unit,
            location_id=location.id,
            location_name=location.name,
            location_code=location.code,
            location_city=location.city,
            location_status=location.status,
            batch=self._to_batch_response(batch),
            on_hand=lot.quantity,
            reserved=lot.reserved_quantity,
            available=lot.quantity - lot.reserved_quantity,
            lot_status=lot.status,
            operational_status=self._operational_status(
                lot.status, lot.quantity, lot.reserved_quantity, batch.expiry_date
            ),
            created_at=lot.created_at,
            updated_at=lot.updated_at,
            recent_movements=[StockMovementResponse.model_validate(m) for m in recent_movements],
            related_orders=[
                RelatedOrderResponse(
                    order_id=order_id,
                    order_number=order_number,
                    reserved_quantity=qty,
                    reservation_status=res_status,
                )
                for order_id, order_number, qty, res_status in related
            ],
        )

    def admin_dashboard(self) -> InventoryDashboardResponse:
        active_lots = self.db.query(InventoryLot).filter(InventoryLot.status != _INACTIVE).all()
        total_skus = len({lot.variant_id for lot in active_lots})
        total_on_hand = sum((lot.quantity for lot in active_lots), Decimal("0"))
        total_reserved = sum((lot.reserved_quantity for lot in active_lots), Decimal("0"))
        total_available = total_on_hand - total_reserved

        today = datetime.now(UTC).date()
        low_stock_count = 0
        out_of_stock_count = 0
        batch_ids = {lot.batch_id for lot in active_lots}
        batches = {
            b.id: b for b in self.db.query(Batch).filter(Batch.id.in_(batch_ids)).all()
        } if batch_ids else {}
        expiring_batches_count = 0
        expired_batches_count = 0
        seen_batches_expiring: set[int] = set()
        seen_batches_expired: set[int] = set()
        for lot in active_lots:
            available = lot.quantity - lot.reserved_quantity
            if available <= 0:
                out_of_stock_count += 1
            elif available < DEFAULT_LOW_STOCK_THRESHOLD:
                low_stock_count += 1
            batch = batches.get(lot.batch_id)
            if batch and batch.expiry_date:
                if batch.expiry_date < today and batch.id not in seen_batches_expired:
                    expired_batches_count += 1
                    seen_batches_expired.add(batch.id)
                elif (
                    batch.expiry_date >= today
                    and (batch.expiry_date - today).days <= EXPIRING_SOON_DAYS
                    and batch.id not in seen_batches_expiring
                ):
                    expiring_batches_count += 1
                    seen_batches_expiring.add(batch.id)

        recent_movements = (
            self.db.query(StockMovement)
            .order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
            .limit(10)
            .all()
        )

        warehouses_requiring_attention = (
            self.db.query(InventoryLocation.id)
            .join(InventoryLot, InventoryLot.location_id == InventoryLocation.id)
            .filter(InventoryLot.status != _INACTIVE)
            .filter((InventoryLot.quantity - InventoryLot.reserved_quantity) <= 0)
            .distinct()
            .count()
        )

        return InventoryDashboardResponse(
            total_skus=total_skus,
            total_on_hand=total_on_hand,
            total_reserved=total_reserved,
            total_available=total_available,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            expiring_batches_count=expiring_batches_count,
            expired_batches_count=expired_batches_count,
            recent_movements=[StockMovementResponse.model_validate(m) for m in recent_movements],
            warehouses_requiring_attention=warehouses_requiring_attention,
        )

    def receive_stock(self, data: ReceiveStockRequest, admin_user_id: int) -> AdminInventoryLotListItemResponse:
        """Get-or-create the (batch, variant, location) lot, lock it, and
        apply one RECEIPT movement - one atomic admin action instead of
        the raw two-call POST /lots + POST /lots/{id}/movements sequence.
        """
        lot = self.get_or_create_lot_no_commit(data.batch_id, data.variant_id, data.location_id)
        lot = (
            self.db.query(InventoryLot).filter(InventoryLot.id == lot.id).with_for_update().first()
        )
        self.apply_movement(
            lot,
            "RECEIPT",
            data.quantity,
            admin_user_id,
            reference_type="admin_receive",
            remarks=data.remarks,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not receive stock due to a conflicting update.") from exc
        self.db.refresh(lot)
        last_movement = self._last_movement_by_lot([lot.id]).get(lot.id)
        return self._enrich_lot(lot, last_movement)

    def reconcile_stock(
        self, lot_id: int, data: ReconcileStockRequest, admin_user_id: int
    ) -> AdminInventoryLotListItemResponse:
        """Physical-count reconciliation: locks the lot, computes the
        difference server-side, and applies it as an ADJUSTMENT_IN/OUT
        movement through the same `apply_movement` core every other
        mutation uses - never a separate "set quantity" code path.
        """
        lot = self.db.query(InventoryLot).filter(InventoryLot.id == lot_id).with_for_update().first()
        if not lot:
            raise NotFoundError("Inventory lot not found.")

        system_count = lot.quantity
        difference = data.physical_count - system_count
        remarks = f"Reconciliation: system={system_count} physical={data.physical_count} reason={data.reason}"
        if data.notes:
            remarks += f" notes={data.notes}"

        if difference == 0:
            movement = None
        elif difference > 0:
            movement = self.apply_movement(
                lot, "ADJUSTMENT_IN", difference, admin_user_id,
                reference_type="reconciliation", remarks=remarks,
            )
        else:
            movement = self.apply_movement(
                lot, "ADJUSTMENT_OUT", abs(difference), admin_user_id,
                reference_type="reconciliation", remarks=remarks,
            )

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="inventory.reconcile",
            resource_type="inventory_lot",
            resource_id=lot.id,
            previous_state=str(system_count),
            new_state=str(data.physical_count),
            reason=data.reason,
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not reconcile stock due to a conflicting update.") from exc
        self.db.refresh(lot)
        last_movement = self._last_movement_by_lot([lot.id]).get(lot.id)
        return self._enrich_lot(lot, last_movement)

    def transfer_stock(self, data: TransferStockRequest, admin_user_id: int) -> TransferStockResponse:
        """Atomic TRANSFER_OUT (source) + TRANSFER_IN (destination,
        get-or-created for the same batch+variant). No in-transit state -
        the backend has no transfer-request entity to represent one, so
        this commits both sides together or neither.
        """
        source = (
            self.db.query(InventoryLot).filter(InventoryLot.id == data.source_lot_id).with_for_update().first()
        )
        if not source:
            raise NotFoundError("Source inventory lot not found.")
        if source.location_id == data.destination_location_id:
            raise BusinessValidationError("Source and destination locations must differ.")
        self.get_location_or_404(data.destination_location_id)

        destination = self.get_or_create_lot_no_commit(
            source.batch_id, source.variant_id, data.destination_location_id
        )
        # Lock destination too (it may already have existed with concurrent
        # activity) - fixed id-ascending order across the two lots avoids a
        # deadlock against a concurrent transfer running the opposite way.
        lot_ids_in_order = sorted([source.id, destination.id])
        locked = {
            lot.id: lot
            for lot in self.db.query(InventoryLot).filter(InventoryLot.id.in_(lot_ids_in_order)).with_for_update().all()
        }
        source = locked[source.id]
        destination = locked[destination.id]

        self.apply_movement(
            source, "TRANSFER_OUT", data.quantity, admin_user_id,
            reference_type="transfer", reference_id=destination.id, remarks=data.remarks,
        )
        self.apply_movement(
            destination, "TRANSFER_IN", data.quantity, admin_user_id,
            reference_type="transfer", reference_id=source.id, remarks=data.remarks,
        )

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="inventory.transfer",
            resource_type="inventory_lot",
            resource_id=source.id,
            reason=f"to_location_id={data.destination_location_id} quantity={data.quantity}",
        )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not transfer stock due to a conflicting update.") from exc
        self.db.refresh(source)
        self.db.refresh(destination)
        moves = self._last_movement_by_lot([source.id, destination.id])
        return TransferStockResponse(
            source_lot=self._enrich_lot(source, moves.get(source.id)),
            destination_lot=self._enrich_lot(destination, moves.get(destination.id)),
        )
