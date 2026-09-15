"""Order domain routes.

`router`: CUSTOMER-only, always scoped to the authenticated user - reads,
self-cancellation, and refund status for one's own orders.
`admin_router`: ADMIN-only administrative cancellation, mounted under
`/admin/` to avoid colliding with the customer-facing cancel path (see
app/api/v1/fulfillments.py / bulk_orders.py for the same per-route-RBAC
pattern used when one router's roles differ from another's within the
same domain).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, CUSTOMER
from app.dependencies.auth import get_current_user, require_permission, require_roles
from app.dependencies.database import get_db
from app.dependencies.payments import get_payment_gateway
from app.exceptions.base import NotFoundError
from app.models.order import Order
from app.models.user import User
from app.schemas.admin_order import (
    AdminOrderDetailResponse,
    AdminOrderListResponse,
)
from app.schemas.admin_order import MAX_PAGE_SIZE as ADMIN_MAX_PAGE_SIZE
from app.schemas.fulfillment import CustomerFulfillmentResponse
from app.schemas.inventory_reservation import InventoryReservationResponse
from app.schemas.order import (
    MAX_PAGE_SIZE,
    CancelOrderRequest,
    OrderDetailResponse,
    OrderListResponse,
)
from app.schemas.payment import PaymentResponse
from app.schemas.refund import RefundResponse
from app.services.fulfillment import FulfillmentService
from app.services.inventory_reservation import InventoryReservationService
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.payment_gateway import PaymentGateway
from app.services.refund import RefundService

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])
admin_router = APIRouter(dependencies=[Depends(require_roles(ADMIN))])
# No blanket role restriction (unlike admin_router above, which is
# ADMIN-only for the destructive cancel action): each route below declares
# its own `require_permission(...)`, since orders.read is granted to
# OPERATIONS/HUB_STAFF too (see app/core/permissions.py) while cancellation
# stays ADMIN-only. Same per-route-RBAC-within-one-file pattern already
# used in fulfillments.py.
staff_router = APIRouter()


@router.get("", response_model=OrderListResponse, summary="List the current user's orders")
def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderListResponse:
    return OrderService(db).list_orders(current_user.id, page, page_size)


@router.get(
    "/{order_id}",
    response_model=OrderDetailResponse,
    summary="Get one of the current user's orders",
)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetailResponse:
    return OrderService(db).get_order_detail(current_user.id, order_id)


@router.get(
    "/{order_id}/payment",
    response_model=PaymentResponse,
    summary="Get the payment for one of the current user's orders",
)
def get_order_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> PaymentResponse:
    return PaymentService(db, gateway).get_payment_for_order(current_user.id, order_id)


@router.get(
    "/{order_id}/reservation",
    response_model=InventoryReservationResponse,
    summary="Get the inventory reservation for one of the current user's orders",
)
def get_order_reservation(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryReservationResponse:
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise NotFoundError("Order not found.")
    return InventoryReservationService(db).get_reservation_response_for_order(order.id)


@router.get(
    "/{order_id}/fulfillment",
    response_model=CustomerFulfillmentResponse,
    summary="Get the safe fulfillment status for one of the current user's orders",
)
def get_order_fulfillment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerFulfillmentResponse:
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise NotFoundError("Order not found.")
    return FulfillmentService(db).get_customer_fulfillment_response_for_order(order.id)


@router.get(
    "/{order_id}/refund",
    response_model=RefundResponse,
    summary="Get the refund status for one of the current user's orders, if any",
)
def get_order_refund(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RefundResponse:
    return RefundService(db).get_refund_for_order(current_user.id, order_id)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderDetailResponse,
    summary="Cancel one of the current user's own orders (any time before delivery is completed)",
)
def cancel_order(
    order_id: int,
    payload: CancelOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetailResponse:
    return OrderService(db).cancel_own_order(current_user.id, order_id, payload.reason)


@admin_router.post(
    "/admin/{order_id}/cancel",
    response_model=OrderDetailResponse,
    summary="Administrative cancellation of any order (any time before delivery is completed)",
)
def admin_cancel_order(
    order_id: int,
    payload: CancelOrderRequest,
    current_user: User = Depends(require_roles(ADMIN)),
    db: Session = Depends(get_db),
) -> OrderDetailResponse:
    return OrderService(db).admin_cancel_order(current_user.id, order_id, payload.reason)


@staff_router.get(
    "/admin",
    response_model=AdminOrderListResponse,
    summary="List/search/filter every order on the platform (admin panel)",
)
def admin_list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=ADMIN_MAX_PAGE_SIZE),
    status: str | None = Query(default=None, description="Order status, e.g. PENDING"),
    payment_status: str | None = Query(default=None),
    fulfillment_status: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None, description="placed_at >= this"),
    date_to: datetime | None = Query(default=None, description="placed_at <= this"),
    q: str | None = Query(default=None, max_length=150, description="Order number or customer name/email/phone"),
    current_user: User = Depends(require_permission("orders.read")),
    db: Session = Depends(get_db),
) -> AdminOrderListResponse:
    return OrderService(db).admin_list_orders(
        page, page_size, status, payment_status, fulfillment_status, date_from, date_to, q
    )


@staff_router.get(
    "/admin/{order_id}",
    response_model=AdminOrderDetailResponse,
    summary="Get the complete operational detail for any order (admin panel)",
)
def admin_get_order(
    order_id: int,
    current_user: User = Depends(require_permission("orders.read")),
    db: Session = Depends(get_db),
) -> AdminOrderDetailResponse:
    return OrderService(db).admin_get_order_detail(order_id)
