"""Centralized HTTP exception handlers for FastAPI.

Ensures all error responses adhere strictly to the uniform contract:
{
    "code": "...",
    "message": "...",
    "details": null
}
Unexpected errors are logged internally with stack traces but sanitized
for clients to prevent leakage of internal architecture, queries, or secrets.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import logger
from app.exceptions.base import AppException


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers with FastAPI."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        logger.warning(
            "Application error on %s %s: [%s] %s",
            request.method,
            request.url.path,
            exc.code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(
            "Validation failed on %s %s: %d error(s)",
            request.method,
            request.url.path,
            len(exc.errors()),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "Validation error in request parameters or body",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Log sanitized exception type and full internal traceback without dumping request bodies
        logger.error(
            "Unhandled server exception on %s %s [%s]: %s",
            request.method,
            request.url.path,
            type(exc).__name__,
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred",
                "details": None,
            },
        )
