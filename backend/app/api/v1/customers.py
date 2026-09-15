"""Customer Management routes: admin visibility into existing User/Order/
Address/PromotionRedemption data (ADMIN-only, gated by the granular
`customers.*` permissions in app/core/permissions.py). No customer identity,
address, or order data is duplicated here - see app/services/customer.py.

ROUTE ORDERING: `/dashboard` (literal) is registered before `/{user_id}`
(param) - both are GET at the same path depth, and FastAPI/Starlette match
routes in registration order, so the literal path must come first or every
request to `/dashboard` would be swallowed by `/{user_id}` trying (and
failing) to parse "dashboard" as an integer. Same established pattern as
orders.py/promotions.py.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import role_has_permission
from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.address import AddressResponse
from app.schemas.admin_customer import (
    MAX_PAGE_SIZE,
    AdminCustomerDetailResponse,
    AdminCustomerListResponse,
    ConfirmContactChangeRequest,
    CreateCustomerNoteRequest,
    CustomerNoteListResponse,
    CustomerNoteResponse,
    CustomerOrderListResponse,
    CustomerPromotionRedemptionListResponse,
    CustomersDashboardResponse,
    CustomerTimelineResponse,
    PendingContactChangeResponse,
    RequestContactChangeRequest,
    UpdateCustomerNoteRequest,
    UpdateCustomerStatusRequest,
)
from app.services.customer import CustomerService
from app.services.order import OrderService

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=CustomersDashboardResponse,
    summary="Customer base overview: status counts, order behavior, realized revenue",
)
def get_dashboard(
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> CustomersDashboardResponse:
    return CustomerService(db).admin_dashboard()


@router.get(
    "",
    response_model=AdminCustomerListResponse,
    summary="List/search/filter/sort customers",
)
def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(default=None, max_length=150, description="Name, email, phone, or customer id"),
    account_status: str | None = Query(default=None, description="ACTIVE, INACTIVE, or SUSPENDED"),
    activity: str | None = Query(
        default=None, description="new, returning, no_orders, recently_active, or inactive"
    ),
    has_orders: bool | None = Query(default=None),
    registered_from: str | None = Query(default=None),
    registered_to: str | None = Query(default=None),
    last_order_from: str | None = Query(default=None),
    last_order_to: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> AdminCustomerListResponse:
    def _parse(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    view_sensitive = _has_permission(current_user, db, "customers.view_sensitive")
    return CustomerService(db).admin_list_customers(
        page=page,
        page_size=page_size,
        view_sensitive=view_sensitive,
        q=q,
        account_status=account_status,
        activity=activity,
        has_orders=has_orders,
        registered_from=_parse(registered_from),
        registered_to=_parse(registered_to),
        last_order_from=_parse(last_order_from),
        last_order_to=_parse(last_order_to),
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get(
    "/{user_id}",
    response_model=AdminCustomerDetailResponse,
    summary="Full customer profile + order/spend/promotion summary + addresses",
)
def get_customer(
    user_id: int,
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> AdminCustomerDetailResponse:
    view_sensitive = _has_permission(current_user, db, "customers.view_sensitive")
    return CustomerService(db).admin_get_customer_detail(user_id, view_sensitive)


@router.get(
    "/{user_id}/orders",
    response_model=CustomerOrderListResponse,
    summary="This customer's order history (same rows/shape as the Orders admin module)",
)
def get_customer_orders(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> CustomerOrderListResponse:
    CustomerService(db).get_customer_or_404(user_id)
    return OrderService(db).admin_list_orders(page, page_size, user_id=user_id)


@router.get(
    "/{user_id}/promotions",
    response_model=CustomerPromotionRedemptionListResponse,
    summary="This customer's promotion/coupon redemption history",
)
def get_customer_promotions(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> CustomerPromotionRedemptionListResponse:
    return CustomerService(db).list_customer_promotion_redemptions(user_id, page, page_size)


@router.get(
    "/{user_id}/addresses",
    response_model=list[AddressResponse],
    summary="This customer's saved addresses (read-only admin view)",
)
def get_customer_addresses(
    user_id: int,
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> list[AddressResponse]:
    return CustomerService(db).list_customer_addresses(user_id)


@router.get(
    "/{user_id}/timeline",
    response_model=CustomerTimelineResponse,
    summary="Chronological account/order/promotion events for this customer",
)
def get_customer_timeline(
    user_id: int,
    current_user: User = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
) -> CustomerTimelineResponse:
    return CustomerService(db).get_customer_timeline(user_id)


@router.get(
    "/{user_id}/notes",
    response_model=CustomerNoteListResponse,
    summary="Internal support notes about this customer",
)
def get_customer_notes(
    user_id: int,
    current_user: User = Depends(require_permission("customers.notes")),
    db: Session = Depends(get_db),
) -> CustomerNoteListResponse:
    return CustomerService(db).list_notes(user_id)


@router.post(
    "/{user_id}/notes",
    response_model=CustomerNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an internal support note about this customer",
)
def create_customer_note(
    user_id: int,
    payload: CreateCustomerNoteRequest,
    current_user: User = Depends(require_permission("customers.notes")),
    db: Session = Depends(get_db),
) -> CustomerNoteResponse:
    return CustomerService(db).create_note(user_id, payload, current_user.id)


@router.patch(
    "/notes/{note_id}",
    response_model=CustomerNoteResponse,
    summary="Edit an internal support note",
)
def update_customer_note(
    note_id: int,
    payload: UpdateCustomerNoteRequest,
    current_user: User = Depends(require_permission("customers.notes")),
    db: Session = Depends(get_db),
) -> CustomerNoteResponse:
    return CustomerService(db).update_note(note_id, payload, current_user.id)


@router.post(
    "/{user_id}/status",
    response_model=AdminCustomerDetailResponse,
    summary="Change a customer's account status (ACTIVE/INACTIVE/SUSPENDED) - enforced on their very next request",
)
def set_customer_status(
    user_id: int,
    payload: UpdateCustomerStatusRequest,
    current_user: User = Depends(require_permission("customers.manage_status")),
    db: Session = Depends(get_db),
) -> AdminCustomerDetailResponse:
    return CustomerService(db).admin_set_account_status(
        user_id, payload.status, current_user.id, payload.reason
    )


@router.post(
    "/{user_id}/contact-change",
    response_model=PendingContactChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request an email/phone change - sends a verification code to the NEW address/number",
)
def request_contact_change(
    user_id: int,
    payload: RequestContactChangeRequest,
    current_user: User = Depends(require_permission("customers.manage_contact")),
    db: Session = Depends(get_db),
) -> PendingContactChangeResponse:
    return CustomerService(db).request_contact_change(user_id, payload, current_user.id)


@router.post(
    "/{user_id}/contact-change/confirm",
    response_model=AdminCustomerDetailResponse,
    summary="Confirm a pending email/phone change with the code sent to the new address/number",
)
def confirm_contact_change(
    user_id: int,
    payload: ConfirmContactChangeRequest,
    current_user: User = Depends(require_permission("customers.manage_contact")),
    db: Session = Depends(get_db),
) -> AdminCustomerDetailResponse:
    return CustomerService(db).confirm_contact_change(user_id, payload, current_user.id)


@router.delete(
    "/{user_id}/contact-change/{field}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a pending email/phone change request",
)
def cancel_contact_change(
    user_id: int,
    field: str,
    current_user: User = Depends(require_permission("customers.manage_contact")),
    db: Session = Depends(get_db),
) -> None:
    CustomerService(db).cancel_contact_change(user_id, field, current_user.id)


def _has_permission(current_user: User, db: Session, permission: str) -> bool:
    """Local re-check of a second, weaker permission on the same already-
    authenticated request (view_sensitive) - avoids a second round-trip
    dependency while still reading live role data, same query shape as
    `require_permission` itself."""
    role_names = [
        name
        for (name,) in db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id)
        .all()
    ]
    return role_has_permission(role_names, permission)
