from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db
from app.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events (startup and shutdown)."""
    logger.info(
        "Starting %s [environment=%s, debug=%s]",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.DEBUG,
    )
    yield
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

    # Configure CORS
    if settings.ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Include versioned API router
    app.include_router(api_router, prefix="/api/v1")

    # Root health endpoints
    @app.get("/health", tags=["health"], summary="Service Health Check")
    def health_check() -> dict[str, Any]:
        """Verify service operational status."""
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV,
        }

    @app.get("/health/db", tags=["health"], summary="Database Health Check")
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
