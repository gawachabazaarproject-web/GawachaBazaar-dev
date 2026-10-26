import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.concurrency import InflightLimitMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.rate_limit import limiter
from app.core.realtime import register_main_loop
from app.core.request_id import RequestIDMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.session import SessionLocal
from app.dependencies.database import get_db
from app.dependencies.payments import get_payment_gateway
from app.exceptions.handlers import register_exception_handlers
from app.schemas.base import DatabaseHealthResponse, HealthResponse
from app.services.checkout_session import CheckoutSessionService
from app.services.inventory_reservation import InventoryReservationService

# No Celery/APScheduler exists in this codebase - this is the smallest
# safe way to give inventory reservation expiry a proactive sweep
# instead of relying only on something happening to read/pay/expire one
# specific order. See InventoryReservationService.sweep_expired_reservations.
RESERVATION_EXPIRY_SWEEP_INTERVAL_SECONDS = 120


def _run_reservation_sweep(db: Session) -> int:
    return InventoryReservationService(db).sweep_expired_reservations(now=datetime.now(UTC))


async def _reservation_expiry_sweep_loop() -> None:
    while True:
        await asyncio.sleep(RESERVATION_EXPIRY_SWEEP_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            count = await asyncio.to_thread(_run_reservation_sweep, db)
            if count:
                logger.info("INVENTORY_RESERVATION_SWEEP: expired_count=%s", count)
        except Exception:
            logger.exception("INVENTORY_RESERVATION_SWEEP_LOOP_ERROR")
        finally:
            db.close()


# Paid-but-no-order safety net (PAY-005): re-asks Razorpay about recent pending
# online checkouts the webhook and the app both missed. Same in-process
# single-worker pattern as the reservation sweep; duplicates are harmless.
CHECKOUT_RECONCILE_INTERVAL_SECONDS = 300


def _run_checkout_reconcile(db: Session) -> int:
    gateway = get_payment_gateway()
    if not gateway.is_configured:
        return 0
    service = CheckoutSessionService(db, gateway)
    now = datetime.now(UTC)
    return service.reconcile_pending(now=now) + service.retry_failed_refunds(now=now)


async def _checkout_reconcile_loop() -> None:
    while True:
        await asyncio.sleep(CHECKOUT_RECONCILE_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            count = await asyncio.to_thread(_run_checkout_reconcile, db)
            if count:
                logger.warning("CHECKOUT_RECONCILE_SWEEP: settled_count=%s", count)
        except Exception:
            logger.exception("CHECKOUT_RECONCILE_LOOP_ERROR")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events (startup and shutdown)."""
    # Captured once here so service code (sync, threadpooled) can schedule
    # realtime WebSocket sends onto it - see app/core/realtime.py.
    register_main_loop(asyncio.get_running_loop())
    logger.info(
        "Starting %s [environment=%s, debug=%s]",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.DEBUG,
    )
    # Online payments and uploads degrade honestly (a clear 503) rather
    # than failing startup, but in production that is invisible until a
    # customer or admin hits it - say so loudly at boot instead.
    if settings.is_production and not settings.RAZORPAY_KEY_ID:
        logger.warning(
            "RAZORPAY_KEY_ID is not set: online payments are OFF - customers "
            "can only use Cash on Delivery."
        )
    elif settings.is_production and settings.RAZORPAY_KEY_ID.startswith("rzp_test_"):
        logger.warning(
            "Razorpay is using TEST keys (rzp_test_...) in production - no "
            "real money will be collected. Switch to rzp_live_ keys to go live."
        )
    # Delivery routing: in production say loudly what is not production-grade.
    if settings.is_production:
        if not settings.REDIS_URL:
            logger.warning(
                "REDIS_URL is not set: route distances are cached in-process only "
                "(per worker, lost on restart). Set REDIS_URL for a shared cache."
            )
        if settings.PACKING_POINT_LATITUDE is None and settings.PACKING_POINT_LONGITUDE is None:
            logger.warning(
                "PACKING_POINT_* is not set: delivery distance needs an admin-chosen "
                "packing point (Admin -> Settings), else only the base fee is charged."
            )
        if "router.project-osrm.org" in settings.OSRM_BASE_URL:
            logger.warning(
                "OSRM_BASE_URL is the public demo server (best effort, no SLA): "
                "self-host OSRM for production."
            )
    # Uploads - see the comment above.
    if settings.is_production and not (
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    ):
        logger.warning(
            "Cloudinary is not configured: Admin image uploads will fail "
            "with UPLOADS_NOT_CONFIGURED."
        )
    sweep_task = asyncio.create_task(_reservation_expiry_sweep_loop())
    reconcile_task = asyncio.create_task(_checkout_reconcile_loop())
    yield
    for task in (sweep_task, reconcile_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="Gawacha Bazaar - Production Backend Service",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Cap in-flight requests at the DB pool size (innermost, so request-id
    # logging and CORS still wrap the 503 it can produce).
    app.add_middleware(
        InflightLimitMiddleware,
        max_inflight=settings.MAX_INFLIGHT_REQUESTS,
        queue_timeout=settings.INFLIGHT_QUEUE_TIMEOUT_SECONDS,
    )

    # Compress JSON responses - catalog/home payloads are large and the
    # mobile network is the slow part.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # Request correlation & structured execution timing (outer ASGI middleware)
    app.add_middleware(RequestIDMiddleware)

    # Baseline security response headers (HSTS, X-Content-Type-Options,
    # etc.) - see app/core/security_headers.py for what's set and why.
    app.add_middleware(SecurityHeadersMiddleware)

    # Configure CORS
    if settings.ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Rate limiting for sensitive auth flows (login/register/refresh) -
    # see app/core/rate_limit.py.
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        logger.warning(
            "RATE_LIMIT_EXCEEDED: %s %s from %s (%s)",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            exc.detail,
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "details": None,
            },
        )

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Include versioned API router
    app.include_router(api_router, prefix="/api/v1")

    # Root health endpoints
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Service Health Check",
    )
    def health_check() -> HealthResponse:
        """Verify service operational status."""
        return HealthResponse(
            status="ok",
            app=settings.APP_NAME,
            environment=settings.APP_ENV,
        )

    @app.get(
        "/health/db",
        response_model=DatabaseHealthResponse,
        responses={
            status.HTTP_200_OK: {"model": DatabaseHealthResponse},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": DatabaseHealthResponse},
        },
        tags=["health"],
        summary="Database Health Check",
    )
    def database_health_check(db: Session = Depends(get_db)) -> JSONResponse:
        """Execute lightweight connectivity probe against the database."""
        try:
            db.execute(text("SELECT 1"))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "healthy",
                    "database": "connected",
                },
            )
        except Exception as exc:
            logger.error("Database health check probe failed: %s", str(exc))
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "database": "disconnected",
                },
            )

    @app.get(
        "/readiness",
        tags=["health"],
        summary="Readiness: can this instance serve traffic?",
    )
    def readiness(db: Session = Depends(get_db)) -> JSONResponse:
        """DB must answer (503 otherwise). Redis is an optional cache and only
        reported. OSRM/Nominatim/Razorpay are deliberately NOT called here - a
        probe must be cheap and an outage of an external dependency must not
        pull the whole API out of rotation."""
        checks: dict[str, str] = {}
        ok = True
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.error("Readiness: database probe failed: %s", type(exc).__name__)
            checks["database"] = "down"
            ok = False
        if settings.REDIS_URL:
            from app.services.routing.cache import route_cache

            checks["redis"] = "ok" if route_cache.ping() else "degraded (in-process cache)"
        else:
            checks["redis"] = "not configured (in-process cache)"
        checks["origin"] = (
            "configured" if settings.PACKING_POINT_LATITUDE is not None else "env-fallback-unset"
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "ready" if ok else "not_ready", "checks": checks},
        )

    return app


app = create_application()
