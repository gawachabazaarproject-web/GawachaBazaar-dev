"""Order domain routes: CUSTOMER-only, always scoped to the authenticated user.

No status PATCH, no cancellation, no fulfillment status - reads only.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.dependencies.payments import get_payment_gateway
from app.exceptions.base import NotFoundError
from app.models.order import Order
from app.models.user import User
from app.schemas.inventory_reservation import InventoryReservationResponse
from app.schemas.order import MAX_PAGE_SIZE, OrderDetailResponse, OrderListResponse
from app.schemas.payment import PaymentResponse
from app.services.inventory_reservation import InventoryReservationService
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.payment_gateway import PaymentGateway

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])


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
