"""API v1 Central Router.

Acts as the central registry for all v1 domain sub-routers.
Domain routers (auth, catalog, farms, inventory, cart, checkout, orders, payments)
will be registered here as each phase is implemented.
"""

from fastapi import APIRouter

from app.schemas.base import PingResponse

api_router = APIRouter()


@api_router.get(
    "/ping",
    response_model=PingResponse,
    tags=["system"],
    summary="API v1 Liveness Probe",
)
def ping() -> PingResponse:
    """Simple ping check for API v1."""
    return PingResponse(ping="pong")
