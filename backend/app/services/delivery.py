"""Delivery pricing and the "Bazaar" offer.

Rule (all values configurable, see app/core/config.py):
  * A basket of FREE_DELIVERY_MIN_ITEMS (15) or more DIFFERENT PRODUCTS - a
    "Bazaar" - ships free.
  * Anything smaller pays DELIVERY_BASE_FEE (Rs 20) plus DELIVERY_PER_KM
    (Rs 10) per km from the packing point to the delivery address.

"Items" means distinct products: the same product in two sizes, or in a
bigger quantity, still counts once.

`calculate_delivery_fee` is pure (no DB) so the rule is trivial to test and
the quote shown in the app and the fee charged at checkout can never drift:
both go through it.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from app.core.config import settings

_EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class DeliveryQuote:
    fee: Decimal
    free_delivery: bool
    item_count: int
    free_delivery_min_items: int
    items_to_free_delivery: int
    distance_km: float | None
    # True when the per-km part could not be priced (packing point not
    # configured, or the address has no GPS) and only the base fee applies.
    distance_estimated: bool


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def distinct_product_count(product_ids) -> int:
    """Number of different products in a basket."""
    return len(set(product_ids))


def calculate_delivery_fee(
    item_count: int,
    address_latitude: float | None = None,
    address_longitude: float | None = None,
) -> DeliveryQuote:
    threshold = settings.FREE_DELIVERY_MIN_ITEMS
    remaining = max(0, threshold - item_count)

    if item_count >= threshold:
        return DeliveryQuote(Decimal("0"), True, item_count, threshold, 0, None, False)

    base = settings.DELIVERY_BASE_FEE
    origin_lat = settings.PACKING_POINT_LATITUDE
    origin_lon = settings.PACKING_POINT_LONGITUDE
    if None in (origin_lat, origin_lon, address_latitude, address_longitude):
        return DeliveryQuote(base, False, item_count, threshold, remaining, None, True)

    km = haversine_km(origin_lat, origin_lon, float(address_latitude), float(address_longitude))
    charged_km = min(km, settings.DELIVERY_MAX_CHARGED_KM)
    fee = (base + settings.DELIVERY_PER_KM * Decimal(str(charged_km))).to_integral_value(rounding=ROUND_CEILING)
    return DeliveryQuote(fee, False, item_count, threshold, remaining, round(km, 1), False)
