"""Refund domain schemas.

Client never supplies amount, currency, status, or approval decisions -
all server-derived (see app/services/refund.py). The only client input
anywhere in this domain is an admin's rejection reason.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100


class RefundResponse(BaseSchema):
    """Customer-facing: enough to know the refund exists and its status,
    nothing about internal approval/gateway detail.
    """

    id: int
    order_id: int
    status: str
    amount: Decimal
    currency: str
    requested_at: datetime
    created_at: datetime
    updated_at: datetime


class AdminRefundResponse(RefundResponse):
    """Ops-facing: adds approval/rejection audit fields never shown to
    the customer.
    """

    payment_id: int
    approved_by_user_id: int | None
    approved_at: datetime | None
    rejection_reason: str | None
    processed_at: datetime | None


class AdminRefundListResponse(BaseSchema):
    items: list[AdminRefundResponse]
    page: int
    page_size: int
    total: int


class RejectRefundRequest(BaseSchema):
    reason: str | None = Field(default=None, max_length=500)
