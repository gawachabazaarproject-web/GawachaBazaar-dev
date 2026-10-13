"""Public offers list for the mobile app's Home carousel (no auth). The
admin controls it from the Promotions page: a promotion shows here when it
is live and "Show in app carousel" is on. See app/services/offers.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.offer import OfferResponse
from app.services.offers import OfferService

router = APIRouter()


@router.get("", response_model=list[OfferResponse], summary="List live offers for the Home carousel")
def list_offers(db: Session = Depends(get_db)) -> list[OfferResponse]:
    return OfferService(db).list_live_offers()
