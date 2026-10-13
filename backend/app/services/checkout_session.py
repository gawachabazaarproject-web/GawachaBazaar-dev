"""Pay-first online checkout.

For online payment the order is placed AFTER the payment succeeds, not
before:

  1. `start`    - price the cart (same code as order checkout), create a
                  Razorpay order for that amount, remember it in a
                  CheckoutSession. No Order, no reservation; cart untouched.
  2. the app opens Razorpay Checkout with that order.
  3. `complete` - after Razorpay reports success: verify the signature, ask
                  Razorpay (not the client) whether the order was captured,
                  and only then create the order from the cart, attach the
                  PAID payment and confirm it. The Razorpay webhook runs the
                  very same completion (`complete_from_webhook`) so a payment
                  whose app callback never arrived still produces its order.

If money was captured but the order cannot be placed (stock ran out, prices
changed), the payment is refunded automatically and the session records it.
Every step is idempotent: completing twice returns the same order.
"""

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.exceptions.base import (
    AppException,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.models.checkout_session import CheckoutSession
from app.models.inventory_lot import InventoryLot
from app.models.payment import Payment
from app.models.payment_transaction import PaymentTransaction
from app.models.user import User
from app.schemas.online_checkout import (
    OnlineCheckoutCompleteResponse,
    OnlineCheckoutResponse,
    StartOnlineCheckoutRequest,
)
from app.schemas.order import CheckoutRequest
from app.schemas.payment import ConfirmCheckoutRequest, PaymentResponse
from app.services.order import OrderService
from app.services.payment import OnlinePaymentsUnavailableError, PaymentService
from app.services.payment_gateway import GatewayError, PaymentGateway
from app.services.payment_state import PaymentStatus, TransactionStatus
from app.services.razorpay_gateway import to_paise

_PENDING = "PENDING"


class PaymentNotConfirmedError(AppException):
    def __init__(self) -> None:
        super().__init__(
            "We haven't received confirmation of your payment yet. "
            "If money was deducted, your order will appear automatically in a moment.",
            status_code=409,
            code="PAYMENT_NOT_CONFIRMED",
        )


class CheckoutSessionService:
    def __init__(self, db: Session, gateway: PaymentGateway) -> None:
        self.db = db
        self.gateway = gateway

    # ------------------------------------------------------------------
    # 1. start
    # ------------------------------------------------------------------

    def start(self, user_id: int, data: StartOnlineCheckoutRequest) -> OnlineCheckoutResponse:
        PaymentService(self.db, self.gateway)._require_online_payments()
        key_id = getattr(self.gateway, "checkout_key_id", None)
        if not key_id:
            raise OnlinePaymentsUnavailableError()

        plan = OrderService(self.db).quote_checkout(
            user_id, CheckoutRequest(address_id=data.address_id, promo_code=data.promo_code)
        )
        self._require_stock(plan)

        # Re-opening the sheet for an unchanged basket must reuse the same
        # Razorpay order (a customer who paid in a UPI app and came back
        # must not get a second order to pay).
        session = (
            self.db.query(CheckoutSession)
            .filter(
                CheckoutSession.user_id == user_id,
                CheckoutSession.cart_id == plan.cart_id,
                CheckoutSession.address_id == data.address_id,
                CheckoutSession.promo_code.is_(None) if not data.promo_code
                else CheckoutSession.promo_code == data.promo_code,
                CheckoutSession.amount == plan.total_amount,
                CheckoutSession.status == _PENDING,
            )
            .order_by(CheckoutSession.id.desc())
            .first()
        )
        if session is None:
            reference = f"cart-{plan.cart_id}-{int(datetime.now(UTC).timestamp())}"
            result = self.gateway.initiate_payment(
                reference=reference,
                amount=plan.total_amount,
                currency=plan.currency,
                idempotency_key=PaymentService._new_idempotency_key(),
            )
            session = CheckoutSession(
                user_id=user_id,
                cart_id=plan.cart_id,
                address_id=data.address_id,
                promo_code=data.promo_code or None,
                amount=plan.total_amount,
                currency=plan.currency,
                gateway_name=self.gateway.gateway_name,
                gateway_order_id=result.gateway_order_id,
                status=_PENDING,
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        user = self.db.query(User).filter(User.id == user_id).first()
        return OnlineCheckoutResponse(
            session_id=session.id,
            gateway=self.gateway.gateway_name,
            key_id=key_id,
            gateway_order_id=session.gateway_order_id,
            amount=session.amount,
            amount_minor=to_paise(session.amount),
            currency=session.currency,
            merchant_name=settings.APP_NAME,
            description="Gawacha Bazaar order",
            customer_name=user.name,
            customer_email=user.email,
            customer_phone=user.phone,
            test_mode=bool(getattr(self.gateway, "is_test_mode", False)),
        )

    def _require_stock(self, plan) -> None:
        """Do not take a customer's money for items that are already out of
        stock. Not a reservation - the binding check happens when the order
        is created after payment (and refunds if it then fails)."""
        wanted: dict[int, object] = {}
        for variant_id, quantity in plan.cart_items or []:
            wanted[variant_id] = wanted.get(variant_id, 0) + quantity
        if not wanted:
            return
        rows = (
            self.db.query(
                InventoryLot.variant_id,
                func.sum(InventoryLot.quantity - InventoryLot.reserved_quantity),
            )
            .filter(InventoryLot.variant_id.in_(list(wanted)), InventoryLot.status == "ACTIVE")
            .group_by(InventoryLot.variant_id)
            .all()
        )
        available = {variant_id: total for variant_id, total in rows}
        names = {row["variant_id"]: row for row in plan.order_item_rows}
        for variant_id, quantity in wanted.items():
            if (available.get(variant_id) or 0) < quantity:
                row = names.get(variant_id, {})
                raise ConflictError(
                    f"Sorry, {row.get('product_name', 'an item')} ({row.get('variant_name', '')}) "
                    "doesn't have enough stock right now. Please lower the quantity or remove it."
                )

    # ------------------------------------------------------------------
    # 3. complete (client callback)
    # ------------------------------------------------------------------

    def complete(
        self, user_id: int, session_id: int, data: ConfirmCheckoutRequest
    ) -> OnlineCheckoutCompleteResponse:
        session = (
            self.db.query(CheckoutSession)
            .filter(CheckoutSession.id == session_id, CheckoutSession.user_id == user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if not session:
            raise NotFoundError("Checkout not found.")

        if data.razorpay_order_id != session.gateway_order_id:
            self.db.rollback()
            raise BusinessValidationError("Payment does not belong to this checkout.")
        verify_signature = getattr(self.gateway, "verify_checkout_signature", None)
        if verify_signature is None or not verify_signature(
            gateway_order_id=data.razorpay_order_id,
            gateway_payment_id=data.razorpay_payment_id,
            signature=data.razorpay_signature,
        ):
            logger.warning("CHECKOUT_SESSION_BAD_SIGNATURE: session_id=%s", session.id)
            self.db.rollback()
            raise BusinessValidationError("Payment signature verification failed.")

        return self._finalize(session)

    def verify(self, user_id: int, session_id: int) -> OnlineCheckoutCompleteResponse:
        """Customer-triggered re-check, e.g. after the Razorpay sheet closed
        without a success callback (a UPI app can take the money and lose the
        hand-off). Needs no client proof: Razorpay itself is asked whether the
        order was captured, and only then is the order placed."""
        session = (
            self.db.query(CheckoutSession)
            .filter(CheckoutSession.id == session_id, CheckoutSession.user_id == user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if not session:
            raise NotFoundError("Checkout not found.")
        return self._finalize(session)

    # ------------------------------------------------------------------
    # Webhook entry point
    # ------------------------------------------------------------------

    def find_session_for_gateway_order(self, gateway_order_id: str) -> CheckoutSession | None:
        return (
            self.db.query(CheckoutSession)
            .filter(
                CheckoutSession.gateway_name == self.gateway.gateway_name,
                CheckoutSession.gateway_order_id == gateway_order_id,
            )
            .first()
        )

    def complete_from_webhook(self, session_id: int) -> None:
        """Razorpay says this session's order was paid. Same completion as the
        client callback; business failures (already refunded...) are logged,
        never raised, so the webhook is always acknowledged."""
        session = (
            self.db.query(CheckoutSession)
            .filter(CheckoutSession.id == session_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if session is None:
            return
        try:
            self._finalize(session)
        except AppException as exc:
            logger.warning("CHECKOUT_SESSION_WEBHOOK_NOT_COMPLETED: session_id=%s reason=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Shared completion
    # ------------------------------------------------------------------

    def _finalize(self, session: CheckoutSession) -> OnlineCheckoutCompleteResponse:
        """Caller holds the session row lock. Idempotent."""
        if session.status == "COMPLETED":
            self.db.commit()
            return self._response_for_order(session.user_id, session.order_id)
        if session.status in ("REFUNDED", "REFUND_FAILED"):
            reason = session.failure_reason or "This payment could not be turned into an order."
            self.db.commit()
            raise ConflictError(reason)

        # Authoritative: ask Razorpay, never trust the client. A gateway
        # outage propagates (GatewayError -> 502/504) and can simply be retried.
        try:
            status = self.gateway.query_status(gateway_order_id=session.gateway_order_id, gateway_transaction_id=None)
        except GatewayError:
            self.db.commit()
            raise
        if status.status != TransactionStatus.SUCCESS or not status.gateway_transaction_id:
            self.db.commit()
            raise PaymentNotConfirmedError()
        if status.amount is not None and status.amount != session.amount:
            logger.error(
                "PAYMENT_RECONCILIATION: checkout_session=%s amount mismatch gateway=%s ours=%s",
                session.id, status.amount, session.amount,
            )
            self.db.commit()
            raise PaymentNotConfirmedError()
        gateway_payment_id = status.gateway_transaction_id

        try:
            order_detail, _created = OrderService(self.db).checkout(
                session.user_id,
                CheckoutRequest(address_id=session.address_id, promo_code=session.promo_code),
                expected_total=session.amount,
            )
        except AppException as exc:
            # Paid, but the order cannot be placed (out of stock, price
            # changed, address deleted...). Give the money back.
            self.db.rollback()
            self._refund_and_fail(session.id, gateway_payment_id, str(exc))
            raise ConflictError(
                f"{exc} Your payment has been refunded."
            ) from exc

        payment = self._attach_paid_payment(session, order_detail.id, gateway_payment_id)
        result_payment = PaymentService(self.db, self.gateway).verify_payment(session.user_id, payment.id)

        session = (
            self.db.query(CheckoutSession)
            .filter(CheckoutSession.id == session.id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        session.status = "COMPLETED"
        session.order_id = order_detail.id
        session.completed_at = datetime.now(UTC)
        self.db.commit()

        order = OrderService(self.db).get_order_detail(session.user_id, order_detail.id)
        return OnlineCheckoutCompleteResponse(order=order, payment=result_payment)

    def _attach_paid_payment(self, session: CheckoutSession, order_id: int, gateway_payment_id: str) -> Payment:
        """Creates the Payment (+ its attempt) for the freshly placed order,
        pointing at the Razorpay order that was already paid. Idempotent."""
        existing = self.db.query(Payment).filter(Payment.order_id == order_id).first()
        if existing:
            return existing
        payment = Payment(
            order_id=order_id,
            payment_method="UPI",
            status=PaymentStatus.PROCESSING,
            amount=session.amount,
            currency=session.currency,
            gateway_name=session.gateway_name,
            gateway_order_id=session.gateway_order_id,
        )
        self.db.add(payment)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            return self.db.query(Payment).filter(Payment.order_id == order_id).one()
        self.db.add(
            PaymentTransaction(
                payment_id=payment.id,
                transaction_type="PAYMENT",
                status=TransactionStatus.INITIATED,
                amount=session.amount,
                currency=session.currency,
                gateway_name=session.gateway_name,
                gateway_transaction_id=gateway_payment_id,
                idempotency_key=PaymentService._new_idempotency_key(),
                initiated_at=datetime.now(UTC),
            )
        )
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def _refund_and_fail(self, session_id: int, gateway_payment_id: str, reason: str) -> None:
        session = (
            self.db.query(CheckoutSession)
            .filter(CheckoutSession.id == session_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        session.failure_reason = reason[:1000]
        try:
            self.gateway.refund_payment(
                gateway_order_id=session.gateway_order_id,
                gateway_transaction_id=gateway_payment_id,
                amount=session.amount,
                currency=session.currency,
                idempotency_key=PaymentService._new_idempotency_key(),
            )
            session.status = "REFUNDED"
        except Exception as exc:  # money is stuck: needs a human, never swallow quietly
            session.status = "REFUND_FAILED"
            logger.error(
                "PAYMENT_RECONCILIATION: checkout_session=%s paid but order failed (%s) and the "
                "automatic refund FAILED (%s) - refund payment %s manually",
                session.id, reason, exc, gateway_payment_id,
            )
        self.db.commit()

    def _response_for_order(self, user_id: int, order_id: int) -> OnlineCheckoutCompleteResponse:
        order = OrderService(self.db).get_order_detail(user_id, order_id)
        payment = self.db.query(Payment).filter(Payment.order_id == order_id).first()
        return OnlineCheckoutCompleteResponse(order=order, payment=PaymentResponse.model_validate(payment))
