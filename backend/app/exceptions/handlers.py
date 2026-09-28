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
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import logger
from app.exceptions.base import AppException
from app.services.payment_gateway import (
    GatewayConnectionError,
    GatewayError,
    GatewayRejectedError,
    GatewayTimeoutError,
)


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

    @app.exception_handler(GatewayError)
    async def gateway_exception_handler(request: Request, exc: GatewayError) -> JSONResponse:
        """Payment gateway failures surface as 502, never a generic 500.
        A timeout/connection failure means the outcome is UNKNOWN (the
        charge may still land - PaymentService leaves the payment
        PROCESSING and a webhook or /verify resolves it), so the message
        must not tell the customer the payment failed."""
        logger.warning(
            "Payment gateway error on %s %s [%s]: %s",
            request.method, request.url.path, type(exc).__name__, exc,
        )
        if isinstance(exc, GatewayRejectedError):
            code, message = "PAYMENT_GATEWAY_REJECTED", f"The payment gateway declined this request: {exc}"
        elif isinstance(exc, (GatewayTimeoutError, GatewayConnectionError)):
            code, message = (
                "PAYMENT_GATEWAY_UNAVAILABLE",
                "The payment gateway did not respond. If you were charged, your "
                "payment will be confirmed automatically - please check your order shortly.",
            )
        else:
            code, message = (
                "PAYMENT_GATEWAY_ERROR",
                "The payment gateway reported an error. Please check your order before trying again.",
            )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"code": code, "message": message, "details": None},
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
                # Pydantic v2 error `ctx` can carry raw Python values (e.g. Decimal
                # from a `gt=0` constraint) that json.dumps cannot serialize directly.
                "details": jsonable_encoder(exc.errors()),
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
