from decimal import Decimal

import httpx
import pytest

from app.core.config import get_settings
from app.exceptions.base import BusinessValidationError
from app.services import delivery


@pytest.fixture(autouse=True)
def _warehouse(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "WAREHOUSE_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "WAREHOUSE_LONGITUDE", 79.0882)
    delivery._road_km.cache_clear()


def test_fee_is_base_plus_per_km_on_road_distance(monkeypatch):
    class Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"routes": [{"distance": 5240.0}]}

    monkeypatch.setattr(delivery.httpx, "get", lambda *a, **k: Resp())
    q = delivery.quote_delivery(Decimal("21.2"), Decimal("79.1"))
    assert q.method == "road"
    assert q.distance_km == Decimal("5.2")
    assert q.fee == Decimal("72.00")  # 20 + 10 * 5.2


def test_falls_back_to_estimate_when_routing_is_down(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(delivery.httpx, "get", boom)
    q = delivery.quote_delivery(Decimal("21.2"), Decimal("79.1"))
    assert q.method == "estimate"
    assert q.fee > Decimal("20")


def test_missing_coordinates_is_rejected():
    with pytest.raises(BusinessValidationError):
        delivery.quote_delivery(None, None)
