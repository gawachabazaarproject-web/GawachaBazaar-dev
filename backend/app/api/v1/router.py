"""API v1 Central Router.

Acts as the central registry for all v1 domain sub-routers.
Domain routers (auth, catalog, farms, inventory, cart, checkout, orders, payments)
will be registered here as each phase is implemented.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.schemas.base import PingResponse

api_router = APIRouter()

# Authentication domain routes
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])


@api_router.get(
    "/ping",
    response_model=PingResponse,
    tags=["system"],
    summary="API v1 Liveness Probe",
)
def ping() -> PingResponse:
    """Simple ping check for API v1."""
    return PingResponse(ping="pong")
