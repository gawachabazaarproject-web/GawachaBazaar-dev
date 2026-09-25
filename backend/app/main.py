import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger
from app.core.rate_limit import limiter
from app.core.realtime import register_main_loop
from app.core.request_id import RequestIDMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.session import SessionLocal
from app.dependencies.database import get_db
from app.exceptions.handlers import register_exception_handlers
from app.schemas.base import DatabaseHealthResponse, HealthResponse
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
    sweep_task = asyncio.create_task(_reservation_expiry_sweep_loop())
    yield
    sweep_task.cancel()
    try:
        await sweep_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Gawacha Bazaar - Production Backend Service",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

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

    return app


app = create_application()
