"""Payment gateway interface and the PNB adapter boundary.

PNBGateway is a deliberately incomplete, clearly-labeled adapter: no PNB
merchant integration specification exists anywhere in this repository (a
full-repository search found none before this phase began). Per the
project's explicit instruction for this situation, this module:

1. Defines a small `PaymentGateway` protocol our business logic depends on
   (app/services/payment.py never imports PNB-specific types).
2. Implements `PNBGateway.initiate_payment` / `query_status` /
   `refund_payment` (Phase 18) as `NotImplementedError` - we do not know
   PNB's actual request/response shape, authentication scheme, or endpoint
   URLs, and inventing them would misrepresent this as a working
   integration.
3. Implements `PNBGateway.verify_webhook_signature` / `parse_webhook_event`
   using a clearly-labeled PLACEHOLDER scheme (HMAC-SHA256 over the raw
   body), so the webhook safety pipeline (dedup, ordering, concurrency -
   the actual point of Phase 14) is fully exercisable end-to-end in tests.
   This is a generic, industry-common webhook-signing convention (the kind
   used by many providers), presented honestly as OUR placeholder, not as
   a claim about PNB's real algorithm.

DO NOT wire PNBGateway into a real base_url and call it in production
before the official PNB merchant integration specification is obtained and
this adapter is rewritten against it. See
docs/architecture/PHASE_14_PAYMENTS.md - "PNB Integration Boundary".
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.services.payment_state import TransactionStatus


class WebhookParseError(Exception):
    """Raised when a webhook body cannot be parsed into a GatewayWebhookEvent."""


class GatewayError(Exception):
    """Base class for all gateway-call failures.

    Deliberately NOT a single flat exception: PaymentService must react
    differently depending on WHICH of these is raised (see §13 of the
    Phase 14 spec - a timeout is never treated the same as a definitive
    rejection). Catching plain `GatewayError` broadly for logging is fine;
    deciding the payment's fate must switch on the specific subclass.
    """


class GatewayTimeoutError(GatewayError):
    """The gateway call timed out. The payment MAY have succeeded on PNB's
    side despite us never receiving a response - outcome is UNKNOWN.
    PaymentService must leave the payment in PROCESSING, never FAILED.
    """


class GatewayConnectionError(GatewayError):
    """Could not reach the gateway at all (DNS/connection refused/etc).
    Same UNKNOWN-outcome handling as GatewayTimeoutError.
    """


class GatewayRejectedError(GatewayError):
    """The gateway synchronously and definitively rejected the request
    (e.g. validation error, before any order/transaction was created on
    its side). Safe to mark the attempt FAILED - nothing is unresolved.
    """


@dataclass(frozen=True)
class GatewayInitiateResult:
    gateway_order_id: str
    gateway_transaction_id: str | None
    status: TransactionStatus
    raw_response: dict | None = None
    # Present only if the gateway provides something the client needs
    # directly (e.g. a UPI intent URI/QR payload or a hosted session
    # token). Never a secret.
    payment_session_token: str | None = None
    upi_intent_uri: str | None = None


@dataclass(frozen=True)
class GatewayRefundResult:
    gateway_refund_id: str | None
    status: TransactionStatus
    raw_response: dict | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class GatewayStatusResult:
    gateway_order_id: str
    gateway_transaction_id: str | None
    status: TransactionStatus
    amount: Decimal | None = None
    currency: str | None = None
    raw_response: dict | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class GatewayWebhookEvent:
    event_id: str
    event_type: str
    gateway_order_id: str | None
    gateway_transaction_id: str | None
    status: TransactionStatus
    amount: Decimal | None = None
    currency: str | None = None
    raw_response: dict | None = None


class PaymentGateway(Protocol):
    """The one boundary PaymentService depends on. Kept deliberately small -
    no factory-of-factories, no generic gateway framework.
    """

    gateway_name: str

    def initiate_payment(
        self,
        *,
        reference: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> GatewayInitiateResult: ...

    def query_status(
        self,
        *,
        gateway_order_id: str,
        gateway_transaction_id: str | None,
    ) -> GatewayStatusResult: ...

    def refund_payment(
        self,
        *,
        gateway_order_id: str,
        gateway_transaction_id: str | None,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> GatewayRefundResult: ...

    def verify_webhook_signature(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> bool: ...

    def parse_webhook_event(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> GatewayWebhookEvent: ...


_NOT_IMPLEMENTED_MESSAGE = (
    "PNB merchant API contract for '{operation}' is not yet available. "
    "No PNB technical integration specification exists in this repository. "
    "See docs/architecture/PHASE_14_PAYMENTS.md - PNB Integration Boundary. "
    "This adapter is a structural placeholder, not a working PNB integration."
)

# PLACEHOLDER webhook signature header name - not confirmed against any
# real PNB specification.
_SIGNATURE_HEADER = "x-pnb-signature"


class PNBGateway:
    """PNB adapter boundary. See module docstring for exactly what is and
    is not implemented, and why.
    """

    gateway_name = "PNB"

    def __init__(
        self,
        *,
        merchant_id: str,
        webhook_secret: str,
        base_url: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._merchant_id = merchant_id
        self._webhook_secret = webhook_secret
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    def initiate_payment(
        self,
        *,
        reference: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> GatewayInitiateResult:
        raise NotImplementedError(
            _NOT_IMPLEMENTED_MESSAGE.format(operation="initiate_payment")
        )

    def query_status(
        self,
        *,
        gateway_order_id: str,
        gateway_transaction_id: str | None,
    ) -> GatewayStatusResult:
        raise NotImplementedError(
            _NOT_IMPLEMENTED_MESSAGE.format(operation="query_status")
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
        """Phase 18: no PNB refund API specification exists in this
        repository either, so this follows initiate_payment/query_status's
        own precedent exactly - a clearly labeled structural placeholder,
        not a working refund integration. See the module docstring.
        """
        raise NotImplementedError(
            _NOT_IMPLEMENTED_MESSAGE.format(operation="refund_payment")
        )

    def verify_webhook_signature(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> bool:
        """PLACEHOLDER: HMAC-SHA256 over the exact raw request body, compared
        in constant time. Header name and algorithm are NOT confirmed
        against any real PNB specification - replace once available.
        """
        if not self._webhook_secret:
            return False
        signature = None
        for key, value in headers.items():
            if key.lower() == _SIGNATURE_HEADER:
                signature = value
                break
        if not signature:
            return False

        expected = hmac.new(
            self._webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook_event(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> GatewayWebhookEvent:
        """PLACEHOLDER payload shape - NOT confirmed against any real PNB
        specification. Only called after verify_webhook_signature has
        already returned True.
        """
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WebhookParseError("Webhook body is not valid JSON.") from exc

        try:
            event_id = str(payload["event_id"])
            event_type = str(payload["event_type"])
            raw_status = str(payload["status"]).upper()
        except (KeyError, TypeError) as exc:
            raise WebhookParseError(
                "Webhook payload is missing a required field."
            ) from exc

        try:
            status = TransactionStatus(raw_status)
        except ValueError as exc:
            raise WebhookParseError(
                f"Webhook payload has an unrecognized status: {raw_status!r}"
            ) from exc

        amount = None
        if payload.get("amount") is not None:
            try:
                amount = Decimal(str(payload["amount"]))
            except Exception as exc:  # noqa: BLE001 - any parse failure is a WebhookParseError
                raise WebhookParseError("Webhook payload has an invalid amount.") from exc

        return GatewayWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            gateway_order_id=payload.get("gateway_order_id"),
            gateway_transaction_id=payload.get("gateway_transaction_id"),
            status=status,
            amount=amount,
            currency=payload.get("currency"),
            raw_response=payload,
        )
