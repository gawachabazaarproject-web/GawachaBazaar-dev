import uuid
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.v1.router import api_router
from app.core.request_id import (
    REQUEST_ID_HEADER,
    get_request_id,
    sanitize_or_generate_request_id,
)
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.main import create_application
from app.schemas.base import HealthResponse, PingResponse


def test_application_factory_and_import() -> None:
    """Verify application factory creates a valid FastAPI instance with lifespan."""
    test_app = create_application()
    assert test_app.title == "GawachaBazaar"
    assert test_app.version == "0.1.0"


def test_health_endpoint(client: TestClient) -> None:
    """Verify /health returns HTTP 200 and matches HealthResponse schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    validated = HealthResponse.model_validate(data)
    assert validated.status == "ok"
    assert validated.app == "GawachaBazaar"
    assert validated.environment in ["development", "testing", "staging", "production"]


def test_database_health_endpoint_with_live_db(
    client: TestClient, db_session: Session
) -> None:
    """Verify /health/db returns HTTP 200 with test DB."""
    response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "status": "healthy",
        "database": "connected",
    }


def test_api_v1_router_registration(client: TestClient) -> None:
    """Verify /api/v1 prefix router is registered and ping works."""
    assert api_router is not None
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    validated = PingResponse.model_validate(response.json())
    assert validated.ping == "pong"


def test_request_id_generated_when_header_absent(client: TestClient) -> None:
    """Verify X-Request-ID is generated and returned in response when absent in request."""
    response = client.get("/health")
    assert REQUEST_ID_HEADER in response.headers
    req_id = response.headers[REQUEST_ID_HEADER]
    assert len(req_id) >= 16


def test_request_id_propagated_when_header_present(client: TestClient) -> None:
    """Verify trusted X-Request-ID header is propagated into response headers."""
    client_id = f"client-req-{uuid.uuid4().hex[:12]}"
    response = client.get("/health", headers={REQUEST_ID_HEADER: client_id})
    assert response.headers[REQUEST_ID_HEADER] == client_id


def test_request_id_sanitization_and_length_limit() -> None:
    """Verify sanitize_or_generate_request_id enforces valid chars and length limit."""
    # Valid alphanumeric and dashes
    assert sanitize_or_generate_request_id("valid-req-id_123") == "valid-req-id_123"

    # Too long (> 64 chars) should be rejected and fresh UUID generated
    too_long = "a" * 65
    sanitized = sanitize_or_generate_request_id(too_long)
    assert sanitized != too_long
    assert len(sanitized) == 32  # uuid4 hex

    # Dangerous or invalid characters should be rejected
    invalid_chars = "req<script>alert(1)</script>"
    sanitized_invalid = sanitize_or_generate_request_id(invalid_chars)
    assert sanitized_invalid != invalid_chars

    # Whitespace or None
    assert len(sanitize_or_generate_request_id(None)) == 32
    assert len(sanitize_or_generate_request_id("   ")) == 32


def test_request_id_contextvar_isolation_and_cleanup(client: TestClient) -> None:
    """Verify ContextVar request ID is cleaned up and reset after request completion."""
    assert get_request_id() == "-"

    # Issue a request
    client.get("/health")

    # Outside the request, ContextVar must be reset back to default
    assert get_request_id() == "-"


def test_database_dependency_lifecycle() -> None:
    """Verify get_db dependency yields a session and closes it in finally."""
    gen: Generator[Session, None, None] = get_db()
    session = next(gen)
    assert isinstance(session, Session)
    assert session.is_active

    # Closing generator should trigger session.close()
    with pytest.raises(StopIteration):
        next(gen)


def test_auth_dependency_boundaries_not_wired_to_active_routes() -> None:
    """Verify get_current_user enforces authentication and require_roles exists as Phase 9 boundary."""
    mock_db = MagicMock(spec=Session)

    # Calling get_current_user without credentials raises AuthenticationError
    with pytest.raises(AuthenticationError) as exc_info:
        get_current_user(credentials=None, db=mock_db)
    assert "Not authenticated" in exc_info.value.message

    # Role checker factory raises explicit AuthorizationError
    role_checker = require_roles("admin")
    with pytest.raises(AuthorizationError) as authz_exc:
        role_checker(current_user=None)
    assert "Phase 9" in authz_exc.value.message
