from pydantic import BaseModel, Field
from starlette.testclient import TestClient

from app.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.main import app


class SampleValidationModel(BaseModel):
    name: str = Field(..., min_length=2)
    quantity: int = Field(..., gt=0)


def test_custom_exception_handling(client: TestClient) -> None:
    """Verify uniform {code, message, details} formatting across exceptions."""

    @app.get("/test-not-found")
    def trigger_not_found() -> None:
        raise NotFoundError("Product item not found", details={"id": 42})

    @app.get("/test-auth-error")
    def trigger_auth_error() -> None:
        raise AuthenticationError("Invalid login credentials")

    @app.get("/test-authorization-error")
    def trigger_authorization_error() -> None:
        raise AuthorizationError("Insufficient role permissions")

    @app.get("/test-business-validation")
    def trigger_validation_error() -> None:
        raise BusinessValidationError("Quantity exceeds max limit", details={"max": 10})

    @app.get("/test-conflict")
    def trigger_conflict() -> None:
        raise ConflictError("User with this email already exists")

    @app.get("/test-base-app-exception")
    def trigger_base_app_exception() -> None:
        raise AppException("Generic domain failure", status_code=400, code="DOMAIN_FAILURE")

    @app.get("/test-unhandled")
    def trigger_unhandled() -> None:
        raise RuntimeError("Unexpected internal crash with sensitive database connection info")

    @app.post("/test-request-validation")
    def trigger_request_validation(body: SampleValidationModel) -> None:
        return None

    # 404
    r1 = client.get("/test-not-found")
    assert r1.status_code == 404
    assert r1.json() == {
        "code": "NOT_FOUND",
        "message": "Product item not found",
        "details": {"id": 42},
    }

    # 401
    r2 = client.get("/test-auth-error")
    assert r2.status_code == 401
    assert r2.json() == {
        "code": "AUTHENTICATION_ERROR",
        "message": "Invalid login credentials",
        "details": None,
    }

    # 403
    r_authz = client.get("/test-authorization-error")
    assert r_authz.status_code == 403
    assert r_authz.json() == {
        "code": "AUTHORIZATION_ERROR",
        "message": "Insufficient role permissions",
        "details": None,
    }

    # 422 - business validation
    r3 = client.get("/test-business-validation")
    assert r3.status_code == 422
    assert r3.json() == {
        "code": "BUSINESS_VALIDATION_ERROR",
        "message": "Quantity exceeds max limit",
        "details": {"max": 10},
    }

    # 409
    r4 = client.get("/test-conflict")
    assert r4.status_code == 409
    assert r4.json() == {
        "code": "CONFLICT_ERROR",
        "message": "User with this email already exists",
        "details": None,
    }

    # 400 - base app exception
    r_base = client.get("/test-base-app-exception")
    assert r_base.status_code == 400
    assert r_base.json() == {
        "code": "DOMAIN_FAILURE",
        "message": "Generic domain failure",
        "details": None,
    }

    # 422 - request validation error with details populated
    r_val = client.post("/test-request-validation", json={"name": "a", "quantity": 0})
    assert r_val.status_code == 422
    val_data = r_val.json()
    assert val_data["code"] == "REQUEST_VALIDATION_ERROR"
    assert val_data["message"] == "Validation error in request parameters or body"
    assert isinstance(val_data["details"], list)
    assert len(val_data["details"]) > 0

    # 500 - unexpected exception sanitized, internals not leaked
    r5 = client.get("/test-unhandled")
    assert r5.status_code == 500
    assert r5.json() == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected internal server error occurred",
        "details": None,
    }
    assert "sensitive" not in r5.text
    assert "database" not in r5.text
