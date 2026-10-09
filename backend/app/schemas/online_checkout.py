"""Pay-first online checkout schemas (see app/services/checkout_session.py)."""

from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.order import OrderDetailResponse
from app.schemas.payment import PaymentResponse


class StartOnlineCheckoutRequest(BaseSchema):
    """No amount accepted - the server prices the cart itself."""

    address_id: int = Field(..., gt=0)
    promo_code: str | None = Field(default=None, max_length=50)


class OnlineCheckoutResponse(BaseSchema):
    """Everything the client needs to open Razorpay Checkout BEFORE any
    order exists. `key_id` is the gateway's PUBLIC key - no secret."""

    session_id: int
    gateway: str
    key_id: str
    gateway_order_id: str
    amount: Decimal
    amount_minor: int = Field(..., description="Amount in paise.")
    currency: str
    merchant_name: str
    description: str
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    test_mode: bool


class OnlineCheckoutCompleteResponse(BaseSchema):
    order: OrderDetailResponse
    payment: PaymentResponse
