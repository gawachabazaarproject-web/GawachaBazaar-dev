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
