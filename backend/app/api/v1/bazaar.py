"""Bazaar offer routes (CUSTOMER-only): delivery quote for the current cart
and Gawacha Bazaar+ progress. See app/services/bazaar.py."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.bazaar import BazaarStatusResponse, DeliveryQuoteResponse
from app.services.bazaar import BazaarService

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])


@router.get("/status", response_model=BazaarStatusResponse, summary="Bazaar / Bazaar+ progress")
def bazaar_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BazaarStatusResponse:
    return BazaarService(db).status(current_user.id)


@router.get(
    "/delivery-quote",
    response_model=DeliveryQuoteResponse,
    summary="Delivery fee for the current cart (optionally to a saved address)",
)
def delivery_quote(
    address_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryQuoteResponse:
    return BazaarService(db).delivery_quote(current_user.id, address_id)
