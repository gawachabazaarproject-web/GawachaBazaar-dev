"""Order domain routes: CUSTOMER-only, always scoped to the authenticated user.

No status PATCH, no cancellation, no fulfillment status - reads only.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.order import MAX_PAGE_SIZE, OrderDetailResponse, OrderListResponse
from app.services.order import OrderService

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
