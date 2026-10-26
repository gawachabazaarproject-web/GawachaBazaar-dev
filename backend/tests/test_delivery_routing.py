"""OSRM provider, route cache (Redis + in-process) and geocoder - all mocked,
no network."""

import json

import httpx
import pytest

from app.core.config import settings
from app.services.geocoding.base import GeocodingError
from app.services.geocoding.nominatim import NominatimProvider
from app.services.routing.base import NoRouteError, RoutingError
from app.services.routing.cache import RouteCache
from app.services.routing.osrm import OSRMProvider
from app.services.routing.service import RoutingService
from tests.test_delivery_fee import StubProvider

O = (21.1458, 79.0882)  # noqa: E741
D = (21.1900, 79.1100)


class FakeResponse:
    def __init__(self, status=200, body=None, text_ok=True):
        self.status_code = status
        self._body = body
        self._ok = text_ok

    def json(self):
        if not self._ok:
            raise ValueError("not json")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def patch_get(monkeypatch, response=None, exc=None, capture=None):
    def fake_get(url, **kw):
        if capture is not None:
            capture.update(url=url, **kw)
        if exc:
            raise exc
        return response

    monkeypatch.setattr(httpx, "get", fake_get)


OK_BODY = {"code": "Ok", "routes": [{"distance": 4700.4, "duration": 899.6}]}


# --- OSRM provider -------------------------------------------------------------


def test_osrm_success_and_lng_lat_order(monkeypatch):
    seen = {}
    patch_get(monkeypatch, FakeResponse(200, OK_BODY), capture=seen)
    result = OSRMProvider("http://osrm.test/", 2.0).calculate_route(*O, *D)
    assert (result.distance_meters, result.duration_seconds, result.provider) == (4700, 900, "osrm")
    assert result.distance_km == 4.7
    # longitude FIRST, then latitude
    assert seen["url"] == "http://osrm.test/route/v1/driving/79.0882,21.1458;79.11,21.19"
    assert seen["params"]["overview"] == "false"
    assert seen["timeout"] == 2.0


def test_osrm_timeout(monkeypatch):
    patch_get(monkeypatch, exc=httpx.ReadTimeout("slow"))
    with pytest.raises(RoutingError):
        OSRMProvider("http://osrm.test").calculate_route(*O, *D)


def test_osrm_http_500(monkeypatch):
    patch_get(monkeypatch, FakeResponse(500, {"message": "boom"}))
    with pytest.raises(RoutingError):
        OSRMProvider("http://osrm.test").calculate_route(*O, *D)


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(200, text_ok=False),
        FakeResponse(200, {"code": "Ok"}),
        FakeResponse(200, {"code": "Ok", "routes": []}),
        FakeResponse(200, {"code": "Ok", "routes": [{"distance": "x", "duration": 1}]}),
        FakeResponse(200, {"code": "Ok", "routes": [{"distance": -5, "duration": 1}]}),
        FakeResponse(200, {"code": "InvalidQuery"}),
    ],
)
def test_osrm_malformed_response(monkeypatch, response):
    patch_get(monkeypatch, response)
    with pytest.raises(RoutingError):
        OSRMProvider("http://osrm.test").calculate_route(*O, *D)


def test_osrm_no_route(monkeypatch):
    patch_get(monkeypatch, FakeResponse(400, {"code": "NoRoute"}))
    with pytest.raises(NoRouteError):
        OSRMProvider("http://osrm.test").calculate_route(*O, *D)


def test_osrm_far_from_any_road_is_unroutable(monkeypatch):
    body = {**OK_BODY, "waypoints": [{"distance": 5.0}, {"distance": 40_000.0}]}
    patch_get(monkeypatch, FakeResponse(200, body))
    with pytest.raises(NoRouteError):
        OSRMProvider("http://osrm.test").calculate_route(*O, *D)
    body["waypoints"][1]["distance"] = 35.0
    assert OSRMProvider("http://osrm.test").calculate_route(*O, *D).distance_meters == 4700


def test_osrm_rejects_out_of_range_coordinates():
    with pytest.raises(ValueError):
        OSRMProvider("http://osrm.test").calculate_route(*O, 95.0, 79.0)
    with pytest.raises(ValueError):
        OSRMProvider("http://osrm.test").calculate_route(*O, 21.0, 181.0)


# --- cache ---------------------------------------------------------------------


class FakeRedis:
    def __init__(self):
        self.data, self.ttls = {}, {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return None
        self.data[key] = value
        self.ttls[key] = ex
        return True

    def delete(self, key):
        self.data.pop(key, None)


class BrokenRedis:
    def __init__(self):
        self.calls = 0

    def get(self, key):
        self.calls += 1
        raise ConnectionError("redis down")

    def set(self, *a, **k):
        self.calls += 1
        raise ConnectionError("redis down")


def test_cache_miss_then_hit_calls_provider_once():
    provider, redis = StubProvider(4700), FakeRedis()
    svc = RoutingService(provider, RouteCache(redis))
    first = svc.get_route(*O, *D)
    second = svc.get_route(*O, *D)
    assert provider.calls == 1
    assert first == second
    (key,) = redis.data
    assert key.startswith("route:v1:stub:")
    assert json.loads(redis.data[key]) == {
        "distance_meters": 4700, "distance_km": 4.7, "duration_seconds": 600, "provider": "stub",
    }
    assert redis.ttls[key] == settings.ROUTE_CACHE_TTL_SECONDS


def test_expired_cache_calls_provider_again(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("app.services.routing.cache.time.monotonic", lambda: clock[0])
    provider = StubProvider(4700)
    svc = RoutingService(provider, RouteCache())  # in-process cache
    svc.get_route(*O, *D)
    clock[0] += settings.ROUTE_CACHE_TTL_SECONDS + 1
    svc.get_route(*O, *D)
    assert provider.calls == 2


def test_redis_down_still_routes_and_trips_the_breaker():
    provider, broken = StubProvider(4700), BrokenRedis()
    svc = RoutingService(provider, RouteCache(broken))
    assert svc.get_route(*O, *D).distance_meters == 4700
    assert svc.get_route(*O, *D).distance_meters == 4700
    # Redis was hit once (get fails -> breaker opens); afterwards the worker
    # uses its in-process cache instead of paying the socket timeout every time.
    assert broken.calls == 1
    assert provider.calls == 1


def test_provider_failure_is_not_cached():
    provider = StubProvider(error=RoutingError("down"))
    svc = RoutingService(provider, RouteCache())
    for _ in range(2):
        with pytest.raises(RoutingError):
            svc.get_route(*O, *D)
    assert provider.calls == 2
    provider.error, provider.meters = None, 1000
    assert svc.get_route(*O, *D).distance_meters == 1000


def test_cache_key_rounds_to_about_11_metres():
    provider = StubProvider(1000)
    svc = RoutingService(provider, RouteCache())
    svc.get_route(21.14581, 79.08821, 21.19001, 79.11001)
    svc.get_route(21.14582, 79.08822, 21.19002, 79.11002)
    assert provider.calls == 1


# --- Nominatim -----------------------------------------------------------------


def test_nominatim_parses_results_and_sends_user_agent(monkeypatch):
    monkeypatch.setattr("app.services.geocoding.nominatim._throttle", lambda: None)
    seen = {}
    rows = [
        {"place_id": 123, "display_name": "Sitabuldi, Nagpur", "lat": "21.1463", "lon": "79.0849"},
        {"place_id": 5, "display_name": "bad", "lat": "999", "lon": "79"},
        {"display_name": "missing coords"},
    ]
    patch_get(monkeypatch, FakeResponse(200, rows), capture=seen)
    (hit,) = NominatimProvider("http://nom.test").search("Sitabuldi Nagpur")
    assert (hit.latitude, hit.longitude, hit.provider, hit.provider_id) == (
        21.1463, 79.0849, "nominatim", "123",
    )
    assert seen["headers"]["User-Agent"] == settings.NOMINATIM_USER_AGENT
    assert seen["params"]["countrycodes"] == "in"


def test_nominatim_unavailable(monkeypatch):
    monkeypatch.setattr("app.services.geocoding.nominatim._throttle", lambda: None)
    patch_get(monkeypatch, exc=httpx.ConnectError("no"))
    with pytest.raises(GeocodingError):
        NominatimProvider("http://nom.test").search("x y z")
