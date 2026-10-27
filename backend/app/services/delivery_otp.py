"""COD delivery OTP: generate, show to the owning customer, verify for the partner.

Where things live
-----------------
* generation  - `DeliveryOtpService.send_for_assignment` (partner taps "I have arrived,
  send OTP" while OUT_FOR_DELIVERY). It is not issued at checkout or at departure on
  purpose: a code lives `DELIVERY_OTP_EXPIRY_MINUTES` (10), so it must be created
  when the partner is at the door, not when they leave the hub.
* retrieval   - `DeliveryOtpService.customer_view` (owner only, plaintext only while ACTIVE).
* verification - `DeliveryOtpService.verify_for_delivery`, called from
  `FulfillmentService.confirm_delivery` INSIDE its single atomic transaction, so
  "code verified", COD collected, order COMPLETED and the partner's earning commit
  together or not at all. A wrong code commits only its attempt counter and then raises.

Rules: 6 digits from `secrets`; HMAC-SHA256 hash (server key) - never plaintext in
the DB or logs; one active code per order; expiry; per-code attempt limit; replay is
impossible (a verified row is final); resend is rate limited per order.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.exceptions.base import (
    AppException,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from app.models.delivery_otp import DeliveryOtp
from app.models.delivery_partner import DeliveryAssignment
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.schemas.delivery_partner import CustomerDeliveryOtpResponse, OtpStatusSummary
from app.services.payment_state import PaymentStatus
from app.services.push import notify_delivery_otp

_DEV_FALLBACK_SECRET = "dev-and-test-only-delivery-otp-secret-not-for-production"


class OtpError(AppException):
    """A delivery-OTP failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message=message, status_code=status_code, code=code)


def generate_code() -> str:
    """Six digits, leading zeros kept, from the OS CSPRNG (never `random`)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _secret() -> bytes:
    return (settings.DELIVERY_OTP_SECRET or _DEV_FALLBACK_SECRET).encode()


def hash_code(code: str, order_id: int, assignment_id: int) -> str:
    msg = f"{order_id}:{assignment_id}:{code}".encode()
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"fernet:" + _secret()).digest()))


def cod_is_due(payment: Payment | None) -> bool:
    return (
        payment is not None
        and payment.payment_method == "COD"
        and payment.status != PaymentStatus.PAID
    )


class DeliveryOtpService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _active(self, order_id: int, *, lock: bool = False) -> DeliveryOtp | None:
        q = (
            self.db.query(DeliveryOtp)
            .filter(
                DeliveryOtp.order_id == order_id,
                DeliveryOtp.verified_at.is_(None),
                DeliveryOtp.invalidated_at.is_(None),
            )
            .order_by(DeliveryOtp.id.desc())
        )
        if lock:
            q = q.populate_existing().with_for_update()
        return q.first()

    @staticmethod
    def _invalidate(row: DeliveryOtp, reason: str, now: datetime) -> None:
        row.invalidated_at = now
        row.invalidated_reason = reason
        row.otp_encrypted = None  # the readable copy never outlives the code

    def invalidate_for_order(self, order_id: int, reason: str) -> None:
        """Called (inside the caller's transaction) when the order/assignment ends."""
        row = self._active(order_id, lock=True)
        if row is not None:
            self._invalidate(row, reason, datetime.now(UTC))

    # ------------------------------------------------------------------
    # generation (partner at the door)
    # ------------------------------------------------------------------

    def _create(
        self, order: Order, assignment: DeliveryAssignment, now: datetime, user_id: int | None = None
    ) -> DeliveryOtp:
        previous = self._active(order.id, lock=True)
        if previous is not None:
            self._invalidate(previous, "REPLACED", now)
            self.db.flush()
        code = generate_code()
        row = DeliveryOtp(
            order_id=order.id,
            assignment_id=assignment.id,
            otp_hash=hash_code(code, order.id, assignment.id),
            otp_encrypted=_fernet().encrypt(code.encode()),
            expires_at=now + timedelta(minutes=settings.DELIVERY_OTP_EXPIRY_MINUTES),
            max_attempts=settings.DELIVERY_OTP_MAX_ATTEMPTS,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:  # two simultaneous sends for one order
            self.db.rollback()
            raise ConflictError("A delivery code is already being issued. Please retry.") from exc
        self.db.refresh(row)
        logger.info(
            "DELIVERY_OTP_GENERATED: order_id=%s assignment_id=%s partner=%s otp_id=%s",
            order.id, assignment.id, user_id, row.id,
        )
        # Best effort and after the commit: a push failure never affects the code.
        try:
            notify_delivery_otp(user_id=order.user_id, order_id=order.id, otp=code, otp_row_id=row.id)
            logger.info("DELIVERY_OTP_NOTIFICATION_ATTEMPTED: order_id=%s otp_id=%s", order.id, row.id)
        except Exception:  # noqa: BLE001
            logger.exception("DELIVERY_OTP_NOTIFICATION_FAILED: order_id=%s otp_id=%s", order.id, row.id)
        return row

    def send_for_assignment(self, assignment_id: int, user: User) -> OtpStatusSummary:
        """Issue a fresh code for the caller's own assignment and push it to the
        customer. Re-sending invalidates the previous code (rate limited). Every
        delivery needs a code (prepaid and COD alike)."""
        from app.services.delivery_assignment import DeliveryAssignmentService

        order, _fulfillment, assignment = DeliveryAssignmentService(self.db)._lock_for_partner(
            assignment_id, user
        )
        if assignment.status != "OUT_FOR_DELIVERY" or order.status != "CONFIRMED":
            raise OtpError(
                "ORDER_NOT_ELIGIBLE",
                "The delivery code can only be sent while the order is out for delivery.",
                409,
            )
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=settings.DELIVERY_OTP_RESEND_WINDOW_MINUTES)
        issued = self.db.scalar(
            select(func.count())
            .select_from(DeliveryOtp)
            .where(DeliveryOtp.order_id == order.id, DeliveryOtp.created_at >= window_start)
        )
        if issued >= settings.DELIVERY_OTP_RESEND_LIMIT:
            self.db.rollback()
            raise RateLimitError(
                "Too many delivery codes were requested for this order. Please wait a few minutes."
            )

        row = self._create(order, assignment, now, user_id=user.id)
        return self._summary(row, now)

    def issue_for_order(self, order_id: int) -> None:
        """Best effort, called right after an order goes OUT_FOR_DELIVERY: the customer
        gets the code without anyone tapping anything. Skips quietly when a live code
        already exists; never raises (the partner/admin can still resend)."""
        try:
            if not settings.DELIVERY_OTP_ENFORCED:
                return
            order = self.db.query(Order).filter(Order.id == order_id).first()
            assignment = (
                self.db.query(DeliveryAssignment)
                .filter(
                    DeliveryAssignment.order_id == order_id,
                    DeliveryAssignment.status == "OUT_FOR_DELIVERY",
                )
                .first()
            )
            if order is None or assignment is None or order.status != "CONFIRMED":
                return
            now = datetime.now(UTC)
            active = self._active(order_id)
            if active is not None and now < active.expires_at:
                return
            self._create(order, assignment, now)
        except Exception:  # noqa: BLE001
            self.db.rollback()
            logger.exception("DELIVERY_OTP_AUTO_ISSUE_FAILED: order_id=%s", order_id)

    # ------------------------------------------------------------------
    # customer view
    # ------------------------------------------------------------------

    def customer_view(self, order_id: int, customer_user_id: int) -> CustomerDeliveryOtpResponse:
        """Own order only (anything else is a 404). The code is returned only
        while it is ACTIVE; never to partners/admins (their routes do not call this)."""
        order = self.db.query(Order).filter(Order.id == order_id, Order.user_id == customer_user_id).first()
        if order is None:
            raise NotFoundError("Order not found.")
        now = datetime.now(UTC)
        if not settings.DELIVERY_OTP_ENFORCED:
            return CustomerDeliveryOtpResponse(required=False, status="NOT_REQUIRED")
        if order.status == "CANCELLED":
            return CustomerDeliveryOtpResponse(required=False, status="CANCELLED")
        if order.status == "COMPLETED":
            verified = (
                self.db.query(DeliveryOtp)
                .filter(DeliveryOtp.order_id == order.id, DeliveryOtp.verified_at.is_not(None))
                .first()
            )
            return CustomerDeliveryOtpResponse(
                required=False, status="VERIFIED" if verified else "COMPLETED"
            )
        row = self._active(order.id)
        if row is None:
            last = (
                self.db.query(DeliveryOtp)
                .filter(DeliveryOtp.order_id == order.id)
                .order_by(DeliveryOtp.id.desc())
                .first()
            )
            status = "WAITING" if last is None else ("LOCKED" if last.invalidated_reason == "ATTEMPTS" else "EXPIRED")
            return CustomerDeliveryOtpResponse(required=True, status=status)
        if now >= row.expires_at:
            return CustomerDeliveryOtpResponse(required=True, status="EXPIRED", expires_at=row.expires_at)
        code = None
        if row.otp_encrypted is not None:
            try:
                code = _fernet().decrypt(row.otp_encrypted).decode()
            except InvalidToken:  # key rotated: treat as unavailable, never crash
                logger.error("DELIVERY_OTP_DECRYPT_FAILED: otp_id=%s", row.id)
        return CustomerDeliveryOtpResponse(
            required=True,
            status="ACTIVE" if code else "WAITING",
            otp=code,
            expires_at=row.expires_at,
            seconds_left=max(0, int((row.expires_at - now).total_seconds())),
        )

    # ------------------------------------------------------------------
    # status for partner / admin (never the code)
    # ------------------------------------------------------------------

    def _summary(self, row: DeliveryOtp | None, now: datetime) -> OtpStatusSummary:
        if row is None:
            return OtpStatusSummary(status="NOT_GENERATED")
        if row.verified_at is not None:
            status = "VERIFIED"
        elif row.invalidated_at is not None:
            status = "LOCKED" if row.invalidated_reason == "ATTEMPTS" else "INVALIDATED"
        elif now >= row.expires_at:
            status = "EXPIRED"
        else:
            status = "ACTIVE"
        return OtpStatusSummary(
            status=status,
            generated_at=row.created_at,
            expires_at=row.expires_at,
            verified_at=row.verified_at,
            attempts_left=max(0, row.max_attempts - row.attempts),
        )

    def status_for_order(self, order_id: int) -> OtpStatusSummary:
        row = (
            self.db.query(DeliveryOtp)
            .filter(DeliveryOtp.order_id == order_id)
            .order_by(DeliveryOtp.id.desc())
            .first()
        )
        return self._summary(row, datetime.now(UTC))

    # ------------------------------------------------------------------
    # verification (inside confirm_delivery's transaction)
    # ------------------------------------------------------------------

    def verify_for_delivery(
        self, order: Order, assignment: DeliveryAssignment | None, supplied: str | None
    ) -> None:
        """Raise `OtpError` unless `supplied` is the order's ACTIVE, unexpired,
        unlocked code. On success mark it verified (the caller commits it with the
        delivery). On a wrong code commit ONLY the attempt counter, then raise."""
        if assignment is None:
            raise OtpError("DELIVERY_ASSIGNMENT_NOT_FOUND", "This order has no active delivery assignment.", 409)
        row = self._active(order.id, lock=True)
        if supplied is None or not supplied.isdigit() or len(supplied) != 6:
            raise OtpError("OTP_INVALID", "Enter the 6-digit delivery code from the customer.")
        if row is None:
            self.db.rollback()
            raise OtpError("OTP_NOT_FOUND", "No delivery code is active. Send a new code to the customer first.", 409)
        now = datetime.now(UTC)
        if row.assignment_id != assignment.id:
            self._invalidate(row, "REASSIGNED", now)
            self.db.commit()
            raise OtpError("OTP_NOT_FOUND", "No delivery code is active. Send a new code to the customer first.", 409)
        if now >= row.expires_at:
            self._invalidate(row, "EXPIRED", now)
            self.db.commit()
            logger.info("DELIVERY_OTP_EXPIRED: order_id=%s otp_id=%s", order.id, row.id)
            raise OtpError("OTP_EXPIRED", "The delivery code has expired. Send a new code to the customer.", 409)
        if row.attempts >= row.max_attempts:
            self._invalidate(row, "ATTEMPTS", now)
            self.db.commit()
            raise OtpError("OTP_ATTEMPTS_EXCEEDED", "Too many wrong attempts. Send a new code to the customer.", 429)

        expected = row.otp_hash
        if hmac.compare_digest(expected, hash_code(supplied, order.id, assignment.id)):
            row.verified_at = now
            row.otp_encrypted = None
            self.db.flush()
            logger.info("DELIVERY_OTP_VERIFIED: order_id=%s otp_id=%s", order.id, row.id)
            return
        row.attempts += 1
        locked = row.attempts >= row.max_attempts
        if locked:
            self._invalidate(row, "ATTEMPTS", now)
        self.db.commit()  # the failed attempt must survive the error response
        logger.warning(
            "DELIVERY_OTP_WRONG: order_id=%s otp_id=%s attempts=%s locked=%s", order.id, row.id, row.attempts, locked
        )
        if locked:
            raise OtpError("OTP_ATTEMPTS_EXCEEDED", "Too many wrong attempts. Send a new code to the customer.", 429)
        raise OtpError("OTP_INVALID", "That code is not correct. Please ask the customer to check it.")


def require_for_delivery(payment: Payment | None) -> bool:
    """True when completing this order's delivery needs a verified code: always
    (prepaid and COD), unless the rollout switch is off."""
    return settings.DELIVERY_OTP_ENFORCED
