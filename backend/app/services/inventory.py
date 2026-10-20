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

import secrets
from datetime import UTC, date, datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal

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
from app.models.category import Category
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.schemas.admin_inventory import (
    AdminInventoryLotDetailResponse,
    AdminInventoryLotListItemResponse,
    AdminInventoryLotListResponse,
    InventoryDashboardResponse,
    ProductStockItemResponse,
    ProductStockListResponse,
    ProductStockTotalResponse,
    ProductStockVariantResponse,
    ReceiveStockRequest,
    ReconcileStockRequest,
    RelatedOrderResponse,
    RemoveStockRequest,
    SetStockSharesRequest,
    StockAlertItemResponse,
    StockAlertsResponse,
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
from app.services.stock_alerts import count_by_level, list_stock_alerts
from app.services.stock_levels import (
    BELOW,
    DEFAULT_RESERVE,
    NEAR,
    effective_reserve,
    stock_level,
)
from app.services.stock_pool import (
    amount_in_base,
    display_amount,
    pool_base_amounts,
    to_packs,
    variant_size,
    weight_to_packs,
)

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
DEFAULT_LOW_STOCK_THRESHOLD = DEFAULT_RESERVE
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
            latitude=data.latitude,
            longitude=data.longitude,
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
        # A deactivated or un-pinned location can no longer be the delivery origin.
        if location.is_packing_point and (
            location.status != "ACTIVE" or location.latitude is None or location.longitude is None
        ):
            location.is_packing_point = False

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "An inventory location with this code already exists."
            ) from exc
        self.db.refresh(location)
        return InventoryLocationResponse.model_validate(location)

    def delete_location(self, location_id: int) -> None:
        """Remove a hub/warehouse from use. Stock history (lots, movements,
        reservations) points at it, so this archives it (status INACTIVE)
        instead of erasing the row - and refuses while it still holds stock.
        """
        location = self.get_location_or_404(location_id)
        holds_stock = (
            self.db.query(InventoryLot.id)
            .filter(InventoryLot.location_id == location.id, InventoryLot.quantity > 0)
            .first()
        )
        if holds_stock:
            raise ConflictError(
                "This hub still holds stock. Transfer or adjust its stock to zero before deleting it."
            )
        location.status = "INACTIVE"
        location.is_packing_point = False
        self.db.commit()

    def set_packing_point(self, location_id: int) -> InventoryLocationResponse:
        """Make this the one location delivery distance is measured from."""
        location = self.get_location_or_404(location_id)
        if location.status != "ACTIVE":
            raise BusinessValidationError("Only an active location can be the packing point.")
        if location.latitude is None or location.longitude is None:
            raise BusinessValidationError(
                "Set this location's map coordinates before making it the packing point."
            )
        self.db.query(InventoryLocation).filter(
            InventoryLocation.is_packing_point.is_(True), InventoryLocation.id != location.id
        ).update({InventoryLocation.is_packing_point: False})
        location.is_packing_point = True
        self.db.commit()
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
        self, batch_id: int, variant_id: int, location_id: int, *, is_share: bool = False
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
                InventoryLot.is_share == is_share,
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
            is_share=is_share,
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

        quantity = data.quantity
        if quantity is None:
            quantity = weight_to_packs(lot.variant, data.amount, data.amount_unit)

        movement = self.apply_movement(
            lot,
            data.movement_type,
            quantity,
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

    def _operational_status(
        self,
        lot_status: str,
        on_hand: Decimal,
        reserved: Decimal,
        expiry: date | None,
        reserve_level: Decimal | None = None,
    ) -> str:
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
        # At/below the variant's reserve level, or running close to it.
        if stock_level(available, reserve_level) in (BELOW, NEAR):
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
            variant_unit=variant.unit,
            variant_quantity=variant.quantity,
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
                lot.status, lot.quantity, lot.reserved_quantity, batch.expiry_date, variant.reserve_level
            ),
            reserve_level=variant.reserve_level,
            effective_reserve=effective_reserve(variant.reserve_level),
            last_movement_at=last_movement,
            updated_at=lot.updated_at,
        )

    def admin_list_product_stock(
        self,
        page: int,
        page_size: int,
        category_id: int | None = None,
        q: str | None = None,
    ) -> ProductStockListResponse:
        """Stock per product: the stock total ("100 kg") with each size's
        whole packs and weight underneath. Sizes of one unit family draw from
        the same pool unless the stock was divided, see app.services.stock_pool."""
        query = (
            self.db.query(Product, Category.name)
            .join(Category, Product.category_id == Category.id)
            .filter(Product.status != "ARCHIVED", Product.variants.any())
        )
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(Product.name.ilike(f"%{escaped}%", escape="\\"))
        total = query.count()
        rows = query.order_by(Product.name).offset((page - 1) * page_size).limit(page_size).all()
        items = self._product_stock_items(rows)
        return ProductStockListResponse(items=items, page=page, page_size=page_size, total=total)

    def _product_stock_items(self, rows: list[tuple[Product, str]]) -> list[ProductStockItemResponse]:
        pool, variants, shares = pool_base_amounts(self.db, {p.id for p, _ in rows})
        variants_by_product: dict[int, list[ProductVariant]] = {}
        for v in sorted(variants, key=lambda v: v.id):
            variants_by_product.setdefault(v.product_id, []).append(v)

        items = []
        for product, category_name in rows:
            families: list[str] = []
            variant_items = []
            for v in variants_by_product.get(product.id, []):
                family, size = variant_size(v)
                if family not in families:
                    families.append(family)
                share_base = shares.get(v.id, Decimal("0"))
                packs = to_packs(pool[(product.id, family)] + share_base, size).to_integral_value(rounding=ROUND_DOWN)
                amount, amount_unit = display_amount(family, packs * size)
                share_amount, _ = display_amount(family, share_base)
                variant_items.append(
                    ProductStockVariantResponse(
                        variant_id=v.id,
                        variant_name=v.name,
                        sku=v.sku,
                        status=v.status,
                        pack_quantity=v.quantity,
                        pack_unit=v.unit,
                        available_packs=packs,
                        available_amount=amount,
                        amount_unit=amount_unit,
                        share_amount=share_amount,
                        share_packs=to_packs(share_base, size).to_integral_value(rounding=ROUND_DOWN),
                    )
                )
            totals = []
            for family in families:
                unassigned = pool[(product.id, family)]
                assigned = sum(
                    (shares.get(v.id, Decimal("0")) for v in variants_by_product[product.id] if variant_size(v)[0] == family),
                    Decimal("0"),
                )
                amount, amount_unit = display_amount(family, unassigned + assigned)
                totals.append(
                    ProductStockTotalResponse(
                        family=family,
                        amount=amount,
                        amount_unit=amount_unit,
                        unassigned_amount=display_amount(family, unassigned)[0],
                    )
                )
            items.append(
                ProductStockItemResponse(
                    product_id=product.id,
                    product_name=product.name,
                    category_name=category_name,
                    totals=totals,
                    variants=variant_items,
                )
            )
        return items

    def _product_stock_item(self, product_id: int) -> ProductStockItemResponse:
        row = (
            self.db.query(Product, Category.name)
            .join(Category, Product.category_id == Category.id)
            .filter(Product.id == product_id)
            .first()
        )
        return self._product_stock_items([row])[0]

    def set_stock_shares(
        self, product_id: int, data: SetStockSharesRequest, admin_user_id: int
    ) -> ProductStockItemResponse:
        """Assign stock of a product to specific sizes ("10 kg to the 1 kg
        size"). A share lives in a share lot of that size (`is_share`): only
        that size sells from it, while the unassigned rest stays in the
        ordinary lots every size of the unit family draws from. Raising a share
        moves free stock (same batch and warehouse) into the size's share lot
        with TRANSFER_OUT / TRANSFER_IN; lowering it moves stock back. Only
        AVAILABLE stock moves - reserved stock stays where it is. All or nothing."""
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise NotFoundError("Product not found.")
        variants = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.id)
            .all()
        )
        by_id = {v.id: v for v in variants}

        wanted: dict[int, Decimal] = {}
        family: str | None = None
        for share in data.shares:
            variant = by_id.get(share.variant_id)
            if variant is None:
                raise NotFoundError("Product variant not found.")
            if share.variant_id in wanted:
                raise BusinessValidationError("Each size can only appear once.")
            fam, base = amount_in_base(share.amount, share.amount_unit)
            if fam != variant_size(variant)[0]:
                raise BusinessValidationError(f"{share.amount_unit} cannot be used for the {variant.name} size.")
            if family is None:
                family = fam
            elif fam != family:
                raise BusinessValidationError("All sizes must be in the same unit family.")
            wanted[variant.id] = base
        if family not in {"MASS", "VOLUME", "COUNT"}:
            raise BusinessValidationError("Only weight, volume or piece-counted sizes can be assigned.")
        family_variants = [v for v in variants if variant_size(v)[0] == family]
        size_of = {v.id: variant_size(v)[1] for v in family_variants}

        # Lock every lot of the family up front, ascending id.
        lots = (
            self.db.query(InventoryLot)
            .filter(
                InventoryLot.variant_id.in_(list(size_of)),
                InventoryLot.status != _INACTIVE,
            )
            .order_by(InventoryLot.id.asc())
            .with_for_update()
            .all()
        )

        def avail(lot: InventoryLot) -> Decimal:
            return lot.quantity - lot.reserved_quantity if lot.status == _ACTIVE else Decimal("0")

        def locked(lot: InventoryLot) -> InventoryLot:
            return self.db.query(InventoryLot).filter(InventoryLot.id == lot.id).with_for_update().first()

        def free_lots() -> list[InventoryLot]:
            return sorted((l for l in lots if not l.is_share and avail(l) > 0), key=lambda l: (l.created_at, l.id))

        current = {
            vid: sum((avail(l) * size_of[vid] for l in lots if l.variant_id == vid and l.is_share), Decimal("0"))
            for vid in wanted
        }
        free_base = sum((avail(l) * size_of[l.variant_id] for l in free_lots()), Decimal("0"))
        release = {vid: current[vid] - wanted[vid] for vid in wanted if current[vid] > wanted[vid]}
        need = {vid: wanted[vid] - current[vid] for vid in wanted if wanted[vid] > current[vid]}
        if sum(need.values(), Decimal("0")) > free_base + sum(release.values(), Decimal("0")) + Decimal("0.5"):
            free_amount, unit_label = display_amount(family, free_base + sum(release.values(), Decimal("0")))
            raise BusinessValidationError(
                f"Only {free_amount} {unit_label} is unassigned, which is not enough for those shares."
            )

        # 1) Lowered shares go back to the size's ordinary lots (same batch, warehouse).
        for vid, amount in sorted(release.items()):
            for share_lot in sorted((l for l in lots if l.variant_id == vid and l.is_share and avail(l) > 0), key=lambda l: l.id):
                if amount <= 0:
                    break
                packs = min(avail(share_lot), (amount / size_of[vid]).quantize(Decimal("0.001"), rounding=ROUND_DOWN))
                if packs <= 0:
                    continue
                back = locked(self.get_or_create_lot_no_commit(share_lot.batch_id, vid, share_lot.location_id))
                if back not in lots:
                    lots.append(back)
                self.apply_movement(
                    share_lot, "TRANSFER_OUT", packs, admin_user_id,
                    reference_type="stock_share", reference_id=back.id, remarks="Stock share released",
                )
                self.apply_movement(
                    back, "TRANSFER_IN", packs, admin_user_id,
                    reference_type="stock_share", reference_id=share_lot.id, remarks="Stock share released",
                )
                amount -= packs * size_of[vid]

        # 2) Raised shares are filled from the unassigned stock - the size's own
        #    ordinary lots first, then the siblings' (FIFO).
        for vid, amount in sorted(need.items()):
            dest_size = size_of[vid]
            for src in sorted(free_lots(), key=lambda l: (l.variant_id != vid, l.created_at, l.id)):
                if amount <= 0:
                    break
                src_size = size_of[src.variant_id]
                dest_packs = to_packs(min(avail(src) * src_size, amount), dest_size)
                if dest_packs <= 0:
                    continue
                moved = dest_packs * dest_size
                src_packs = min(avail(src), (moved / src_size).quantize(Decimal("0.001"), rounding=ROUND_UP))
                dest = locked(self.get_or_create_lot_no_commit(src.batch_id, vid, src.location_id, is_share=True))
                if dest not in lots:
                    lots.append(dest)
                self.apply_movement(
                    src, "TRANSFER_OUT", src_packs, admin_user_id,
                    reference_type="stock_share", reference_id=dest.id, remarks="Stock assigned to a size",
                )
                self.apply_movement(
                    dest, "TRANSFER_IN", dest_packs, admin_user_id,
                    reference_type="stock_share", reference_id=src.id, remarks="Stock assigned to a size",
                )
                amount -= moved
            need[vid] = amount
        if any(left > max(Decimal("0.5"), size_of[vid] * Decimal("0.001")) for vid, left in need.items()):
            self.db.rollback()
            raise ConflictError(
                "That much stock could not be assigned (stock reserved for customer orders cannot be moved). "
                "Try a smaller amount."
            )

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="inventory.assign_share",
            resource_type="product",
            resource_id=product.id,
            reason="shares=" + ", ".join(f"{vid}:{amt}" for vid, amt in sorted(wanted.items())) + f" ({family} base units)",
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not assign stock due to a conflicting update.") from exc
        return self._product_stock_item(product_id)

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
            variant_quantity=variant.quantity,
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
                lot.status, lot.quantity, lot.reserved_quantity, batch.expiry_date, lot.variant.reserve_level
            ),
            reserve_level=lot.variant.reserve_level,
            effective_reserve=effective_reserve(lot.variant.reserve_level),
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
        reserve_by_variant = {
            vid: reserve
            for vid, reserve in self.db.query(ProductVariant.id, ProductVariant.reserve_level)
            .filter(ProductVariant.id.in_({lot.variant_id for lot in active_lots}))
            .all()
        } if active_lots else {}
        for lot in active_lots:
            available = lot.quantity - lot.reserved_quantity
            if available <= 0:
                out_of_stock_count += 1
            elif stock_level(available, reserve_by_variant.get(lot.variant_id)) in (BELOW, NEAR):
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

        If `data.batch_id` is omitted, a minimal Batch is auto-created
        first (server-generated code, harvest date today, no
        supplier/wholesaler) - the traceability row still exists, it's
        just not admin-authored. See ReceiveStockRequest docstring.
        """
        variant = self.db.query(ProductVariant).filter(ProductVariant.id == data.variant_id).first()
        if not variant:
            raise NotFoundError("Product variant not found.")
        quantity = (
            data.quantity
            if data.quantity is not None
            else weight_to_packs(variant, data.amount, data.amount_unit)
        )
        batch_id = data.batch_id
        if batch_id is None:
            batch = Batch(
                product_id=variant.product_id,
                batch_code=f"ADMIN-{secrets.token_hex(4).upper()}",
                harvest_date=date.today(),
                quantity=quantity,
                unit=variant.unit if variant.unit != "PACK" else "BOX",
                status="APPROVED",
            )
            self.db.add(batch)
            self.db.flush()
            batch_id = batch.id

        lot = self.get_or_create_lot_no_commit(batch_id, data.variant_id, data.location_id)
        lot = (
            self.db.query(InventoryLot).filter(InventoryLot.id == lot.id).with_for_update().first()
        )
        self.apply_movement(
            lot,
            "RECEIPT",
            quantity,
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

        if difference > 0:
            self.apply_movement(
                lot, "ADJUSTMENT_IN", difference, admin_user_id,
                reference_type="reconciliation", remarks=remarks,
            )
        elif difference < 0:
            self.apply_movement(
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

    def stock_alerts(self) -> StockAlertsResponse:
        alerts = list_stock_alerts(self.db)
        counts = count_by_level(alerts)
        return StockAlertsResponse(
            count=len(alerts),
            out_count=counts["OUT"],
            below_count=counts["BELOW"],
            near_count=counts["NEAR"],
            items=[
                StockAlertItemResponse(
                    product_id=a.product_id, variant_id=a.variant_id, product_name=a.product_name,
                    variant_name=a.variant_name, unit=a.unit, available=a.available,
                    reserve_level=a.reserve_level, level=a.level,
                )
                for a in alerts[:20]
            ],
        )

    def remove_stock(
        self, lot_id: int, data: RemoveStockRequest, admin_user_id: int
    ) -> AdminInventoryLotListItemResponse:
        """Takes stock out of a lot (spoilage, damage, a mistaken receipt...).
        Omit `quantity` to remove everything available. Stock already promised
        to customer orders (reserved) is never touched. Recorded as an
        ADJUSTMENT_OUT movement through the same `apply_movement` core as every
        other change, with the reason on the movement and in the audit log."""
        lot = self.db.query(InventoryLot).filter(InventoryLot.id == lot_id).with_for_update().first()
        if not lot:
            raise NotFoundError("Inventory lot not found.")
        available = lot.quantity - lot.reserved_quantity
        if available <= 0:
            raise BusinessValidationError("There is no available stock in this lot to remove.")
        quantity = data.quantity if data.quantity is not None else available
        if quantity > available:
            raise BusinessValidationError(
                f"Only {available} is available to remove - the rest is reserved for customer orders."
            )

        self.apply_movement(
            lot, "ADJUSTMENT_OUT", quantity, admin_user_id,
            reference_type="stock_removal", remarks=f"Stock removed: {data.reason}",
        )
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="inventory.remove",
            resource_type="inventory_lot",
            resource_id=lot.id,
            previous_state=str(lot.quantity + quantity),
            new_state=str(lot.quantity),
            reason=data.reason,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not remove stock due to a conflicting update.") from exc
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
            source.batch_id, source.variant_id, data.destination_location_id, is_share=source.is_share
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
