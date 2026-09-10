"""Base Pydantic v2 schemas and common response models."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema for all Pydantic request and response models."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorResponse(BaseSchema):
    """Uniform error response schema."""

    code: str
    message: str
    details: Any = None


class HealthResponse(BaseSchema):
    """Service health check response schema."""

    status: str
    app: str
    environment: str


class DatabaseHealthResponse(BaseSchema):
    """Database health check response schema."""

    status: str
    database: str


class PingResponse(BaseSchema):
    """API v1 ping response schema."""

    ping: str
