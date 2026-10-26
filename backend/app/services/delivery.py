"""Delivery pricing and the "Bazaar" offer.

Rule (all values configurable, see app/core/config.py and delivery_pricing.py):
  * A basket of FREE_DELIVERY_MIN_ITEMS (15) or more DIFFERENT PRODUCTS - a
    "Bazaar" - ships free.
  * Anything smaller pays DELIVERY_BASE_FEE plus DELIVERY_PER_KM per km of
    ROAD distance from the packing point to the delivery address (OSRM via
    RoutingService, cached).
  * If routing is down the quote FAILS (503). Straight-line distance is never
    presented as a road distance.

"Items" means distinct products: the same product in two sizes, or in a
bigger quantity, still counts once.

`calculate_delivery_fee` is the one function the cart quote, the
/delivery/quote endpoint and checkout all go through, so the quote shown in
the app and the fee charged at checkout can never drift.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.exceptions.base import (
    BusinessValidationError,
    ServiceUnavailableError,
)
from app.models.inventory_location import InventoryLocation
from app.services.delivery_pricing import PricingRules, price_for_distance
from app.services.routing.base import NoRouteError, RouteResult
from app.services.routing.service import RoutingService

logger = logging.getLogger(__name__)


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
    # Route audit data, stored on the order (None when no route was used).
    distance_meters: int | None = None
    duration_seconds: int | None = None
    routing_provider: str | None = None
    warehouse_id: int | None = None


class DeliveryUnavailableError(BusinessValidationError):
    """The address cannot be delivered to (outside the radius / no road route)."""

    def __init__(self, message: str, distance_km: float | None = None) -> None:
        super().__init__(message)
        self.code = "DELIVERY_UNAVAILABLE"
        self.distance_km = distance_km


def distinct_product_count(product_ids) -> int:
    """Number of different products in a basket."""
    return len(set(product_ids))


def get_packing_origin(db: Session) -> tuple[float | None, float | None, int | None]:
    """(lat, lon, warehouse_id): the admin-chosen packing point (inventory
    location flagged is_packing_point), else the PACKING_POINT_* env fallback
    (warehouse_id None). The warehouse seam: pick another location here to
    support several fulfilment centres."""
    row = (
        db.query(InventoryLocation.latitude, InventoryLocation.longitude, InventoryLocation.id)
        .filter(
            InventoryLocation.is_packing_point.is_(True),
            InventoryLocation.status == "ACTIVE",
            InventoryLocation.latitude.isnot(None),
            InventoryLocation.longitude.isnot(None),
        )
        .first()
    )
    if row:
        return float(row[0]), float(row[1]), row[2]
    return settings.PACKING_POINT_LATITUDE, settings.PACKING_POINT_LONGITUDE, None


def get_packing_point(db: Session) -> tuple[float | None, float | None]:
    lat, lon, _ = get_packing_origin(db)
    return lat, lon


@dataclass(frozen=True)
class RouteOutcome:
    """Result of the (network) route lookup, resolved BEFORE any database row
    lock is taken (DEL-1). `route` or `error` is set; `error` is only raised
    later, by `price_delivery`, if the order actually needs a distance."""

    origin: tuple[float, float]
    destination: tuple[float, float]
    warehouse_id: int | None
    route: RouteResult | None = None
    error: Exception | None = None


def resolve_route(
    origin: tuple[float | None, float | None],
    address_latitude,
    address_longitude,
    warehouse_id: int | None = None,
    routing: RoutingService | None = None,
) -> RouteOutcome | None:
    """Look up the road route. Never raises: returns None when there is no
    origin/destination to route between, else an outcome holding the route or
    the error. May call the network - do not call it while holding row locks."""
    o_lat, o_lon = origin
    if None in (o_lat, o_lon, address_latitude, address_longitude):
        return None
    pts = (float(o_lat), float(o_lon)), (float(address_latitude), float(address_longitude))
    try:
        route = (routing or RoutingService()).get_route(*pts[0], *pts[1])
        return RouteOutcome(pts[0], pts[1], warehouse_id, route=route)
    except Exception as exc:  # noqa: BLE001 - classified in price_delivery
        return RouteOutcome(pts[0], pts[1], warehouse_id, error=exc)


def price_delivery(
    item_count: int,
    outcome: RouteOutcome | None,
    rules: PricingRules | None = None,
) -> DeliveryQuote:
    """Pure pricing from an already-resolved route (no network, no DB).
    Raises DeliveryUnavailableError (outside radius / no route) or
    ServiceUnavailableError (routing down, and the order needs a distance)."""
    rules = rules or PricingRules.from_settings()
    threshold = rules.free_delivery_min_items
    remaining = max(0, threshold - item_count)
    is_bazaar = item_count >= threshold

    if outcome is None:  # no origin configured or address without GPS
        if is_bazaar:
            return DeliveryQuote(Decimal("0"), True, item_count, threshold, 0, None, False)
        return DeliveryQuote(rules.base_fee, False, item_count, threshold, remaining, None, True)

    exc = outcome.error
    if exc is not None:
        needs_distance = (not is_bazaar) or rules.max_distance_km > 0
        if not needs_distance:
            # A free Bazaar with no radius does not depend on the router.
            return DeliveryQuote(Decimal("0"), True, item_count, threshold, 0, None, False)
        if isinstance(exc, ValueError):
            raise DeliveryUnavailableError("This address has invalid coordinates.") from exc
        if isinstance(exc, NoRouteError):
            raise DeliveryUnavailableError("No road route to this address was found.") from exc
        raise ServiceUnavailableError(
            "Delivery distance cannot be calculated right now. Please try again shortly."
        ) from exc

    route = outcome.route
    km = round(route.distance_meters / 1000, 1)
    if rules.is_beyond_radius(route.distance_meters):
        raise DeliveryUnavailableError(
            f"Delivery is not available beyond {rules.max_distance_km.normalize():f} km.",
            distance_km=km,
        )
    fee = Decimal("0") if is_bazaar else price_for_distance(route.distance_meters, rules)
    logger.info(
        "delivery_priced distance_m=%d fee=%s free=%s provider=%s warehouse_id=%s",
        route.distance_meters, fee, is_bazaar, route.provider, outcome.warehouse_id,
    )
    return DeliveryQuote(
        fee, is_bazaar, item_count, threshold, remaining, km, False,
        distance_meters=route.distance_meters,
        duration_seconds=route.duration_seconds,
        routing_provider=route.provider,
        warehouse_id=outcome.warehouse_id,
    )


def calculate_delivery_fee(
    item_count: int,
    address_latitude: float | None = None,
    address_longitude: float | None = None,
    origin: tuple[float | None, float | None] | None = None,
    warehouse_id: int | None = None,
    routing: RoutingService | None = None,
    rules: PricingRules | None = None,
) -> DeliveryQuote:
    """Resolve the route and price it in one go. Only for callers that hold no
    row locks (the quote endpoints); checkout resolves first, locks, then prices."""
    origin = origin or (settings.PACKING_POINT_LATITUDE, settings.PACKING_POINT_LONGITUDE)
    outcome = resolve_route(origin, address_latitude, address_longitude, warehouse_id, routing)
    return price_delivery(item_count, outcome, rules)
