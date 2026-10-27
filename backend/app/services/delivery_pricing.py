"""Delivery pricing rules: distance in, rupees out. Pure - no DB, no network.

Routing (OSRM) only supplies the distance; every rupee amount is decided
here from `PricingRules`. Rules are read from settings (environment) today;
`PricingRules.from_settings()` is the single place to swap in a database /
admin-panel source later.

How to change a rule (environment variables, then restart the backend):
  base delivery fee        DELIVERY_BASE_FEE         (Rs, default 20)
  per-km price             DELIVERY_PER_KM           (Rs/km, default 10)
  km that stop being billed DELIVERY_MAX_CHARGED_KM  (default 30)

Rule (pricing version PRICING_VERSION):
  billable_km = max(1, ceil(distance_meters / 1000))   (integer arithmetic)
  billable_km = min(billable_km, floor(DELIVERY_MAX_CHARGED_KM))
  fee         = DELIVERY_BASE_FEE + DELIVERY_PER_KM x billable_km
Example with base 20 / per-km 10: 0-1000 m -> Rs 30, 1001-2000 m -> Rs 40,
5200 m -> Rs 80, 10100 m -> Rs 130.
  maximum delivery radius  DELIVERY_MAX_DISTANCE_KM  (km; 0 = no limit)
  free-delivery threshold  FREE_DELIVERY_MIN_ITEMS   (distinct products, 15)
  minimum order value      DELIVERY_MIN_ORDER_VALUE  (Rs, 0 = off)
"""

from dataclasses import dataclass
from decimal import Decimal

from app.core.config import settings

# Stored on every order so a later rule change can never reinterpret history.
PRICING_VERSION = "ceil-km-v1"


@dataclass(frozen=True)
class PricingRules:
    base_fee: Decimal
    per_km: Decimal
    max_charged_km: Decimal
    max_distance_km: Decimal  # 0 = unlimited
    free_delivery_min_items: int
    min_order_value: Decimal

    @classmethod
    def from_settings(cls) -> "PricingRules":
        return cls(
            base_fee=settings.DELIVERY_BASE_FEE,
            per_km=settings.DELIVERY_PER_KM,
            max_charged_km=Decimal(str(settings.DELIVERY_MAX_CHARGED_KM)),
            max_distance_km=Decimal(str(settings.DELIVERY_MAX_DISTANCE_KM)),
            free_delivery_min_items=settings.FREE_DELIVERY_MIN_ITEMS,
            min_order_value=settings.DELIVERY_MIN_ORDER_VALUE,
        )

    def is_beyond_radius(self, distance_meters: int) -> bool:
        return self.max_distance_km > 0 and Decimal(distance_meters) / 1000 > self.max_distance_km


def billable_km_for_distance(distance_meters: int, rules: PricingRules) -> int:
    """Whole kilometres charged: rounded UP, at least 1, capped. Integer math only."""
    if distance_meters < 0:
        raise ValueError("distance_meters must not be negative")
    km = max(1, (distance_meters + 999) // 1000)
    return min(km, max(1, int(rules.max_charged_km)))


def price_for_distance(distance_meters: int, rules: PricingRules) -> Decimal:
    """fee = base + per_km x billable_km (whole km, rounded up), Decimal rupees."""
    return rules.base_fee + rules.per_km * billable_km_for_distance(distance_meters, rules)
