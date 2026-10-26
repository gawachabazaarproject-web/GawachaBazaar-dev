"""Delivery quote / geocoding schemas. The client sends only an address id (or
a search string) - never a distance, fee, warehouse or zone."""

from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class DeliveryQuoteRequest(BaseSchema):
    address_id: int = Field(..., ge=1)


class DeliveryQuoteResponse(BaseSchema):
    available: bool
    distance_km: float | None = None
    distance_meters: int | None = None
    estimated_duration_minutes: int | None = None
    delivery_fee: Decimal | None = None
    free_delivery: bool = False
    currency: str = "INR"
    reason: str | None = None


class GeocodeRequest(BaseSchema):
    query: str = Field(..., min_length=3, max_length=200)


class GeocodeCandidate(BaseSchema):
    display_name: str
    latitude: float
    longitude: float
    provider: str
    provider_id: str | None = None


class GeocodeResponse(BaseSchema):
    items: list[GeocodeCandidate]
