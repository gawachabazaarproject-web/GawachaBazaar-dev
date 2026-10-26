"""Production hardening: /readiness, DB pool/timeouts, per-user rate limits."""

from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.db.session import _server_options, engine
from tests.test_delivery_quote_api import _locate
from tests.test_phase_13_cart_orders import _create_address, _customer


def test_readiness_ok_and_does_not_call_the_router(client: TestClient, monkeypatch) -> None:
    from app.services.routing import service as routing_service

    def boom():
        raise AssertionError("readiness must not touch the routing provider")

    monkeypatch.setattr(routing_service, "get_routing_provider", boom)
    r = client.get("/readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready" and body["checks"]["database"] == "ok"


def test_readiness_is_503_when_the_database_is_down(client: TestClient) -> None:
    from sqlalchemy.exc import OperationalError

    from app.dependencies.database import get_db
    from app.main import app

    class DeadSession:
        def execute(self, *_a, **_k):
            raise OperationalError("SELECT 1", {}, Exception("down"))

    def dead():
        yield DeadSession()

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = dead
    try:
        r = client.get("/readiness")
    finally:
        app.dependency_overrides[get_db] = previous
    assert r.status_code == 503 and r.json()["checks"]["database"] == "down"


def test_pool_and_server_side_timeouts_are_configured() -> None:
    opts = _server_options()
    assert f"statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}" in opts
    assert f"idle_in_transaction_session_timeout={settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS}" in opts
    pool = engine.pool
    assert pool.size() == settings.DB_POOL_SIZE
    assert pool._max_overflow == settings.DB_MAX_OVERFLOW
    # worst case connections = workers x (pool + overflow); production runs 1 worker
    assert settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW <= 30  # db.t4g.micro max_connections ~110


def test_server_side_timeouts_really_apply_to_a_connection() -> None:
    q = "SELECT setting FROM pg_settings WHERE name = :n"  # value in ms
    with engine.connect() as conn:
        assert int(conn.execute(text(q), {"n": "statement_timeout"}).scalar()) == settings.DB_STATEMENT_TIMEOUT_MS
        assert (
            int(conn.execute(text(q), {"n": "idle_in_transaction_session_timeout"}).scalar())
            == settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS
        )


def test_quote_is_rate_limited_per_user_not_per_ip(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PACKING_POINT_LATITUDE", 21.1458)
    monkeypatch.setattr(settings, "PACKING_POINT_LONGITUDE", 79.0882)
    user_a, headers_a = _customer(db_session, "RL1")
    user_b, headers_b = _customer(db_session, "RL2")
    addr_a = _locate(db_session, _create_address(db_session, user_a))
    addr_b = _locate(db_session, _create_address(db_session, user_b))
    codes = [
        client.post("/api/v1/delivery/quote", json={"address_id": addr_a.id}, headers=headers_a).status_code
        for _ in range(32)
    ]
    assert codes.count(429) >= 1 and codes[0] != 429
    # same IP (the test client), different user: not throttled by A's usage
    assert client.post("/api/v1/delivery/quote", json={"address_id": addr_b.id}, headers=headers_b).status_code != 429


def test_geocode_and_checkout_have_limits(client: TestClient, db_session: Session, monkeypatch) -> None:
    from app.services.geocoding.base import GeocodeResult

    class Fake:
        def search(self, query, limit=5):
            return [GeocodeResult("x", 21.1, 79.1, "nominatim", "1")]

    monkeypatch.setattr("app.api.v1.delivery.get_geocoding_provider", lambda: Fake())
    _user, headers = _customer(db_session, "RL3")
    codes = [
        client.post("/api/v1/delivery/geocode", json={"query": "Sitabuldi"}, headers=headers).status_code
        for _ in range(12)
    ]
    assert 429 in codes
    checkout_codes = [
        client.post("/api/v1/cart/checkout", json={"address_id": 1}, headers=headers).status_code
        for _ in range(12)
    ]
    assert 429 in checkout_codes
