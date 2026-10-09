"""Delivery pricing and the "Bazaar" offer.

Rule (all values configurable, see app/core/config.py):
  * A basket of FREE_DELIVERY_MIN_ITEMS (15) or more DIFFERENT PRODUCTS - a
    "Bazaar" - ships free.
  * Anything smaller pays DELIVERY_BASE_FEE (Rs 20) plus DELIVERY_PER_KM
    (Rs 10) per km of ROAD distance from the packing point to the delivery
    address (Google Distance Matrix if GOOGLE_MAPS_API_KEY is set, otherwise
    OSRM; if routing is down, straight-line x DELIVERY_ROAD_FACTOR).

"Items" means distinct products: the same product in two sizes, or in a
bigger quantity, still counts once.

`calculate_delivery_fee` is pure (no DB) so the rule is trivial to test and
the quote shown in the app and the fee charged at checkout can never drift:
both go through it.
"""

import logging
import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from functools import lru_cache

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory_location import InventoryLocation

logger = logging.getLogger(__name__)

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


def _google_road_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    resp = httpx.get(
        "https://maps.googleapis.com/maps/api/distancematrix/json",
        params={
            "origins": f"{lat1},{lon1}",
            "destinations": f"{lat2},{lon2}",
            "mode": "driving",
            "key": settings.GOOGLE_MAPS_API_KEY,
        },
        timeout=settings.ROUTING_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    element = resp.json()["rows"][0]["elements"][0]
    if element.get("status") != "OK":
        raise ValueError(f"no route: {element.get('status')}")
    return element["distance"]["value"] / 1000.0


def _osrm_road_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    base = settings.OSRM_BASE_URL.rstrip("/")
    resp = httpx.get(
        f"{base}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
        params={"overview": "false"},
        timeout=settings.ROUTING_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"no route: {data.get('code')}")
    return data["routes"][0]["distance"] / 1000.0


@lru_cache(maxsize=2048)
def _cached_road_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Failures raise, so lru_cache never stores them and the next quote retries.
    if settings.GOOGLE_MAPS_API_KEY:
        return _google_road_km(lat1, lon1, lat2, lon2)
    return _osrm_road_km(lat1, lon1, lat2, lon2)


def road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Driving distance in km. Coordinates are rounded to ~11 m so repeat
    quotes for the same address hit the cache instead of the routing API."""
    try:
        return _cached_road_km(round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4))
    except Exception as exc:  # noqa: BLE001 - any routing failure falls back
        logger.warning("DELIVERY_ROUTING_FAILED: %s", exc)
        return haversine_km(lat1, lon1, lat2, lon2) * settings.DELIVERY_ROAD_FACTOR


def distinct_product_count(product_ids) -> int:
    """Number of different products in a basket."""
    return len(set(product_ids))


def get_packing_point(db: Session) -> tuple[float | None, float | None]:
    """Where delivery distance is measured from: the admin-chosen packing
    point (inventory location flagged is_packing_point), else the
    PACKING_POINT_* env fallback."""
    row = (
        db.query(InventoryLocation.latitude, InventoryLocation.longitude)
        .filter(
            InventoryLocation.is_packing_point.is_(True),
            InventoryLocation.status == "ACTIVE",
            InventoryLocation.latitude.isnot(None),
            InventoryLocation.longitude.isnot(None),
        )
        .first()
    )
    if row:
        return float(row[0]), float(row[1])
    return settings.PACKING_POINT_LATITUDE, settings.PACKING_POINT_LONGITUDE


def calculate_delivery_fee(
    item_count: int,
    address_latitude: float | None = None,
    address_longitude: float | None = None,
    origin: tuple[float | None, float | None] | None = None,
) -> DeliveryQuote:
    threshold = settings.FREE_DELIVERY_MIN_ITEMS
    remaining = max(0, threshold - item_count)

    if item_count >= threshold:
        return DeliveryQuote(Decimal("0"), True, item_count, threshold, 0, None, False)

    base = settings.DELIVERY_BASE_FEE
    origin_lat, origin_lon = origin or (settings.PACKING_POINT_LATITUDE, settings.PACKING_POINT_LONGITUDE)
    if None in (origin_lat, origin_lon, address_latitude, address_longitude):
        return DeliveryQuote(base, False, item_count, threshold, remaining, None, True)

    km = road_distance_km(origin_lat, origin_lon, float(address_latitude), float(address_longitude))
    charged_km = min(km, settings.DELIVERY_MAX_CHARGED_KM)
    fee = (base + settings.DELIVERY_PER_KM * Decimal(str(charged_km))).to_integral_value(rounding=ROUND_CEILING)
    return DeliveryQuote(fee, False, item_count, threshold, remaining, round(km, 1), False)
