"""Cart domain routes: CUSTOMER-only. Also hosts POST /cart/checkout, which
delegates to OrderService (checkout orchestration lives there, not in
CartService) even though its path is under /cart.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.cart import (
    AddCartItemRequest,
    CartItemResponse,
    CartResponse,
    UpdateCartItemRequest,
)
from app.schemas.order import CheckoutRequest, OrderDetailResponse
from app.services.cart import CartService
from app.services.order import OrderService

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])


@router.get("", response_model=CartResponse, summary="Get the current user's active cart")
def get_cart(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CartResponse:
    return CartService(db).get_cart(current_user.id)


@router.post("", response_model=CartResponse, summary="Ensure and return an active cart")
def create_cart(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CartResponse:
    return CartService(db).create_cart(current_user.id)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to the cart (merges quantity if already present)",
)
def add_item(
    payload: AddCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartItemResponse:
    return CartService(db).add_item(current_user.id, payload)


@router.patch(
    "/items/{item_id}",
    response_model=CartItemResponse,
    summary="Set a cart item's quantity",
)
def update_item(
    item_id: int,
    payload: UpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartItemResponse:
    return CartService(db).update_item_quantity(current_user.id, item_id, payload)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove one item from the cart",
)
def remove_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    CartService(db).remove_item(current_user.id, item_id)


@router.delete(
    "/items",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove all items (cart stays ACTIVE)",
)
def clear_cart(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    CartService(db).clear_cart(current_user.id)


@router.post(
    "/checkout",
    response_model=OrderDetailResponse,
    summary="Checkout the active cart into a PENDING order",
)
def checkout(
    payload: CheckoutRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetailResponse:
    order, created = OrderService(db).checkout(current_user.id, payload)
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return order
