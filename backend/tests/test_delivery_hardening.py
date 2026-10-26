"""DEL-1 (no router call while row locks are held), cache-key isolation,
quote-vs-route-cache separation and free-delivery route recording."""

import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.cart import Cart
from app.models.order import Order
from app.services import order as order_module
from app.services.delivery import calculate_delivery_fee
from app.services.routing import service as routing_service
from app.services.routing.base import RouteResult, RoutingProvider
from app.services.routing.cache import RouteCache, route_cache
from app.services.routing.osrm import OSRMProvider
from app.services.routing.service import RoutingService
from tests.test_delivery_fee import StubProvider
from tests.test_delivery_quote_api import _cart_with_item, _locate
from tests.test_delivery_routing import FakeRedis
from tests.test_phase_13_cart_orders import _ready_customer


@pytest.fixture
def env(monkeypatch):
    route_cache._local.clear()
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", 79.0882)
    monkeypatch.setattr(settings, "DELIVERY_BASE_FEE", Decimal("20"))
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("10"))
    monkeypatch.setattr(settings, "DELIVERY_MAX_DISTANCE_KM", 0.0)
    monkeypatch.setattr(settings, "DELIVERY_MIN_ORDER_VALUE", Decimal("0"))


class LockProbeProvider(RoutingProvider):
    """On every router call, tries to NOWAIT-lock the customer's cart and the
    variant rows from a SEPARATE connection. If checkout held those locks while
    waiting for the router, the probe fails."""

    name = "probe"

    def __init__(self, engine, user_id: int):
        self.engine, self.user_id = engine, user_id
        self.calls, self.blocked = 0, []

    def probe(self) -> list[str]:
        blocked = []
        with self.engine.connect() as conn:
            for table, where in (
                ("carts", f"user_id = {self.user_id}"),
                ("product_variants", "true"),
            ):
                try:
                    conn.execute(text(f"SELECT id FROM {table} WHERE {where} FOR UPDATE NOWAIT"))
                except OperationalError:
                    blocked.append(table)
                conn.rollback()
        return blocked

    def calculate_route(self, *_a) -> RouteResult:
        self.calls += 1
        self.blocked += self.probe()
        return RouteResult(4700, 600, self.name)


def test_probe_detects_a_held_lock(db_session: Session, test_engine, env) -> None:
    """Control: the probe really sees a lock, so the DEL-1 test is not vacuous."""
    user, _h, _v, _a = _ready_customer(db_session, "H0")
    db_session.add(Cart(user_id=user.id, status="ACTIVE"))
    db_session.commit()
    db_session.query(Cart).filter(Cart.user_id == user.id).with_for_update().all()  # held
    assert "carts" in LockProbeProvider(test_engine, user.id).probe()
    db_session.rollback()


def test_checkout_does_not_hold_row_locks_during_routing(
    client: TestClient, db_session: Session, test_engine, env, monkeypatch
) -> None:
    user, headers, variant, address = _ready_customer(db_session, "H1")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    provider = LockProbeProvider(test_engine, user.id)
    monkeypatch.setattr(routing_service, "get_routing_provider", lambda: provider)
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 201, r.text
    assert provider.calls == 1
    assert provider.blocked == [], f"row locks held during the router call: {provider.blocked}"


def test_checkout_conflicts_if_address_moved_after_routing(
    client: TestClient, db_session: Session, env, monkeypatch
) -> None:
    """The route is resolved before locking; if the address changes in between,
    checkout must not price with the stale route."""
    user, headers, variant, address = _ready_customer(db_session, "H2")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    monkeypatch.setattr(routing_service, "get_routing_provider", lambda: StubProvider(4700))

    real = order_module.OrderService._resolve_delivery_route

    def resolve_then_move(self, uid, aid):
        outcome = real(self, uid, aid)
        address.latitude = Decimal("21.250000")  # customer edits the pin meanwhile
        db_session.commit()
        return outcome

    monkeypatch.setattr(order_module.OrderService, "_resolve_delivery_route", resolve_then_move)
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 409
    assert db_session.query(Order).filter_by(user_id=user.id).count() == 0


def test_free_delivery_still_records_the_route(
    client: TestClient, db_session: Session, env, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "FREE_DELIVERY_MIN_ITEMS", 1)
    _user, headers, variant, address = _ready_customer(db_session, "H3")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    monkeypatch.setattr(routing_service, "get_routing_provider", lambda: StubProvider(4700))
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 201
    assert Decimal(r.json()["delivery_fee"]) == 0
    order = db_session.get(Order, r.json()["id"])
    assert order.delivery_distance_meters == 4700 and order.routing_provider == "stub"


def test_free_delivery_survives_routing_outage(
    client: TestClient, db_session: Session, env, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "FREE_DELIVERY_MIN_ITEMS", 1)
    _user, headers, variant, address = _ready_customer(db_session, "H4")
    _locate(db_session, address)
    _cart_with_item(client, headers, variant)
    # conftest's offline provider behaves like a router that is down
    r = client.post("/api/v1/cart/checkout", json={"address_id": address.id}, headers=headers)
    assert r.status_code == 201
    assert Decimal(r.json()["delivery_fee"]) == 0


# --- cache key isolation / quote vs route cache --------------------------------


def test_cache_key_isolates_origin_destination_and_endpoint():
    a = RoutingService(OSRMProvider("http://a.test"), RouteCache())
    b = RoutingService(OSRMProvider("http://b.test"), RouteCache())
    o1, o2, d = (21.1458, 79.0882), (21.2000, 79.1000), (21.19, 79.11)
    keys = {a._key(*o1, *d), a._key(*o2, *d), a._key(*d, *o1), b._key(*o1, *d)}
    assert len(keys) == 4
    assert a._key(*o1, *d).startswith("route:v1:osrm:driving:")


def test_changed_pricing_reprices_a_cached_route(monkeypatch):
    provider = StubProvider(5000)
    svc = RoutingService(provider, RouteCache())
    origin = (21.1458, 79.0882)
    first = calculate_delivery_fee(3, 21.2, 79.1, origin=origin, routing=svc)
    monkeypatch.setattr(settings, "DELIVERY_PER_KM", Decimal("12"))
    second = calculate_delivery_fee(3, 21.2, 79.1, origin=origin, routing=svc)
    assert provider.calls == 1  # the second price used the cached route
    assert first.fee == settings.DELIVERY_BASE_FEE + Decimal("10") * 5
    assert second.fee == settings.DELIVERY_BASE_FEE + Decimal("12") * 5


def test_distributed_lock_shares_one_router_call_across_workers():
    """Two 'workers' (separate RouteCache objects) sharing one fake Redis."""
    redis = FakeRedis()

    class Slow(StubProvider):
        def calculate_route(self, *a):
            time.sleep(0.4)
            return super().calculate_route(*a)

    provider = Slow(4700)
    services = [RoutingService(provider, RouteCache(redis)) for _ in range(2)]
    results = []

    def run(svc):
        results.append(svc.get_route(21.1458, 79.0882, 21.19, 79.11))

    threads = [threading.Thread(target=run, args=(s,)) for s in services]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert provider.calls == 1
    assert [r.distance_meters for r in results] == [4700, 4700]
