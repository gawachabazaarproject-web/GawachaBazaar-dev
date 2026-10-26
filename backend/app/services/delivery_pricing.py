"""Delivery pricing rules: distance in, rupees out. Pure - no DB, no network.

Routing (OSRM) only supplies the distance; every rupee amount is decided
here from `PricingRules`. Rules are read from settings (environment) today;
`PricingRules.from_settings()` is the single place to swap in a database /
admin-panel source later.

How to change a rule (environment variables, then restart the backend):
  base delivery fee        DELIVERY_BASE_FEE         (Rs, default 40)
  per-km price             DELIVERY_PER_KM           (Rs/km, default 10)
  km that stop being billed DELIVERY_MAX_CHARGED_KM  (default 30)
  maximum delivery radius  DELIVERY_MAX_DISTANCE_KM  (km; 0 = no limit)
  free-delivery threshold  FREE_DELIVERY_MIN_ITEMS   (distinct products, 15)
  minimum order value      DELIVERY_MIN_ORDER_VALUE  (Rs, 0 = off)
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from app.core.config import settings


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


def price_for_distance(distance_meters: int, rules: PricingRules) -> Decimal:
    """fee = ceil(base + per_km x min(km, max_charged_km)), whole rupees."""
    km = Decimal(distance_meters) / 1000
    charged_km = min(km, rules.max_charged_km)
    return (rules.base_fee + rules.per_km * charged_km).to_integral_value(rounding=ROUND_CEILING)
