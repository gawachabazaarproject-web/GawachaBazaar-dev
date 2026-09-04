from unittest.mock import MagicMock

from starlette.testclient import TestClient

from app.db.session import get_db
from app.main import app


def test_service_health(client: TestClient) -> None:
    """Verify GET /health returns 200 and expected payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "environment" in data


def test_api_v1_ping(client: TestClient) -> None:
    """Verify GET /api/v1/ping returns 200."""
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}


def test_database_health_success(client: TestClient) -> None:
    """Verify GET /health/db returns 200 when database executes successfully."""
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy",
            "database": "connected",
        }
    finally:
        app.dependency_overrides.clear()


def test_database_health_failure(client: TestClient) -> None:
    """Verify GET /health/db returns 503 when database execution fails, with no leaks."""
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Connection refused password=secret")
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data == {
            "status": "unhealthy",
            "database": "disconnected",
        }
        assert "password" not in str(data)
        assert "secret" not in str(data)
    finally:
        app.dependency_overrides.clear()
