"""Razorpay adapter for the PaymentGateway protocol (payment_gateway.py).

Online payments use Razorpay Standard Checkout with the Orders API:

1. `initiate_payment` creates ONE Razorpay order per Payment obligation
   (POST /v1/orders). A retry reuses that same order - a Razorpay order
   accepts repeated payment attempts until one is captured, which matches
   PaymentService's "gateway_order_id is set once per payment and reused
   across retries" rule exactly. Webhook/verify lookups by order id then
   always find the right Payment.
2. The client opens Razorpay Checkout with our public key id + that order
   id. On success Checkout hands the client `razorpay_payment_id` and a
   `razorpay_signature`; the client posts them to
   POST /payments/{id}/confirm, which checks the signature
   (`verify_checkout_signature`) and then asks Razorpay for the
   authoritative order state (`query_status`) - the client's claim alone
   never marks anything PAID.
3. Signed webhooks (payment.captured / order.paid) are the source of truth
   when the app is closed before step 2 finishes.

Status mapping - a Razorpay payment *attempt* failing is NOT a terminal
failure of our Payment: the customer can simply try again in the same
Checkout against the same order, and a later capture must still land.
So only `captured`/`refunded` map to SUCCESS; everything else stays
non-terminal (INITIATED/PROCESSING). Automatic capture must be enabled on
the Razorpay account (Dashboard -> Account & Settings -> Capture) - an
`authorized` payment is money on hold, not money received.

Amounts: Razorpay speaks integer paise; this module is the only place that
converts, in both directions.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from decimal import Decimal

import httpx

from app.services.payment_gateway import (
    GatewayConnectionError,
    GatewayError,
    GatewayInitiateResult,
    GatewayRefundEvent,
    GatewayRefundResult,
    GatewayRejectedError,
    GatewayStatusResult,
    GatewayTimeoutError,
    GatewayWebhookEvent,
    WebhookEventIgnored,
    WebhookParseError,
)
from app.services.payment_state import TransactionStatus

DEFAULT_BASE_URL = "https://api.razorpay.com/v1"

_CAPTURED_STATUSES = {"captured", "refunded"}

# Webhook events this integration acts on. Everything else Razorpay may be
# configured to send (refund.*, dispute.*, ...) is acknowledged and ignored.
_WEBHOOK_STATUS: dict[str, TransactionStatus] = {
    "payment.captured": TransactionStatus.SUCCESS,
    "order.paid": TransactionStatus.SUCCESS,
    "payment.authorized": TransactionStatus.PROCESSING,
    # A failed attempt - the customer may still retry in Checkout, see the
    # module docstring for why this is deliberately not FAILED.
    "payment.failed": TransactionStatus.PROCESSING,
}

# Refund outcome webhooks - see GatewayRefundEvent. refund.created is
# ignored: the refund call itself already told us it exists.
_REFUND_WEBHOOK_STATUS: dict[str, TransactionStatus] = {
    "refund.processed": TransactionStatus.SUCCESS,
    "refund.failed": TransactionStatus.FAILED,
}

_REFUND_STATUS: dict[str, TransactionStatus] = {
    "processed": TransactionStatus.SUCCESS,
    "pending": TransactionStatus.PROCESSING,
    "created": TransactionStatus.PROCESSING,
    "failed": TransactionStatus.FAILED,
}


def to_paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


def from_paise(value: int | str) -> Decimal:
    return (Decimal(int(value)) / 100).quantize(Decimal("0.01"))


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


class RazorpayGateway:
    gateway_name = "RAZORPAY"

    def __init__(
        self,
        *,
        key_id: str,
        key_secret: str,
        webhook_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        # Injectable for tests (httpx.MockTransport) - production uses the
        # default network transport.
        self._transport = transport

    # ------------------------------------------------------------------
    # Capability / config
    # ------------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self._key_id and self._key_secret)

    @property
    def checkout_key_id(self) -> str:
        """Public key id the client passes to Razorpay Checkout. Never the
        secret."""
        return self._key_id

    @property
    def is_test_mode(self) -> bool:
        return self._key_id.startswith("rzp_test_")

    # ------------------------------------------------------------------
    # PaymentGateway protocol
    # ------------------------------------------------------------------

    def initiate_payment(
        self,
        *,
        reference: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
        existing_gateway_order_id: str | None = None,
    ) -> GatewayInitiateResult:
        if existing_gateway_order_id:
            # Retry: keep using the same order. If it was already paid in
            # the meantime (e.g. a capture whose webhook is still in
            # flight), report that instead of asking the customer to pay
            # twice.
            status = self.query_status(
                gateway_order_id=existing_gateway_order_id, gateway_transaction_id=None
            )
            return GatewayInitiateResult(
                gateway_order_id=existing_gateway_order_id,
                gateway_transaction_id=status.gateway_transaction_id,
                status=(
                    TransactionStatus.SUCCESS
                    if status.status == TransactionStatus.SUCCESS
                    else TransactionStatus.INITIATED
                ),
                raw_response=status.raw_response,
            )

        try:
            order = self._request(
                "POST",
                "/orders",
                payload={
                    "amount": to_paise(amount),
                    "currency": currency,
                    "receipt": reference[:40],
                    "notes": {"reference": reference, "idempotency_key": idempotency_key},
                },
            )
        except GatewayRejectedError:
            raise
        except GatewayError as exc:
            # Unlike a refund or a status check, creating a Razorpay order
            # moves no money: a customer can only pay into an order whose id
            # reached their app, and this one never did. Even if Razorpay
            # created it before the connection failed, nobody can pay it and
            # no webhook can arrive for it. So an "unknown outcome" here is
            # safe to report as a definite failure - the Payment becomes
            # FAILED and retryable instead of stuck PROCESSING with no order
            # id to verify against. (The existing-order branch above keeps
            # the unknown-outcome semantics: that order may already be paid.)
            raise GatewayRejectedError(f"Could not create the Razorpay order: {exc}") from exc
        if order.get("amount") != to_paise(amount) or order.get("currency") != currency:
            # Should be impossible - but never hand the customer a checkout
            # for a different amount than the order total.
            raise GatewayRejectedError("Razorpay order amount/currency does not match the request.")
        return GatewayInitiateResult(
            gateway_order_id=order["id"],
            gateway_transaction_id=None,
            status=TransactionStatus.INITIATED,
            raw_response=order,
        )

    def query_status(
        self,
        *,
        gateway_order_id: str,
        gateway_transaction_id: str | None,
    ) -> GatewayStatusResult:
        """Order-level truth: which of this order's payment attempts (if
        any) was captured. `gateway_transaction_id` is deliberately not
        trusted on its own - only a payment that Razorpay lists under THIS
        order can mark it paid."""
        body = self._request("GET", f"/orders/{gateway_order_id}/payments")
        items = body.get("items") or []
        captured = next((p for p in items if p.get("status") in _CAPTURED_STATUSES), None)
        if captured is not None:
            return GatewayStatusResult(
                gateway_order_id=gateway_order_id,
                gateway_transaction_id=captured["id"],
                status=TransactionStatus.SUCCESS,
                amount=from_paise(captured["amount"]),
                currency=captured.get("currency"),
                raw_response=captured,
            )
        latest = items[0] if items else None  # Razorpay lists newest first
        return GatewayStatusResult(
            gateway_order_id=gateway_order_id,
            gateway_transaction_id=None,
            status=TransactionStatus.PROCESSING if items else TransactionStatus.INITIATED,
            raw_response=latest,
            failure_reason=(latest or {}).get("error_description"),
        )

    def refund_payment(
        self,
        *,
        gateway_order_id: str,
        gateway_transaction_id: str | None,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> GatewayRefundResult:
        payment_id = gateway_transaction_id
        if not (payment_id and payment_id.startswith("pay_")):
            status = self.query_status(gateway_order_id=gateway_order_id, gateway_transaction_id=None)
            if status.status != TransactionStatus.SUCCESS or not status.gateway_transaction_id:
                raise GatewayRejectedError("This order has no captured Razorpay payment to refund.")
            payment_id = status.gateway_transaction_id

        refund = self._request(
            "POST",
            f"/payments/{payment_id}/refund",
            payload={
                "amount": to_paise(amount),
                "speed": "normal",
                "notes": {"idempotency_key": idempotency_key},
            },
        )
        status = _REFUND_STATUS.get(str(refund.get("status")), TransactionStatus.PROCESSING)
        return GatewayRefundResult(
            gateway_refund_id=refund.get("id"),
            status=status,
            raw_response=refund,
            failure_reason=refund.get("error_description") if status == TransactionStatus.FAILED else None,
        )

    def query_refund(self, *, gateway_refund_id: str) -> GatewayRefundResult:
        refund = self._request("GET", f"/refunds/{gateway_refund_id}")
        status = _REFUND_STATUS.get(str(refund.get("status")), TransactionStatus.PROCESSING)
        return GatewayRefundResult(
            gateway_refund_id=refund.get("id"),
            status=status,
            raw_response=refund,
            failure_reason=refund.get("error_description") if status == TransactionStatus.FAILED else None,
        )

    def verify_webhook_signature(self, *, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        """X-Razorpay-Signature = hex HMAC-SHA256(webhook secret, raw body)."""
        signature = _header(headers, "x-razorpay-signature")
        if not self._webhook_secret or not signature:
            return False
        expected = hmac.new(self._webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook_event(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> GatewayWebhookEvent | GatewayRefundEvent:
        try:
            payload = json.loads(raw_body)
            event_type = str(payload["event"])
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
            raise WebhookParseError("Not a Razorpay webhook payload.") from exc

        # Razorpay sends a unique id per delivery in X-Razorpay-Event-Id;
        # fall back to a body hash so re-deliveries still dedupe.
        event_id = _header(headers, "x-razorpay-event-id") or hashlib.sha256(raw_body).hexdigest()

        refund_status = _REFUND_WEBHOOK_STATUS.get(event_type)
        if refund_status is not None:
            refund = ((payload.get("payload") or {}).get("refund") or {}).get("entity") or {}
            if not refund.get("id"):
                raise WebhookParseError(f"{event_type} payload has no refund id.")
            return GatewayRefundEvent(
                event_id=event_id,
                event_type=event_type,
                gateway_refund_id=refund["id"],
                status=refund_status,
                raw_response=payload,
            )

        status = _WEBHOOK_STATUS.get(event_type)
        if status is None:
            raise WebhookEventIgnored(event_type)

        entities = payload.get("payload") or {}
        payment = (entities.get("payment") or {}).get("entity") or {}
        order = (entities.get("order") or {}).get("entity") or {}
        gateway_order_id = payment.get("order_id") or order.get("id")
        if not gateway_order_id:
            raise WebhookParseError(f"{event_type} payload has no order id.")

        raw_amount = payment.get("amount", order.get("amount_paid"))
        return GatewayWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            gateway_order_id=gateway_order_id,
            gateway_transaction_id=payment.get("id"),
            status=status,
            amount=from_paise(raw_amount) if raw_amount is not None else None,
            currency=payment.get("currency") or order.get("currency"),
            raw_response=payload,
        )

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def verify_checkout_signature(self, *, gateway_order_id: str, gateway_payment_id: str, signature: str) -> bool:
        """razorpay_signature = hex HMAC-SHA256(key secret, "order_id|payment_id")."""
        if not self._key_secret or not signature:
            return False
        message = f"{gateway_order_id}|{gateway_payment_id}".encode()
        expected = hmac.new(self._key_secret.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        try:
            with httpx.Client(
                base_url=self._base_url,
                auth=(self._key_id, self._key_secret),
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, json=payload)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(f"Razorpay {method} {path} timed out.") from exc
        except httpx.TransportError as exc:
            raise GatewayConnectionError(f"Could not reach Razorpay: {exc}") from exc

        if response.status_code >= 500:
            # Razorpay-side failure: the outcome of a write is unknown.
            raise GatewayError(f"Razorpay {method} {path} returned {response.status_code}.")
        try:
            body = response.json()
        except ValueError as exc:
            raise GatewayError(f"Razorpay {method} {path} returned a non-JSON body.") from exc
        if response.status_code >= 400:
            error = body.get("error") or {}
            raise GatewayRejectedError(
                error.get("description") or f"Razorpay rejected {method} {path} ({response.status_code})."
            )
        return body
