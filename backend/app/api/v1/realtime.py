"""Live order/fulfillment/payment/refund status-change events.

No REST response model here - this is a WebSocket, not a resource. Auth
uses a query-string token (`?token=...`) rather than the Authorization
header every other route in this codebase uses, because a browser's
native WebSocket API cannot set custom headers on the handshake request -
see app/dependencies/auth.py's HTTPBearer for how every other route does
it. The token still goes through the exact same
AuthService.resolve_current_user(...) validation as any Bearer token
(signature, type=access, live un-revoked session, ACTIVE user) - nothing
about the check itself is weaker for arriving via query string.

See app/core/realtime.py for the connection registry and the message
contract this route's connections receive.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.realtime import manager
from app.core.roles import CATALOG_STAFF, DELIVERY_PARTNER, STAFF_ROLES
from app.dependencies.database import get_db
from app.services.auth import AuthService

router = APIRouter()


def receives_order_events(roles) -> bool:
    """Who gets every customer's order events. Delivery partners are staff but
    only ever act on their own assignments (which they poll), and catalogue
    staff work on products, not on customers' orders."""
    return not (STAFF_ROLES - {DELIVERY_PARTNER, CATALOG_STAFF}).isdisjoint(roles)


@router.websocket("/events")
async def order_events(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    auth_service = AuthService(db)
    try:
        user = auth_service.resolve_current_user(token)
    except Exception:  # noqa: BLE001 - any validation failure is an equally-invalid handshake
        await websocket.close(code=1008)
        return

    user_id = user.id
    roles = auth_service.get_role_names(user_id)
    is_staff = receives_order_events(roles)
    # Release the DB connection NOW. FastAPI keeps a yield-dependency's
    # session open until the handler returns, i.e. for the whole life of
    # the socket - every connected client would pin one pooled connection
    # (pool is 5 + 10 overflow) and ~15 online users would starve every
    # REST request.
    db.close()

    await manager.connect(websocket, user_id=user_id, is_staff=is_staff)
    try:
        # Server -> client only channel; this just blocks on the client's
        # side of the connection so we notice a disconnect. Any inbound
        # text is intentionally ignored rather than rejected - a client
        # sending a stray ping/keepalive frame should never tear down the
        # connection.
        while True:
            text = await websocket.receive_text()
            # Client heartbeat: answering lets the app detect a silently
            # dead socket (idle proxy timeout, backgrounded phone).
            if text == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id=user_id, is_staff=is_staff)
