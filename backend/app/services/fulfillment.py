"""Fulfillment domain service: status progression, delivery-partner
assignment, and delivery confirmation.

TRANSACTION DESIGN: same autobegin/no-explicit-begin rule as every other
service in this codebase. `confirm_delivery` is the one large atomic
transaction in this file and is where physical inventory consumption
happens - see its docstring for the full lock sequence.

LOCK ORDERING: Order -> Fulfillment -> Reservation -> InventoryLots,
consistent with the order documented in
app/services/inventory_reservation.py (Order is always locked before any
Fulfillment/Reservation/Lot row it owns, and lots are always locked in a
single deterministic id-ASC order). `assign_delivery_partner`,
`mark_out_for_delivery`, and `update_status` now also lock Order first
(Phase 18, via `_lock_order_and_fulfillment`) purely to serialize against
a concurrent cancellation - see `_assert_order_still_active` - even though
none of them otherwise reads/writes the Order row.

PHASE 18 CANCELLATION GUARD: every fulfillment-progressing method rejects
a non-CONFIRMED order (`_assert_order_still_active` for the three
warehouse/assignment methods; `confirm_delivery`'s own pre-existing
`order.status != "CONFIRMED"` check for delivery) - this is what stops a
cancelled order from ever reaching ASSIGNED/OUT_FOR_DELIVERY/DELIVERED,
and, combined with the shared Order-first lock order, what makes a
cancellation racing any of these actions resolve to exactly one
deterministic outcome rather than a corrupt mixed state.

AUTHORIZATION MODEL (Phase 16): the router grants route-level access via
`require_roles`, but two further checks live here in the service, since
they depend on data (not just role membership):
  - "Privileged" staff (ADMIN, HUB_STAFF, OPERATIONS) see/manage every
    fulfillment. A caller holding ONLY the DELIVERY_PARTNER role is
    scoped to fulfillments actually assigned to them (`get_fulfillment_or_404`,
    `list_fulfillments`) - a 404, not a 403, on someone else's fulfillment,
    matching this codebase's established "don't disclose existence"
    convention (see PaymentService._get_owned_payment).
  - Delivery-partner-gated mutations (`mark_out_for_delivery`,
    `confirm_delivery`) require the acting user to BE the assigned
    delivery_partner_user_id, with ADMIN as the only override - HUB_STAFF/
    OPERATIONS are warehouse roles and are deliberately excluded from
    these two delivery-in-transit actions, mirroring how DELIVERY_PARTNER
    is excluded from the warehouse-side transitions (`update_status`,
    `assign_delivery_partner`).
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.roles import ADMIN, DELIVERY_PARTNER, HUB_STAFF, OPERATIONS
from app.exceptions.base import AuthorizationError, ConflictError, NotFoundError
from app.models.fulfillment import Fulfillment
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.fulfillment import (
    CustomerFulfillmentResponse,
    FulfillmentListResponse,
    FulfillmentResponse,
)
from app.services.fulfillment_state import (
    FulfillmentStatus,
    IllegalFulfillmentTransitionError,
    transition_fulfillment_status,
)
from app.services.inventory import InventoryService
from app.services.reservation_state import ReservationStatus

_DELIVERY_MOVEMENT_TYPE = "DISPATCH"
_DELIVERY_REFERENCE_TYPE = "ORDER"
_PRIVILEGED_ROLES = (ADMIN, HUB_STAFF, OPERATIONS)


class FulfillmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Role/ownership helpers
    # ------------------------------------------------------------------

    def _has_any_role(self, user_id: int, *role_names: str) -> bool:
        return (
            self.db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id, Role.name.in_(role_names))
            .first()
            is not None
        )

    def _is_privileged(self, user_id: int) -> bool:
        return self._has_any_role(user_id, *_PRIVILEGED_ROLES)

    def _assert_can_act_as_delivery_partner(
        self, fulfillment: Fulfillment, current_user: User
    ) -> None:
        """Only the assigned delivery partner, or ADMIN as an
        administrative override, may perform delivery-in-transit actions.
        HUB_STAFF/OPERATIONS are warehouse roles and are deliberately
        excluded here even though they can perform the earlier
        picking/packing/ready/assign steps.
        """
        if fulfillment.delivery_partner_user_id == current_user.id:
            return
        if self._has_any_role(current_user.id, ADMIN):
            return
        raise AuthorizationError(
            "You are not the delivery partner assigned to this fulfillment."
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_fulfillment_or_404(
        self, fulfillment_id: int, current_user: User
    ) -> FulfillmentResponse:
        fulfillment = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.id == fulfillment_id)
            .first()
        )
        if fulfillment is None:
            raise NotFoundError("Fulfillment not found.")
        if (
            fulfillment.delivery_partner_user_id != current_user.id
            and not self._is_privileged(current_user.id)
        ):
            # Same "don't disclose existence to a non-owner" convention as
            # PaymentService._get_owned_payment - a DELIVERY_PARTNER who
            # isn't assigned gets the identical 404 a nonexistent id would.
            raise NotFoundError("Fulfillment not found.")
        return FulfillmentResponse.model_validate(fulfillment)

    def list_fulfillments(
        self,
        current_user: User,
        *,
        status: str | None,
        delivery_partner_user_id: int | None,
        page: int,
        page_size: int,
    ) -> FulfillmentListResponse:
        query = self.db.query(Fulfillment)
        if status is not None:
            query = query.filter(Fulfillment.status == status)

        if self._is_privileged(current_user.id):
            if delivery_partner_user_id is not None:
                query = query.filter(
                    Fulfillment.delivery_partner_user_id == delivery_partner_user_id
                )
        else:
            # A non-privileged caller (DELIVERY_PARTNER) is always scoped
            # to their own assignments - any client-supplied
            # delivery_partner_user_id filter is ignored rather than
            # honored, so one partner can never enumerate another's load.
            query = query.filter(
                Fulfillment.delivery_partner_user_id == current_user.id
            )

        total = query.count()
        items = (
            query.order_by(Fulfillment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return FulfillmentListResponse(
            items=[FulfillmentResponse.model_validate(f) for f in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_fulfillment_response_for_order(self, order_id: int) -> FulfillmentResponse:
        """Ops-facing. Caller (route) is responsible for any ownership
        check beyond role - this mirrors PaymentService.get_payment_for_order.
        """
        fulfillment = (
            self.db.query(Fulfillment).filter(Fulfillment.order_id == order_id).first()
        )
        if fulfillment is None:
            raise NotFoundError("Fulfillment not found for this order.")
        return FulfillmentResponse.model_validate(fulfillment)

    def get_customer_fulfillment_response_for_order(
        self, order_id: int
    ) -> CustomerFulfillmentResponse:
        fulfillment = (
            self.db.query(Fulfillment).filter(Fulfillment.order_id == order_id).first()
        )
        if fulfillment is None:
            raise NotFoundError("Fulfillment not found for this order.")
        return CustomerFulfillmentResponse.model_validate(fulfillment)

    # ------------------------------------------------------------------
    # Status progression (PENDING -> PICKING -> PACKED -> READY_FOR_DELIVERY)
    # ------------------------------------------------------------------

    def update_status(self, fulfillment_id: int, new_status: str) -> FulfillmentResponse:
        """Advances the fulfillment exactly one warehouse step. ASSIGNED,
        OUT_FOR_DELIVERY, and DELIVERED are rejected here - each has its
        own dedicated endpoint with its own extra validation (assignment
        target, delivery-partner ownership, physical consumption).
        """
        if new_status in (
            FulfillmentStatus.ASSIGNED,
            FulfillmentStatus.OUT_FOR_DELIVERY,
            FulfillmentStatus.DELIVERED,
        ):
            raise ConflictError(
                f"Use the dedicated endpoint to move a fulfillment to {new_status}."
            )

        order, fulfillment = self._lock_order_and_fulfillment(fulfillment_id)
        self._assert_order_still_active(order)

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
    # Delivery partner assignment (READY_FOR_DELIVERY -> ASSIGNED)
    # ------------------------------------------------------------------

    def assign_delivery_partner(
        self, fulfillment_id: int, delivery_partner_user_id: int
    ) -> FulfillmentResponse:
        """Lock order + fulfillment -> verify READY_FOR_DELIVERY -> ASSIGNED
        is legal -> verify the target user exists and holds
        DELIVERY_PARTNER -> set delivery_partner_user_id + assigned_at ->
        transition -> commit. Order is locked first (Phase 18) so a
        concurrent cancellation (which also locks Order first - see
        OrderService._lock_order_for_cancel) cannot race an assignment
        into existing on an order that is being/was just cancelled.

        Deliberately does NOT use `transition_fulfillment_status`'s
        generic same-state-is-a-no-op rule here: that rule exists so a
        retried warehouse action (e.g. PICKING -> PICKING) is a harmless
        idempotent no-op, but assignment is not idempotent in that sense
        - a second call could name a DIFFERENT delivery_partner_user_id,
        and treating current==target(ASSIGNED) as a no-op would silently
        let it overwrite the first assignment instead of being rejected.
        So the only legal current status here is READY_FOR_DELIVERY,
        checked explicitly and unconditionally.
        """
        order, fulfillment = self._lock_order_and_fulfillment(fulfillment_id)
        self._assert_order_still_active(order)

        if FulfillmentStatus(fulfillment.status) != FulfillmentStatus.READY_FOR_DELIVERY:
            raise ConflictError(
                f"Cannot assign a delivery partner from status {fulfillment.status}."
            )

        target_user = (
            self.db.query(User).filter(User.id == delivery_partner_user_id).first()
        )
        if target_user is None:
            raise NotFoundError("Delivery partner user not found.")
        if not self._has_any_role(target_user.id, DELIVERY_PARTNER):
            raise ConflictError(
                "The target user does not hold the DELIVERY_PARTNER role."
            )

        now = datetime.now(UTC)
        fulfillment.delivery_partner_user_id = target_user.id
        fulfillment.assigned_at = now
        fulfillment.status = FulfillmentStatus.ASSIGNED

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not assign delivery partner due to a conflicting update."
            ) from exc
        self.db.refresh(fulfillment)

        logger.info(
            "FULFILLMENT_ASSIGNED: fulfillment_id=%s delivery_partner_user_id=%s",
            fulfillment.id, target_user.id,
        )
        return FulfillmentResponse.model_validate(fulfillment)

    # ------------------------------------------------------------------
    # Out for delivery (ASSIGNED -> OUT_FOR_DELIVERY, partner-owned)
    # ------------------------------------------------------------------

    def mark_out_for_delivery(
        self, fulfillment_id: int, current_user: User
    ) -> FulfillmentResponse:
        order, fulfillment = self._lock_order_and_fulfillment(fulfillment_id)
        self._assert_order_still_active(order)
        self._assert_can_act_as_delivery_partner(fulfillment, current_user)

        try:
            result = transition_fulfillment_status(
                FulfillmentStatus(fulfillment.status), FulfillmentStatus.OUT_FOR_DELIVERY
            )
        except IllegalFulfillmentTransitionError as exc:
            raise ConflictError(
                f"Cannot mark OUT_FOR_DELIVERY from status {exc.current.value}."
            ) from exc

        if result.applied:
            fulfillment.status = FulfillmentStatus.OUT_FOR_DELIVERY
            logger.info(
                "FULFILLMENT_OUT_FOR_DELIVERY: fulfillment_id=%s delivery_partner_user_id=%s",
                fulfillment.id, fulfillment.delivery_partner_user_id,
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
        self, fulfillment_id: int, current_user: User
    ) -> FulfillmentResponse:
        """Atomically: lock order -> lock fulfillment -> verify ownership
        (assigned delivery partner, or ADMIN override) -> verify
        OUT_FOR_DELIVERY (idempotent no-op if already DELIVERED) -> verify
        order CONFIRMED -> lock reservation -> verify COMMITTED -> read
        its allocation items -> lock every allocated lot in a fixed
        id-ASC order -> decrease both `quantity` (via the existing
        DISPATCH stock-movement path) and `reserved_quantity` on each ->
        mark fulfillment DELIVERED -> mark order COMPLETED -> commit once.

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

        self._assert_can_act_as_delivery_partner(fulfillment, current_user)

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

        if order.status != "CONFIRMED":
            # Phase 18: this is also what stops a CANCELLED order from
            # ever being delivered - if a concurrent cancellation won the
            # race for the Order row lock above, `order.status` is
            # already CANCELLED by the time this re-read happens, so
            # nothing below (reservation release, DISPATCH movement,
            # reserved_quantity decrement, DELIVERED/COMPLETED) ever runs.
            raise ConflictError(
                f"Cannot confirm delivery: order status is {order.status}, not CONFIRMED."
            )

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
                current_user.id,
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
            "FULFILLMENT_DELIVERED: fulfillment_id=%s order_id=%s lots_consumed=%s "
            "performed_by_user_id=%s",
            fulfillment.id, order.id, len(items), current_user.id,
        )
        return FulfillmentResponse.model_validate(fulfillment)

    # ------------------------------------------------------------------
    # Locking helpers
    # ------------------------------------------------------------------

    def _lock_order_and_fulfillment(self, fulfillment_id: int) -> tuple[Order, Fulfillment]:
        """Locks Order before Fulfillment (Phase 18) - both unconditionally
        on id (no status filter), the same retry-safety pattern used
        throughout this codebase: a status-filtered FOR UPDATE would
        silently exclude the row once a concurrent transaction changes its
        status. Locking Order FIRST here (mirroring confirm_delivery's own
        established sequence) is what lets a concurrent cancellation
        (OrderService._lock_order_for_cancel, which also locks Order
        first) and a concurrent warehouse/assignment action resolve
        deterministically via Postgres's row lock rather than a race.

        `.populate_existing()` is required on both re-queries: the initial
        unlocked Fulfillment read (needed only to discover order_id before
        Order can be locked first) pollutes this session's identity map -
        the same Phase 14 stale-identity-map precondition documented in
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
        fulfillment = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.id == fulfillment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        return order, fulfillment

    @staticmethod
    def _assert_order_still_active(order: Order) -> None:
        """Phase 18: a cancelled (or otherwise no-longer-CONFIRMED) order
        must never progress through fulfillment any further - this is the
        guard that makes "fulfillment cannot continue to ASSIGNED,
        OUT_FOR_DELIVERY, DELIVERED after cancellation" true for every
        warehouse/assignment/dispatch action, not just delivery
        confirmation (which already has its own equivalent check in
        confirm_delivery, placed after its DELIVERED-idempotent check
        rather than here, so a repeated /deliver call on an
        already-delivered - now COMPLETED - order still returns its
        existing idempotent 200 instead of a 409 from this guard).
        """
        if order is None or order.status != "CONFIRMED":
            raise ConflictError(
                f"Cannot modify this fulfillment: order status is "
                f"{order.status if order else 'unknown'}, not CONFIRMED."
            )
