import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("gawachabazaar.http")

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# Context variable to hold request ID for logging and async execution flow
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Retrieve the current request ID from context, or '-' if outside a request."""
    return request_id_ctx_var.get()


def sanitize_or_generate_request_id(incoming_id: str | None) -> str:
    """Validate and sanitize an incoming request ID header, or generate a fresh UUID4."""
    if incoming_id and _REQUEST_ID_REGEX.match(incoming_id.strip()):
        return incoming_id.strip()
    return uuid.uuid4().hex


class RequestIDMiddleware:
    """Pure ASGI middleware for request correlation and structured execution logging.

    1. Extracts or generates a sanitized X-Request-ID.
    2. Sets ContextVar and request.state.request_id.
    3. Injects X-Request-ID into outgoing response headers.
    4. Ensures ContextVar is always reset in a finally block to prevent leakage.
    5. Logs request start and completion with method, path, status, and duration.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract incoming X-Request-ID from ASGI headers
        incoming_id: str | None = None
        for key, value in scope.get("headers", []):
            if key.lower() == b"x-request-id":
                try:
                    incoming_id = value.decode("latin1")
                except UnicodeDecodeError:
                    incoming_id = None
                break

        request_id = sanitize_or_generate_request_id(incoming_id)
        token = request_id_ctx_var.set(request_id)

        # Store in scope state for FastAPI request.state access
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        start_time = time.perf_counter()
        status_code: int = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            # Log completion safely without request bodies or sensitive headers
            logger.info(
                "%s %s -> %d (%.2fms)",
                method,
                path,
                status_code,
                duration_ms,
            )
            # Guarantee ContextVar cleanup
            request_id_ctx_var.reset(token)
