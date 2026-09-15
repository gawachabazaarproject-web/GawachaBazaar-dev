from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import limiter
from app.dependencies.database import get_db
from app.main import app

# Explicitly isolate test database: gawachabazaar_test
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "/gawachabazaar", "/gawachabazaar_test"
)


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine bound strictly to gawachabazaar_test."""
    assert "gawachabazaar_test" in TEST_DATABASE_URL, (
        f"Safety failure: tests must run against gawachabazaar_test, got {TEST_DATABASE_URL}"
    )
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """`limiter` (app/core/rate_limit.py) is a module-level singleton shared
    by every request the test app handles, in-process, for the lifetime of
    the pytest run - unlike the database, nothing resets its in-memory
    counters between tests. Without this, tests that legitimately call a
    rate-limited endpoint (register/login/refresh) more than a handful of
    times across a single test *file* run start tripping 429s that have
    nothing to do with what each individual test is actually verifying.
    TestClient's fixed "testclient" remote address makes this worse than
    it would be against real distinct client IPs.
    """
    limiter.reset()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Isolated session per test that truncates test tables between tests."""
    connection = test_engine.connect()
    SessionLocalTest = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionLocalTest()

    # Clean test tables before each test in dependency order
    session.execute(
        text(
            "TRUNCATE TABLE auth_sessions, payment_webhook_events, "
            "payment_transactions, refunds, payments, "
            "quote_items, quote_versions, quotes, "
            "bulk_order_request_items, bulk_order_requests, bulk_customer_profiles, "
            "fulfillments, inventory_reservation_items, inventory_reservations, "
            "order_addresses, order_items, orders, cart_items, carts, "
            "packaging_outputs, packaging_inputs, packaging_operations, "
            "stock_movements, inventory_lots, inventory_locations, "
            "prices, product_images, quality_checks, batches, "
            "supplier_evaluations, supplier_products, suppliers, "
            "product_variants, products, categories, farms, user_roles, addresses, users, roles "
            "RESTART IDENTITY CASCADE;"
        )
    )
    session.commit()

    yield session

    session.close()
    connection.close()


@pytest.fixture
def client(test_engine, db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient fixture that interacts with the FastAPI app in-process using isolated test db."""
    SessionLocalTest = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = SessionLocalTest()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app=app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
