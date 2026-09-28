"""Payment domain schemas.

Client controls only order_id and payment_method - amount, currency,
status, gateway references, and order confirmation are always server- or
gateway-authoritative. See app/services/payment.py.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

PaymentMethod = Literal["UPI", "COD"]


class CreatePaymentRequest(BaseSchema):
    order_id: int = Field(..., gt=0)
    payment_method: PaymentMethod


class PaymentResponse(BaseSchema):
    id: int
    order_id: int
    payment_method: str
    status: str
    amount: Decimal
    currency: str
    gateway_name: str | None
    gateway_order_id: str | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentInitiationResponse(PaymentResponse):
    """Returned only from the initiation/retry call - carries ephemeral,
    client-actionable gateway data that is not meaningful on later reads.
    """

    payment_session_token: str | None = None
    upi_intent_uri: str | None = None


class WebhookAckResponse(BaseSchema):
    received: bool = True


class PaymentCheckoutResponse(BaseSchema):
    """Everything the client needs to open the gateway's hosted checkout
    (Razorpay Standard Checkout) for an existing online payment. `key_id`
    is the gateway's PUBLIC key - no secret is ever included."""

    payment_id: int
    order_id: int
    gateway: str
    key_id: str
    gateway_order_id: str
    amount: Decimal
    amount_minor: int = Field(..., description="Amount in the currency's smallest unit (paise).")
    currency: str
    merchant_name: str
    description: str
    customer_name: str
    customer_email: str
    customer_phone: str
    test_mode: bool


class ConfirmCheckoutRequest(BaseSchema):
    """The three values Razorpay Checkout hands the client on success,
    passed through unchanged. The signature is verified server-side and the
    order is then re-checked against Razorpay - the client's claim alone
    never marks a payment PAID."""

    razorpay_order_id: str = Field(..., min_length=1, max_length=64)
    razorpay_payment_id: str = Field(..., min_length=1, max_length=64)
    razorpay_signature: str = Field(..., min_length=1, max_length=256)
