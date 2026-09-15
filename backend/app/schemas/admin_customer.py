"""Admin Customer Management schemas.

A "customer" is not a separate table - it is a `User` holding the existing
CUSTOMER role (see app/core/roles.py). This module never introduces a
parallel customer identity, status, or address system; every shape here is
either read directly off `User`/`Address`/`Order`/`PromotionRedemption` or
is a thin aggregate over them (order counts, spend totals). Order rows reuse
`AdminOrderListItemResponse` from admin_order.py verbatim (see
CustomerOrderListResponse below) rather than re-describing an order.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.address import AddressResponse
from app.schemas.admin_order import AdminOrderListResponse as CustomerOrderListResponse  # noqa: F401
from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100

CUSTOMER_ACCOUNT_STATUSES = ("ACTIVE", "INACTIVE", "SUSPENDED")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class CustomersDashboardResponse(BaseSchema):
    """Every figure is a real aggregate over `users`/`orders` - a metric is
    omitted entirely (never fabricated) if it cannot be computed reliably
    from existing data. `new_customers` uses a documented, non-authoritative
    30-day window (the same UI-heuristic convention as Inventory's
    LOW_STOCK_THRESHOLD) - it is a display convenience, not a stored
    business rule.
    """

    total_customers: int
    active_customers: int
    inactive_customers: int
    suspended_customers: int
    new_customers_last_30_days: int
    customers_with_orders: int
    customers_with_no_orders: int
    returning_customers: int
    average_order_value: Decimal | None
    total_realized_revenue: Decimal


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class AdminCustomerListItemResponse(BaseSchema):
    """One row of the admin customer table. `total_spend`/`average_order_value`
    are computed only over COMPLETED (delivered) orders - the only orders
    that represent realized revenue; a PENDING or CANCELLED order's
    total_amount was never actually collected. `phone` is masked unless the
    caller holds `customers.view_sensitive` (see CustomerService).
    """

    id: int
    name: str
    email: str
    phone: str
    account_status: str
    order_count: int
    completed_order_count: int
    total_spend: Decimal
    average_order_value: Decimal | None
    last_order_at: datetime | None
    created_at: datetime


class AdminCustomerListResponse(BaseSchema):
    items: list[AdminCustomerListItemResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class CustomerOrderSummaryResponse(BaseSchema):
    """Aggregate order/spend figures for one customer - computed server-
    side from `orders`, never assembled from a full order list fetched into
    the frontend.
    """

    total_orders: int
    completed_orders: int
    cancelled_orders: int
    pending_orders: int
    total_spend: Decimal
    average_order_value: Decimal | None
    first_order_at: datetime | None
    last_order_at: datetime | None
    promotion_redemptions_count: int


class PendingContactChangeResponse(BaseSchema):
    """Surfaced on the customer detail response so the admin UI can show
    "verification pending" instead of a blank edit form - never exposes the
    code itself, only what was requested and when it expires."""

    field: str
    new_value: str
    expires_at: datetime
    attempts: int


class AdminCustomerDetailResponse(BaseSchema):
    id: int
    name: str
    email: str
    phone: str
    account_status: str
    roles: list[str]
    is_bulk_customer: bool
    created_at: datetime
    updated_at: datetime
    summary: CustomerOrderSummaryResponse
    addresses: list[AddressResponse]
    pending_email_change: PendingContactChangeResponse | None = None
    pending_phone_change: PendingContactChangeResponse | None = None


# ---------------------------------------------------------------------------
# Promotions (customer-scoped redemption rows - Customers never recomputes a
# discount, only displays the same PromotionRedemption rows Promotions owns)
# ---------------------------------------------------------------------------


class CustomerPromotionRedemptionRowResponse(BaseSchema):
    id: int
    promotion_id: int
    promotion_name: str
    promotion_code: str | None
    order_id: int
    order_number: str
    discount_amount: Decimal
    status: str
    redeemed_at: datetime


class CustomerPromotionRedemptionListResponse(BaseSchema):
    items: list[CustomerPromotionRedemptionRowResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class CustomerTimelineEventResponse(BaseSchema):
    """One real business event, sourced directly from an existing table's
    own timestamp column - never a synthesized or invented event."""

    event_type: str
    occurred_at: datetime
    title: str
    description: str | None
    resource_type: str | None
    resource_id: int | None


class CustomerTimelineResponse(BaseSchema):
    items: list[CustomerTimelineEventResponse]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


class CreateCustomerNoteRequest(BaseSchema):
    note: str = Field(..., min_length=1, max_length=4000)


class UpdateCustomerNoteRequest(BaseSchema):
    note: str = Field(..., min_length=1, max_length=4000)


class CustomerNoteResponse(BaseSchema):
    id: int
    user_id: int
    note: str
    author_name: str
    created_at: datetime
    updated_at: datetime


class CustomerNoteListResponse(BaseSchema):
    items: list[CustomerNoteResponse]


# ---------------------------------------------------------------------------
# Account status
# ---------------------------------------------------------------------------


class UpdateCustomerStatusRequest(BaseSchema):
    status: str = Field(..., description="ACTIVE, INACTIVE, or SUSPENDED")
    reason: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Contact change (verification-backed email/phone edit)
# ---------------------------------------------------------------------------


class RequestContactChangeRequest(BaseSchema):
    field: str = Field(..., description="EMAIL or PHONE")
    new_value: str = Field(..., min_length=3, max_length=255)


class ConfirmContactChangeRequest(BaseSchema):
    field: str = Field(..., description="EMAIL or PHONE")
    code: str = Field(..., min_length=6, max_length=6)
