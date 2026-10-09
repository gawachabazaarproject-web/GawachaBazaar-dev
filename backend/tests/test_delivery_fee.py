"""Pure-logic tests for the delivery fee / Bazaar rule (no database)."""

from decimal import Decimal

import pytest

from app.core.config import settings
from app.services.delivery import calculate_delivery_fee, distinct_product_count, haversine_km


@pytest.fixture(autouse=True)
def _delivery_settings(monkeypatch):
    monkeypatch.setattr(settings, "FREE_DELIVERY_MIN_ITEMS", 15)
    monkeypatch.setattr(settings, "DELIVERY_BASE_FEE", Decimal("20"))
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("10"))
    monkeypatch.setattr(settings, "DELIVERY_MAX_CHARGED_KM", 30.0)
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", 79.0882)


def test_fifteen_items_ships_free():
    quote = calculate_delivery_fee(15, 21.20, 79.10)
    assert quote.free_delivery and quote.fee == 0 and quote.items_to_free_delivery == 0


def test_fourteen_items_pays_base_plus_per_km():
    quote = calculate_delivery_fee(14, 21.2358, 79.0882)  # ~10 km north
    assert not quote.free_delivery
    assert quote.items_to_free_delivery == 1
    assert 9.5 < quote.distance_km < 10.5
    assert quote.fee in (Decimal("120"), Decimal("121"))  # 20 + 10/km, rounded up


def test_zero_distance_is_base_fee_only():
    assert calculate_delivery_fee(3, 21.1458, 79.0882).fee == Decimal("20")


def test_missing_gps_falls_back_to_base_fee():
    quote = calculate_delivery_fee(3, None, None)
    assert quote.fee == Decimal("20") and quote.distance_estimated


def test_unconfigured_packing_point_falls_back_to_base_fee(monkeypatch):
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", None)
    quote = calculate_delivery_fee(3, 21.2, 79.1)
    assert quote.fee == Decimal("20") and quote.distance_estimated


def test_absurd_coordinate_is_capped():
    quote = calculate_delivery_fee(3, 0.0, 0.0)
    assert quote.fee == Decimal("20") + Decimal("10") * 30


def test_same_product_in_several_sizes_counts_once():
    # 15 cart lines but only 3 different products -> not a Bazaar.
    assert distinct_product_count([1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3]) == 3
    assert not calculate_delivery_fee(distinct_product_count([1] * 15), 21.2, 79.1).free_delivery


def test_fifteen_different_products_is_a_bazaar():
    assert calculate_delivery_fee(distinct_product_count(range(15)), 21.2, 79.1).free_delivery


def test_month_start_is_first_of_month_in_ist():
    from datetime import UTC, datetime

    from app.services.bazaar import month_start

    # 2026-10-31 20:00 UTC is already 2026-11-01 01:30 in IST.
    start = month_start(datetime(2026, 10, 31, 20, 0, tzinfo=UTC))
    assert (start.year, start.month, start.day, start.hour) == (2026, 11, 1, 0)


def test_haversine_known_distance():
    # Nagpur -> Wardha is roughly 70 km as the crow flies.
    assert 60 < haversine_km(21.1458, 79.0882, 20.7453, 78.6022) < 80
