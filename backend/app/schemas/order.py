"""Order/checkout domain schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100


class CheckoutRequest(BaseSchema):
    """No price/total/currency/user_id/order_number/status accepted - all
    are computed or authenticated server-side.
    """

    address_id: int = Field(..., gt=0)


class OrderItemResponse(BaseSchema):
    id: int
    variant_id: int
    product_name: str
    variant_name: str
    sku: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal


class OrderAddressResponse(BaseSchema):
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str
    latitude: Decimal | None
    longitude: Decimal | None


class OrderResponse(BaseSchema):
    id: int
    order_number: str
    status: str
    total_amount: Decimal
    currency: str
    placed_at: datetime
    created_at: datetime


class OrderDetailResponse(OrderResponse):
    items: list[OrderItemResponse]
    address: OrderAddressResponse | None


class OrderListResponse(BaseSchema):
    items: list[OrderResponse]
    page: int
    page_size: int
    total: int
