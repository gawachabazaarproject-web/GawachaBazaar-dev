"""Distance-based delivery fee.

fee = DELIVERY_BASE_FEE + DELIVERY_PER_KM * road_km, where road_km is the
driving distance (streets and turns, not a straight line) from the
warehouse to the customer's pinned location. The route comes from an
OSRM-compatible routing service (DELIVERY_ROUTING_BASE_URL); if that is
unreachable we fall back to a straight-line distance scaled by a road
factor and flag the quote `method="estimate"` so it is never passed off as
an exact road distance.

The fee is computed on the backend only - checkout recomputes it from the
saved address, so a client can never choose its own fee.
"""

import logging
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.exceptions.base import BusinessValidationError

logger = logging.getLogger(__name__)

_CENTS = Decimal("0.01")
_TENTH = Decimal("0.1")
_EARTH_RADIUS_KM = 6371.0088
# Roads are longer than the crow flies; only used when routing is down.
_FALLBACK_ROAD_FACTOR = 1.35


@dataclass(frozen=True)
class DeliveryQuote:
    distance_km: Decimal
    fee: Decimal
    base_fee: Decimal
    per_km_fee: Decimal
    method: str  # "road" | "estimate"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@lru_cache(maxsize=2048)
def _road_km(
    wh_lat: float, wh_lng: float, lat: float, lng: float, base_url: str, timeout: float
) -> tuple[float, str]:
    url = f"{base_url.rstrip('/')}/route/v1/driving/{wh_lng},{wh_lat};{lng},{lat}"
    try:
        resp = httpx.get(url, params={"overview": "false"}, timeout=timeout)
        resp.raise_for_status()
        routes = resp.json().get("routes") or []
        if routes:
            return routes[0]["distance"] / 1000.0, "road"
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Routing service failed (%s); using estimated distance.", exc)
    return _haversine_km(wh_lat, wh_lng, lat, lng) * _FALLBACK_ROAD_FACTOR, "estimate"


def quote_delivery(latitude: Decimal | None, longitude: Decimal | None) -> DeliveryQuote:
    settings = get_settings()
    if latitude is None or longitude is None:
        raise BusinessValidationError(
            "Pin your delivery location on this address so we can calculate the delivery charge."
        )
    if settings.WAREHOUSE_LATITUDE is None or settings.WAREHOUSE_LONGITUDE is None:
        raise BusinessValidationError("Delivery charges are not available right now. Please try again later.")

    km, method = _road_km(
        round(settings.WAREHOUSE_LATITUDE, 5),
        round(settings.WAREHOUSE_LONGITUDE, 5),
        round(float(latitude), 5),
        round(float(longitude), 5),
        settings.DELIVERY_ROUTING_BASE_URL,
        settings.DELIVERY_ROUTING_TIMEOUT_SECONDS,
    )
    distance = Decimal(str(km)).quantize(_TENTH, rounding=ROUND_HALF_UP)
    base = settings.DELIVERY_BASE_FEE
    per_km = settings.DELIVERY_PER_KM
    fee = (base + per_km * distance).quantize(_CENTS, rounding=ROUND_HALF_UP)
    return DeliveryQuote(distance_km=distance, fee=fee, base_fee=base, per_km_fee=per_km, method=method)
