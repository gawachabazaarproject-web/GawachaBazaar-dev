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
from app.core.roles import STAFF_ROLES
from app.dependencies.database import get_db
from app.services.auth import AuthService

router = APIRouter()


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

    roles = auth_service.get_role_names(user.id)
    is_staff = not STAFF_ROLES.isdisjoint(roles)

    await manager.connect(websocket, user_id=user.id, is_staff=is_staff)
    try:
        # Server -> client only channel; this just blocks on the client's
        # side of the connection so we notice a disconnect. Any inbound
        # text is intentionally ignored rather than rejected - a client
        # sending a stray ping/keepalive frame should never tear down the
        # connection.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id=user.id, is_staff=is_staff)
