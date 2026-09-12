"""Payment domain service: initiation, retry, verification, and webhook processing.

TRANSACTION DESIGN: same rule as every prior atomic-transaction phase
(Inventory's create_movement, Packaging's complete_operation, Order's
checkout) - every customer-facing route here is protected by
`require_roles`, which composes `get_current_user` and therefore always
autobegins the session's transaction via its own reads before any service
method runs. No method here calls `db.begin()`. The webhook route has no
such dependency, but this service still never calls `db.begin()` there
either, for consistency and because `db.flush()` (used for the webhook
dedup check) requires no explicit transaction start.

LOCK ORDERING: every code path that touches both an Order and a Payment
locks Order FIRST, then Payment, via `_lock_payment_and_order` /
`_lock_owned_order`. This is enforced uniformly even though webhook/verify
naturally start from a payment reference and create_payment naturally
starts from an order_id - a consistent global lock order is what prevents
a deadlock between those two directions under concurrency.

CLIENT IS NEVER AUTHORITY: no method here ever sets `payment.status` from
a client-supplied value. Status only ever moves through
`transition_payment_status` (app/services/payment_state.py), driven by
either our own gateway call's synchronous result or an authenticated
webhook/verify gateway response.

PHASE 15 INTEGRATION: order confirmation is now gated by successfully
committing the order's inventory reservation
(InventoryReservationService.commit_reservation_for_order), not just by
payment status. This is invoked from the two places order confirmation
already happened - `_confirm_cod` and `_confirm_order_if_paid` - and
nowhere else. It is what implements "a payment success arriving after the
reservation already expired must not resurrect it": if the commit call
returns False, the order is left exactly as it was and a
PAYMENT_RESERVATION_MISMATCH reconciliation event is logged, never a
silent auto-confirm.
"""

import hashlib
import json
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.exceptions.base import (
    AuthenticationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.schemas.payment import (
    CreatePaymentRequest,
    PaymentInitiationResponse,
    PaymentResponse,
)
from app.services.inventory_reservation import InventoryReservationService
from app.services.payment_gateway import (
    GatewayConnectionError,
    GatewayError,
    GatewayInitiateResult,
    GatewayRejectedError,
    GatewayTimeoutError,
    GatewayWebhookEvent,
    PaymentGateway,
    WebhookParseError,
)
from app.services.payment_state import (
    IllegalTransitionError,
    PaymentStatus,
    TransactionStatus,
    can_retry_payment,
    is_payment_terminal,
    is_transaction_terminal,
    transition_payment_status,
)
from app.services.refund import RefundService

_GATEWAY_TO_PAYMENT_STATUS: dict[TransactionStatus, PaymentStatus] = {
    TransactionStatus.INITIATED: PaymentStatus.PROCESSING,
    TransactionStatus.PROCESSING: PaymentStatus.PROCESSING,
    TransactionStatus.SUCCESS: PaymentStatus.PAID,
    TransactionStatus.FAILED: PaymentStatus.FAILED,
    TransactionStatus.CANCELLED: PaymentStatus.CANCELLED,
    TransactionStatus.EXPIRED: PaymentStatus.EXPIRED,
}


class PaymentService:
    def __init__(self, db: Session, gateway: PaymentGateway) -> None:
        self.db = db
        self.gateway = gateway

    # ------------------------------------------------------------------
    # Customer-facing
    # ------------------------------------------------------------------

    def create_payment(self, user_id: int, data: CreatePaymentRequest) -> PaymentResponse:
        order = self._lock_owned_order(user_id, data.order_id)

        payment = (
            self.db.query(Payment)
            .filter(Payment.order_id == order.id)
            .with_for_update()
            .first()
        )

        if payment:
            if payment.status == PaymentStatus.PAID:
                self.db.commit()
                raise ConflictError("This order has already been paid.")
            if payment.payment_method != data.payment_method:
                raise ConflictError(
                    "A payment already exists for this order with a "
                    "different payment method."
                )
            # Idempotent: return the existing (non-PAID) obligation as-is.
            # Re-attempting a non-PAID UPI payment happens explicitly via
            # POST /payments/{id}/retry - a duplicate POST here never
            # implicitly triggers another gateway call.
            self.db.commit()
            return PaymentResponse.model_validate(payment)

        if order.status != "PENDING":
            raise ConflictError(f"Order is not payable in status {order.status}.")

        payment = Payment(
            order_id=order.id,
            payment_method=data.payment_method,
            status=PaymentStatus.PENDING,
            amount=order.total_amount,
            currency=order.currency,
        )
        self.db.add(payment)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A payment for this order already exists.") from exc

        if data.payment_method == "COD":
            return self._confirm_cod(order, payment)
        return self._initiate_upi(order, payment)

    def get_payment(self, user_id: int, payment_id: int) -> PaymentResponse:
        payment = self._get_owned_payment(user_id, payment_id)
        return PaymentResponse.model_validate(payment)

    def get_payment_for_order(self, user_id: int, order_id: int) -> PaymentResponse:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            raise NotFoundError("Order not found.")
        payment = self.db.query(Payment).filter(Payment.order_id == order.id).first()
        if not payment:
            raise NotFoundError("Payment not found for this order.")
        return PaymentResponse.model_validate(payment)

    def retry_payment(self, user_id: int, payment_id: int) -> PaymentInitiationResponse:
        order, payment = self._lock_payment_and_order(payment_id)
        if order.user_id != user_id:
            raise NotFoundError("Payment not found.")

        if payment.payment_method != "UPI":
            raise ConflictError("Only UPI payments can be retried.")

        if payment.status == PaymentStatus.PROCESSING:
            raise ConflictError(
                "Payment status is still being confirmed by the gateway. "
                "Call POST /payments/{id}/verify to check the authoritative "
                "status before retrying."
            )
        if not can_retry_payment(PaymentStatus(payment.status)):
            raise ConflictError(f"Cannot retry a payment in status {payment.status}.")

        # Lock is carried through into _initiate_upi's own commit below -
        # tighter protection against a concurrent second retry than
        # releasing and re-acquiring it would give.
        return self._initiate_upi(order, payment)

    def verify_payment(self, user_id: int, payment_id: int) -> PaymentResponse:
        """Client-triggered reconciliation. Never trusts a client-supplied
        status - always re-derives it from the gateway (or reports current
        state honestly when there is nothing to check).
        """
        order, payment = self._lock_payment_and_order(payment_id)
        if order.user_id != user_id:
            raise NotFoundError("Payment not found.")

        if (
            is_payment_terminal(PaymentStatus(payment.status))
            or payment.payment_method == "COD"
            or payment.gateway_order_id is None
        ):
            self.db.commit()  # release the lock; nothing to change
            return PaymentResponse.model_validate(payment)

        latest_transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.payment_id == payment.id)
            .order_by(PaymentTransaction.id.desc())
            .first()
        )

        try:
            result = self.gateway.query_status(
                gateway_order_id=payment.gateway_order_id,
                gateway_transaction_id=(
                    latest_transaction.gateway_transaction_id
                    if latest_transaction
                    else None
                ),
            )
        except (NotImplementedError, GatewayTimeoutError, GatewayConnectionError, GatewayError):
            # Outcome unknown or gateway unavailable - release the lock,
            # report current (unresolved) state, and re-raise so the client
            # gets an honest error rather than a silently-stale 200.
            self.db.commit()
            raise

        if latest_transaction is not None:
            applied = self._apply_transaction_status(
                payment, latest_transaction, TransactionStatus(result.status), source="verify"
            )
            if applied:
                self._confirm_order_if_paid(order, payment)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not verify payment due to a conflicting update."
            ) from exc

        self.db.refresh(payment)
        return PaymentResponse.model_validate(payment)

    # ------------------------------------------------------------------
    # Webhook processing
    # ------------------------------------------------------------------

    def process_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> None:
        """Full pipeline: verify authenticity -> parse -> deduplicate ->
        lock payment -> validate amount/currency -> apply state transition
        -> possibly confirm order -> commit once. Payment state is never
        touched before signature verification succeeds.
        """
        if not self.gateway.verify_webhook_signature(raw_body=raw_body, headers=headers):
            logger.warning(
                "PAYMENT_WEBHOOK_INVALID_SIGNATURE: gateway=%s", self.gateway.gateway_name
            )
            raise AuthenticationError("Invalid webhook signature.")

        try:
            event = self.gateway.parse_webhook_event(raw_body=raw_body, headers=headers)
        except WebhookParseError as exc:
            logger.warning(
                "PAYMENT_WEBHOOK_MALFORMED: gateway=%s error=%s",
                self.gateway.gateway_name, exc,
            )
            raise BusinessValidationError(f"Malformed webhook payload: {exc}") from exc

        payload_hash = hashlib.sha256(raw_body).hexdigest()

        webhook_event = PaymentWebhookEvent(
            gateway_name=self.gateway.gateway_name,
            event_id=event.event_id,
            event_type=event.event_type,
            status="RECEIVED",
            payload_hash=payload_hash,
        )
        self.db.add(webhook_event)
        try:
            # flush (not commit) - this is what makes the whole pipeline one
            # transaction. The UNIQUE(gateway_name, event_id) constraint
            # still fires/blocks here exactly as it would on commit; a
            # concurrent duplicate's own INSERT blocks on this uncommitted
            # row until we commit or roll back.
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            logger.info(
                "PAYMENT_WEBHOOK_DUPLICATE: gateway=%s event_id=%s",
                self.gateway.gateway_name, event.event_id,
            )
            return

        self._process_new_webhook_event(webhook_event, event)

    def _process_new_webhook_event(
        self, webhook_event: PaymentWebhookEvent, event: GatewayWebhookEvent
    ) -> None:
        transaction = self._resolve_transaction_for_event(event)
        if transaction is None:
            webhook_event.status = "FAILED"
            webhook_event.processed_at = datetime.now(UTC)
            logger.warning(
                "PAYMENT_WEBHOOK_UNKNOWN_REFERENCE: gateway=%s event_id=%s "
                "gateway_order_id=%s gateway_transaction_id=%s",
                self.gateway.gateway_name, event.event_id,
                event.gateway_order_id, event.gateway_transaction_id,
            )
            self.db.commit()
            return

        order, payment = self._lock_payment_and_order(transaction.payment_id)
        transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.id == transaction.id)
            .first()
        )

        if event.amount is not None and event.amount != payment.amount:
            webhook_event.status = "FAILED"
            webhook_event.processed_at = datetime.now(UTC)
            webhook_event.payment_transaction_id = transaction.id
            logger.error(
                "PAYMENT_RECONCILIATION: payment_id=%s amount mismatch "
                "gateway=%s ours=%s event_id=%s",
                payment.id, event.amount, payment.amount, event.event_id,
            )
            self.db.commit()
            return

        if event.currency is not None and event.currency != payment.currency:
            webhook_event.status = "FAILED"
            webhook_event.processed_at = datetime.now(UTC)
            webhook_event.payment_transaction_id = transaction.id
            logger.error(
                "PAYMENT_RECONCILIATION: payment_id=%s currency mismatch "
                "gateway=%s ours=%s event_id=%s",
                payment.id, event.currency, payment.currency, event.event_id,
            )
            self.db.commit()
            return

        applied = self._apply_transaction_status(
            payment, transaction, event.status, source="webhook"
        )
        if applied:
            self._confirm_order_if_paid(order, payment)

        webhook_event.status = "PROCESSED"
        webhook_event.processed_at = datetime.now(UTC)
        webhook_event.payment_transaction_id = transaction.id

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not process webhook due to a conflicting update."
            ) from exc

        logger.info(
            "PAYMENT_WEBHOOK_PROCESSED: gateway=%s event_id=%s payment_id=%s transaction_id=%s",
            self.gateway.gateway_name, event.event_id, payment.id, transaction.id,
        )

    def _resolve_transaction_for_event(
        self, event: GatewayWebhookEvent
    ) -> PaymentTransaction | None:
        if event.gateway_transaction_id:
            transaction = (
                self.db.query(PaymentTransaction)
                .filter(
                    PaymentTransaction.gateway_name == self.gateway.gateway_name,
                    PaymentTransaction.gateway_transaction_id
                    == event.gateway_transaction_id,
                )
                .first()
            )
            if transaction:
                return transaction

        if event.gateway_order_id:
            payment = (
                self.db.query(Payment)
                .filter(
                    Payment.gateway_name == self.gateway.gateway_name,
                    Payment.gateway_order_id == event.gateway_order_id,
                )
                .first()
            )
            if payment:
                return (
                    self.db.query(PaymentTransaction)
                    .filter(PaymentTransaction.payment_id == payment.id)
                    .order_by(PaymentTransaction.id.desc())
                    .first()
                )
        return None

    # ------------------------------------------------------------------
    # COD / UPI initiation internals
    # ------------------------------------------------------------------

    def _confirm_cod(self, order: Order, payment: Payment) -> PaymentResponse:
        """COD: payment stays PENDING (cash collected later, future
        Delivery phase); order confirms immediately. No gateway call, no
        transaction row - per Phase 7's documented COD lifecycle.

        Phase 15: confirmation is gated by committing the order's
        inventory reservation. COD is not exempt from the 30-minute
        reservation window (it is fixed at checkout time, before any
        payment method is known) - if the customer waits past it before
        ever choosing COD, this rolls back (discarding the just-created
        PENDING payment row too) rather than confirming an order with no
        held inventory behind it.
        """
        committed = InventoryReservationService(self.db).commit_reservation_for_order(
            order, now=datetime.now(UTC)
        )
        if not committed:
            self.db.rollback()
            raise ConflictError(
                "This order's inventory reservation has expired and can no "
                "longer be confirmed via Cash on Delivery."
            )

        order.status = "CONFIRMED"
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not confirm order due to a conflicting update."
            ) from exc
        self.db.refresh(payment)
        logger.info(
            "PAYMENT_COD_CONFIRMED: payment_id=%s order_id=%s", payment.id, order.id
        )
        return PaymentResponse.model_validate(payment)

    def _initiate_upi(self, order: Order, payment: Payment) -> PaymentInitiationResponse:
        idempotency_key = self._new_idempotency_key()
        now = datetime.now(UTC)
        transaction = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="PAYMENT",
            status=TransactionStatus.INITIATED,
            amount=payment.amount,
            currency=payment.currency,
            gateway_name=self.gateway.gateway_name,
            idempotency_key=idempotency_key,
            initiated_at=now,
        )
        self.db.add(transaction)
        payment.status = PaymentStatus.PROCESSING
        try:
            # Short transaction - the lock is released here, BEFORE the
            # external gateway call below. Never hold a DB row lock across
            # a network call.
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not initiate payment due to a conflicting update."
            ) from exc
        self.db.refresh(payment)
        self.db.refresh(transaction)

        reference = f"order-{order.id}-payment-{payment.id}"
        logger.info(
            "PAYMENT_UPI_INITIATING: payment_id=%s order_id=%s transaction_id=%s gateway=%s",
            payment.id, order.id, transaction.id, self.gateway.gateway_name,
        )

        try:
            result = self.gateway.initiate_payment(
                reference=reference,
                amount=payment.amount,
                currency=payment.currency,
                idempotency_key=idempotency_key,
            )
        except NotImplementedError as exc:
            # No PNB integration contract exists yet - this attempt
            # definitively did not reach the gateway. Safe to mark FAILED
            # (not "unknown") and retryable via /retry once real
            # connectivity exists.
            self._fail_unresolved_attempt(transaction.id, f"Gateway not available: {exc}")
            raise
        except GatewayRejectedError as exc:
            # Gateway synchronously and definitively rejected the request -
            # nothing is left unresolved. Safe to mark FAILED.
            self._fail_unresolved_attempt(transaction.id, str(exc))
            raise
        except (GatewayTimeoutError, GatewayConnectionError, GatewayError) as exc:
            # THE critical case: the payment may have succeeded on PNB's
            # side despite us never getting a response. Leave payment/
            # transaction as PROCESSING - never FAILED. Recoverable via
            # POST /payments/{id}/verify once connectivity is restored.
            logger.warning(
                "PAYMENT_UPI_INITIATE_OUTCOME_UNKNOWN: payment_id=%s transaction_id=%s error=%s",
                payment.id, transaction.id, exc,
            )
            raise

        return self._persist_initiation_result(payment.id, transaction.id, result)

    def _persist_initiation_result(
        self, payment_id: int, transaction_id: int, result: GatewayInitiateResult
    ) -> PaymentInitiationResponse:
        order, payment = self._lock_payment_and_order(payment_id)
        transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.id == transaction_id)
            .first()
        )

        # gateway_order_id is set once per payment obligation and reused
        # across retries (§6.1: "on the logical payment").
        if payment.gateway_name is None:
            payment.gateway_name = self.gateway.gateway_name
            payment.gateway_order_id = result.gateway_order_id

        transaction.gateway_transaction_id = result.gateway_transaction_id
        if result.raw_response is not None:
            transaction.gateway_response = json.dumps(result.raw_response)[:8000]

        # The gateway may confirm/reject synchronously right at initiation.
        applied = self._apply_transaction_status(
            payment, transaction, TransactionStatus(result.status), source="initiate"
        )
        if applied:
            self._confirm_order_if_paid(order, payment)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not persist payment gateway reference due to a conflicting update."
            ) from exc
        self.db.refresh(payment)
        self.db.refresh(transaction)

        return PaymentInitiationResponse(
            **PaymentResponse.model_validate(payment).model_dump(),
            payment_session_token=result.payment_session_token,
            upi_intent_uri=result.upi_intent_uri,
        )

    def _fail_unresolved_attempt(self, transaction_id: int, reason: str) -> None:
        transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.id == transaction_id)
            .first()
        )
        order, payment = self._lock_payment_and_order(transaction.payment_id)
        transaction = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.id == transaction_id)
            .first()
        )

        if not is_transaction_terminal(TransactionStatus(transaction.status)):
            transaction.status = TransactionStatus.FAILED
            transaction.failure_reason = reason[:2000]
            transaction.completed_at = datetime.now(UTC)

        try:
            result = transition_payment_status(
                PaymentStatus(payment.status), PaymentStatus.FAILED
            )
            if result.applied:
                payment.status = PaymentStatus.FAILED
        except IllegalTransitionError:
            logger.warning(
                "PAYMENT_RECONCILIATION: payment_id=%s illegal FAILED transition "
                "from %s ignored", payment.id, payment.status,
            )

        self.db.commit()
        logger.info(
            "PAYMENT_ATTEMPT_FAILED: payment_id=%s transaction_id=%s reason=%s",
            payment.id, transaction_id, reason,
        )

    # ------------------------------------------------------------------
    # Shared state-transition core (used by initiate/webhook/verify)
    # ------------------------------------------------------------------

    def _apply_transaction_status(
        self,
        payment: Payment,
        transaction: PaymentTransaction,
        new_transaction_status: TransactionStatus,
        *,
        source: str,
    ) -> bool:
        """Caller MUST already hold the payment row lock in the current
        transaction. Returns True iff the payment's status actually
        changed. Never raises for illegal/late/duplicate transitions -
        those are logged as a reconciliation condition and safely ignored
        (§7/§19), so a late FAILED after PAID, or a repeated PAID event,
        can never corrupt an already-resolved payment.
        """
        if is_transaction_terminal(TransactionStatus(transaction.status)):
            logger.info(
                "PAYMENT_EVENT_NOOP_TERMINAL_TRANSACTION: payment_id=%s transaction_id=%s "
                "source=%s existing_status=%s incoming_status=%s",
                payment.id, transaction.id, source,
                transaction.status, new_transaction_status.value,
            )
            return False

        transaction.status = new_transaction_status
        if is_transaction_terminal(new_transaction_status):
            transaction.completed_at = datetime.now(UTC)

        target_payment_status = _GATEWAY_TO_PAYMENT_STATUS[new_transaction_status]
        try:
            result = transition_payment_status(
                PaymentStatus(payment.status), target_payment_status
            )
        except IllegalTransitionError:
            logger.warning(
                "PAYMENT_RECONCILIATION: payment_id=%s source=%s illegal transition "
                "%s -> %s ignored (payment status unchanged)",
                payment.id, source, payment.status, target_payment_status.value,
            )
            return False

        if not result.applied:
            return False  # already in target status - idempotent no-op

        payment.status = target_payment_status
        if target_payment_status == PaymentStatus.PAID:
            payment.paid_at = datetime.now(UTC)

        logger.info(
            "PAYMENT_STATE_TRANSITION: payment_id=%s source=%s %s -> %s",
            payment.id, source, result.previous.value, result.current.value,
        )
        return True

    def _confirm_order_if_paid(self, order: Order, payment: Payment) -> None:
        """Caller must already hold the order row lock.

        Phase 15: order confirmation additionally requires committing the
        order's inventory reservation. If the reservation already expired
        (or was otherwise released) before this payment resolved, the
        reservation is NOT resurrected and the order is NOT confirmed -
        this is the late-payment-after-expiry case, logged as a
        reconciliation event rather than silently applied. The payment
        itself still stays PAID; only order confirmation is withheld.

        Phase 18: a payment can also resolve to PAID AFTER its order was
        already cancelled (the customer cancelled while a UPI attempt was
        still PROCESSING). Money was genuinely collected for an order that
        will never be fulfilled, so this is the second of the two call
        sites that create refund eligibility (the first being
        OrderService.cancel_order itself, for the case where the payment
        was already PAID at cancellation time) - never issuing the refund
        itself, only making it visible for ADMIN approval.
        """
        if payment.status != PaymentStatus.PAID:
            return
        if order.status == "PENDING":
            committed = InventoryReservationService(
                self.db
            ).commit_reservation_for_order(order, now=datetime.now(UTC))
            if not committed:
                logger.error(
                    "PAYMENT_RESERVATION_MISMATCH: order_id=%s payment_id=%s payment "
                    "PAID but reservation could not be committed (expired/released) "
                    "- order left PENDING, not auto-confirmed",
                    order.id, payment.id,
                )
                return
            order.status = "CONFIRMED"
            logger.info(
                "PAYMENT_ORDER_CONFIRMED: order_id=%s payment_id=%s", order.id, payment.id
            )
        elif order.status == "CANCELLED":
            RefundService(self.db).create_refund_if_eligible(order, payment)
            logger.warning(
                "PAYMENT_RECONCILIATION: order_id=%s payment_id=%s payment resolved "
                "PAID after the order was already cancelled - refund eligibility "
                "created for admin review",
                order.id, payment.id,
            )
        elif order.status != "COMPLETED":
            logger.warning(
                "PAYMENT_RECONCILIATION: order_id=%s payment_id=%s payment PAID but "
                "order status is %s", order.id, payment.id, order.status,
            )

    # ------------------------------------------------------------------
    # Locking / ownership helpers
    # ------------------------------------------------------------------

    def _lock_owned_order(self, user_id: int, order_id: int) -> Order:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not order:
            raise NotFoundError("Order not found.")
        return order

    def _lock_payment_and_order(self, payment_id: int) -> tuple[Order, Payment]:
        """Locks Order then Payment, in that fixed order, everywhere in this
        service - see module docstring on lock ordering.

        `.populate_existing()` is required on both locked queries: the
        initial unlocked read below (needed only to discover `order_id`
        before Order can be locked first) puts that Payment row into this
        session's identity map. Without `.populate_existing()`, SQLAlchemy
        returns the SAME already-mapped Python object from the later
        `with_for_update()` re-query without refreshing its attributes from
        the fresh (possibly just-changed-by-a-concurrent-transaction) row -
        the lock itself is still correctly acquired at the SQL level, but
        the caller would silently see stale in-memory values. This was
        found via test_concurrent_retries_do_not_create_two_new_attempts:
        without this fix, two concurrent retries could both observe a
        stale pre-lock status and both proceed.
        """
        payment_unlocked = (
            self.db.query(Payment).filter(Payment.id == payment_id).first()
        )
        if not payment_unlocked:
            raise NotFoundError("Payment not found.")
        order = (
            self.db.query(Order)
            .filter(Order.id == payment_unlocked.order_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        payment = (
            self.db.query(Payment)
            .filter(Payment.id == payment_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        return order, payment

    def _get_owned_payment(self, user_id: int, payment_id: int) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise NotFoundError("Payment not found.")
        order = (
            self.db.query(Order)
            .filter(Order.id == payment.order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            # Ownership violation gets the identical 404 as "doesn't exist"
            # - never disclose that another user's payment exists.
            raise NotFoundError("Payment not found.")
        return payment

    @staticmethod
    def _new_idempotency_key() -> str:
        return secrets.token_urlsafe(32)
