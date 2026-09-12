"""Refund domain service: refund-eligibility creation, admin approval,
rejection, and gateway processing.

CORE RULE (Phase 18): a customer cancellation NEVER issues a refund by
itself. Cancelling only creates a `Refund` row in PENDING_APPROVAL (via
`create_refund_if_eligible`, called from OrderService.cancel_own_order /
admin_cancel_order and from PaymentService's late-payment-after-cancellation
path - see its call site for why both exist). Only an explicit ADMIN
approve + a separate explicit ADMIN process action ever moves money.

TRANSACTION DESIGN: `create_refund_if_eligible` never commits - it is
always called from inside another service's already-open transaction
(OrderService.cancel_order's single commit), exactly like
InventoryReservationService.create_reservation_for_order is called from
inside OrderService.checkout. Every other method here owns its own
commit, same autobegin rule as every other service in this codebase.

LOCK ORDERING: `refunds` sits downstream of `payments` in this phase's
chain (a refund always references an existing, already-resolved Payment).
`approve_refund`/`reject_refund`/`process_refund` lock only the single
`Refund` row - they never need to touch Order/Payment/Reservation, since
Phase 18 deliberately never mutates Payment.status for a refund (PAID
stays PAID - see refund_state.py and payment_state.py's own "PAID is
terminal" rule, which this phase does not touch).
"""

import secrets
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.exceptions.base import ConflictError, NotFoundError
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.refund import Refund
from app.schemas.refund import (
    AdminRefundListResponse,
    AdminRefundResponse,
    RefundResponse,
)
from app.services.payment_gateway import (
    GatewayConnectionError,
    GatewayError,
    GatewayRefundResult,
    GatewayRejectedError,
    GatewayTimeoutError,
    PaymentGateway,
)
from app.services.payment_state import PaymentStatus, TransactionStatus
from app.services.refund_state import (
    IllegalRefundTransitionError,
    RefundStatus,
    transition_refund_status,
)

_REFUND_TRANSACTION_TYPE = "REFUND"


class RefundService:
    def __init__(self, db: Session, gateway: PaymentGateway | None = None) -> None:
        self.db = db
        self.gateway = gateway

    # ------------------------------------------------------------------
    # Eligibility (called from inside another service's transaction)
    # ------------------------------------------------------------------

    def create_refund_if_eligible(
        self, order: Order, payment: Payment | None
    ) -> Refund | None:
        """Creates a PENDING_APPROVAL refund iff `payment` is an online
        (UPI) payment that has actually reached PAID. COD never creates a
        refund (nothing was collected). Idempotent on `order_id` UNIQUE -
        safe to call more than once for the same order (e.g. once from
        cancellation, once from a late-arriving payment-success event that
        resolves AFTER the order was already cancelled).

        Does not commit - caller owns the transaction boundary.
        """
        if payment is None or payment.payment_method != "UPI":
            return None
        if PaymentStatus(payment.status) != PaymentStatus.PAID:
            return None

        existing = (
            self.db.query(Refund).filter(Refund.order_id == order.id).first()
        )
        if existing is not None:
            return existing

        refund = Refund(
            order_id=order.id,
            payment_id=payment.id,
            status=RefundStatus.PENDING_APPROVAL,
            amount=payment.amount,
            currency=payment.currency,
            requested_at=datetime.now(UTC),
        )
        self.db.add(refund)
        self.db.flush()
        logger.info(
            "REFUND_ELIGIBILITY_CREATED: refund_id=%s order_id=%s payment_id=%s amount=%s %s",
            refund.id, order.id, payment.id, refund.amount, refund.currency,
        )
        return refund

    # ------------------------------------------------------------------
    # Customer-facing read
    # ------------------------------------------------------------------

    def get_refund_for_order(self, user_id: int, order_id: int) -> RefundResponse:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            raise NotFoundError("Order not found.")
        refund = self.db.query(Refund).filter(Refund.order_id == order.id).first()
        if refund is None:
            raise NotFoundError("No refund exists for this order.")
        return RefundResponse.model_validate(refund)

    # ------------------------------------------------------------------
    # Admin-facing
    # ------------------------------------------------------------------

    def admin_get_refund_or_404(self, refund_id: int) -> AdminRefundResponse:
        refund = self.db.query(Refund).filter(Refund.id == refund_id).first()
        if refund is None:
            raise NotFoundError("Refund not found.")
        return self._to_admin_response(refund)

    def admin_list_refunds(
        self, status: str | None, page: int, page_size: int
    ) -> AdminRefundListResponse:
        query = self.db.query(Refund)
        if status is not None:
            query = query.filter(Refund.status == status)
        total = query.count()
        items = (
            query.order_by(Refund.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return AdminRefundListResponse(
            items=[self._to_admin_response(r) for r in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def approve_refund(self, refund_id: int, admin_user_id: int) -> AdminRefundResponse:
        refund = self._lock_refund(refund_id)
        # Explicit unconditional check rather than relying on
        # `_apply_transition`'s generic same-state-is-a-no-op rule: a
        # second approve call on an already-APPROVED refund must not
        # silently re-stamp approved_by_user_id/approved_at with a
        # different admin - same reasoning as
        # FulfillmentService.assign_delivery_partner (Phase 16).
        if RefundStatus(refund.status) != RefundStatus.PENDING_APPROVAL:
            raise ConflictError(
                f"Cannot approve a refund in status {refund.status}."
            )
        self._apply_transition(refund, RefundStatus.APPROVED)
        refund.approved_by_user_id = admin_user_id
        refund.approved_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(refund)
        logger.info(
            "REFUND_APPROVED: refund_id=%s admin_user_id=%s", refund.id, admin_user_id
        )
        return self._to_admin_response(refund)

    def reject_refund(
        self, refund_id: int, admin_user_id: int, reason: str | None
    ) -> AdminRefundResponse:
        refund = self._lock_refund(refund_id)
        if RefundStatus(refund.status) != RefundStatus.PENDING_APPROVAL:
            raise ConflictError(
                f"Cannot reject a refund in status {refund.status}."
            )
        self._apply_transition(refund, RefundStatus.REJECTED)
        refund.approved_by_user_id = admin_user_id
        refund.approved_at = datetime.now(UTC)
        refund.rejection_reason = reason
        self.db.commit()
        self.db.refresh(refund)
        logger.info(
            "REFUND_REJECTED: refund_id=%s admin_user_id=%s", refund.id, admin_user_id
        )
        return self._to_admin_response(refund)

    def process_refund(self, refund_id: int, admin_user_id: int) -> AdminRefundResponse:
        """APPROVED (or a previously-FAILED attempt) -> PROCESSING, then a
        gateway call - the same short-transaction-then-network-call shape
        as PaymentService._initiate_upi: the row lock is released via
        commit BEFORE the outbound call, never held across it.
        """
        if self.gateway is None:
            raise ConflictError("No payment gateway configured for refund processing.")

        refund = self._lock_refund(refund_id)
        if RefundStatus(refund.status) == RefundStatus.PROCESSING:
            # Same-state would otherwise be a silent no-op (see
            # refund_state.py) and let a second concurrent call fall
            # through to launch a DUPLICATE gateway attempt - explicitly
            # rejected instead, mirroring PaymentService.retry_payment's
            # identical guard against retrying a payment still PROCESSING.
            raise ConflictError(
                "This refund is still being processed by the gateway. "
                "Wait for the current attempt to resolve before retrying."
            )
        self._apply_transition(refund, RefundStatus.PROCESSING)

        payment = self.db.query(Payment).filter(Payment.id == refund.payment_id).first()
        if payment is None:
            raise ConflictError("The payment for this refund could not be found.")

        idempotency_key = f"refund-{refund.id}-{secrets.token_urlsafe(16)}"
        now = datetime.now(UTC)
        transaction = PaymentTransaction(
            payment_id=payment.id,
            refund_id=refund.id,
            transaction_type=_REFUND_TRANSACTION_TYPE,
            status=TransactionStatus.INITIATED,
            amount=refund.amount,
            currency=refund.currency,
            gateway_name=self.gateway.gateway_name,
            idempotency_key=idempotency_key,
            initiated_at=now,
        )
        self.db.add(transaction)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not start refund processing due to a conflicting update."
            ) from exc
        self.db.refresh(refund)
        self.db.refresh(transaction)

        logger.info(
            "REFUND_PROCESSING_STARTED: refund_id=%s transaction_id=%s admin_user_id=%s",
            refund.id, transaction.id, admin_user_id,
        )

        try:
            result = self.gateway.refund_payment(
                gateway_order_id=payment.gateway_order_id or "",
                gateway_transaction_id=None,
                amount=refund.amount,
                currency=refund.currency,
                idempotency_key=idempotency_key,
            )
        except NotImplementedError as exc:
            self._fail_unresolved_attempt(transaction.id, refund.id, f"Gateway not available: {exc}")
            raise
        except GatewayRejectedError as exc:
            self._fail_unresolved_attempt(transaction.id, refund.id, str(exc))
            raise
        except (GatewayTimeoutError, GatewayConnectionError, GatewayError) as exc:
            # Outcome unknown - leave PROCESSING, never FAILED. Recoverable
            # by an admin re-invoking this same action once resolved,
            # mirroring PaymentService._initiate_upi's identical handling.
            logger.warning(
                "REFUND_PROCESSING_OUTCOME_UNKNOWN: refund_id=%s transaction_id=%s error=%s",
                refund.id, transaction.id, exc,
            )
            raise

        return self._persist_gateway_result(refund.id, transaction.id, result)

    def _persist_gateway_result(
        self, refund_id: int, transaction_id: int, result: GatewayRefundResult
    ) -> AdminRefundResponse:
        refund = self._lock_refund(refund_id)
        transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.id == transaction_id)
            .first()
        )
        transaction.gateway_transaction_id = result.gateway_refund_id
        transaction.status = result.status
        transaction.completed_at = datetime.now(UTC)
        if result.status == TransactionStatus.FAILED:
            transaction.failure_reason = (result.failure_reason or "")[:2000]
            self._apply_transition(refund, RefundStatus.FAILED)
        elif result.status == TransactionStatus.SUCCESS:
            self._apply_transition(refund, RefundStatus.REFUNDED)
            refund.processed_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(refund)
        return self._to_admin_response(refund)

    def _fail_unresolved_attempt(
        self, transaction_id: int, refund_id: int, reason: str
    ) -> None:
        refund = self._lock_refund(refund_id)
        transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.id == transaction_id)
            .first()
        )
        if transaction is not None and transaction.status not in (
            TransactionStatus.SUCCESS, TransactionStatus.FAILED,
        ):
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = reason[:2000]
            transaction.completed_at = datetime.now(UTC)
        try:
            self._apply_transition(refund, RefundStatus.FAILED)
        except ConflictError:
            pass
        self.db.commit()
        logger.info(
            "REFUND_ATTEMPT_FAILED: refund_id=%s transaction_id=%s reason=%s",
            refund_id, transaction_id, reason,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lock_refund(self, refund_id: int) -> Refund:
        refund = (
            self.db.query(Refund)
            .filter(Refund.id == refund_id)
            .with_for_update()
            .first()
        )
        if refund is None:
            raise NotFoundError("Refund not found.")
        return refund

    @staticmethod
    def _apply_transition(refund: Refund, target: RefundStatus) -> None:
        try:
            result = transition_refund_status(RefundStatus(refund.status), target)
        except IllegalRefundTransitionError as exc:
            raise ConflictError(
                f"Cannot move refund from {exc.current.value} to {exc.target.value}."
            ) from exc
        if result.applied:
            refund.status = target
            logger.info(
                "REFUND_STATE_TRANSITION: refund_id=%s %s -> %s",
                refund.id, result.previous.value, result.current.value,
            )

    @staticmethod
    def _to_admin_response(refund: Refund) -> AdminRefundResponse:
        return AdminRefundResponse.model_validate(refund)
