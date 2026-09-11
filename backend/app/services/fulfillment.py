"""Fulfillment domain service: status progression and delivery confirmation.

TRANSACTION DESIGN: same autobegin/no-explicit-begin rule as every other
service in this codebase. `confirm_delivery` is the one large atomic
transaction in this file and is where physical inventory consumption
happens - see its docstring for the full lock sequence.

LOCK ORDERING: Order -> Fulfillment -> Reservation -> InventoryLots,
consistent with the order documented in
app/services/inventory_reservation.py (Order is always locked before any
Fulfillment/Reservation/Lot row it owns, and lots are always locked in a
single deterministic id-ASC order).
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.exceptions.base import ConflictError, NotFoundError
from app.models.fulfillment import Fulfillment
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.schemas.fulfillment import FulfillmentResponse
from app.services.fulfillment_state import (
    FulfillmentStatus,
    IllegalFulfillmentTransitionError,
    transition_fulfillment_status,
)
from app.services.inventory import InventoryService
from app.services.reservation_state import ReservationStatus

_DELIVERY_MOVEMENT_TYPE = "DISPATCH"
_DELIVERY_REFERENCE_TYPE = "ORDER"


class FulfillmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_fulfillment_or_404(self, fulfillment_id: int) -> Fulfillment:
        fulfillment = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.id == fulfillment_id)
            .first()
        )
        if fulfillment is None:
            raise NotFoundError("Fulfillment not found.")
        return fulfillment

    # ------------------------------------------------------------------
    # Status progression (PENDING -> ... -> OUT_FOR_DELIVERY)
    # ------------------------------------------------------------------

    def update_status(self, fulfillment_id: int, new_status: str) -> FulfillmentResponse:
        """Advances the fulfillment exactly one step in the fixed chain.
        DELIVERED is rejected here - it is only reachable via
        `confirm_delivery`, which is the only path that consumes physical
        inventory and confirms the order.
        """
        if new_status == FulfillmentStatus.DELIVERED:
            raise ConflictError(
                "Use POST /fulfillments/{id}/deliver to mark a fulfillment DELIVERED."
            )

        fulfillment = self._lock_fulfillment(fulfillment_id)

        try:
            result = transition_fulfillment_status(
                FulfillmentStatus(fulfillment.status), FulfillmentStatus(new_status)
            )
        except IllegalFulfillmentTransitionError as exc:
            raise ConflictError(
                f"Cannot move fulfillment from {exc.current.value} to {exc.target.value}."
            ) from exc

        if result.applied:
            fulfillment.status = new_status
            logger.info(
                "FULFILLMENT_STATUS_CHANGED: fulfillment_id=%s %s -> %s",
                fulfillment.id, result.previous.value, result.current.value,
            )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not update fulfillment due to a conflicting update."
            ) from exc
        self.db.refresh(fulfillment)
        return FulfillmentResponse.model_validate(fulfillment)

    # ------------------------------------------------------------------
    # Delivery confirmation (the only physical-consumption path)
    # ------------------------------------------------------------------

    def confirm_delivery(
        self, fulfillment_id: int, performed_by_user_id: int
    ) -> FulfillmentResponse:
        """Atomically: lock order -> lock fulfillment -> verify
        OUT_FOR_DELIVERY (idempotent no-op if already DELIVERED) -> lock
        reservation -> verify COMMITTED -> read its allocation items ->
        lock every allocated lot in a fixed id-ASC order -> decrease both
        `quantity` (via the existing DISPATCH stock-movement path) and
        `reserved_quantity` on each -> mark fulfillment DELIVERED -> mark
        order COMPLETED -> commit once.

        No partial fulfillment: if any lot can no longer support its
        allocated quantity (should be unreachable given the reservation
        invariants, but is not trusted blindly), the whole transaction is
        aborted and nothing is written.

        Lock order is Order -> Fulfillment, matching every other service
        in this codebase. Discovering `order_id` requires an initial
        unlocked read of `fulfillment`, which pollutes this session's
        identity map - `.populate_existing()` is therefore required on
        BOTH subsequent locked re-queries (Order and Fulfillment) to avoid
        the Phase 14 stale-identity-map bug documented in
        PaymentService._lock_payment_and_order.
        """
        fulfillment_unlocked = (
            self.db.query(Fulfillment).filter(Fulfillment.id == fulfillment_id).first()
        )
        if fulfillment_unlocked is None:
            raise NotFoundError("Fulfillment not found.")

        order = (
            self.db.query(Order)
            .filter(Order.id == fulfillment_unlocked.order_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if order is None:
            raise NotFoundError("Order not found for this fulfillment.")

        fulfillment = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.id == fulfillment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

        if FulfillmentStatus(fulfillment.status) == FulfillmentStatus.DELIVERED:
            self.db.commit()  # idempotent: nothing left to do, release locks
            return FulfillmentResponse.model_validate(fulfillment)

        try:
            transition_fulfillment_status(
                FulfillmentStatus(fulfillment.status), FulfillmentStatus.DELIVERED
            )
        except IllegalFulfillmentTransitionError as exc:
            raise ConflictError(
                f"Cannot mark fulfillment DELIVERED from status {exc.current.value}."
            ) from exc

        reservation = (
            self.db.query(InventoryReservation)
            .filter(InventoryReservation.order_id == order.id)
            .with_for_update()
            .first()
        )
        if reservation is None or ReservationStatus(reservation.status) != ReservationStatus.COMMITTED:
            raise ConflictError(
                "Cannot confirm delivery: order's inventory reservation is not "
                "in a COMMITTED state."
            )

        items = (
            self.db.query(InventoryReservationItem)
            .filter(InventoryReservationItem.reservation_id == reservation.id)
            .order_by(InventoryReservationItem.inventory_lot_id.asc())
            .all()
        )
        lot_ids = sorted({i.inventory_lot_id for i in items})
        lots = {
            lot.id: lot
            for lot in self.db.query(InventoryLot)
            .filter(InventoryLot.id.in_(lot_ids))
            .order_by(InventoryLot.id.asc())
            .with_for_update()
            .all()
        }

        inventory_service = InventoryService(self.db)
        for item in items:
            lot = lots.get(item.inventory_lot_id)
            if lot is None or lot.reserved_quantity < item.quantity:
                raise ConflictError(
                    "Cannot confirm delivery: reserved inventory is inconsistent "
                    "with this order's allocation."
                )
            inventory_service.apply_movement(
                lot,
                _DELIVERY_MOVEMENT_TYPE,
                item.quantity,
                performed_by_user_id,
                reference_type=_DELIVERY_REFERENCE_TYPE,
                reference_id=order.id,
                occurred_at=datetime.now(UTC),
                remarks="Physical inventory consumed at delivery confirmation.",
            )
            lot.reserved_quantity = lot.reserved_quantity - item.quantity

        fulfillment.status = FulfillmentStatus.DELIVERED
        fulfillment.delivered_at = datetime.now(UTC)
        order.status = "COMPLETED"

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not confirm delivery due to a conflicting update."
            ) from exc
        self.db.refresh(fulfillment)

        logger.info(
            "FULFILLMENT_DELIVERED: fulfillment_id=%s order_id=%s lots_consumed=%s",
            fulfillment.id, order.id, len(items),
        )
        return FulfillmentResponse.model_validate(fulfillment)

    # ------------------------------------------------------------------
    # Locking helpers
    # ------------------------------------------------------------------

    def _lock_fulfillment(self, fulfillment_id: int) -> Fulfillment:
        """Locks unconditionally on id (no status filter) - same
        retry-safety pattern used throughout this phase: a status-filtered
        FOR UPDATE would silently exclude the row once a concurrent
        transaction changes its status.
        """
        fulfillment = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.id == fulfillment_id)
            .with_for_update()
            .first()
        )
        if fulfillment is None:
            raise NotFoundError("Fulfillment not found.")
        return fulfillment
