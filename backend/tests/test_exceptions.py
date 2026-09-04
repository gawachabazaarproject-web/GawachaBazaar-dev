from starlette.testclient import TestClient

from app.exceptions import (
    AuthenticationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.main import app


def test_custom_exception_handling(client: TestClient) -> None:
    """Verify custom AppException formatting through temporary test routes."""

    @app.get("/test-not-found")
    def trigger_not_found() -> None:
        raise NotFoundError("Product item not found", details={"id": 42})

    @app.get("/test-auth-error")
    def trigger_auth_error() -> None:
        raise AuthenticationError("Invalid login credentials")

    @app.get("/test-business-validation")
    def trigger_validation_error() -> None:
        raise BusinessValidationError("Quantity exceeds max limit", details={"max": 10})

    @app.get("/test-conflict")
    def trigger_conflict() -> None:
        raise ConflictError("User with this email already exists")

    @app.get("/test-unhandled")
    def trigger_unhandled() -> None:
        raise RuntimeError("Unexpected internal crash with sensitive info")

    # 404
    r1 = client.get("/test-not-found")
    assert r1.status_code == 404
    assert r1.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Product item not found",
            "details": {"id": 42},
        }
    }

    # 401
    r2 = client.get("/test-auth-error")
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "AUTHENTICATION_ERROR"

    # 422
    r3 = client.get("/test-business-validation")
    assert r3.status_code == 422
    assert r3.json()["error"]["code"] == "BUSINESS_VALIDATION_ERROR"

    # 409
    r4 = client.get("/test-conflict")
    assert r4.status_code == 409
    assert r4.json()["error"]["code"] == "CONFLICT_ERROR"

    # 500 - ensures sensitive info is NOT leaked in message
    r5 = client.get("/test-unhandled")
    assert r5.status_code == 500
    assert r5.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred",
            "details": None,
        }
    }
