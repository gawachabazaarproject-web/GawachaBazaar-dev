"""Delivery partner assignments: the partner-facing workflow on top of the
existing fulfillment pipeline.

    admin assigns   ->  ASSIGNED   (fulfillment ASSIGNED)
    partner accepts ->  ACCEPTED
    partner picks up->  PICKED_UP
    partner departs ->  OUT_FOR_DELIVERY  (fulfillment OUT_FOR_DELIVERY)
    partner delivers->  DELIVERED          (fulfillment DELIVERED, order COMPLETED,
                                            stock consumed, COD collected - atomic,
                                            in FulfillmentService.confirm_delivery)
    partner fails   ->  FAILED             (fulfillment back to READY_FOR_DELIVERY)
    partner rejects ->  REJECTED           (only before accepting; back to READY)
    admin reassigns / order cancelled -> CANCELLED (history kept, new row for the next try)

LOCK ORDER (same as the rest of the codebase): Order -> Fulfillment ->
Assignment (-> Payment). Never a gateway call while a lock is held (there is none).

Authorization is data-dependent and lives here: a partner only ever sees or
touches rows where partner_user_id is theirs (anything else is a 404, the same
"don't disclose existence" rule used for customers). The router adds the role gate.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from urllib.parse import quote

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.realtime import notify_status_event
from app.exceptions.base import (
    AuthorizationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from app.models.delivery_partner import (
    ACTIVE_ASSIGNMENT_STATUSES,
    DeliveryAssignment,
    DeliveryPartnerEarning,
    DeliveryPartnerLocation,
    DeliveryPartnerProfile,
)
from app.models.fulfillment import Fulfillment
from app.models.order import Order
from app.models.order_address import OrderAddress
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.delivery_partner import (
    ActiveDeliveryItem,
    AdminEarningsSummaryItem,
    AdminPartnerListResponse,
    AssignmentAddress,
    AssignmentItem,
    AssignmentListResponse,
    AssignmentResponse,
    CodListResponse,
    CodSummaryItem,
    CustomerTrackingResponse,
    EarningItem,
    EarningsResponse,
    PartnerMeResponse,
    PartnerProfileResponse,
)
from app.services.admin_audit import AdminAuditService
from app.services.delivery_pricing import PricingRules, billable_km_for_distance
from app.services.fulfillment_state import (
    FulfillmentStatus,
    IllegalFulfillmentTransitionError,
    reopen_for_dispatch,
)
from app.services.payment_state import PaymentStatus

DELIVERY_PARTNER = "DELIVERY_PARTNER"
_ACTIVE = ACTIVE_ASSIGNMENT_STATUSES

# action -> (statuses it may start from, status it moves to)
_TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "accept": (("ASSIGNED",), "ACCEPTED"),
    "pickup": (("ACCEPTED",), "PICKED_UP"),
    "out_for_delivery": (("PICKED_UP",), "OUT_FOR_DELIVERY"),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance, used ONLY to reject impossible GPS jumps - never for pricing."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


class DeliveryAssignmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def _has_partner_role(self, user_id: int) -> bool:
        return (
            self.db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id, Role.name == DELIVERY_PARTNER)
            .first()
            is not None
        )

    def ensure_profile(self, user_id: int) -> DeliveryPartnerProfile:
        """The profile of a DELIVERY_PARTNER user; created ACTIVE/OFFLINE on first
        use (accounts that held the role before profiles existed). Caller commits."""
        profile = (
            self.db.query(DeliveryPartnerProfile)
            .filter(DeliveryPartnerProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = DeliveryPartnerProfile(user_id=user_id, status="ACTIVE", availability="OFFLINE")
            self.db.add(profile)
            self.db.flush()
        return profile

    def _active_count(self, partner_user_id: int) -> int:
        return (
            self.db.query(func.count(DeliveryAssignment.id))
            .filter(
                DeliveryAssignment.partner_user_id == partner_user_id,
                DeliveryAssignment.status.in_(_ACTIVE),
            )
            .scalar()
        )

    def _refresh_availability(self, partner_user_id: int) -> None:
        profile = self.ensure_profile(partner_user_id)
        self.db.flush()
        active = self._active_count(partner_user_id)
        if active > 0:
            profile.availability = "ON_DELIVERY"
        elif profile.availability == "ON_DELIVERY":
            profile.availability = "AVAILABLE"

    def _require_active_partner(self, user_id: int) -> DeliveryPartnerProfile:
        profile = self.ensure_profile(user_id)
        if profile.status != "ACTIVE":
            raise AuthorizationError("Your delivery partner account is not active.")
        return profile

    # ------------------------------------------------------------------
    # Creation / closing (called inside the fulfillment transaction)
    # ------------------------------------------------------------------

    def create_for_assignment(
        self, order: Order, fulfillment: Fulfillment, partner_user_id: int, assigned_by: int | None
    ) -> DeliveryAssignment:
        profile = self.ensure_profile(partner_user_id)
        if profile.status != "ACTIVE":
            raise ConflictError("The delivery partner's account is not active.")
        payment = self.db.query(Payment).filter(Payment.order_id == order.id).first()
        cod_pending = (
            payment is not None
            and payment.payment_method == "COD"
            and payment.status != PaymentStatus.PAID
        )
        assignment = DeliveryAssignment(
            order_id=order.id,
            fulfillment_id=fulfillment.id,
            partner_user_id=partner_user_id,
            assigned_by_user_id=assigned_by,
            status="ASSIGNED",
            cod_status="COD_PENDING" if cod_pending else "NOT_APPLICABLE",
            # The expected cash is copied from the payment by the server, never typed by anyone.
            cod_expected_amount=payment.amount if cod_pending else Decimal("0"),
        )
        try:
            with self.db.begin_nested():
                self.db.add(assignment)
                self.db.flush()
        except IntegrityError as exc:
            raise ConflictError("This order already has an active delivery assignment.") from exc
        return assignment

    def close_active_for_order(
        self, order_id: int, status: str, reason: str
    ) -> DeliveryAssignment | None:
        """Close the order's active assignment (reassign / cancellation). Caller
        holds the order+fulfillment locks and commits."""
        assignment = (
            self.db.query(DeliveryAssignment)
            .filter(DeliveryAssignment.order_id == order_id, DeliveryAssignment.status.in_(_ACTIVE))
            .populate_existing()
            .with_for_update()
            .first()
        )
        if assignment is None:
            return None
        now = datetime.now(UTC)
        assignment.status = status
        assignment.closed_at = now
        assignment.close_reason = reason[:300]
        if assignment.cod_status == "COD_PENDING":
            assignment.cod_status = "NOT_APPLICABLE"
        self.db.query(DeliveryPartnerLocation).filter(
            DeliveryPartnerLocation.assignment_id == assignment.id
        ).delete()
        self.db.flush()
        self._invalidate_otp(order_id, "REASSIGNED" if status == "REASSIGNED" else "ORDER_CANCELLED")
        self._refresh_availability(assignment.partner_user_id)
        return assignment

    def _invalidate_otp(self, order_id: int, reason: str) -> None:
        from app.services.delivery_otp import DeliveryOtpService

        DeliveryOtpService(self.db).invalidate_for_order(order_id, reason)

    def close_for_cancelled_order(self, order_id: int) -> None:
        self.close_active_for_order(order_id, "CANCELLED", "Order cancelled")

    # ------------------------------------------------------------------
    # Locking
    # ------------------------------------------------------------------

    def _lock_for_partner(
        self, assignment_id: int, user: User
    ) -> tuple[Order, Fulfillment, DeliveryAssignment]:
        probe = (
            self.db.query(DeliveryAssignment).filter(DeliveryAssignment.id == assignment_id).first()
        )
        if probe is None or probe.partner_user_id != user.id:
            raise NotFoundError("Delivery assignment not found.")
        order = (
            self.db.query(Order)
            .filter(Order.id == probe.order_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        fulfillment = (
            self.db.query(Fulfillment)
            .filter(Fulfillment.id == probe.fulfillment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        assignment = (
            self.db.query(DeliveryAssignment)
            .filter(DeliveryAssignment.id == assignment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if assignment is None or assignment.partner_user_id != user.id:
            # Reassigned between the probe and the lock.
            self.db.rollback()
            raise NotFoundError("Delivery assignment not found.")
        return order, fulfillment, assignment

    @staticmethod
    def _require_open(order: Order, assignment: DeliveryAssignment) -> None:
        if assignment.status not in _ACTIVE:
            raise ConflictError(f"This delivery is already {assignment.status}.")
        if order.status != "CONFIRMED":
            raise ConflictError(f"The order is {order.status}; this delivery cannot continue.")

    # ------------------------------------------------------------------
    # Partner actions
    # ------------------------------------------------------------------

    def _step(self, action: str, assignment_id: int, user: User) -> AssignmentResponse:
        allowed_from, target = _TRANSITIONS[action]
        order, fulfillment, assignment = self._lock_for_partner(assignment_id, user)
        self._require_open(order, assignment)
        self._require_active_partner(user.id)
        if assignment.status != allowed_from[0]:
            raise ConflictError(f"Cannot {action.replace('_', ' ')} from status {assignment.status}.")

        now = datetime.now(UTC)
        previous_fulfillment = fulfillment.status
        assignment.status = target
        if action == "accept":
            assignment.accepted_at = now
        elif action == "pickup":
            assignment.picked_up_at = now
        else:
            assignment.out_for_delivery_at = now
            if fulfillment.status == FulfillmentStatus.ASSIGNED:
                fulfillment.status = FulfillmentStatus.OUT_FOR_DELIVERY
        self._refresh_availability(user.id)
        self._commit("Could not update the delivery due to a conflicting update.")
        logger.info(
            "DELIVERY_ASSIGNMENT_%s: assignment_id=%s partner=%s", action.upper(), assignment.id, user.id
        )
        if fulfillment.status != previous_fulfillment:
            notify_status_event(
                resource="fulfillment",
                order_id=order.id,
                user_id=order.user_id,
                new_status=fulfillment.status,
                previous_status=previous_fulfillment,
            )
        return self._to_response(assignment, for_partner=True)

    def accept(self, assignment_id: int, user: User) -> AssignmentResponse:
        return self._step("accept", assignment_id, user)

    def pickup(self, assignment_id: int, user: User) -> AssignmentResponse:
        return self._step("pickup", assignment_id, user)

    def out_for_delivery(self, assignment_id: int, user: User) -> AssignmentResponse:
        return self._step("out_for_delivery", assignment_id, user)

    def reject(self, assignment_id: int, user: User, reason: str) -> AssignmentResponse:
        order, fulfillment, assignment = self._lock_for_partner(assignment_id, user)
        self._require_open(order, assignment)
        if assignment.status != "ASSIGNED":
            raise ConflictError("Only a delivery you have not accepted yet can be declined.")
        now = datetime.now(UTC)
        assignment.status = "REJECTED"
        assignment.closed_at = now
        assignment.close_reason = reason
        if assignment.cod_status == "COD_PENDING":
            assignment.cod_status = "NOT_APPLICABLE"
        self._release_fulfillment(fulfillment)
        self.db.flush()
        self._refresh_availability(user.id)
        self._commit("Could not decline the delivery due to a conflicting update.")
        notify_status_event(
            resource="fulfillment", order_id=order.id, user_id=order.user_id,
            new_status=FulfillmentStatus.READY_FOR_DELIVERY.value,
            previous_status=FulfillmentStatus.ASSIGNED.value,
        )
        return self._to_response(assignment, for_partner=True)

    def fail(self, assignment_id: int, user: User, reason: str) -> AssignmentResponse:
        order, fulfillment, assignment = self._lock_for_partner(assignment_id, user)
        self._require_open(order, assignment)
        if assignment.status not in ("PICKED_UP", "OUT_FOR_DELIVERY"):
            raise ConflictError(
                "A delivery can only be marked failed after pickup. Decline it instead if you "
                "have not picked it up."
            )
        previous_fulfillment = fulfillment.status
        now = datetime.now(UTC)
        assignment.status = "FAILED"
        assignment.failed_at = now
        assignment.closed_at = now
        assignment.close_reason = reason
        # Nothing was collected: the cash state is explicit, not left PENDING.
        if assignment.cod_status == "COD_PENDING":
            assignment.cod_status = "COD_FAILED"
        self._release_fulfillment(fulfillment)
        self.db.query(DeliveryPartnerLocation).filter(
            DeliveryPartnerLocation.assignment_id == assignment.id
        ).delete()
        self.db.flush()
        self._invalidate_otp(order.id, "DELIVERY_FAILED")
        self._refresh_availability(user.id)
        self._commit("Could not update the delivery due to a conflicting update.")
        logger.info("DELIVERY_ASSIGNMENT_FAILED: assignment_id=%s partner=%s", assignment.id, user.id)
        notify_status_event(
            resource="fulfillment", order_id=order.id, user_id=order.user_id,
            new_status=FulfillmentStatus.READY_FOR_DELIVERY.value, previous_status=previous_fulfillment,
        )
        return self._to_response(assignment, for_partner=True)

    @staticmethod
    def _release_fulfillment(fulfillment: Fulfillment) -> None:
        try:
            fulfillment.status = reopen_for_dispatch(FulfillmentStatus(fulfillment.status))
        except IllegalFulfillmentTransitionError as exc:
            raise ConflictError(
                f"Cannot release a fulfillment in status {exc.current.value}."
            ) from exc
        fulfillment.delivery_partner_user_id = None
        fulfillment.assigned_at = None

    def deliver(
        self,
        assignment_id: int,
        user: User,
        cod_collected_amount: Decimal | None,
        otp: str | None = None,
    ) -> AssignmentResponse:
        """Delegates to the one atomic delivery transaction (stock, order, COD,
        assignment, earnings) in FulfillmentService.confirm_delivery."""
        from app.services.fulfillment import FulfillmentService

        probe = (
            self.db.query(DeliveryAssignment).filter(DeliveryAssignment.id == assignment_id).first()
        )
        if probe is None or probe.partner_user_id != user.id:
            raise NotFoundError("Delivery assignment not found.")
        self._require_active_partner(user.id)
        FulfillmentService(self.db).confirm_delivery(
            probe.fulfillment_id,
            user,
            assignment_id=assignment_id,
            cod_collected_amount=cod_collected_amount,
            strict=True,
            otp=otp,
        )
        self.db.expire_all()
        assignment = self.db.query(DeliveryAssignment).filter_by(id=assignment_id).one()
        return self._to_response(assignment, for_partner=True)

    # ---- called by confirm_delivery, inside its transaction ----

    def settle_delivered(
        self,
        order: Order,
        assignment: DeliveryAssignment,
        payment: Payment | None,
        cod_collected_amount: Decimal | None,
        strict: bool,
    ) -> None:
        """Mark the assignment DELIVERED, record COD and write the partner's
        earning. Caller holds the Order/Fulfillment/Assignment/Payment locks and commits."""
        if strict and assignment.status != "OUT_FOR_DELIVERY":
            raise ConflictError(f"Cannot deliver from status {assignment.status}.")
        now = datetime.now(UTC)
        cod_due = (
            payment is not None
            and payment.payment_method == "COD"
            and payment.status != PaymentStatus.PAID
        )
        if cod_due:
            expected = Decimal(payment.amount)
            if cod_collected_amount is None and strict:
                raise BusinessValidationError(
                    f"Enter the cash you collected (expected {expected:f})."
                )
            if cod_collected_amount is not None and Decimal(cod_collected_amount) != expected:
                raise BusinessValidationError(
                    "The cash amount does not match the amount due for this order. "
                    "Partial or excess payments cannot be recorded."
                )
            assignment.cod_status = "COD_COLLECTED"
            assignment.cod_expected_amount = expected
            assignment.cod_collected_amount = expected
            assignment.cod_collected_at = now
        assignment.status = "DELIVERED"
        assignment.delivered_at = now
        assignment.closed_at = now
        if assignment.accepted_at is None:  # legacy fast path
            assignment.accepted_at = now
        self.db.query(DeliveryPartnerLocation).filter(
            DeliveryPartnerLocation.assignment_id == assignment.id
        ).delete()
        self.db.flush()
        self._record_earning(order, assignment, cod=cod_due)
        self._refresh_availability(assignment.partner_user_id)

    def _record_earning(self, order: Order, assignment: DeliveryAssignment, cod: bool) -> None:
        if order.delivery_billable_km is not None:
            km = order.delivery_billable_km
        elif order.delivery_distance_meters is not None:
            km = billable_km_for_distance(order.delivery_distance_meters, PricingRules.from_settings())
        else:
            km = 0
        base = settings.PARTNER_EARNING_BASE
        per_km = settings.PARTNER_EARNING_PER_KM * km
        bonus = settings.PARTNER_EARNING_COD_BONUS if cod else Decimal("0")
        self.db.add(
            DeliveryPartnerEarning(
                assignment_id=assignment.id,
                partner_user_id=assignment.partner_user_id,
                order_id=order.id,
                entry_type="EARNING",
                amount=base + per_km + bonus,
                rule_version=settings.PARTNER_EARNING_RULE_VERSION,
                base_amount=base,
                per_km_amount=per_km,
                billable_km=km,
                cod_bonus=bonus,
            )
        )
        self.db.flush()

    # ------------------------------------------------------------------
    # Location
    # ------------------------------------------------------------------

    def update_location(
        self, assignment_id: int, user: User, lat: float, lng: float, accuracy: float | None
    ) -> None:
        assignment = (
            self.db.query(DeliveryAssignment)
            .filter(DeliveryAssignment.id == assignment_id, DeliveryAssignment.partner_user_id == user.id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if assignment is None:
            raise NotFoundError("Delivery assignment not found.")
        if assignment.status not in ("PICKED_UP", "OUT_FOR_DELIVERY"):
            raise ConflictError("Location can only be shared during an active delivery.")
        self._require_active_partner(user.id)
        now = datetime.now(UTC)
        loc = (
            self.db.query(DeliveryPartnerLocation)
            .filter(DeliveryPartnerLocation.assignment_id == assignment.id)
            .first()
        )
        if loc is not None:
            elapsed = (now - loc.updated_at).total_seconds()
            if elapsed < settings.PARTNER_LOCATION_MIN_INTERVAL_SECONDS:
                self.db.rollback()
                raise RateLimitError("Location updates are too frequent.")
            km = _haversine_km(loc.latitude, loc.longitude, lat, lng)
            if elapsed > 0 and km / (elapsed / 3600) > settings.PARTNER_LOCATION_MAX_SPEED_KMH and km > 0.2:
                self.db.rollback()
                raise BusinessValidationError("That location is not plausible. Check your GPS.")
            loc.latitude, loc.longitude, loc.accuracy_m, loc.updated_at = lat, lng, accuracy, now
        else:
            self.db.add(
                DeliveryPartnerLocation(
                    assignment_id=assignment.id,
                    partner_user_id=user.id,
                    latitude=lat,
                    longitude=lng,
                    accuracy_m=accuracy,
                    updated_at=now,
                )
            )
        self._commit("Could not save the location.")

    def customer_tracking(self, order_id: int, customer_user_id: int) -> CustomerTrackingResponse:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.user_id == customer_user_id)
            .first()
        )
        if order is None:
            raise NotFoundError("Order not found.")
        assignment = (
            self.db.query(DeliveryAssignment)
            .filter(
                DeliveryAssignment.order_id == order.id,
                DeliveryAssignment.status.in_(("PICKED_UP", "OUT_FOR_DELIVERY")),
            )
            .first()
        )
        if assignment is None or order.status != "CONFIRMED":
            return CustomerTrackingResponse(tracking_available=False)
        partner = self.db.query(User).filter(User.id == assignment.partner_user_id).first()
        profile = self.ensure_profile(assignment.partner_user_id)
        loc = (
            self.db.query(DeliveryPartnerLocation)
            .filter(DeliveryPartnerLocation.assignment_id == assignment.id)
            .first()
        )
        fresh = loc is not None and loc.updated_at > datetime.now(UTC) - timedelta(
            seconds=settings.PARTNER_LOCATION_STALE_SECONDS
        )
        return CustomerTrackingResponse(
            tracking_available=True,
            status=assignment.status,
            partner_first_name=((partner.name or "").split() or [None])[0] if partner else None,
            vehicle_type=profile.vehicle_type,
            latitude=loc.latitude if fresh else None,
            longitude=loc.longitude if fresh else None,
            location_updated_at=loc.updated_at if fresh else None,
        )

    # ------------------------------------------------------------------
    # Partner reads
    # ------------------------------------------------------------------

    def me(self, user: User) -> PartnerMeResponse:
        profile = self.ensure_profile(user.id)
        self.db.commit()
        start = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
        delivered_today = (
            self.db.query(func.count(DeliveryAssignment.id))
            .filter(
                DeliveryAssignment.partner_user_id == user.id,
                DeliveryAssignment.status == "DELIVERED",
                DeliveryAssignment.delivered_at >= start,
            )
            .scalar()
        )
        earned_today = (
            self.db.query(func.coalesce(func.sum(DeliveryPartnerEarning.amount), 0))
            .filter(
                DeliveryPartnerEarning.partner_user_id == user.id,
                DeliveryPartnerEarning.created_at >= start,
            )
            .scalar()
        )
        base = self._profile_response(profile, user.name).model_dump()
        return PartnerMeResponse(
            **base,
            active_assignments=self._active_count(user.id),
            delivered_today=delivered_today,
            earned_today=Decimal(earned_today),
        )

    def set_availability(self, user: User, availability: str) -> PartnerMeResponse:
        profile = (
            self.db.query(DeliveryPartnerProfile)
            .filter(DeliveryPartnerProfile.user_id == user.id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if profile is None:
            profile = self.ensure_profile(user.id)
        if profile.status != "ACTIVE":
            raise AuthorizationError("Your delivery partner account is not active.")
        if availability == "OFFLINE" and self._active_count(user.id) > 0:
            raise ConflictError("Finish or hand back your active deliveries before going offline.")
        profile.availability = availability if self._active_count(user.id) == 0 else "ON_DELIVERY"
        self._commit("Could not update availability.")
        return self.me(user)

    def list_for_partner(
        self, user: User, scope: str, status: str | None, date_from: date | None,
        date_to: date | None, page: int, page_size: int,
    ) -> AssignmentListResponse:
        q = self.db.query(DeliveryAssignment).filter(DeliveryAssignment.partner_user_id == user.id)
        if scope == "active":
            q = q.filter(DeliveryAssignment.status.in_(_ACTIVE))
        else:
            q = q.filter(~DeliveryAssignment.status.in_(_ACTIVE))
        if status:
            q = q.filter(DeliveryAssignment.status == status)
        if date_from:
            q = q.filter(DeliveryAssignment.assigned_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC))
        if date_to:
            q = q.filter(
                DeliveryAssignment.assigned_at
                < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
            )
        total = q.count()
        rows = (
            q.order_by(DeliveryAssignment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )
        return AssignmentListResponse(
            items=[self._to_response(r, for_partner=True) for r in rows],
            total=total, page=page, page_size=page_size,
        )

    def get_for_partner(self, assignment_id: int, user: User) -> AssignmentResponse:
        row = (
            self.db.query(DeliveryAssignment)
            .filter(DeliveryAssignment.id == assignment_id, DeliveryAssignment.partner_user_id == user.id)
            .first()
        )
        if row is None:
            raise NotFoundError("Delivery assignment not found.")
        return self._to_response(row, for_partner=True)

    def earnings(
        self, user: User, date_from: date | None, date_to: date | None, page: int, page_size: int
    ) -> EarningsResponse:
        q = self.db.query(DeliveryPartnerEarning).filter(DeliveryPartnerEarning.partner_user_id == user.id)
        if date_from:
            q = q.filter(DeliveryPartnerEarning.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC))
        if date_to:
            q = q.filter(
                DeliveryPartnerEarning.created_at
                < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
            )
        total = q.with_entities(func.coalesce(func.sum(DeliveryPartnerEarning.amount), 0)).scalar()
        count = q.count()
        rows = (
            q.order_by(DeliveryPartnerEarning.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )
        return EarningsResponse(
            total=Decimal(total), count=count,
            items=[EarningItem.model_validate(r) for r in rows], page=page, page_size=page_size,
        )

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def admin_create_partner(
        self, admin_user_id: int, user_id: int, vehicle_type: str, vehicle_number: str | None,
        phone: str | None,
    ) -> PartnerProfileResponse:
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise NotFoundError("User not found.")
        if not self._has_partner_role(user_id):
            raise BusinessValidationError("The user must hold the DELIVERY_PARTNER role first.")
        existing = (
            self.db.query(DeliveryPartnerProfile).filter(DeliveryPartnerProfile.user_id == user_id).first()
        )
        if existing is not None:
            raise ConflictError("This user already has a delivery partner profile.")
        profile = DeliveryPartnerProfile(
            user_id=user_id, status="ACTIVE", availability="OFFLINE", vehicle_type=vehicle_type,
            vehicle_number=vehicle_number, phone=phone,
        )
        self.db.add(profile)
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id, action="delivery_partner.create",
            resource_type="delivery_partner", resource_id=user_id, new_state="ACTIVE",
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("This user already has a delivery partner profile.") from exc
        self.db.refresh(profile)
        return self._profile_response(profile, user.name)

    def admin_update_partner(
        self, admin_user_id: int, user_id: int, changes: dict
    ) -> PartnerProfileResponse:
        profile = (
            self.db.query(DeliveryPartnerProfile)
            .filter(DeliveryPartnerProfile.user_id == user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if profile is None:
            raise NotFoundError("Delivery partner not found.")
        previous = profile.status
        new_status = changes.get("status")
        if new_status in ("INACTIVE", "SUSPENDED") and self._active_count(user_id) > 0:
            raise ConflictError(
                "Reassign this partner's active deliveries before deactivating or suspending them."
            )
        for key in ("status", "vehicle_type", "vehicle_number", "phone"):
            if key in changes and changes[key] is not None:
                setattr(profile, key, changes[key])
        if new_status in ("INACTIVE", "SUSPENDED"):
            profile.availability = "OFFLINE"
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id, action="delivery_partner.update",
            resource_type="delivery_partner", resource_id=user_id,
            previous_state=previous, new_state=profile.status,
        )
        self._commit("Could not update the partner due to a conflicting update.")
        user = self.db.query(User).filter(User.id == user_id).first()
        return self._profile_response(profile, user.name if user else None)

    def admin_list_partners(
        self, status: str | None, availability: str | None, page: int, page_size: int
    ) -> AdminPartnerListResponse:
        q = self.db.query(DeliveryPartnerProfile, User.name).join(
            User, User.id == DeliveryPartnerProfile.user_id
        )
        if status:
            q = q.filter(DeliveryPartnerProfile.status == status)
        if availability:
            q = q.filter(DeliveryPartnerProfile.availability == availability)
        total = q.count()
        rows = q.order_by(DeliveryPartnerProfile.id).offset((page - 1) * page_size).limit(page_size).all()
        return AdminPartnerListResponse(
            items=[self._profile_response(p, name) for p, name in rows],
            total=total, page=page, page_size=page_size,
        )

    def admin_list_assignments(
        self, status: str | None, partner_user_id: int | None, order_id: int | None,
        page: int, page_size: int,
    ) -> AssignmentListResponse:
        q = self.db.query(DeliveryAssignment)
        if status:
            q = q.filter(DeliveryAssignment.status == status)
        if partner_user_id:
            q = q.filter(DeliveryAssignment.partner_user_id == partner_user_id)
        if order_id:
            q = q.filter(DeliveryAssignment.order_id == order_id)
        total = q.count()
        rows = q.order_by(DeliveryAssignment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return AssignmentListResponse(
            items=[self._to_response(r, for_partner=False) for r in rows],
            total=total, page=page, page_size=page_size,
        )

    def admin_active_deliveries(self) -> list[ActiveDeliveryItem]:
        rows = (
            self.db.query(DeliveryAssignment, DeliveryPartnerLocation)
            .outerjoin(
                DeliveryPartnerLocation, DeliveryPartnerLocation.assignment_id == DeliveryAssignment.id
            )
            .filter(DeliveryAssignment.status.in_(_ACTIVE))
            .order_by(DeliveryAssignment.id)
            .limit(500)
            .all()
        )
        return [
            ActiveDeliveryItem(
                assignment_id=a.id, order_id=a.order_id, partner_user_id=a.partner_user_id,
                status=a.status,
                latitude=loc.latitude if loc else None, longitude=loc.longitude if loc else None,
                location_updated_at=loc.updated_at if loc else None,
            )
            for a, loc in rows
        ]

    def admin_cod_list(
        self, reconciled: bool | None, partner_user_id: int | None, page: int, page_size: int
    ) -> CodListResponse:
        q = self.db.query(DeliveryAssignment).filter(
            DeliveryAssignment.cod_status.in_(("COD_PENDING", "COD_COLLECTED", "COD_FAILED"))
        )
        if partner_user_id:
            q = q.filter(DeliveryAssignment.partner_user_id == partner_user_id)
        if reconciled is True:
            q = q.filter(DeliveryAssignment.cod_reconciled_at.isnot(None))
        elif reconciled is False:
            q = q.filter(DeliveryAssignment.cod_reconciled_at.is_(None))
        total = q.count()
        outstanding = (
            q.filter(
                DeliveryAssignment.cod_status == "COD_COLLECTED",
                DeliveryAssignment.cod_reconciled_at.is_(None),
            )
            .with_entities(func.coalesce(func.sum(DeliveryAssignment.cod_collected_amount), 0))
            .scalar()
        )
        rows = q.order_by(DeliveryAssignment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return CodListResponse(
            items=[
                CodSummaryItem(
                    assignment_id=a.id, order_id=a.order_id, partner_user_id=a.partner_user_id,
                    cod_status=a.cod_status, cod_expected_amount=a.cod_expected_amount,
                    cod_collected_amount=a.cod_collected_amount, cod_collected_at=a.cod_collected_at,
                    cod_reconciled_at=a.cod_reconciled_at,
                )
                for a in rows
            ],
            total=total, outstanding_amount=Decimal(outstanding), page=page, page_size=page_size,
        )

    def admin_cod_reconcile(self, assignment_id: int, admin_user_id: int, note: str | None) -> CodSummaryItem:
        a = (
            self.db.query(DeliveryAssignment)
            .filter(DeliveryAssignment.id == assignment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if a is None:
            raise NotFoundError("Delivery assignment not found.")
        if a.cod_status != "COD_COLLECTED":
            raise ConflictError("Only collected cash can be reconciled.")
        if a.cod_reconciled_at is not None:
            raise ConflictError("This cash has already been reconciled.")
        a.cod_reconciled_at = datetime.now(UTC)
        a.cod_reconciled_by_user_id = admin_user_id
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id, action="delivery.cod_reconcile",
            resource_type="delivery_assignment", resource_id=a.id,
            previous_state="COD_COLLECTED", new_state="RECONCILED", reason=note,
        )
        self._commit("Could not reconcile due to a conflicting update.")
        return CodSummaryItem(
            assignment_id=a.id, order_id=a.order_id, partner_user_id=a.partner_user_id,
            cod_status=a.cod_status, cod_expected_amount=a.cod_expected_amount,
            cod_collected_amount=a.cod_collected_amount, cod_collected_at=a.cod_collected_at,
            cod_reconciled_at=a.cod_reconciled_at,
        )

    def admin_earnings_summary(
        self, date_from: date | None, date_to: date | None
    ) -> list[AdminEarningsSummaryItem]:
        q = self.db.query(
            DeliveryPartnerEarning.partner_user_id,
            func.coalesce(func.sum(DeliveryPartnerEarning.amount), 0),
            func.count(DeliveryPartnerEarning.id),
        )
        if date_from:
            q = q.filter(DeliveryPartnerEarning.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC))
        if date_to:
            q = q.filter(
                DeliveryPartnerEarning.created_at
                < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
            )
        return [
            AdminEarningsSummaryItem(partner_user_id=pid, total=Decimal(total), deliveries=n)
            for pid, total, n in q.group_by(DeliveryPartnerEarning.partner_user_id).all()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _commit(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(message) from exc

    @staticmethod
    def _profile_response(profile: DeliveryPartnerProfile, name: str | None) -> PartnerProfileResponse:
        return PartnerProfileResponse(
            user_id=profile.user_id, name=name, status=profile.status,
            availability=profile.availability, vehicle_type=profile.vehicle_type,
            vehicle_number=profile.vehicle_number, phone=profile.phone,
        )

    def _to_response(self, a: DeliveryAssignment, *, for_partner: bool) -> AssignmentResponse:
        order = self.db.query(Order).filter(Order.id == a.order_id).first()
        addr = self.db.query(OrderAddress).filter(OrderAddress.order_id == a.order_id).first()
        customer = self.db.query(User).filter(User.id == order.user_id).first() if order else None
        items = self.db.query(OrderItem).filter(OrderItem.order_id == a.order_id).order_by(OrderItem.id).all()
        earning = (
            self.db.query(DeliveryPartnerEarning.amount)
            .filter(DeliveryPartnerEarning.assignment_id == a.id, DeliveryPartnerEarning.entry_type == "EARNING")
            .scalar()
        )
        maps_url = None
        address = None
        if addr is not None:
            address = AssignmentAddress(
                address_line_1=addr.address_line_1, address_line_2=addr.address_line_2, city=addr.city,
                state=addr.state, postal_code=addr.postal_code,
                latitude=float(addr.latitude) if addr.latitude is not None else None,
                longitude=float(addr.longitude) if addr.longitude is not None else None,
            )
            if addr.latitude is not None and addr.longitude is not None:
                maps_url = (
                    "https://www.google.com/maps/dir/?api=1&travelmode=driving&destination="
                    f"{float(addr.latitude)},{float(addr.longitude)}"
                )
            else:
                text = ", ".join(p for p in (addr.address_line_1, addr.city, addr.postal_code) if p)
                maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(text)}"
        # A partner sees the customer's name only while the job is theirs and open.
        show_customer = (not for_partner) or a.status in _ACTIVE
        from app.services.delivery_otp import DeliveryOtpService, require_for_delivery

        payment = self.db.query(Payment).filter(Payment.order_id == a.order_id).first()
        otp_required = require_for_delivery(payment) or (
            a.status == "DELIVERED"
            and DeliveryOtpService(self.db).status_for_order(a.order_id).status == "VERIFIED"
        )
        return AssignmentResponse(
            otp_required=otp_required,
            delivery_otp=DeliveryOtpService(self.db).status_for_order(a.order_id),
            id=a.id, order_id=a.order_id, order_number=order.order_number if order else "",
            fulfillment_id=a.fulfillment_id, partner_user_id=a.partner_user_id, status=a.status,
            assigned_at=a.assigned_at, accepted_at=a.accepted_at, picked_up_at=a.picked_up_at,
            out_for_delivery_at=a.out_for_delivery_at, delivered_at=a.delivered_at,
            failed_at=a.failed_at, closed_at=a.closed_at, close_reason=a.close_reason,
            cod_status=a.cod_status, cod_expected_amount=a.cod_expected_amount,
            cod_collected_amount=a.cod_collected_amount, cod_collected_at=a.cod_collected_at,
            customer_name=(customer.name if customer and show_customer else None),
            address=address if show_customer else None,
            items=[
                AssignmentItem(name=f"{i.product_name} {i.variant_name}".strip(), quantity=i.quantity, unit=i.unit)
                for i in items
            ],
            maps_url=maps_url if show_customer else None,
            earning_amount=Decimal(earning) if earning is not None else None,
        )
