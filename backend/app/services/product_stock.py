"""Product-level stock actions: correct, remove and move stock by *product*.

Staff talk about a product and an amount ("I counted 43 kg", "2 kg was
damaged", "move 10 kg to Nagpur"). The lots, batches and pack sizes behind that
are the server's job. Each action here is ONE transaction that

  1. locks every lot it may touch in ascending id order (the same fixed order
     every other stock change uses, so concurrent actions cannot deadlock),
  2. never takes stock that is reserved for a customer order,
  3. changes quantities only through `InventoryService.apply_movement`, the
     shared movement core (so the movement ledger stays the only way quantity
     changes and `reserved <= quantity` keeps holding), and
  4. writes one audit row whose id is stamped on every movement it made, which
     is what makes Undo possible as a compensating transaction.

Allocation rule (a business decision, documented here and in the API summary):
stock is taken **oldest first** - the same FIFO order checkout uses to reserve
stock - and stock that is shared by all sizes before stock assigned to one
size. A surplus found in a count is added to the **newest** shared lot of the
warehouse.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import role_has_permission
from app.core.roles import ADMIN
from app.exceptions.base import (
    AuthorizationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.models.admin_action_log import AdminActionLog
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.admin_inventory import (
    ProductCorrectStockRequest,
    ProductMoveStockRequest,
    ProductRemoveStockRequest,
    ProductStockOperationResponse,
    StockChangeResponse,
)
from app.services import units as units_mod
from app.services.admin_audit import AdminAuditService
from app.services.inventory import InventoryService
from app.services.stock_pool import (
    amount_in_base,
    display_amount,
    variant_size,
)

UNDO_WINDOW = timedelta(minutes=30)

_ACTIVE = "ACTIVE"
_INACTIVE = "INACTIVE"
_PACK_STEP = Decimal("0.001")
# Rounding slack in the family's base unit (g / ml / pieces): amounts are
# stored in thousandths of a pack, so a request can be off by well under this.
_TOLERANCE = Decimal("0.5")
_SUPPORTED_FAMILIES = {"MASS", "VOLUME", "COUNT"}

_MOVEMENT_REFERENCE = {
    "correct": "product_correct",
    "remove": "product_remove",
    "move": "product_move",
}
_AUDIT_ACTION = {
    "correct": "inventory.correct_product",
    "remove": "inventory.remove_product",
    "move": "inventory.move_product",
}
_KIND_BY_ACTION = {action: kind for kind, action in _AUDIT_ACTION.items()}
_UNDO_PERMISSION = {
    "correct": "inventory.reconcile",
    "remove": "inventory.adjust",
    "move": "inventory.transfer",
}
_UNIT_LABELS = {"KG": "kg", "G": "g", "L": "L", "ML": "ml", "UNIT": "pcs", "DOZEN": "dozen"}
_INVERSE_MOVEMENT = {
    "ADJUSTMENT_OUT": "ADJUSTMENT_IN",
    "DAMAGE": "ADJUSTMENT_IN",
    "WASTE": "ADJUSTMENT_IN",
    "TRANSFER_OUT": "TRANSFER_IN",
    "ADJUSTMENT_IN": "ADJUSTMENT_OUT",
    "TRANSFER_IN": "TRANSFER_OUT",
}
_UNSAFE_UNDO = (
    "This can no longer be undone automatically because that stock has since been used or moved. "
    "Check the stock history to see what happened."
)


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f") if value != 0 else "0"


class ProductStockService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _product(self, product_id: int) -> Product:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise NotFoundError("Product not found.")
        return product

    def _family_sizes(self, product_id: int, family: str, unit: str) -> dict[int, int]:
        """Exact size of one pack (integer base units: g / ml / pieces) for each
        size of the product that is measured in `family`."""
        if family not in _SUPPORTED_FAMILIES:
            raise BusinessValidationError("Use kg, g, L, ml, pieces or dozen for this action.")
        sizes = {
            v.id: v.size_base
            for v in self.db.query(ProductVariant).filter(ProductVariant.product_id == product_id).all()
            if variant_size(v)[0] == family
        }
        if not sizes:
            raise BusinessValidationError(
                f"This product has no size measured in {_UNIT_LABELS.get(unit, unit)}."
            )
        return sizes

    def _candidate_lots(self, variant_ids, location_id: int | None = None) -> list[InventoryLot]:
        query = self.db.query(InventoryLot).filter(
            InventoryLot.variant_id.in_(list(variant_ids)),
            InventoryLot.status != _INACTIVE,
            InventoryLot.quantity_base.is_not(None),  # lots on hold for review are never touched
        )
        if location_id is not None:
            query = query.filter(InventoryLot.location_id == location_id)
        return query.order_by(InventoryLot.id.asc()).all()

    def _lock(self, lot_ids) -> dict[int, InventoryLot]:
        """Row-lock lots in ascending id order (the system-wide lock order)."""
        ids = sorted(set(lot_ids))
        if not ids:
            return {}
        return {
            lot.id: lot
            for lot in self.db.query(InventoryLot)
            .filter(InventoryLot.id.in_(ids))
            .order_by(InventoryLot.id.asc())
            .with_for_update()
            .all()
        }

    @staticmethod
    def _available(lot: InventoryLot) -> int:
        """Exact base units a lot can still give out (not reserved)."""
        return lot.quantity_base - lot.reserved_base if lot.status == _ACTIVE else 0

    @staticmethod
    def _fifo(lots) -> list[InventoryLot]:
        """Which lots a physical-count correction, a removal or a move takes
        from, in order: oldest first; stock shared by all sizes before a size's
        own share.

        This is an IMPLEMENTATION ASSUMPTION, not an approved business rule, and
        it is deliberately separate from the FIFO that checkout uses to reserve
        stock for customers (`inventory_reservation.py`, which this module never
        touches). If the business wants e.g. "remove the lot that expires first",
        this one function is the only place to change."""
        return sorted(lots, key=lambda lot: (lot.is_share, lot.created_at, lot.id))

    @staticmethod
    def _to_unit(base: int, unit: str) -> Decimal:
        """Display only: base units as an amount of `unit`."""
        return (Decimal(base) / amount_in_base(Decimal(1), unit)[1]).quantize(_PACK_STEP)

    def _amount_text(self, family: str, base: int) -> str:
        amount, label = display_amount(family, base)
        return f"{_fmt(amount)} {label}"

    def _pick_location(self, lots: list[InventoryLot], location_id: int | None) -> int | None:
        locations = {lot.location_id for lot in lots}
        if location_id is not None:
            return location_id if location_id in locations else None
        if len(locations) > 1:
            raise BusinessValidationError(
                "This product is stored in more than one warehouse. Choose the warehouse you counted."
            )
        return next(iter(locations), None)

    def _record(
        self, kind: str, product: Product, user_id: int, *, previous: str, new: str, reason: str
    ) -> AdminActionLog:
        return AdminAuditService(self.db).record(
            admin_user_id=user_id,
            action=_AUDIT_ACTION[kind],
            resource_type="product",
            resource_id=product.id,
            previous_state=previous[:50],
            new_state=new[:50],
            reason=reason,
        )

    def _move(
        self,
        changes: list[dict],
        lot: InventoryLot,
        movement_type: str,
        base: int,
        user_id: int,
        kind: str,
        operation_id: int,
        remarks: str,
    ) -> StockMovement:
        movement = self.inventory.apply_movement_base(
            lot,
            movement_type,
            base,
            user_id,
            reference_type=_MOVEMENT_REFERENCE[kind],
            reference_id=operation_id,
            remarks=remarks,
        )
        changes.append(
            {
                "lot": lot,
                "movement_type": movement_type,
                "packs": units_mod.packs_exact(base, lot.variant.size_base),
            }
        )
        return movement

    def _finish(
        self,
        kind: str,
        product_id: int,
        operation_id: int | None,
        message: str,
        difference: Decimal,
        unit: str,
        changes: list[dict],
    ) -> ProductStockOperationResponse:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("The stock changed while you were working. Nothing was saved - please try again.") from exc
        names = {
            loc.id: loc.name
            for loc in self.db.query(InventoryLocation)
            .filter(InventoryLocation.id.in_({c["lot"].location_id for c in changes} or {0}))
            .all()
        }
        return ProductStockOperationResponse(
            operation_id=operation_id,
            kind=kind,
            message=message,
            difference=difference,
            amount_unit=unit,
            changes=[
                StockChangeResponse(
                    lot_id=c["lot"].id,
                    location_id=c["lot"].location_id,
                    location_name=names.get(c["lot"].location_id, ""),
                    variant_id=c["lot"].variant_id,
                    movement_type=c["movement_type"],
                    packs=c["packs"],
                )
                for c in changes
            ],
            undo_until=(datetime.now(UTC) + UNDO_WINDOW) if operation_id and kind != "undo" else None,
            product=self.inventory._product_stock_item(product_id),
        )

    # ------------------------------------------------------------------
    # Correct stock ("I counted 43 kg")
    # ------------------------------------------------------------------

    def correct_stock(
        self, product_id: int, data: ProductCorrectStockRequest, user_id: int
    ) -> ProductStockOperationResponse:
        product = self._product(product_id)
        family, counted = amount_in_base(data.physical_amount, data.amount_unit)
        sizes = self._family_sizes(product_id, family, data.amount_unit)

        location = self._pick_location(self._candidate_lots(sizes), data.location_id)
        if location is None:
            raise BusinessValidationError(
                "There is no stock record for this product in that warehouse yet. Use Add stock first."
            )
        locked = self._lock(lot.id for lot in self._candidate_lots(sizes, location))
        lots = list(locked.values())

        on_hand = sum(lot.quantity_base for lot in lots)
        reserved = sum(lot.reserved_base for lot in lots)
        if counted < reserved:
            raise BusinessValidationError(
                f"{self._amount_text(family, reserved)} is reserved for customer orders, "
                "so the count cannot be lower than that."
            )
        difference = counted - on_hand
        unit_label = _UNIT_LABELS[data.amount_unit]
        if difference == 0:
            return ProductStockOperationResponse(
                operation_id=None,
                kind="correct",
                message="Your count matches the system. Nothing was changed.",
                difference=Decimal("0"),
                amount_unit=data.amount_unit,
                changes=[],
                product=self.inventory._product_stock_item(product_id),
            )

        reason = data.reason if not data.notes else f"{data.reason} - {data.notes}"
        entry = self._record(
            "correct",
            product,
            user_id,
            previous=self._amount_text(family, on_hand),
            new=self._amount_text(family, counted),
            reason=reason,
        )
        remarks = (
            f"Stock count: system={self._amount_text(family, on_hand)} "
            f"counted={self._amount_text(family, counted)} reason={reason}"
        )
        changes: list[dict] = []
        if difference < 0:
            need = -difference
            for lot in self._fifo(lots):
                if need <= 0:
                    break
                take = min(self._available(lot), need)
                if take <= 0:
                    continue
                self._move(changes, lot, "ADJUSTMENT_OUT", take, user_id, "correct", entry.id, remarks)
                need -= take
            if need > 0:
                self.db.rollback()
                raise ConflictError("That much stock could not be taken out because it is reserved for orders.")
        else:
            shared = [lot for lot in lots if not lot.is_share] or lots
            target = max(shared, key=lambda lot: (lot.created_at, lot.id))
            self._move(changes, target, "ADJUSTMENT_IN", difference, user_id, "correct", entry.id, remarks)

        sign = "+" if difference > 0 else "-"
        return self._finish(
            "correct",
            product_id,
            entry.id,
            f"Stock corrected to {_fmt(data.physical_amount)} {unit_label} "
            f"({sign}{_fmt(abs(self._to_unit(difference, data.amount_unit)))} {unit_label}).",
            self._to_unit(difference, data.amount_unit),
            data.amount_unit,
            changes,
        )

    # ------------------------------------------------------------------
    # Remove stock ("2 kg was damaged")
    # ------------------------------------------------------------------

    @staticmethod
    def _removal_type(reason: str) -> str:
        text = reason.lower()
        if "damag" in text:
            return "DAMAGE"
        if any(word in text for word in ("spoil", "waste", "expire")):
            return "WASTE"
        return "ADJUSTMENT_OUT"

    def remove_stock(
        self, product_id: int, data: ProductRemoveStockRequest, user_id: int
    ) -> ProductStockOperationResponse:
        product = self._product(product_id)
        family, amount = amount_in_base(data.amount, data.amount_unit)
        sizes = self._family_sizes(product_id, family, data.amount_unit)
        locked = self._lock(lot.id for lot in self._candidate_lots(sizes, data.location_id))
        lots = list(locked.values())

        available = sum(self._available(lot) for lot in lots)
        if amount > available:
            raise BusinessValidationError(
                f"Only {self._amount_text(family, available)} is available to remove right now. "
                "Stock reserved for customer orders can't be taken."
            )

        entry = self._record(
            "remove",
            product,
            user_id,
            previous=self._amount_text(family, available),
            new=self._amount_text(family, max(available - amount, 0)),
            reason=data.reason,
        )
        movement_type = self._removal_type(data.reason)
        changes: list[dict] = []
        need = amount
        for lot in self._fifo(lots):
            if need <= 0:
                break
            take = min(self._available(lot), need)
            if take <= 0:
                continue
            self._move(changes, lot, movement_type, take, user_id, "remove", entry.id, f"Stock removed: {data.reason}")
            need -= take
        if need > 0:
            self.db.rollback()
            raise ConflictError("That much stock could not be removed because it is reserved for orders.")

        label = _UNIT_LABELS[data.amount_unit]
        return self._finish(
            "remove",
            product_id,
            entry.id,
            f"Removed {_fmt(data.amount)} {label} of {product.name}.",
            -data.amount,
            data.amount_unit,
            changes,
        )

    # ------------------------------------------------------------------
    # Move stock ("10 kg to Nagpur Hub")
    # ------------------------------------------------------------------

    def move_stock(
        self, product_id: int, data: ProductMoveStockRequest, user_id: int
    ) -> ProductStockOperationResponse:
        product = self._product(product_id)
        if data.from_location_id == data.to_location_id:
            raise BusinessValidationError("Choose a different warehouse to move the stock to.")
        source_location = self.inventory.get_location_or_404(data.from_location_id)
        destination = self.inventory.get_location_or_404(data.to_location_id)
        if destination.status != "ACTIVE":
            raise BusinessValidationError("That warehouse is not active.")
        family, amount = amount_in_base(data.amount, data.amount_unit)
        sizes = self._family_sizes(product_id, family, data.amount_unit)

        # Lock the source lots and any destination lots the move will top up
        # in ONE ascending-id pass, so a move the other way round cannot
        # deadlock with this one.
        source_candidates = self._candidate_lots(sizes, data.from_location_id)
        batch_ids = {lot.batch_id for lot in source_candidates}
        destination_candidates = [
            lot for lot in self._candidate_lots(sizes, data.to_location_id) if lot.batch_id in batch_ids
        ]
        locked = self._lock([lot.id for lot in source_candidates] + [lot.id for lot in destination_candidates])
        sources = [lot for lot in locked.values() if lot.location_id == data.from_location_id]
        destinations = {
            (lot.batch_id, lot.variant_id, lot.is_share): lot
            for lot in locked.values()
            if lot.location_id == data.to_location_id
        }

        available = sum(self._available(lot) for lot in sources)
        if amount > available:
            raise BusinessValidationError(
                f"Only {self._amount_text(family, available)} is available in {source_location.name} right now. "
                "Stock reserved for customer orders can't be moved."
            )

        entry = self._record(
            "move",
            product,
            user_id,
            previous=source_location.name[:20],
            new=destination.name[:20],
            reason=f"{self._amount_text(family, amount)} of {product.name}",
        )
        remarks = f"Moved {source_location.name} -> {destination.name}"
        changes: list[dict] = []
        need = amount
        for lot in self._fifo(sources):
            if need <= 0:
                break
            take = min(self._available(lot), need)
            if take <= 0:
                continue
            key = (lot.batch_id, lot.variant_id, lot.is_share)
            target = destinations.get(key)
            if target is None:
                created = self.inventory.get_or_create_lot_no_commit(
                    lot.batch_id, lot.variant_id, data.to_location_id, is_share=lot.is_share
                )
                target = self._lock([created.id])[created.id]
                destinations[key] = target
            self._move(changes, lot, "TRANSFER_OUT", take, user_id, "move", entry.id, remarks)
            self._move(changes, target, "TRANSFER_IN", take, user_id, "move", entry.id, remarks)
            need -= take
        if need > 0:
            self.db.rollback()
            raise ConflictError("That much stock could not be moved because it is reserved for orders.")

        label = _UNIT_LABELS[data.amount_unit]
        return self._finish(
            "move",
            product_id,
            entry.id,
            f"Moved {_fmt(data.amount)} {label} of {product.name} to {destination.name}.",
            Decimal("0"),
            data.amount_unit,
            changes,
        )

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def undo(self, operation_id: int, user: User, role_names: list[str]) -> ProductStockOperationResponse:
        """Reverse a correct / remove / move with compensating movements.

        Nothing is deleted or rewritten: the original movements stay in the
        ledger and new opposite ones are added, all in one transaction. It is
        refused (and nothing changes) when the operation is old, was already
        undone, belongs to somebody else, or when reversing would take stock
        that has since been reserved, sold or moved."""
        log = (
            self.db.query(AdminActionLog)
            .filter(AdminActionLog.id == operation_id)
            .with_for_update()
            .first()
        )
        kind = _KIND_BY_ACTION.get(log.action) if log else None
        if log is None or kind is None:
            raise NotFoundError("Stock action not found.")
        if log.admin_user_id != user.id and ADMIN not in role_names:
            raise AuthorizationError("Only the person who made this change can undo it.")
        if not role_has_permission(role_names, _UNDO_PERMISSION[kind]):
            raise AuthorizationError("You do not have permission to undo this action.")
        created = log.created_at if log.created_at.tzinfo else log.created_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - created > UNDO_WINDOW:
            raise ConflictError(_UNSAFE_UNDO)
        already = (
            self.db.query(AdminActionLog.id)
            .filter(
                AdminActionLog.action == "inventory.undo",
                AdminActionLog.resource_type == "inventory_operation",
                AdminActionLog.resource_id == operation_id,
            )
            .first()
        )
        if already:
            raise ConflictError("This was already undone.")

        movements = (
            self.db.query(StockMovement)
            .filter(
                StockMovement.reference_type == _MOVEMENT_REFERENCE[kind],
                StockMovement.reference_id == operation_id,
            )
            .order_by(StockMovement.id.desc())
            .all()
        )
        if not movements:
            raise ConflictError(_UNSAFE_UNDO)
        locked = self._lock(m.inventory_lot_id for m in movements)

        AdminAuditService(self.db).record(
            admin_user_id=user.id,
            action="inventory.undo",
            resource_type="inventory_operation",
            resource_id=operation_id,
            reason=f"undo of {_AUDIT_ACTION[kind]} on product {log.resource_id}",
        )
        changes: list[dict] = []
        for movement in movements:
            lot = locked.get(movement.inventory_lot_id)
            inverse = _INVERSE_MOVEMENT.get(movement.movement_type)
            if lot is None or inverse is None:
                self.db.rollback()
                raise ConflictError(_UNSAFE_UNDO)
            if lot.quantity_base is None:
                self.db.rollback()
                raise ConflictError(_UNSAFE_UNDO)
            moved = movement.quantity_base
            if moved is None:  # a pre-migration movement: its packs must convert exactly
                exact = Decimal(movement.quantity) * lot.variant.size_base
                if exact != exact.to_integral_value():
                    self.db.rollback()
                    raise ConflictError(_UNSAFE_UNDO)
                moved = int(exact)
            if inverse.endswith("_OUT") and lot.quantity_base - lot.reserved_base < moved:
                self.db.rollback()
                raise ConflictError(_UNSAFE_UNDO)
            try:
                self.inventory.apply_movement_base(
                    lot,
                    inverse,
                    moved,
                    user.id,
                    reference_type="product_undo",
                    reference_id=operation_id,
                    remarks=f"Undo of stock action {operation_id}",
                )
            except (ConflictError, BusinessValidationError) as exc:
                self.db.rollback()
                raise ConflictError(_UNSAFE_UNDO) from exc
            changes.append({"lot": lot, "movement_type": inverse, "packs": movement.quantity})

        return self._finish(
            "undo",
            log.resource_id,
            operation_id,
            "Undone. The stock is back as it was.",
            Decimal("0"),
            "KG",
            changes,
        )
