"""Payment domain routes.

Three routers in this one file:
- `router`: customer-facing, CUSTOMER-only (create/get/retry/verify).
- `webhook_router`: the PNB gateway callback. No JWT - webhook
  authenticity is verified via the gateway's own signature scheme inside
  PaymentService.process_webhook, not FastAPI auth dependencies.
- `admin_router` (Phase 18, extended Phase 19): ADMIN-only payment list/
  detail plus refund review/approve/reject/process. Refunds are a payment
  concept, so they live here rather than a new file - reuses this domain's
  existing customer/admin per-router-RBAC split (see bulk_orders.py for the
  same pattern). OPERATIONS/HUB_STAFF are deliberately excluded: no existing
  business rule in this codebase grants either role financial/payment
  authority, and this module does not introduce one - a raw Payment record
  (gateway references included) is at least as sensitive as refund
  approval, which was already ADMIN-only.

  This router MUST be registered before `router` in api/v1/router.py - see
  that file's comment for the literal-vs-catch-all routing collision this
  avoids (GET /payments/admin, /payments/refunds vs GET /payments/{id}).

The webhook route is deliberately `async def` (every other route in this
codebase is sync `def`) because verifying the gateway signature requires
the EXACT raw request body, which Starlette only exposes via
`await request.body()`. The synchronous, DB-bound PaymentService call is
explicitly run via `run_in_threadpool` so it never blocks the event loop -
this keeps the one async route from silently behaving differently than
every sync route already does (each of which FastAPI already runs in a
threadpool automatically).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.roles import ADMIN, CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.dependencies.payments import get_payment_gateway
from app.models.user import User
from app.schemas.admin_payment import (
    AdminPaymentDetailResponse,
    AdminPaymentListResponse,
)
from app.schemas.admin_payment import MAX_PAGE_SIZE as ADMIN_MAX_PAGE_SIZE
from app.schemas.payment import (
    CreatePaymentRequest,
    PaymentInitiationResponse,
    PaymentResponse,
    WebhookAckResponse,
)
from app.schemas.refund import (
    MAX_PAGE_SIZE,
    AdminRefundListResponse,
    AdminRefundResponse,
    RejectRefundRequest,
)
from app.services.payment import PaymentService
from app.services.payment_gateway import PaymentGateway
from app.services.refund import RefundService

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])
webhook_router = APIRouter()
admin_router = APIRouter(dependencies=[Depends(require_roles(ADMIN))])


@router.post(
    "",
    response_model=PaymentInitiationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment for an order (UPI or COD)",
)
def create_payment(
    payload: CreatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> PaymentInitiationResponse:
    return PaymentService(db, gateway).create_payment(current_user.id, payload)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get a payment (must belong to the current user)",
)
def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> PaymentResponse:
    return PaymentService(db, gateway).get_payment(current_user.id, payment_id)


@router.post(
    "/{payment_id}/retry",
    response_model=PaymentInitiationResponse,
    summary="Start a new UPI attempt for a FAILED/EXPIRED payment",
)
def retry_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> PaymentInitiationResponse:
    return PaymentService(db, gateway).retry_payment(current_user.id, payment_id)


@router.post(
    "/{payment_id}/verify",
    response_model=PaymentResponse,
    summary="Reconcile payment status against the gateway (never trusts client claims)",
)
def verify_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> PaymentResponse:
    return PaymentService(db, gateway).verify_payment(current_user.id, payment_id)


@webhook_router.post(
    "/pnb",
    response_model=WebhookAckResponse,
    summary="PNB gateway webhook callback (no JWT - gateway signature verified internally)",
)
async def pnb_webhook(
    request: Request,
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> WebhookAckResponse:
    raw_body = await request.body()
    headers = dict(request.headers)

    await run_in_threadpool(
        PaymentService(db, gateway).process_webhook, raw_body, headers
    )
    return WebhookAckResponse()


# ---------------------------------------------------------------------------
# Admin: payment list/detail (Phase 19)
# ---------------------------------------------------------------------------


@admin_router.get(
    "/admin",
    response_model=AdminPaymentListResponse,
    summary="List/search/filter every payment on the platform (admin panel)",
)
def admin_list_payments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=ADMIN_MAX_PAGE_SIZE),
    status_: str | None = Query(default=None, alias="status"),
    payment_method: str | None = Query(default=None),
    order_id: int | None = Query(default=None, gt=0),
    date_from: datetime | None = Query(default=None, description="created_at >= this"),
    date_to: datetime | None = Query(default=None, description="created_at <= this"),
    q: str | None = Query(
        default=None, max_length=150, description="Order number, customer name/email, or gateway order id"
    ),
    db: Session = Depends(get_db),
) -> AdminPaymentListResponse:
    return PaymentService(db, None).admin_list_payments(
        page, page_size, status_, payment_method, order_id, date_from, date_to, q
    )


@admin_router.get(
    "/admin/{payment_id}",
    response_model=AdminPaymentDetailResponse,
    summary="Get the complete detail (incl. gateway attempt history) for any payment (admin panel)",
)
def admin_get_payment(payment_id: int, db: Session = Depends(get_db)) -> AdminPaymentDetailResponse:
    return PaymentService(db, None).admin_get_payment_detail(payment_id)


# ---------------------------------------------------------------------------
# Admin: refund review, approval, rejection, processing (Phase 18)
# ---------------------------------------------------------------------------


@admin_router.get(
    "/refunds",
    response_model=AdminRefundListResponse,
    summary="List refund requests, optionally filtered by status",
)
def admin_list_refunds(
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> AdminRefundListResponse:
    return RefundService(db).admin_list_refunds(status_, page, page_size)


@admin_router.get(
    "/refunds/{refund_id}",
    response_model=AdminRefundResponse,
    summary="Get one refund request",
)
def admin_get_refund(refund_id: int, db: Session = Depends(get_db)) -> AdminRefundResponse:
    return RefundService(db).admin_get_refund_or_404(refund_id)


@admin_router.post(
    "/refunds/{refund_id}/approve",
    response_model=AdminRefundResponse,
    summary="Approve a refund request (PENDING_APPROVAL -> APPROVED)",
)
def admin_approve_refund(
    refund_id: int,
    current_user: User = Depends(require_roles(ADMIN)),
    db: Session = Depends(get_db),
) -> AdminRefundResponse:
    return RefundService(db).approve_refund(refund_id, current_user.id)


@admin_router.post(
    "/refunds/{refund_id}/reject",
    response_model=AdminRefundResponse,
    summary="Reject a refund request (PENDING_APPROVAL -> REJECTED)",
)
def admin_reject_refund(
    refund_id: int,
    payload: RejectRefundRequest,
    current_user: User = Depends(require_roles(ADMIN)),
    db: Session = Depends(get_db),
) -> AdminRefundResponse:
    return RefundService(db).reject_refund(refund_id, current_user.id, payload.reason)


@admin_router.post(
    "/refunds/{refund_id}/process",
    response_model=AdminRefundResponse,
    summary="Process an approved refund through the payment gateway (APPROVED/FAILED -> PROCESSING)",
)
def admin_process_refund(
    refund_id: int,
    current_user: User = Depends(require_roles(ADMIN)),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> AdminRefundResponse:
    return RefundService(db, gateway).process_refund(refund_id, current_user.id)
