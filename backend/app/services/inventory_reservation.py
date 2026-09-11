"""Inventory reservation domain service.

TRANSACTION DESIGN: same rule as every prior atomic-transaction phase -
`create_reservation_for_order` is called from inside `OrderService.checkout`
BEFORE that method's single `db.commit()`, so it never commits itself; a
raised exception here rolls back the whole checkout (order, items, address,
cart status change, and any partial reservation writes) together, since the
caller's session is closed without a commit. `commit_reservation_for_order`
and `expire_reservation_for_order` similarly never commit - they are called
from PaymentService methods that already own the transaction boundary, or
from a thin ops-facing route that commits after calling in.

LOCK ORDERING (documented, extending Phase 13/14's Order-before-Payment
convention): Cart -> Order -> Payment -> Fulfillment -> Reservation ->
InventoryLots. Reservation is always locked after Order/Payment/Fulfillment
and before the lots it allocates/releases, and lots are always locked in a
single deterministic order (id ASC for a known set, created_at ASC/id ASC
for FIFO candidate selection) - this is what prevents a deadlock between
two transactions that both need to touch a reservation and its lots.

FIFO ALLOCATION SCOPE: lots are selected across ALL locations for a given
variant, not scoped to one location. There is no existing concept of a
"default"/"operational" inventory location anywhere in this codebase
(InventoryLocation has no such flag, only ACTIVE/INACTIVE), and nothing in
the Phase 15 spec requires reservations to be location-aware - only
`created_at ASC, id ASC` FIFO order is required. Pooling across locations
is therefore the simplest strategy consistent with the existing schema,
not a gap that needed a new convention invented.

EXPIRY MODEL: a reservation's `expires_at` is fixed at creation
(order.created_at + 30 minutes) and applies uniformly regardless of which
payment method is eventually chosen. The reservation is created at
checkout time, before any payment method is selected, so a UPI-only expiry
window is not representable - COD is not exempt from it. If a customer
waits past the window before ever creating a COD payment, that payment
attempt fails cleanly (see PaymentService._confirm_cod) rather than
resurrecting a stale hold.

FAILURE HANDLING DEVIATION (see class docstring below for the conflict
this resolves): a definitively FAILED UPI payment attempt does NOT release
the reservation. It stays ACTIVE (still holding inventory) so that the
existing, unmodified POST /payments/{id}/retry flow can succeed against
the same reservation. The reservation is still bounded by its own 30-minute
expiry regardless of how many attempts fail in that window.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.exceptions.base import ConflictError, NotFoundError
from app.models.fulfillment import Fulfillment
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation import InventoryReservation
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.inventory_reservation import (
    InventoryReservationDetailResponse,
    InventoryReservationItemResponse,
    InventoryReservationListResponse,
    InventoryReservationResponse,
)
from app.services.fulfillment_state import FulfillmentStatus
from app.services.reservation_state import (
    ReservationStatus,
    transition_reservation_status,
)

RESERVATION_WINDOW_MINUTES = 30

_LOT_ACTIVE = "ACTIVE"


class InventoryReservationService:
    """Reservation creation (FIFO), commit/expire/release, and reads.

    Class-level note on the one deliberate spec deviation in this service:
    the Phase 15 spec states a definitively FAILED UPI payment should
    release its reservation (ACTIVE -> RELEASED). RELEASED is terminal (see
    reservation_state.py) and `inventory_reservations` has UNIQUE(order_id)
    - there is exactly one reservation row per order, ever. If a failure
    released it, a subsequent successful retry via the existing, unmodified
    POST /payments/{id}/retry would have no ACTIVE reservation left to
    commit, and there is no re-activation path without either violating
    reservation terminality or duplicating FIFO re-allocation logic inside
    PaymentService.retry_payment (which would mean duplicating this
    service's allocation logic in two places, and would touch a Phase 14
    method the spec says not to redesign). The smallest correct fix is to
    hold the reservation through payment FAILURE and rely on the
    reservation's own 30-minute expiry as the sole release point besides an
    explicit future cancellation feature - `release_reservation_for_order`
    below still exists and is exercised by tests so that feature has
    something to call, it is simply not wired to payment failure in this
    phase.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Creation (called from OrderService.checkout, pre-commit)
    # ------------------------------------------------------------------

    def create_reservation_for_order(
        self, order: Order, order_items: list[OrderItem]
    ) -> InventoryReservation:
        """FIFO-allocate inventory for every order item and create the
        reservation + its allocation rows. Raises ConflictError (never
        partially applies) if any variant's available inventory is
        insufficient - the caller's checkout transaction then rolls back
        entirely.

        Caller must not have committed yet. Does not commit.
        """
        needed_by_variant: dict[int, Decimal] = {}
        for item in order_items:
            needed_by_variant[item.variant_id] = (
                needed_by_variant.get(item.variant_id, Decimal("0")) + item.quantity
            )

        # Lock every candidate lot for every needed variant up front, in a
        # fixed (variant_id, created_at, id) order, before allocating any
        # of them - this is what makes concurrent checkouts for overlapping
        # variants deadlock-free.
        lots_by_variant: dict[int, list[InventoryLot]] = {}
        for variant_id in sorted(needed_by_variant):
            lots_by_variant[variant_id] = (
                self.db.query(InventoryLot)
                .filter(
                    InventoryLot.variant_id == variant_id,
                    InventoryLot.status == _LOT_ACTIVE,
                )
                .order_by(InventoryLot.created_at.asc(), InventoryLot.id.asc())
                .with_for_update()
                .all()
            )

        # Allocate (in memory only, against the now-locked, fresh
        # quantities) before writing anything - if any variant can't be
        # fully covered, fail the whole reservation with nothing applied.
        allocations: list[tuple[OrderItem, InventoryLot, Decimal]] = []
        remaining_capacity: dict[int, Decimal] = {}

        for item in order_items:
            need = item.quantity
            for lot in lots_by_variant[item.variant_id]:
                if need <= 0:
                    break
                capacity = remaining_capacity.get(
                    lot.id, lot.quantity - lot.reserved_quantity
                )
                if capacity <= 0:
                    remaining_capacity[lot.id] = capacity
                    continue
                take = min(capacity, need)
                allocations.append((item, lot, take))
                remaining_capacity[lot.id] = capacity - take
                need -= take
            if need > 0:
                logger.warning(
                    "INVENTORY_RESERVATION_INSUFFICIENT_STOCK: variant_id=%s "
                    "requested=%s short_by=%s",
                    item.variant_id, item.quantity, need,
                )
                raise ConflictError(
                    f"Insufficient available stock for variant {item.variant_id}."
                )

        # order.created_at is server-generated (func.now()) and not
        # reliably populated on the ORM object within the same
        # transaction before a round-trip refresh, so the 30-minute
        # window is computed from `now` - captured here, at reservation
        # creation time, which happens atomically with order creation in
        # the same checkout transaction and is therefore equivalent to
        # order.created_at for this purpose.
        now = datetime.now(UTC)
        reservation = InventoryReservation(
            order_id=order.id,
            status=ReservationStatus.ACTIVE,
            expires_at=now + timedelta(minutes=RESERVATION_WINDOW_MINUTES),
            released_at=None,
        )
        self.db.add(reservation)
        self.db.flush()  # assign reservation.id

        for item, lot, qty in allocations:
            lot.reserved_quantity = lot.reserved_quantity + qty
            self.db.add(
                InventoryReservationItem(
                    reservation_id=reservation.id,
                    order_item_id=item.id,
                    inventory_lot_id=lot.id,
                    quantity=qty,
                )
            )

        logger.info(
            "INVENTORY_RESERVATION_CREATED: reservation_id=%s order_id=%s "
            "lots_allocated=%s expires_at=%s",
            reservation.id, order.id, len(allocations), reservation.expires_at,
        )
        return reservation

    # ------------------------------------------------------------------
    # Commit (payment success / COD acceptance)
    # ------------------------------------------------------------------

    def commit_reservation_for_order(self, order: Order, *, now: datetime) -> bool:
        """Attempt to move `order`'s reservation ACTIVE -> COMMITTED.

        `order` must already be locked (`with_for_update()`) by the
        caller - see the module lock-ordering note: Order is always
        locked before Reservation, and this method relies on that to stay
        deadlock-free against `expire_reservation_for_order` (which locks
        Order first itself for the same reason).

        Returns True iff the reservation is (now, or already) COMMITTED -
        callers use this as the single gate for "is it safe to confirm
        this order". Returns False for every other outcome: no
        reservation found, already RELEASED, already EXPIRED, or ACTIVE
        but past its expiry (in which case this call performs the lazy
        expiry transition itself - including moving `order.status` from
        PENDING to EXPIRED - before returning False) - this is exactly
        what stops a late payment success from resurrecting an expired
        reservation. Never raises for a normal "can't commit" outcome;
        the caller decides how to react (reject the payment action, or
        skip order confirmation and log a reconciliation event).
        """
        reservation = self._lock_reservation_by_order_id(order.id)
        if reservation is None:
            logger.error(
                "INVENTORY_RESERVATION_MISSING: order_id=%s has no reservation "
                "at payment-confirmation time", order.id,
            )
            return False

        status = ReservationStatus(reservation.status)
        if status == ReservationStatus.COMMITTED:
            return True  # idempotent: already committed (duplicate webhook/verify)
        if status in (ReservationStatus.RELEASED, ReservationStatus.EXPIRED):
            logger.warning(
                "INVENTORY_RESERVATION_LATE_PAYMENT: reservation_id=%s order_id=%s "
                "payment resolved after reservation already %s - order will NOT "
                "be auto-confirmed",
                reservation.id, order.id, status.value,
            )
            return False

        # status == ACTIVE
        if reservation.expires_at <= now:
            self._expire_locked(reservation, now=now)
            self._mark_order_expired_if_pending(order, reservation, now=now)
            logger.warning(
                "INVENTORY_RESERVATION_LATE_PAYMENT: reservation_id=%s order_id=%s "
                "expired at %s before payment resolved at %s - order will NOT "
                "be auto-confirmed",
                reservation.id, order.id, reservation.expires_at, now,
            )
            return False

        result = transition_reservation_status(status, ReservationStatus.COMMITTED)
        if result.applied:
            reservation.status = ReservationStatus.COMMITTED
            reservation.updated_at = now
            self._ensure_fulfillment(order.id)
            logger.info(
                "INVENTORY_RESERVATION_COMMITTED: reservation_id=%s order_id=%s",
                reservation.id, order.id,
            )
        return True

    @staticmethod
    def _mark_order_expired_if_pending(
        order: Order, reservation: InventoryReservation, *, now: datetime
    ) -> None:
        """Caller must already hold the order row lock. The spec calls for
        an explicit terminal order status when its payment window lapses
        (PENDING -> EXPIRED) distinct from CANCELLED/COMPLETED - applied
        here, the single place a reservation actually expires, rather
        than duplicated at each of this class's three expiry call sites.
        """
        if order.status == "PENDING":
            order.status = "EXPIRED"
            logger.info(
                "ORDER_EXPIRED: order_id=%s reservation_id=%s", order.id, reservation.id
            )

    def _ensure_fulfillment(self, order_id: int) -> Fulfillment:
        existing = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.order_id == order_id)
            .first()
        )
        if existing:
            return existing
        fulfillment = Fulfillment(
            order_id=order_id,
            status=FulfillmentStatus.PENDING,
        )
        self.db.add(fulfillment)
        self.db.flush()
        logger.info(
            "FULFILLMENT_CREATED: fulfillment_id=%s order_id=%s",
            fulfillment.id, order_id,
        )
        return fulfillment

    # ------------------------------------------------------------------
    # Expiry
    # ------------------------------------------------------------------

    def expire_reservation_for_order(self, order_id: int, *, now: datetime) -> InventoryReservation:
        """Explicit/lazy expiry entry point (used by the ops endpoint and
        by any read path that wants to force-resolve a stale ACTIVE
        reservation). Idempotent: re-calling on an already-terminal
        reservation is a safe no-op that returns the current row.

        Locks Order before Reservation (even though this path doesn't
        need the order for any other reason) specifically to match
        `commit_reservation_for_order`'s lock order - both methods can
        run concurrently against the same order/reservation pair (the
        payment-success-vs-expiry race), and a consistent order is what
        keeps that race a clean "one wins, one sees terminal state and
        no-ops" instead of a Postgres deadlock.

        `.populate_existing()` is required on this lock: the customer
        `GET /orders/{id}/reservation` route reads `Order` unlocked first
        (for the ownership check) before calling into this service in the
        same session - the exact Phase 14 stale-identity-map precondition.
        Without it, a concurrent status change between that unlocked read
        and this lock could make `_mark_order_expired_if_pending` act on
        a stale `order.status` and wrongly overwrite an order that has
        since legitimately moved on (e.g. to CONFIRMED).
        """
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        reservation = self._lock_reservation_by_order_id(order_id)
        if reservation is None:
            raise NotFoundError("Reservation not found for this order.")

        status = ReservationStatus(reservation.status)
        if status != ReservationStatus.ACTIVE:
            return reservation  # terminal already - no-op

        self._expire_locked(reservation, now=now)
        if order is not None:
            self._mark_order_expired_if_pending(order, reservation, now=now)
        return reservation

    def _expire_locked(self, reservation: InventoryReservation, *, now: datetime) -> None:
        """Caller must already hold the reservation row lock. Releases
        every allocated lot's reserved_quantity and marks the reservation
        EXPIRED. Does not commit.
        """
        self._release_locked(reservation, target=ReservationStatus.EXPIRED, now=now)

    def release_reservation_for_order(
        self, order_id: int, *, now: datetime, reason: str = "manual_release"
    ) -> InventoryReservation:
        """Generic release, kept for reuse by a future cancellation
        feature. Nothing in Phase 15 calls this automatically - see the
        class docstring for why UPI payment failure does not call it.

        Locks Order before Reservation for the same deadlock-avoidance
        reason as `expire_reservation_for_order`, even though release
        itself never touches `order.status` - that is left to whatever
        future cancellation feature calls this, since RELEASED here does
        not imply any particular order status on its own.
        """
        # Held only for lock ordering - this method never reads/writes the
        # order itself, so the row is intentionally not bound to a name.
        # `.populate_existing()` defensively matches `expire_reservation_for_order`
        # in case a future caller reaches this after its own unlocked Order read.
        self.db.query(Order).filter(
            Order.id == order_id
        ).populate_existing().with_for_update().first()
        reservation = self._lock_reservation_by_order_id(order_id)
        if reservation is None:
            raise NotFoundError("Reservation not found for this order.")

        status = ReservationStatus(reservation.status)
        if status != ReservationStatus.ACTIVE:
            return reservation  # terminal already - no-op

        self._release_locked(reservation, target=ReservationStatus.RELEASED, now=now)
        logger.info(
            "INVENTORY_RESERVATION_RELEASED: reservation_id=%s order_id=%s reason=%s",
            reservation.id, order_id, reason,
        )
        return reservation

    def _release_locked(
        self,
        reservation: InventoryReservation,
        *,
        target: ReservationStatus,
        now: datetime,
    ) -> None:
        """Shared core for EXPIRED/RELEASED: lock every allocated lot (in a
        fixed, deterministic id-ASC order) and give back its reserved
        quantity, then transition the reservation. Caller must already
        hold the reservation row lock. Does not commit.
        """
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
        for item in items:
            lot = lots[item.inventory_lot_id]
            lot.reserved_quantity = lot.reserved_quantity - item.quantity

        result = transition_reservation_status(
            ReservationStatus(reservation.status), target
        )
        if result.applied:
            reservation.status = target
            reservation.released_at = now
            reservation.updated_at = now
            if target == ReservationStatus.EXPIRED:
                logger.info(
                    "INVENTORY_RESERVATION_EXPIRED: reservation_id=%s order_id=%s",
                    reservation.id, reservation.order_id,
                )

    # ------------------------------------------------------------------
    # Reads (schema-returning - matches the rest of this codebase's
    # services, which never hand raw ORM rows back to a route)
    # ------------------------------------------------------------------

    def _get_and_maybe_lazy_expire(self, reservation: InventoryReservation) -> InventoryReservation:
        """Any read of an ACTIVE-but-overdue reservation self-corrects it
        before returning, per the "no dependence on a background worker"
        requirement - a GET is itself a relevant touch.
        """
        if (
            ReservationStatus(reservation.status) == ReservationStatus.ACTIVE
            and reservation.expires_at <= datetime.now(UTC)
        ):
            reservation = self.expire_reservation_for_order(
                reservation.order_id, now=datetime.now(UTC)
            )
            self.db.commit()
            self.db.refresh(reservation)
        return reservation

    def get_reservation_response_for_order(
        self, order_id: int
    ) -> InventoryReservationResponse:
        reservation = (
            self.db.query(InventoryReservation)
            .filter(InventoryReservation.order_id == order_id)
            .first()
        )
        if reservation is None:
            raise NotFoundError("Reservation not found for this order.")
        reservation = self._get_and_maybe_lazy_expire(reservation)
        return InventoryReservationResponse.model_validate(reservation)

    def get_reservation_detail_response(
        self, reservation_id: int
    ) -> InventoryReservationDetailResponse:
        reservation = (
            self.db.query(InventoryReservation)
            .filter(InventoryReservation.id == reservation_id)
            .first()
        )
        if reservation is None:
            raise NotFoundError("Reservation not found.")
        reservation = self._get_and_maybe_lazy_expire(reservation)
        items = (
            self.db.query(InventoryReservationItem)
            .filter(InventoryReservationItem.reservation_id == reservation.id)
            .order_by(InventoryReservationItem.id.asc())
            .all()
        )
        return InventoryReservationDetailResponse(
            **InventoryReservationResponse.model_validate(reservation).model_dump(),
            items=[
                InventoryReservationItemResponse.model_validate(i) for i in items
            ],
        )

    def list_reservations_response(
        self, status: str | None, page: int, page_size: int
    ) -> InventoryReservationListResponse:
        query = self.db.query(InventoryReservation)
        if status is not None:
            query = query.filter(InventoryReservation.status == status)
        total = query.count()
        items = (
            query.order_by(InventoryReservation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return InventoryReservationListResponse(
            items=[InventoryReservationResponse.model_validate(r) for r in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def expire_reservation_response(
        self, reservation_id: int
    ) -> InventoryReservationResponse:
        """Explicit ops-triggered expiry (POST /inventory/reservations/{id}/expire).
        Idempotent - calling this on an already-terminal reservation just
        returns its current state.
        """
        existing = (
            self.db.query(InventoryReservation)
            .filter(InventoryReservation.id == reservation_id)
            .first()
        )
        if existing is None:
            raise NotFoundError("Reservation not found.")
        reservation = self.expire_reservation_for_order(
            existing.order_id, now=datetime.now(UTC)
        )
        self.db.commit()
        self.db.refresh(reservation)
        return InventoryReservationResponse.model_validate(reservation)

    # ------------------------------------------------------------------
    # Locking helpers
    # ------------------------------------------------------------------

    def _lock_reservation_by_order_id(self, order_id: int) -> InventoryReservation | None:
        """Locks unconditionally on order_id (no status filter) - same
        retry-safety pattern as OrderService.checkout's cart lock and
        PaymentService's payment/order locks: a status-filtered FOR UPDATE
        would silently exclude the row once a concurrent transaction
        changes its status, per PostgreSQL's WHERE-clause re-evaluation on
        an unblocked lock wait.

        `.populate_existing()` is unconditional here (not just when a
        caller happens to have read this row before) because several
        callers in this class DO read a reservation unlocked before
        eventually reaching this method in the same session
        (`expire_reservation_response`'s id->order_id lookup,
        `_get_and_maybe_lazy_expire`'s callers) - exactly the Phase 14
        stale-identity-map pattern: without it, this locked re-query can
        hand back the same already-mapped Python object with its
        pre-lock (possibly now-stale) attributes instead of the fresh,
        just-locked row, even though the SQL-level lock was acquired
        correctly. Always forcing a refresh here is unconditionally safe.
        """
        return (
            self.db.query(InventoryReservation)
            .filter(InventoryReservation.order_id == order_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
