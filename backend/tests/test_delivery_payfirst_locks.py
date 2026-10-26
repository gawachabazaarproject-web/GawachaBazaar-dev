# ruff: noqa: F811  (pytest fixtures imported from another test module)
"""DEL-7: in the pay-first flow the router is never called while the
checkout-session row (or the cart / variant rows) is locked."""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.order import Order
from app.services.routing import service as routing_service
from app.services.routing.base import RouteResult, RoutingProvider
from app.services.routing.cache import route_cache
from tests.test_delivery_quote_api import _locate
from tests.test_online_checkout import _basket, _pay_and_confirm, _start
from tests.test_razorpay_payments import FakeRazorpay, razorpay  # noqa: F401


class SessionLockProbe(RoutingProvider):
    name = "probe"

    def __init__(self, engine):
        self.engine, self.calls, self.blocked = engine, 0, []

    def calculate_route(self, *_a) -> RouteResult:
        self.calls += 1
        with self.engine.connect() as conn:
            for table in ("checkout_sessions", "carts", "product_variants"):
                try:
                    conn.execute(text(f"SELECT id FROM {table} FOR UPDATE NOWAIT"))
                except OperationalError:
                    self.blocked.append(table)
                conn.rollback()
        return RouteResult(4700, 600, self.name)


def test_pay_first_confirm_routes_before_any_lock(
    client: TestClient, db_session: Session, test_engine, razorpay: FakeRazorpay, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", 79.0882)
    user, headers, _variant, address = _basket(client, db_session, "DP1")
    _locate(db_session, address)
    probe = SessionLockProbe(test_engine)
    monkeypatch.setattr(routing_service, "get_routing_provider", lambda: probe)
    route_cache._local.clear()

    started = _start(client, headers, address.id)
    assert started.status_code == 200, started.text
    assert probe.calls == 1  # `start` quoted the route (no locks at that point either)
    route_cache._local.clear()  # force a real router call during confirm

    response = _pay_and_confirm(client, razorpay, headers, started.json())
    assert response.status_code == 200, response.text
    assert probe.calls == 2, "confirm must have asked the router (cache was cleared)"
    assert probe.blocked == [], f"locks held during the router call: {probe.blocked}"

    db_session.expire_all()
    order = db_session.query(Order).filter_by(user_id=user.id).one()
    assert order.delivery_distance_meters == 4700 and order.routing_provider == "probe"
    assert order.delivery_fee == settings.DELIVERY_BASE_FEE + settings.DELIVERY_PER_KM * Decimal("4.7")
    assert order.total_amount == Decimal(started.json()["amount"])
