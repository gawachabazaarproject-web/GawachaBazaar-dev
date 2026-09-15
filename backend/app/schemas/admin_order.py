"""Admin-facing order schemas.

Kept in a separate module from `schemas/order.py` rather than added
directly to it, purely to avoid a circular import: these types embed
`PaymentResponse` / `FulfillmentResponse` / `AdminRefundResponse`, and
`schemas/fulfillment.py` already imports FROM `schemas/order.py` (for
`OrderAddressResponse`/`OrderItemResponse`) - `order.py` importing back
from `fulfillment.py` would cycle. Every field here is either copied
verbatim from an existing customer/admin schema or newly added; nothing
recomputes a value the backend doesn't already compute (see
`OrderService.admin_list_orders`/`admin_get_order_detail`).
"""

from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema
from app.schemas.fulfillment import FulfillmentResponse
from app.schemas.order import OrderDetailResponse
from app.schemas.payment import PaymentResponse
from app.schemas.refund import AdminRefundResponse

MAX_PAGE_SIZE = 100


class AdminOrderListItemResponse(BaseSchema):
    """One row of the admin order table - enough to render the list
    without a per-row follow-up request. `payment_status`/`method` and
    `fulfillment_status` are null when that sub-resource doesn't exist yet
    (e.g. a brand-new PENDING order with no Payment row) - never a
    fabricated default status.
    """

    id: int
    order_number: str
    status: str
    total_amount: Decimal
    discount_amount: Decimal
    applied_promo_code: str | None
    currency: str
    placed_at: datetime
    customer_id: int
    customer_name: str
    customer_email: str
    item_count: int
    payment_status: str | None
    payment_method: str | None
    fulfillment_status: str | None
    delivery_partner_user_id: int | None


class AdminOrderListResponse(BaseSchema):
    items: list[AdminOrderListItemResponse]
    page: int
    page_size: int
    total: int


class AdminOrderDetailResponse(OrderDetailResponse):
    """Everything the customer-facing OrderDetailResponse has, plus the
    operational picture an admin needs: who cancelled it (if cancelled),
    who the customer is, and the linked payment/fulfillment/refund in one
    response instead of four separate ownership-scoped customer endpoints
    an admin can't call for someone else's order.
    """

    cancelled_by_user_id: int | None
    customer_id: int
    customer_name: str
    customer_email: str
    customer_phone: str
    payment: PaymentResponse | None
    fulfillment: FulfillmentResponse | None
    refund: AdminRefundResponse | None
