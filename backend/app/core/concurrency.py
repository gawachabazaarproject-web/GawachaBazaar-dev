"""Bounded in-flight requests (load shedding).

Every sync endpoint runs in AnyIO's thread pool and holds a PostgreSQL
connection for its whole lifetime. With more concurrent requests than pooled
connections, threads block waiting for a connection while the requests that
HOLD connections wait for a free thread - a stall that ended in 500s after
`pool_timeout` in the 100-concurrent load test (2026-10-26). Capping in-flight
HTTP requests at the pool size makes that impossible by construction: excess
requests wait cheaply in the event loop, and are shed with 503 + Retry-After
if they wait longer than INFLIGHT_QUEUE_TIMEOUT_SECONDS.

Probes (/health, /readiness) bypass the limit; WebSockets are not counted.
"""

import asyncio
import json
import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("gawachabazaar.http")

_BYPASS = ("/health", "/readiness")


class InflightLimitMiddleware:
    def __init__(self, app: ASGIApp, max_inflight: int, queue_timeout: float) -> None:
        self.app = app
        self.queue_timeout = queue_timeout
        self._sem = asyncio.Semaphore(max_inflight) if max_inflight > 0 else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._sem is None or scope["type"] != "http" or scope["path"].startswith(_BYPASS):
            await self.app(scope, receive, send)
            return
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self.queue_timeout)
        except TimeoutError:
            logger.warning("load_shed path=%s waited_s=%s", scope["path"], self.queue_timeout)
            body = json.dumps(
                {"code": "SERVER_BUSY", "message": "The server is busy. Please try again in a moment.", "details": None}
            ).encode()
            await send({
                "type": "http.response.start", "status": 503,
                "headers": [(b"content-type", b"application/json"), (b"retry-after", b"2"),
                            (b"content-length", str(len(body)).encode())],
            })
            await send({"type": "http.response.body", "body": body})
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self._sem.release()
