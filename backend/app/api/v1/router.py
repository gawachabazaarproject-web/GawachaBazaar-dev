"""API v1 Central Router.

Acts as the central registry for all v1 domain sub-routers.
Domain routers (auth, catalog, farms, inventory, cart, checkout, orders, payments)
will be registered here as each phase is implemented.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.bulk_orders import admin_router as bulk_orders_admin_router
from app.api.v1.bulk_orders import customer_router as bulk_orders_customer_router
from app.api.v1.cart import router as cart_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.fulfillments import router as fulfillments_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.orders import router as orders_router
from app.api.v1.packaging import router as packaging_router
from app.api.v1.payments import router as payments_router
from app.api.v1.payments import webhook_router as payments_webhook_router
from app.api.v1.suppliers import router as suppliers_router
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

# Cart domain routes (CUSTOMER-only; also hosts POST /cart/checkout)
api_router.include_router(cart_router, prefix="/cart", tags=["cart"])

# Order domain routes (CUSTOMER-only, user-scoped reads)
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])

# Payment domain routes (CUSTOMER-only: create/get/retry/verify)
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])

# PNB gateway webhook (no JWT - authenticity verified via gateway signature)
api_router.include_router(
    payments_webhook_router, prefix="/payments/webhooks", tags=["payments"]
)

# Fulfillment domain routes (internal staff + delivery partner:
# ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER)
api_router.include_router(
    fulfillments_router, prefix="/fulfillments", tags=["fulfillments"]
)

# Supplier domain routes (internal staff only: ADMIN, HUB_STAFF, OPERATIONS;
# performance evaluations ADMIN-only)
api_router.include_router(suppliers_router, prefix="/suppliers", tags=["suppliers"])

# Bulk & custom commerce routes (CUSTOMER-facing request/quote/accept +
# ADMIN/OPERATIONS review/quote/convert)
api_router.include_router(
    bulk_orders_customer_router, prefix="/bulk-orders", tags=["bulk-orders"]
)
api_router.include_router(
    bulk_orders_admin_router, prefix="/bulk-orders", tags=["bulk-orders"]
)


@api_router.get(
    "/ping",
    response_model=PingResponse,
    tags=["system"],
    summary="API v1 Liveness Probe",
)
def ping() -> PingResponse:
    """Simple ping check for API v1."""
    return PingResponse(ping="pong")
