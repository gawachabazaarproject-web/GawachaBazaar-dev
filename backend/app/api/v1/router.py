"""API v1 Central Router.

Acts as the central registry for all v1 domain sub-routers.
Domain routers (auth, catalog, farms, inventory, cart, checkout, orders, payments)
will be registered here as each phase is implemented.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.packaging import router as packaging_router
from app.schemas.base import PingResponse

api_router = APIRouter()

# Authentication domain routes
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Catalog domain routes (public browsing + ADMIN-only management)
api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])

# Inventory domain routes (internal staff only: ADMIN, HUB_STAFF, OPERATIONS)
api_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])

# Packaging domain routes (internal staff only: ADMIN, HUB_STAFF, OPERATIONS)
api_router.include_router(packaging_router, prefix="/packaging", tags=["packaging"])


@api_router.get(
    "/ping",
    response_model=PingResponse,
    tags=["system"],
    summary="API v1 Liveness Probe",
)
def ping() -> PingResponse:
    """Simple ping check for API v1."""
    return PingResponse(ping="pong")
