"""Customer-facing offers (the Home screen's offers carousel).

Only what a shopper needs to see - never usage counters, targets, internal
names or other customers. See app/services/offers.py."""

from datetime import datetime

from app.schemas.base import BaseSchema


class OfferResponse(BaseSchema):
    id: int
    title: str
    description: str
    image_url: str | None
    # The code to type at checkout; None for automatic offers (applied for you).
    code: str | None
    discount_label: str  # e.g. "Rs 100 OFF" / "15% OFF"
    fine_print: str | None  # e.g. "On orders above Rs 999 - up to Rs 150 off"
    audience: str | None  # e.g. "New customers"
    ends_at: datetime | None
