"""Admin-facing payment schemas.

Kept in a separate module from `schemas/payment.py`, mirroring
`schemas/admin_order.py`'s reasoning: these types embed `AdminRefundResponse`
and are populated from a join across `Payment`/`Order`/`User`, which belongs
with the admin surface, not the customer-facing payment schemas imported by
the CUSTOMER-only router in api/v1/payments.py. Every field is read straight
off `Payment`/`PaymentTransaction`/`Refund` - nothing here is recomputed or
gateway-derived beyond what those rows already store (see
app/services/payment.py's `admin_list_payments`/`admin_get_payment_detail`).
"""

from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema
from app.schemas.refund import AdminRefundResponse

MAX_PAGE_SIZE = 100


class PaymentTransactionResponse(BaseSchema):
    """One gateway attempt (PAYMENT or REFUND) - see
    app/models/payment_transaction.py. `gateway_response` is deliberately
    excluded: it is a raw, unbounded gateway payload (truncated to 8000
    chars at write time) meant for reconciliation debugging, not a stable
    admin-UI field.
    """

    id: int
    transaction_type: str
    status: str
    amount: Decimal
    currency: str
    gateway_name: str | None
    gateway_transaction_id: str | None
    failure_reason: str | None
    initiated_at: datetime
    completed_at: datetime | None


class AdminPaymentListItemResponse(BaseSchema):
    id: int
    order_id: int
    order_number: str
    customer_id: int
    customer_name: str
    customer_email: str
    payment_method: str
    status: str
    amount: Decimal
    currency: str
    gateway_name: str | None
    gateway_order_id: str | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminPaymentListResponse(BaseSchema):
    items: list[AdminPaymentListItemResponse]
    page: int
    page_size: int
    total: int


class AdminPaymentDetailResponse(AdminPaymentListItemResponse):
    """Adds the full attempt history and the linked refund (if any) - the
    two things an admin actually needs to diagnose a stuck/failed payment,
    neither of which is derivable from the list row.
    """

    transactions: list[PaymentTransactionResponse]
    refund: AdminRefundResponse | None
