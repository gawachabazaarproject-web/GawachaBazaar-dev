"""API v1 Central Router.

Acts as the central registry for all v1 domain sub-routers.
Domain routers (auth, catalog, farms, inventory, cart, checkout, orders, payments)
will be registered here as each phase is implemented.
"""

from fastapi import APIRouter

from app.api.v1.addresses import router as addresses_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bulk_orders import admin_router as bulk_orders_admin_router
from app.api.v1.bulk_orders import customer_router as bulk_orders_customer_router
from app.api.v1.cart import router as cart_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.customers import router as customers_router
from app.api.v1.fulfillments import router as fulfillments_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.orders import admin_router as orders_admin_router
from app.api.v1.orders import router as orders_router
from app.api.v1.orders import staff_router as orders_staff_router
from app.api.v1.packaging import router as packaging_router
from app.api.v1.payments import admin_router as payments_admin_router
from app.api.v1.payments import router as payments_router
from app.api.v1.payments import webhook_router as payments_webhook_router
from app.api.v1.promotions import router as promotions_router
from app.api.v1.suppliers import router as suppliers_router
from app.schemas.base import PingResponse

api_router = APIRouter()

# Authentication domain routes
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Address domain routes (CUSTOMER-only, user-scoped address book)
api_router.include_router(addresses_router, prefix="/addresses", tags=["addresses"])

# Catalog domain routes (public browsing + ADMIN-only management)
api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])

# Inventory domain routes (internal staff only: ADMIN, HUB_STAFF, OPERATIONS)
api_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])

# Packaging domain routes (internal staff only: ADMIN, HUB_STAFF, OPERATIONS)
api_router.include_router(packaging_router, prefix="/packaging", tags=["packaging"])

# Cart domain routes (CUSTOMER-only; also hosts POST /cart/checkout)
api_router.include_router(cart_router, prefix="/cart", tags=["cart"])

# Order domain routes (CUSTOMER-only, user-scoped reads + self-cancellation;
# admin_router: ADMIN-only administrative cancellation; staff_router:
# orders.read-permission list/detail for the admin panel).
#
# staff_router MUST be registered before orders_router: both define a GET
# at the same single-segment shape under /orders (literal "/admin" vs the
# customer router's `/{order_id}` catch-all), and FastAPI/Starlette match
# routes in registration order - registering the customer catch-all first
# would swallow `GET /orders/admin` as an attempt to parse "admin" as an
# order id (422) before the staff route is ever tried.
api_router.include_router(orders_staff_router, prefix="/orders", tags=["orders"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(orders_admin_router, prefix="/orders", tags=["orders"])

# Payment domain routes (CUSTOMER-only: create/get/retry/verify;
# admin_router: ADMIN-only payment list/detail + refund review/approve/
# reject/process).
#
# admin_router MUST be registered before the customer router: both define a
# GET at the same single-segment shape under /payments (literal "/refunds"/
# "/admin" vs the customer router's `/{payment_id}` catch-all), and
# FastAPI/Starlette match routes in registration order - registering the
# customer catch-all first would swallow `GET /payments/refunds` as an
# attempt to parse "refunds" as a payment id (422) before the admin route is
# ever tried. Same fix already applied to orders.py/orders_staff_router -
# verified live here: GET /payments/refunds returned 422 int_parsing before
# this reorder.
api_router.include_router(payments_admin_router, prefix="/payments", tags=["payments"])
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

# Promotion domain routes (ADMIN-only management; gated by promotions.*
# permissions). Customer-facing preview lives at POST /cart/evaluate-promo.
api_router.include_router(promotions_router, prefix="/promotions", tags=["promotions"])

# Customer Management domain routes (ADMIN-only; gated by customers.*
# permissions). A "customer" is an existing User with the CUSTOMER role -
# no separate identity system.
api_router.include_router(customers_router, prefix="/customers", tags=["customers"])


@api_router.get(
    "/ping",
    response_model=PingResponse,
    tags=["system"],
    summary="API v1 Liveness Probe",
)
def ping() -> PingResponse:
    """Simple ping check for API v1."""
    return PingResponse(ping="pong")
