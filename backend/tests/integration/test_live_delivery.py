"""LIVE integration tests: real PostgreSQL + real Redis + real OSRM (+ real
Nominatim). Not part of the normal suite - they need the public Internet.

    GB_INTEGRATION=1 GB_INTEGRATION_REDIS_URL=redis://127.0.0.1:16379/0 \\
    TEST_DATABASE_URL=<disposable *_test db> \\
    python -m pytest -p no:cacheprovider tests/integration -m integration -s

Locations are public Nagpur landmarks (coordinates resolved with Nominatim on
2026-10-26); the "packing point" is a stand-in (Zero Mile Stone), NOT the real
Gawacha Bazaar warehouse. No customer data is used.
"""

import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import ROUND_CEILING, Decimal

import httpx
import pytest
import redis as redis_lib
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.inventory_location import InventoryLocation
from app.models.order import Order
from app.services.routing import service as routing_service
from app.services.routing.cache import RouteCache
from app.services.routing.osrm import OSRMProvider
from app.services.routing.service import RoutingService
from tests.test_delivery_quote_api import _cart_with_item
from tests.test_phase_13_cart_orders import _create_address, _customer, _ready_customer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("GB_INTEGRATION") != "1", reason="set GB_INTEGRATION=1"),
]

REDIS_URL = os.environ.get("GB_INTEGRATION_REDIS_URL", "redis://127.0.0.1:16379/0")

# Stand-in packing point (Zero Mile Stone, Nagpur) unless the REAL warehouse
# coordinates are supplied: GB_WAREHOUSE_LAT / GB_WAREHOUSE_LNG.
ORIGIN = (
    float(os.environ.get("GB_WAREHOUSE_LAT", 21.1497877)),
    float(os.environ.get("GB_WAREHOUSE_LNG", 79.0806859)),
)
PLACES = {
    "ambazari": (21.1286919, 79.0457448),  # Ambazari Lake
    "airport": (21.0895028, 79.0460288),  # Dr. Babasaheb Ambedkar Intl Airport
    "kamptee": (21.2170645, 79.1964178),  # Kamptee
}
RESULTS: dict = {}


def haversine_km(a, b) -> float:  # test-only plausibility check, never used by the app
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


@pytest.fixture
def live(monkeypatch):
    """Real Redis (flushed of route keys), real OSRM wrapped by a request counter."""
    client = redis_lib.Redis.from_url(REDIS_URL)
    client.ping()
    for k in client.scan_iter("route:v1:*"):
        client.delete(k)
    for k in client.scan_iter("lock:route:v1:*"):
        client.delete(k)
    monkeypatch.setattr(settings, "REDIS_URL", REDIS_URL)
    cache = RouteCache()
    monkeypatch.setattr(routing_service, "route_cache", cache)
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", ORIGIN[0])
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", ORIGIN[1])
    monkeypatch.setattr(settings, "DELIVERY_BASE_FEE", Decimal("40"))
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("10"))
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 0.0)

    stats = {"osrm_calls": 0, "latencies_ms": [], "nominatim_starts": []}
    lock = threading.Lock()
    real_get = httpx.get

    def counting_get(url, **kw):
        if str(url).startswith(settings.OSRM_BASE_URL):
            t = time.perf_counter()
            try:
                return real_get(url, **kw)
            finally:
                with lock:
                    stats["osrm_calls"] += 1
                    stats["latencies_ms"].append((time.perf_counter() - t) * 1000)
        if str(url).startswith(settings.NOMINATIM_BASE_URL):
            with lock:
                stats["nominatim_starts"].append(time.perf_counter())
        return real_get(url, **kw)

    monkeypatch.setattr(httpx, "get", counting_get)
    stats["redis"] = client
    stats["cache"] = cache
    return stats


def _expected_fee(meters: int) -> Decimal:
    return (Decimal("40") + Decimal("10") * (Decimal(meters) / 1000)).to_integral_value(
        rounding=ROUND_CEILING
    )


def test_real_osrm_parsing_and_coordinate_order(live):
    provider = OSRMProvider()
    result = provider.calculate_route(*ORIGIN, *PLACES["ambazari"])
    lng_lat = f"{ORIGIN[1]},{ORIGIN[0]};{PLACES['ambazari'][1]},{PLACES['ambazari'][0]}"
    raw = httpx.get(
        f"{settings.OSRM_BASE_URL}/route/v1/driving/{lng_lat}", params={"overview": "false"}, timeout=10
    ).json()
    assert raw["code"] == "Ok"
    assert result.distance_meters == round(raw["routes"][0]["distance"])
    assert result.duration_seconds == round(raw["routes"][0]["duration"])
    assert result.distance_km == round(result.distance_meters / 1000, 3)
    straight = haversine_km(ORIGIN, PLACES["ambazari"])
    assert straight <= result.distance_meters / 1000 <= straight * 2.5  # road >= straight, sane
    assert 5.0 < result.distance_meters / 1000 < 9.0  # Zero Mile -> Ambazari is ~6.7 km by road

    # Proof that order matters: lat,lng swapped is NOT the same answer.
    swapped = httpx.get(
        f"{settings.OSRM_BASE_URL}/route/v1/driving/{ORIGIN[0]},{ORIGIN[1]};"
        f"{PLACES['ambazari'][0]},{PLACES['ambazari'][1]}",
        params={"overview": "false"},
        timeout=10,
    ).json()
    swapped_m = swapped["routes"][0]["distance"] if swapped.get("routes") else None
    assert swapped_m != raw["routes"][0]["distance"]
    RESULTS["osrm_ambazari"] = {
        "origin": ORIGIN, "destination": PLACES["ambazari"],
        "distance_meters": result.distance_meters, "distance_km": result.distance_km,
        "duration_seconds": result.duration_seconds, "straight_line_km": round(straight, 2),
        "swapped_order_distance_m": swapped_m,
    }


def test_swapped_coordinates_are_rejected_by_the_snap_guard(live):
    """Public OSRM answers "Ok" with distance 0 when Nagpur's lat/lng are swapped
    (the points land in the Arctic). That must be unroutable, never a free delivery."""
    from app.services.routing.base import RoutingError

    swapped_origin = (ORIGIN[1], ORIGIN[0])  # lat=79.08, lng=21.14 (Svalbard)
    swapped_dest = (PLACES["ambazari"][1], PLACES["ambazari"][0])
    with pytest.raises(RoutingError):  # NoRouteError is a RoutingError
        OSRMProvider().calculate_route(*swapped_origin, *swapped_dest)


def test_redis_miss_set_ttl_then_hit_without_osrm(live, caplog):
    import logging

    caplog.set_level(logging.INFO)
    svc = RoutingService(cache=live["cache"])
    t0 = time.perf_counter()
    first = svc.get_route(*ORIGIN, *PLACES["airport"])
    miss_ms = (time.perf_counter() - t0) * 1000
    assert live["osrm_calls"] == 1
    keys = list(live["redis"].scan_iter("route:v1:*"))
    assert len(keys) == 1 and keys[0].decode().startswith("route:v1:osrm:driving:")
    ttl = live["redis"].ttl(keys[0])
    assert 0 < ttl <= settings.ROUTE_CACHE_TTL_SECONDS
    assert not list(live["redis"].scan_iter("lock:*")), "lock must be released"

    t0 = time.perf_counter()
    second = svc.get_route(*ORIGIN, *PLACES["airport"])
    hit_ms = (time.perf_counter() - t0) * 1000
    assert live["osrm_calls"] == 1, "second request must not reach OSRM"
    assert second == first
    msgs = [r.getMessage() for r in caplog.records if r.name.endswith("routing.service")]
    assert any("cache=miss" in m and "status=ok" in m for m in msgs)
    assert any("cache=hit" in m for m in msgs)
    RESULTS["cache"] = {
        "airport_distance_m": first.distance_meters, "duration_s": first.duration_seconds,
        "miss_ms": round(miss_ms, 1), "hit_ms": round(hit_ms, 2), "ttl_s": ttl,
        "osrm_ms": [round(x, 1) for x in live["latencies_ms"]],
    }


def test_expired_redis_entry_is_refetched(live):
    svc = RoutingService(cache=live["cache"])
    svc.get_route(*ORIGIN, *PLACES["ambazari"])
    (key,) = list(live["redis"].scan_iter("route:v1:*"))
    live["redis"].pexpire(key, 1)
    time.sleep(0.05)
    svc.get_route(*ORIGIN, *PLACES["ambazari"])
    assert live["osrm_calls"] == 2


def test_three_nagpur_locations_have_distinct_plausible_distances(live):
    svc = RoutingService(cache=live["cache"])
    got = {}
    for name, point in PLACES.items():
        r = svc.get_route(*ORIGIN, *point)
        straight = haversine_km(ORIGIN, point)
        assert straight <= r.distance_meters / 1000 <= straight * 2.5
        got[name] = {"distance_m": r.distance_meters, "duration_s": r.duration_seconds,
                     "straight_km": round(straight, 2), "fee": str(_expected_fee(r.distance_meters))}
    km = {k: v["distance_m"] for k, v in got.items()}
    assert len(set(km.values())) == 3
    assert km["ambazari"] < km["airport"] < km["kamptee"]
    RESULTS["three_locations"] = got


def test_ten_simultaneous_identical_requests_make_one_osrm_call(live):
    svc_list = [RoutingService(cache=live["cache"]) for _ in range(10)]
    barrier = threading.Barrier(10)

    def go(s):
        barrier.wait()
        return s.get_route(*ORIGIN, *PLACES["kamptee"]).distance_meters

    with ThreadPoolExecutor(10) as ex:
        results = list(ex.map(go, svc_list))
    assert len(set(results)) == 1
    assert live["osrm_calls"] == 1, f"{live['osrm_calls']} OSRM calls for 10 identical requests"
    RESULTS["stampede"] = {"requests": 10, "osrm_calls": live["osrm_calls"]}


def test_redis_down_still_routes(live, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    svc = RoutingService(cache=RouteCache())
    r = svc.get_route(*ORIGIN, *PLACES["ambazari"])
    assert r.distance_meters > 0
    assert any("redis_unavailable" in x.getMessage() for x in caplog.records)
    assert live["osrm_calls"] == 1


@pytest.mark.skipif(not os.environ.get("GB_INTEGRATION_REDIS_CONTAINER"), reason="needs the redis docker container name")
def test_redis_container_stopped_mid_flight(client: TestClient, db_session: Session, live, caplog):
    """Stop the real Redis container: quote and checkout must still succeed
    (route from OSRM, correct fee), with the outage logged."""
    import logging
    import subprocess

    caplog.set_level(logging.WARNING)
    name = os.environ["GB_INTEGRATION_REDIS_CONTAINER"]
    user, headers, variant, address = _ready_customer(db_session, "L8")
    address.latitude, address.longitude = PLACES["ambazari"]
    db_session.commit()
    _cart_with_item(client, headers, variant)
    subprocess.run(["docker", "stop", name], check=True, capture_output=True)
    try:
        t0 = time.perf_counter()
        q = client.post("/api/v1/delivery/quote", json={"address_id": address.id}, headers=headers)
        down_ms = (time.perf_counter() - t0) * 1000
        assert q.status_code == 200, q.text
        assert Decimal(q.json()["delivery_fee"]) == _expected_fee(q.json()["distance_meters"])
        r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
        assert r.status_code == 201, r.text
        assert Decimal(r.json()["delivery_fee"]) == Decimal(q.json()["delivery_fee"])
        assert any("redis_unavailable" in x.getMessage() for x in caplog.records)
        RESULTS["redis_stopped"] = {"quote_ms_first_call_with_redis_down": round(down_ms), "checkout": 201}
    finally:
        subprocess.run(["docker", "start", name], check=True, capture_output=True)


def test_osrm_down_returns_503_and_no_order(client: TestClient, db_session: Session, live, monkeypatch):
    user, headers, variant, address = _ready_customer(db_session, "L1")
    address.latitude, address.longitude = PLACES["ambazari"][0], PLACES["ambazari"][1]
    db_session.commit()
    _cart_with_item(client, headers, variant)
    monkeypatch.setattr(settings, "OSRM_BASE_URL", "http://127.0.0.1:9")
    assert client.post("/api/v1/delivery/quote", json={"address_id": address.id}, headers=headers).status_code == 503
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 503
    assert db_session.query(Order).filter_by(user_id=user.id).count() == 0


def test_nominatim_down_does_not_affect_saved_addresses(
    client: TestClient, db_session: Session, live, monkeypatch
):
    monkeypatch.setattr(settings, "NOMINATIM_BASE_URL", "http://127.0.0.1:9")
    user, headers = _customer(db_session, "L2")
    address = _create_address(db_session, user)
    address.latitude, address.longitude = PLACES["ambazari"][0], PLACES["ambazari"][1]
    db_session.commit()
    assert client.post("/api/v1/delivery/quote", json={"address_id": address.id}, headers=headers).status_code == 200
    assert client.post("/api/v1/delivery/geocode", json={"query": "Ambazari Lake Nagpur"}, headers=headers).status_code == 503


def test_real_nominatim_geocode_through_the_api(client: TestClient, db_session: Session, live):
    _user, headers = _customer(db_session, "L3")
    t0 = time.perf_counter()
    r = client.post("/api/v1/delivery/geocode", json={"query": "Ambazari Lake, Nagpur"}, headers=headers)
    first_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and items[0]["provider"] == "nominatim" and items[0]["provider_id"]
    assert haversine_km((items[0]["latitude"], items[0]["longitude"]), PLACES["ambazari"]) < 1.0
    # two back-to-back searches are spaced >= 1 s apart (Nominatim policy)
    client.post("/api/v1/delivery/geocode", json={"query": "Futala Lake, Nagpur"}, headers=headers)
    starts = live["nominatim_starts"]
    assert len(starts) == 2 and starts[1] - starts[0] >= 0.99  # request START to START
    empty = client.post("/api/v1/delivery/geocode", json={"query": "zzqqxx nonexistent place 99999"}, headers=headers)
    assert empty.status_code == 200 and empty.json()["items"] == []
    RESULTS["nominatim"] = {"first_ms": round(first_ms), "top": items[0]["display_name"][:60]}


def test_end_to_end_quote_checkout_order(client: TestClient, db_session: Session, live):
    """customer -> address -> cart -> /delivery/quote -> checkout (tampered) -> order row."""
    user, headers, variant, address = _ready_customer(db_session, "L4")
    hub = db_session.query(InventoryLocation).first()  # the warehouse the helper created
    hub.latitude, hub.longitude, hub.is_packing_point = ORIGIN[0], ORIGIN[1], True
    db_session.commit()
    _cart_with_item(client, headers, variant)

    created = client.post(
        "/api/v1/addresses",
        json={"label": "Test", "address_line_1": "Ambazari Lake (landmark)", "city": "Nagpur",
              "state": "Maharashtra", "postal_code": "440010",
              "latitude": str(round(PLACES["ambazari"][0], 6)), "longitude": str(round(PLACES["ambazari"][1], 6)),
              "geocode_provider_id": "248035495"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    aid = created.json()["id"]

    t0 = time.perf_counter()
    q1 = client.post("/api/v1/delivery/quote", json={"address_id": aid}, headers=headers)
    q1_ms = (time.perf_counter() - t0) * 1000
    assert q1.status_code == 200, q1.text
    body = q1.json()
    assert body["available"] and body["distance_meters"] > 0
    assert Decimal(body["delivery_fee"]) == _expected_fee(body["distance_meters"])
    assert live["osrm_calls"] == 1

    t0 = time.perf_counter()
    q2 = client.post("/api/v1/delivery/quote", json={"address_id": aid}, headers=headers)
    q2_ms = (time.perf_counter() - t0) * 1000
    assert q2.json() == body
    assert live["osrm_calls"] == 1, "second quote must be a Redis hit"

    t0 = time.perf_counter()
    r = client.post(
        "/api/v1/cart/checkout",
        json={"address_id": aid, "delivery_fee": 1, "distance_km": 0.1, "warehouse_id": 99999},
        headers=headers,
    )
    checkout_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 201, r.text
    detail = r.json()
    assert live["osrm_calls"] == 1, "checkout reuses the cached route"

    db_session.expire_all()
    order = db_session.get(Order, detail["id"])
    assert order.user_id == user.id
    assert order.delivery_distance_meters == body["distance_meters"]
    assert order.routing_provider == "osrm"
    assert order.warehouse_id == hub.id
    assert order.delivery_fee == Decimal(body["delivery_fee"])
    assert order.total_amount == order.subtotal_amount - order.discount_amount + order.delivery_fee
    RESULTS["e2e"] = {
        "order_id": order.id, "customer_id": user.id, "warehouse_id": order.warehouse_id,
        "distance_m": order.delivery_distance_meters, "provider": order.routing_provider,
        "delivery_fee": str(order.delivery_fee), "subtotal": str(order.subtotal_amount),
        "discount": str(order.discount_amount), "total": str(order.total_amount),
        "quote_miss_ms": round(q1_ms, 1), "quote_hit_ms": round(q2_ms, 1), "checkout_ms": round(checkout_ms, 1),
    }


def test_outside_radius_with_real_route(client: TestClient, db_session: Session, live, monkeypatch):
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 12.0)
    user, headers = _customer(db_session, "L5")
    address = _create_address(db_session, user)
    address.latitude, address.longitude = PLACES["kamptee"]
    db_session.commit()
    r = client.post("/api/v1/delivery/quote", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False and body["delivery_fee"] is None
    assert 16.0 < body["distance_km"] < 17.0
    assert body["reason"] == "Delivery is not available beyond 12 km."


def test_ten_simultaneous_quote_requests(client: TestClient, db_session: Session, live):
    user, headers = _customer(db_session, "L6")
    address = _create_address(db_session, user)
    address.latitude, address.longitude = PLACES["airport"]
    db_session.commit()
    aid = address.id  # read before the threads start: the test session is not thread-safe
    barrier = threading.Barrier(10)

    def go(_):
        barrier.wait()
        return client.post("/api/v1/delivery/quote", json={"address_id": aid}, headers=headers)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(10) as ex:
        responses = list(ex.map(go, range(10)))
    total_ms = (time.perf_counter() - t0) * 1000
    assert [r.status_code for r in responses] == [200] * 10
    assert len({r.text for r in responses}) == 1
    assert live["osrm_calls"] == 1
    RESULTS["ten_quotes"] = {"osrm_calls": live["osrm_calls"], "wall_ms": round(total_ms)}


def test_concurrent_double_submit_creates_one_order(client: TestClient, db_session: Session, live):
    user, headers, variant, address = _ready_customer(db_session, "L7")
    address.latitude, address.longitude = PLACES["ambazari"]
    db_session.commit()
    _cart_with_item(client, headers, variant)
    aid, uid = address.id, user.id  # read before the threads start
    barrier = threading.Barrier(5)

    def go(_):
        barrier.wait()
        return client.post("/api/v1/cart/checkout", json={"address_id": aid}, headers=headers)

    with ThreadPoolExecutor(5) as ex:
        responses = list(ex.map(go, range(5)))
    assert sorted(r.status_code for r in responses)[0] in (200, 201)
    db_session.expire_all()
    assert db_session.query(Order).filter_by(user_id=uid).count() == 1
    fees = {r.json()["delivery_fee"] for r in responses if r.status_code in (200, 201)}
    assert len(fees) == 1
    RESULTS["double_submit"] = {"statuses": sorted(r.status_code for r in responses), "orders": 1}


@pytest.mark.skipif(not os.environ.get("GB_INTEGRATION_SELFHOSTED_OSRM"), reason="needs a self-hosted OSRM URL")
def test_switching_osrm_base_url_changes_endpoint_not_logic(live, monkeypatch):
    """Same code, same pricing, different OSRM_BASE_URL: results agree and the
    cache namespace differs, so the two endpoints never share cache entries."""
    own = os.environ["GB_INTEGRATION_SELFHOSTED_OSRM"]
    public_svc = RoutingService(OSRMProvider("https://router.project-osrm.org"), live["cache"])
    public = public_svc.get_route(*ORIGIN, *PLACES["ambazari"])
    monkeypatch.setattr(settings, "OSRM_BASE_URL", own)
    own_svc = RoutingService(cache=live["cache"])  # default provider reads OSRM_BASE_URL
    assert own_svc.provider.base_url == own.rstrip("/")
    mine = own_svc.get_route(*ORIGIN, *PLACES["ambazari"])
    assert public_svc._key(*ORIGIN, *PLACES["ambazari"]) != own_svc._key(*ORIGIN, *PLACES["ambazari"])
    assert abs(mine.distance_meters - public.distance_meters) / public.distance_meters < 0.05
    RESULTS["self_hosted"] = {"public_m": public.distance_meters, "self_hosted_m": mine.distance_meters,
                              "public_fee": str(_expected_fee(public.distance_meters)),
                              "self_hosted_fee": str(_expected_fee(mine.distance_meters))}


def test_zz_print_evidence():
    import json

    print("\nINTEGRATION_EVIDENCE " + json.dumps(RESULTS, default=str, ensure_ascii=False))
