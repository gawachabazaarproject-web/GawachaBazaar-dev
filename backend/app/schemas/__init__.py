"""Pydantic schemas package.

Architecture Conventions:
1. Pydantic v2 schemas define strict request and response API contracts.
2. Schemas are strictly decoupled from SQLAlchemy ORM models.
3. Client requests must never accept server-controlled fields:
   - id
   - created_at
   - updated_at
   - password_hash
4. Standard naming conventions:
   - Create<Resource>Request: payload for creating a resource
   - Update<Resource>Request: payload for updating a resource
   - <Resource>Response: single resource output contract
   - <Resource>ListResponse: collection/paginated output contract
"""

from app.schemas.base import (
    BaseSchema,
    DatabaseHealthResponse,
    ErrorResponse,
    HealthResponse,
    PingResponse,
)

__all__ = [
    "BaseSchema",
    "DatabaseHealthResponse",
    "ErrorResponse",
    "HealthResponse",
    "PingResponse",
]
