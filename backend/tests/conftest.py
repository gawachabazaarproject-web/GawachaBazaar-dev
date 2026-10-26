import os
from collections.abc import Generator

import pytest

from tests._db_safety import (
    UNROUTABLE_SENTINEL_URL,
    UnsafeTestDatabaseError,
    resolve_test_database_url,
    verify_live_target,
)

# ---------------------------------------------------------------------------
# Database safety - must run BEFORE `app` is imported.
#
# The suite TRUNCATEs tables, and application code outside the `get_db`
# override (app.db.session.SessionLocal: the reservation-expiry sweep, push
# sends) connects to whatever settings.DATABASE_URL says. So DATABASE_URL
# itself is pinned to the validated local test database (or to an unroutable
# sentinel if the configuration is unsafe). The target is never derived from
# the developer's DATABASE_URL. See tests/_db_safety.py for the policy.
# ---------------------------------------------------------------------------
try:
    TEST_DATABASE_URL: str | None = resolve_test_database_url(os.environ)
    TEST_DATABASE_ERROR: UnsafeTestDatabaseError | None = None
except UnsafeTestDatabaseError as _exc:
    TEST_DATABASE_URL = None
    TEST_DATABASE_ERROR = _exc

os.environ["DATABASE_URL"] = TEST_DATABASE_URL or UNROUTABLE_SENTINEL_URL
os.environ["APP_ENV"] = "testing"
# Never let a test reach real third-party services configured in a dev .env.
for _name in (
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
    "GOOGLE_MAPS_API_KEY",
    "FIREBASE_SERVICE_ACCOUNT_JSON",
):
    os.environ[_name] = ""

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.core.firebase import set_firebase  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.dependencies.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.firebase_fake import fake_firebase  # noqa: E402


def require_test_database_url() -> str:
    """The validated URL, or fail closed before any connection is attempted."""
    if TEST_DATABASE_URL is None:
        raise UnsafeTestDatabaseError(str(TEST_DATABASE_ERROR))
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine bound strictly to the validated local test DB."""
    url = require_test_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        verify_live_target(conn, url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def firebase_fake():
    """Every test runs against the in-memory Firebase fake - never the
    real Admin SDK (no network, no service account)."""
    fake_firebase.reset()
    set_firebase(fake_firebase)
    yield fake_firebase
    set_firebase(None)


@pytest.fixture(autouse=True)
def offline_routing(request, monkeypatch) -> None:
    """The ordinary suite never depends on public Internet services: the
    default routing provider is a stub that fails like an unreachable router.
    Tests that need a route inject their own provider; tests marked
    `integration` use the real one."""
    if request.node.get_closest_marker("integration"):
        return
    from app.services.routing import service as routing_service
    from app.services.routing.base import RoutingError, RoutingProvider

    class _Offline(RoutingProvider):
        name = "offline"

        def calculate_route(self, *_a):
            raise RoutingError("routing is disabled in the unit-test suite")

    monkeypatch.setattr(routing_service, "get_routing_provider", lambda: _Offline())


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

    # Re-verify the live target immediately before the only destructive SQL
    # in the suite.
    verify_live_target(connection, require_test_database_url())
    # verify_live_target autobegins a transaction on the raw Connection; end
    # it so the Session below owns (and really commits) its own transaction.
    # Left open, the Session would join it, `session.commit()` would not
    # commit, and the TRUNCATE's ACCESS EXCLUSIVE locks would block every
    # other connection for the rest of the test.
    connection.rollback()

    # Clean test tables before each test in dependency order
    session.execute(
        text(
            "TRUNCATE TABLE "
            "customer_notes, admin_action_logs, payment_webhook_events, "
            "payment_transactions, refunds, payments, "
            "promotion_redemptions, promotion_targets, promotion_eligible_customers, promotions, "
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
