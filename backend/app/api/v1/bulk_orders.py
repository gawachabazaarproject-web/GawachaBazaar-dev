"""Bulk & custom commerce routes.

Three role surfaces in one router, matching Phase 16's per-route (not
router-wide) RBAC style since they differ per endpoint:
  - CUSTOMER: profile, own requests, accept.
  - ADMIN/OPERATIONS: review, quote, convert, admin listing/detail.
    HUB_STAFF is deliberately excluded - bulk/custom pricing and
    conversion are commercial decisions, not warehouse-floor operations
    (contrast with suppliers.py, where HUB_STAFF does have access).

No endpoint accepts a client-supplied status, price, or quote-version id
for the operative action - accept always targets the current SENT
version, convert always uses the ACCEPTED version, both resolved
server-side. `send`/`reject` DO take a `version_id` in the URL since
they're explicit admin actions on a specific DRAFT/SENT version, but the
service still verifies it belongs to this request's own quote.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, CUSTOMER, OPERATIONS
from app.dependencies.auth import require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.bulk_order import (
    MAX_PAGE_SIZE,
    AdminBulkOrderRequestListResponse,
    AdminBulkOrderRequestResponse,
    BulkCustomerProfileResponse,
    BulkOrderRequestListResponse,
    BulkOrderRequestResponse,
    CreateBulkOrderRequestRequest,
    CreateQuoteVersionRequest,
    QuoteResponse,
    ReviewBulkOrderRequestRequest,
    UpdateBulkOrderRequestStatusRequest,
    UpsertBulkCustomerProfileRequest,
    VariantAvailabilityResponse,
)
from app.schemas.order import OrderDetailResponse
from app.services.bulk_order import BulkOrderService

customer_router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])
admin_router = APIRouter(dependencies=[Depends(require_roles(ADMIN, OPERATIONS))])


# ---------------------------------------------------------------------------
# Customer: bulk customer profile
# ---------------------------------------------------------------------------


@customer_router.put(
    "/profile",
    response_model=BulkCustomerProfileResponse,
    summary="Create or update the current user's bulk customer profile",
)
def upsert_bulk_customer_profile(
    payload: UpsertBulkCustomerProfileRequest,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkCustomerProfileResponse:
    return BulkOrderService(db).upsert_profile(current_user.id, payload)


@customer_router.get(
    "/profile",
    response_model=BulkCustomerProfileResponse,
    summary="Get the current user's bulk customer profile",
)
def get_bulk_customer_profile(
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkCustomerProfileResponse:
    return BulkOrderService(db).get_profile_or_404(current_user.id)


# ---------------------------------------------------------------------------
# Customer: requests
# ---------------------------------------------------------------------------


@customer_router.post(
    "/requests",
    response_model=BulkOrderRequestResponse,
    status_code=201,
    summary="Submit a bulk/custom order request (never creates an Order)",
)
def create_bulk_order_request(
    payload: CreateBulkOrderRequestRequest,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkOrderRequestResponse:
    return BulkOrderService(db).create_request(current_user.id, payload)


@customer_router.get(
    "/requests",
    response_model=BulkOrderRequestListResponse,
    summary="List the current user's bulk/custom order requests",
)
def list_bulk_order_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkOrderRequestListResponse:
    return BulkOrderService(db).list_requests(current_user.id, page, page_size)


@customer_router.get(
    "/requests/{request_id}",
    response_model=BulkOrderRequestResponse,
    summary="Get one of the current user's bulk/custom order requests",
)
def get_bulk_order_request(
    request_id: int,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkOrderRequestResponse:
    return BulkOrderService(db).get_request_detail(current_user.id, request_id)


@customer_router.post(
    "/requests/{request_id}/cancel",
    response_model=BulkOrderRequestResponse,
    summary="Cancel one of the current user's own requests",
)
def cancel_bulk_order_request(
    request_id: int,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkOrderRequestResponse:
    return BulkOrderService(db).cancel_request(current_user.id, request_id)


@customer_router.get(
    "/requests/{request_id}/quote",
    response_model=QuoteResponse,
    summary="Get the quote (with full version history) for one of the current user's requests",
)
def get_bulk_order_request_quote(
    request_id: int,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    service = BulkOrderService(db)
    service.get_request_detail(current_user.id, request_id)  # ownership check, 404 if not owner
    return service.get_quote(request_id)


@customer_router.post(
    "/requests/{request_id}/accept",
    response_model=BulkOrderRequestResponse,
    summary="Accept the current active quote version for one of the current user's requests",
)
def accept_bulk_order_quote(
    request_id: int,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> BulkOrderRequestResponse:
    return BulkOrderService(db).accept_quote(current_user.id, request_id)


# ---------------------------------------------------------------------------
# Ops: request review, quoting, conversion
# ---------------------------------------------------------------------------


@admin_router.get(
    "/admin/requests",
    response_model=AdminBulkOrderRequestListResponse,
    summary="List all bulk/custom order requests",
)
def admin_list_bulk_order_requests(
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> AdminBulkOrderRequestListResponse:
    return BulkOrderService(db).admin_list_requests(status_, page, page_size)


@admin_router.get(
    "/admin/requests/{request_id}",
    response_model=AdminBulkOrderRequestResponse,
    summary="Get any bulk/custom order request",
)
def admin_get_bulk_order_request(
    request_id: int, db: Session = Depends(get_db)
) -> AdminBulkOrderRequestResponse:
    return BulkOrderService(db).admin_get_request_detail(request_id)


@admin_router.post(
    "/admin/requests/{request_id}/review",
    response_model=AdminBulkOrderRequestResponse,
    summary="Move a request into review (REQUESTED -> UNDER_REVIEW)",
)
def admin_review_bulk_order_request(
    request_id: int,
    payload: ReviewBulkOrderRequestRequest,
    db: Session = Depends(get_db),
) -> AdminBulkOrderRequestResponse:
    return BulkOrderService(db).admin_review(request_id, payload.admin_notes)


@admin_router.post(
    "/admin/requests/{request_id}/status",
    response_model=AdminBulkOrderRequestResponse,
    summary="Move a request to UNDER_REVIEW/REJECTED/CANCELLED/EXPIRED",
)
def admin_update_bulk_order_request_status(
    request_id: int,
    payload: UpdateBulkOrderRequestStatusRequest,
    db: Session = Depends(get_db),
) -> AdminBulkOrderRequestResponse:
    return BulkOrderService(db).admin_update_status(
        request_id, payload.status, payload.admin_notes
    )


@admin_router.post(
    "/admin/requests/{request_id}/quote",
    response_model=QuoteResponse,
    status_code=201,
    summary="Draft a new quote version (DRAFT - not yet visible to the customer)",
)
def admin_create_quote_version(
    request_id: int,
    payload: CreateQuoteVersionRequest,
    current_user: User = Depends(require_roles(ADMIN, OPERATIONS)),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    return BulkOrderService(db).create_quote_version(request_id, payload, current_user.id)


@admin_router.get(
    "/admin/requests/{request_id}/quote",
    response_model=QuoteResponse,
    summary="Get the quote (with full version history) for any request",
)
def admin_get_bulk_order_request_quote(
    request_id: int, db: Session = Depends(get_db)
) -> QuoteResponse:
    return BulkOrderService(db).get_quote(request_id)


@admin_router.post(
    "/admin/requests/{request_id}/quote/{version_id}/send",
    response_model=QuoteResponse,
    summary="Send a DRAFT quote version to the customer (DRAFT -> SENT; supersedes the prior SENT version)",
)
def admin_send_quote_version(
    request_id: int,
    version_id: int,
    current_user: User = Depends(require_roles(ADMIN, OPERATIONS)),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    return BulkOrderService(db).send_quote_version(request_id, version_id, current_user.id)


@admin_router.post(
    "/admin/requests/{request_id}/quote/{version_id}/reject",
    response_model=QuoteResponse,
    summary="Withdraw a SENT quote version (SENT -> REJECTED)",
)
def admin_reject_quote_version(
    request_id: int,
    version_id: int,
    current_user: User = Depends(require_roles(ADMIN, OPERATIONS)),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    return BulkOrderService(db).reject_quote_version(request_id, version_id, current_user.id)


@admin_router.get(
    "/admin/variants/{variant_id}/availability",
    response_model=VariantAvailabilityResponse,
    summary="Read-only available inventory for a variant, for pricing a quote (never reserves)",
)
def admin_get_variant_availability(
    variant_id: int, db: Session = Depends(get_db)
) -> VariantAvailabilityResponse:
    return BulkOrderService(db).get_variant_availability(variant_id)


@admin_router.post(
    "/admin/requests/{request_id}/convert",
    response_model=OrderDetailResponse,
    status_code=201,
    summary="Convert an accepted request into a real Order (CUSTOMER_ACCEPTED -> CONVERTED_TO_ORDER)",
)
def admin_convert_bulk_order_request(
    request_id: int,
    current_user: User = Depends(require_roles(ADMIN, OPERATIONS)),
    db: Session = Depends(get_db),
) -> OrderDetailResponse:
    return BulkOrderService(db).convert_to_order(request_id, current_user.id)
