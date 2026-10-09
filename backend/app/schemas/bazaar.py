"""Bazaar offer schemas (free delivery at 15+ items, Gawacha Bazaar+)."""

from decimal import Decimal

from app.schemas.base import BaseSchema


class DeliveryQuoteResponse(BaseSchema):
    """What delivering the customer's current cart to an address costs."""

    fee: Decimal
    free_delivery: bool
    item_count: int
    free_delivery_min_items: int
    items_to_free_delivery: int
    distance_km: float | None
    # True when only the base fee could be applied (no GPS on the address,
    # or the packing point is not configured) - checkout adds the per-km
    # part whenever the chosen address has GPS.
    distance_estimated: bool
    currency: str


class BazaarStatusResponse(BaseSchema):
    """Progress toward Gawacha Bazaar+ - rolling window of Bazaar orders."""

    free_delivery_min_items: int
    cart_item_count: int
    bazaar_orders_in_window: int
    orders_required: int
    window_days: int
    eligible_for_bazaar_plus: bool
