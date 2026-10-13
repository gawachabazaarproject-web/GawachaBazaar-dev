"""Push notifications via the Expo push service.

Tokens are registered by the mobile app (POST /push-tokens). Sends are
best-effort and run on a background thread with their own DB session, so
a push failure can never affect the business action that triggered it.
"""

import threading

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.push_token import PushToken

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# (resource, status) -> (title, body). Only customer-meaningful transitions.
_MESSAGES: dict[tuple[str, str], tuple[str, str]] = {
    ("order", "PENDING"): ("Order placed", "We've received your order #{id}."),
    ("order", "CONFIRMED"): ("Order confirmed", "Your order #{id} is confirmed and being prepared."),
    ("order", "CANCELLED"): ("Order cancelled", "Your order #{id} has been cancelled."),
    ("order", "COMPLETED"): ("Order delivered", "Your order #{id} has been delivered. Enjoy!"),
    ("fulfillment", "PACKED"): ("Order packed", "Your order #{id} is packed and almost ready."),
    ("fulfillment", "OUT_FOR_DELIVERY"): ("Out for delivery", "Your order #{id} is on its way."),
    ("payment", "PAID"): ("Payment received", "Payment for order #{id} was successful."),
    ("refund", "REFUNDED"): ("Refund processed", "Your refund for order #{id} has been processed."),
}


def register_token(db: Session, user_id: int, token: str, platform: str | None) -> None:
    existing = db.scalar(select(PushToken).where(PushToken.token == token))
    if existing is None:
        db.add(PushToken(user_id=user_id, token=token, platform=platform))
    else:
        # A device re-registering after another account signed in on it.
        existing.user_id = user_id
        existing.platform = platform
    db.commit()


def unregister_token(db: Session, user_id: int, token: str) -> None:
    db.execute(delete(PushToken).where(PushToken.token == token, PushToken.user_id == user_id))
    db.commit()


def _send(user_id: int, title: str, body: str, data: dict) -> None:
    db = SessionLocal()
    try:
        tokens = list(db.scalars(select(PushToken.token).where(PushToken.user_id == user_id)))
        if not tokens:
            return
        messages = [
            {"to": t, "title": title, "body": body, "data": data, "sound": "default", "channelId": "orders"}
            for t in tokens
        ]
        resp = httpx.post(EXPO_PUSH_URL, json=messages, timeout=10)
        resp.raise_for_status()
        dead: list[str] = []
        for token, ticket in zip(tokens, resp.json().get("data", []), strict=False):
            if ticket.get("status") == "error" and ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                dead.append(token)
        if dead:
            db.execute(delete(PushToken).where(PushToken.token.in_(dead)))
            db.commit()
    except Exception:  # noqa: BLE001 - push is best-effort
        logger.exception("PUSH_SEND_FAILED: user_id=%s", user_id)
    finally:
        db.close()


def notify_user_status(*, resource: str, order_id: int, user_id: int, new_status: str) -> None:
    msg = _MESSAGES.get((resource, new_status))
    if msg is None:
        return
    title, body = msg
    threading.Thread(
        target=_send,
        args=(user_id, title, body.format(id=order_id), {"orderId": order_id}),
        daemon=True,
    ).start()
