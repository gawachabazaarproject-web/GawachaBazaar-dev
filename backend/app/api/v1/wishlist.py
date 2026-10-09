"""Wishlist routes: CUSTOMER-only, scoped to the authenticated user."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.wishlist import WishlistResponse
from app.services.wishlist import WishlistService

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])


@router.get("", response_model=WishlistResponse, summary="List the current user's wishlist")
def list_wishlist(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WishlistResponse:
    return WishlistService(db).list_items(current_user.id)


@router.put(
    "/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Add a product to the wishlist"
)
def add_to_wishlist(
    product_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    WishlistService(db).add(current_user.id, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a product from the wishlist"
)
def remove_from_wishlist(
    product_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    WishlistService(db).remove(current_user.id, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
