from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.core.config import settings
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


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Isolated session per test that truncates test tables between tests."""
    connection = test_engine.connect()
    SessionLocalTest = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionLocalTest()

    # Clean test tables before each test in dependency order
    session.execute(
        text(
            "TRUNCATE TABLE auth_sessions, payment_transactions, payments, "
            "order_addresses, order_items, orders, cart_items, carts, "
            "packaging_outputs, packaging_inputs, packaging_operations, "
            "stock_movements, inventory_lots, inventory_locations, "
            "prices, product_images, quality_checks, batches, "
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
