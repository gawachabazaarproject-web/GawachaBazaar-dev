"""In-process WebSocket connection registry + event dispatch for live
order/fulfillment/payment/refund status updates.

Single-instance, in-memory by design - same precedent as
app/core/rate_limit.py's Limiter (see its own docstring): this app runs as
one backend container with no load balancer (docker-compose.yml), so an
in-memory registry is correct today. If this is ever horizontally scaled,
delivery needs to move to a shared pub/sub (e.g. Redis), exactly the same
migration note rate_limit.py already flags for its own in-memory state -
flagging it here too so it isn't missed twice.

Service methods that mutate an Order/Fulfillment/Payment/Refund status
call `notify_status_event(...)` (a plain sync function) once the
transition has actually been applied in the current transaction - the
same point each of these methods already places its own `logger.info`
state-transition line (some of those already fire before that
transaction's own final `commit()`, exactly like this does; a rollback
from a rare concurrent-conflict IntegrityError produces at worst one
harmless extra client refetch that finds nothing changed, never a false
report of a change that didn't happen). That function schedules the real
async WebSocket sends onto the main event
loop via `asyncio.run_coroutine_threadsafe`, which is what makes it safe
to call from the sync, threadpooled service methods every route in this
codebase already runs in (see app/api/v1/realtime.py for the one async
entrypoint - the WebSocket route itself - and main.py's lifespan for
where the loop is captured).

Message contract is deliberately minimal - an invalidation signal, not a
full resource payload: {"resource": "order"|"fulfillment"|"payment"|
"refund", "order_id": int, "status": str, "previous_status": str|None,
"occurred_at": iso8601}. Clients treat this as "go refetch order <id>"
rather than trusting the socket to carry authoritative data - that would
mean a second, parallel serialization of every response schema that could
silently drift from the real REST responses. The existing REST endpoints
stay the only source of truth for what actually changed.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from app.core.logging import logger

_main_loop: asyncio.AbstractEventLoop | None = None


def register_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once from main.py's lifespan startup - captures the running
    event loop so notify_status_event (invoked from sync/threadpooled
    service code) has somewhere to schedule the actual async sends.
    """
    global _main_loop
    _main_loop = loop


class ConnectionManager:
    """Tracks live WebSocket connections by owning user id, plus a
    separate staff set that receives every event regardless of whose
    order it is (the Admin panel's whole reason for existing here) - a
    dual-role account (rare, but the login-OTP work already found one
    test account with both) simply ends up in both, which is correct.
    """

    def __init__(self) -> None:
        self._user_sockets: dict[int, set[WebSocket]] = {}
        self._staff_sockets: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, *, user_id: int, is_staff: bool) -> None:
        await websocket.accept()
        self._user_sockets.setdefault(user_id, set()).add(websocket)
        if is_staff:
            self._staff_sockets.add(websocket)

    def disconnect(self, websocket: WebSocket, *, user_id: int, is_staff: bool) -> None:
        sockets = self._user_sockets.get(user_id)
        if sockets is not None:
            sockets.discard(websocket)
            if not sockets:
                self._user_sockets.pop(user_id, None)
        if is_staff:
            self._staff_sockets.discard(websocket)

    async def send_to_user(self, user_id: int, message: dict[str, Any]) -> None:
        for ws in list(self._user_sockets.get(user_id, ())):
            await self._safe_send(ws, message)

    async def broadcast_to_staff(self, message: dict[str, Any]) -> None:
        for ws in list(self._staff_sockets):
            await self._safe_send(ws, message)

    @staticmethod
    async def _safe_send(ws: WebSocket, message: dict[str, Any]) -> None:
        try:
            await ws.send_json(message)
        except Exception as exc:  # noqa: BLE001 - a dead/closing socket must never break the caller
            logger.info("REALTIME_SEND_FAILED: %s", exc)


manager = ConnectionManager()


def notify_status_event(
    *,
    resource: str,
    order_id: int,
    user_id: int,
    new_status: str,
    previous_status: str | None = None,
) -> None:
    """Fire-and-forget from sync service code. Never raises - a realtime
    delivery failure (no loop registered yet, e.g. under pytest; a
    scheduling error) must never surface as an error on the HTTP response
    for the business action that already genuinely succeeded.
    """
    if _main_loop is None:
        return
    message = {
        "resource": resource,
        "order_id": order_id,
        "status": new_status,
        "previous_status": previous_status,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    try:
        asyncio.run_coroutine_threadsafe(manager.send_to_user(user_id, message), _main_loop)
        asyncio.run_coroutine_threadsafe(manager.broadcast_to_staff(message), _main_loop)
    except Exception as exc:  # noqa: BLE001
        logger.warning("REALTIME_NOTIFY_FAILED: %s", exc)
