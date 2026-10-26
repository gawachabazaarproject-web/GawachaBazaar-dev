"""Pure-logic tests for the delivery fee / Bazaar rule (no database, no network)."""

from decimal import Decimal

import pytest

from app.core.config import settings
from app.exceptions.base import ServiceUnavailableError
from app.services.delivery import (
    DeliveryUnavailableError,
    calculate_delivery_fee,
    distinct_product_count,
)
from app.services.delivery_pricing import PricingRules, price_for_distance
from app.services.routing.base import (
    NoRouteError,
    RouteResult,
    RoutingError,
    RoutingProvider,
)
from app.services.routing.cache import RouteCache
from app.services.routing.service import RoutingService


class StubProvider(RoutingProvider):
    name = "stub"

    def __init__(self, meters: int | None = None, error: Exception | None = None):
        self.meters, self.error, self.calls = meters, error, 0

    def calculate_route(self, *_a) -> RouteResult:
        self.calls += 1
        if self.error:
            raise self.error
        return RouteResult(self.meters, 600, self.name)


def routing(meters: int | None = None, error: Exception | None = None) -> RoutingService:
    return RoutingService(StubProvider(meters, error), RouteCache())


@pytest.fixture(autouse=True)
def _delivery_settings(monkeypatch):
    monkeypatch.setattr(settings, "FREE_DELIVERY_MIN_ITEMS", 15)
    monkeypatch.setattr(settings, "DELIVERY_BASE_FEE", Decimal("20"))
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("10"))
    monkeypatch.setattr(settings, "DELIVERY_MAX_CHARGED_KM", 30.0)
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 0.0)
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", 79.0882)


def test_fifteen_items_ships_free():
    quote = calculate_delivery_fee(15, 21.20, 79.10)
    assert quote.free_delivery and quote.fee == 0 and quote.items_to_free_delivery == 0


def test_fourteen_items_pays_base_plus_per_km():
    quote = calculate_delivery_fee(14, 21.2358, 79.0882, routing=routing(14_000))
    assert not quote.free_delivery
    assert quote.items_to_free_delivery == 1
    assert quote.distance_km == 14.0 and quote.distance_meters == 14_000
    assert quote.fee == Decimal("160")  # 20 + 10/km


def test_zero_distance_is_base_fee_only():
    assert calculate_delivery_fee(3, 21.1458, 79.0882, routing=routing(0)).fee == Decimal("20")


def test_missing_gps_falls_back_to_base_fee():
    quote = calculate_delivery_fee(3, None, None)
    assert quote.fee == Decimal("20") and quote.distance_estimated


def test_unconfigured_packing_point_falls_back_to_base_fee(monkeypatch):
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", None)
    quote = calculate_delivery_fee(3, 21.2, 79.1)
    assert quote.fee == Decimal("20") and quote.distance_estimated


def test_absurd_distance_is_capped():
    quote = calculate_delivery_fee(3, 0.0, 0.0, routing=routing(9_000_000))
    assert quote.fee == Decimal("20") + Decimal("10") * 30


def test_same_product_in_several_sizes_counts_once():
    # 15 cart lines but only 3 different products -> not a Bazaar.
    assert distinct_product_count([1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3]) == 3
    assert not calculate_delivery_fee(
        distinct_product_count([1] * 15), 21.2, 79.1, routing=routing(3000)
    ).free_delivery


def test_fifteen_different_products_is_a_bazaar():
    assert calculate_delivery_fee(distinct_product_count(range(15)), 21.2, 79.1).free_delivery


def test_month_start_is_first_of_month_in_ist():
    from datetime import UTC, datetime

    from app.services.bazaar import month_start

    # 2026-10-31 20:00 UTC is already 2026-11-01 01:30 in IST.
    start = month_start(datetime(2026, 10, 31, 20, 0, tzinfo=UTC))
    assert (start.year, start.month, start.day, start.hour) == (2026, 11, 1, 0)


def test_road_distance_comes_from_the_router():
    quote = calculate_delivery_fee(3, 21.2358, 79.0882, routing=routing(12_300))
    assert quote.distance_km == 12.3
    assert quote.fee == Decimal("20") + Decimal("10") * Decimal("12.3")
    assert quote.routing_provider == "stub"


def test_router_failure_fails_the_quote_instead_of_guessing():
    with pytest.raises(ServiceUnavailableError):
        calculate_delivery_fee(3, 21.2358, 79.0882, routing=routing(error=RoutingError("down")))


def test_no_route_is_not_deliverable():
    with pytest.raises(DeliveryUnavailableError):
        calculate_delivery_fee(3, 21.2358, 79.0882, routing=routing(error=NoRouteError("none")))


def test_invalid_stored_coordinates_are_not_deliverable():
    with pytest.raises(DeliveryUnavailableError):
        calculate_delivery_fee(3, 95.0, 79.0882, routing=routing(1000))


# --- distance boundaries (2 / 2.1 / 5 / 5.1 / 10 / 10.1 km) and rounding ---------


@pytest.mark.parametrize(
    "meters, fee",
    [
        (2000, "40"),  # 20 + 10 x 2
        (2100, "41"),
        (5000, "70"),
        (5100, "71"),
        (10000, "120"),
        (10100, "121"),
        (2001, "41"),  # 40.01 rounds UP to a whole rupee
        (0, "20"),
    ],
)
def test_fee_boundaries_and_ceiling_rounding(meters, fee):
    assert calculate_delivery_fee(3, 21.2, 79.1, routing=routing(meters)).fee == Decimal(fee)


def test_money_is_decimal_not_float():
    rules = PricingRules.from_settings()
    assert isinstance(price_for_distance(4700, rules), Decimal)
    assert price_for_distance(4700, rules) == Decimal("67")  # 20 + 47 = 67 exactly


def test_pricing_rules_are_configurable(monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_BASE_FEE", Decimal("30"))
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("8"))
    assert calculate_delivery_fee(3, 21.2, 79.1, routing=routing(5000)).fee == Decimal("70")


def test_max_radius_boundary(monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 10.0)
    assert calculate_delivery_fee(3, 21.2, 79.1, routing=routing(10_000)).fee == Decimal("120")
    with pytest.raises(DeliveryUnavailableError) as exc:
        calculate_delivery_fee(3, 21.2, 79.1, routing=routing(10_100))
    assert exc.value.distance_km == 10.1
    assert "10 km" in exc.value.message


def test_radius_also_applies_to_a_bazaar(monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 10.0)
    assert calculate_delivery_fee(15, 21.2, 79.1, routing=routing(9000)).fee == 0
    with pytest.raises(DeliveryUnavailableError):
        calculate_delivery_fee(15, 21.2, 79.1, routing=routing(11_000))
