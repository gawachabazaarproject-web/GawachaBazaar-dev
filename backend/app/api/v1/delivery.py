"""Delivery routes (CUSTOMER-only): fee quote for a saved address and address
search (geocoding). See app/services/delivery_quote.py."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, user_or_ip_key
from app.core.roles import CUSTOMER
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.exceptions.base import ServiceUnavailableError
from app.models.user import User
from app.schemas.delivery import (
    DeliveryQuoteRequest,
    DeliveryQuoteResponse,
    GeocodeCandidate,
    GeocodeRequest,
    GeocodeResponse,
)
from app.services.delivery_quote import DeliveryQuoteService
from app.services.geocoding.base import GeocodingError
from app.services.geocoding.nominatim import get_geocoding_provider

router = APIRouter(dependencies=[Depends(require_roles(CUSTOMER))])


@router.post(
    "/quote",
    response_model=DeliveryQuoteResponse,
    summary="Road-distance delivery quote for one of the caller's saved addresses",
)
@limiter.limit("30/minute", key_func=user_or_ip_key)
def delivery_quote(
    request: Request,  # required by slowapi
    data: DeliveryQuoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryQuoteResponse:
    return DeliveryQuoteService(db).quote(current_user.id, data.address_id)


@router.post(
    "/geocode",
    response_model=GeocodeResponse,
    summary="Search an address and return map locations to confirm (not autocomplete)",
)
@limiter.limit("10/minute", key_func=user_or_ip_key)
def geocode_address(
    request: Request,  # required by slowapi
    data: GeocodeRequest,
) -> GeocodeResponse:
    try:
        results = get_geocoding_provider().search(data.query)
    except GeocodingError as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    return GeocodeResponse(
        items=[
            GeocodeCandidate(
                display_name=r.display_name,
                latitude=r.latitude,
                longitude=r.longitude,
                provider=r.provider,
                provider_id=r.provider_id,
            )
            for r in results
        ]
    )
