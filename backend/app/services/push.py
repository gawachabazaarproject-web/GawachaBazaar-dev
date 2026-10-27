"""Push notifications via the Expo push service.

Tokens are registered by the mobile app (POST /push-tokens). Sends are
best-effort and run on a background thread with their own DB session, so
a push failure can never affect the business action that triggered it.
"""

import threading

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.notification_event import NotificationEvent
from app.models.push_token import PushToken

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
# Expo's ticket only means "queued"; delivery problems (e.g. missing FCM credentials)
# appear later in the receipt, so check it once after a short delay.
_RECEIPT_DELAY_SECONDS = 45

# (resource, status) -> (title, body). Only customer-meaningful transitions.
_MESSAGES: dict[tuple[str, str], tuple[str, str]] = {
    ("order", "PENDING"): ("Order placed", "We've received your order #{id}."),
    ("order", "CONFIRMED"): ("Order confirmed", "Your order #{id} is confirmed and being prepared."),
    ("order", "CANCELLED"): ("Order cancelled", "Your order #{id} has been cancelled."),
    ("order", "COMPLETED"): ("Order delivered", "Your order #{id} has been delivered. Enjoy!"),
    ("fulfillment", "PACKED"): ("Order packed", "Your order #{id} is packed and almost ready."),
    ("fulfillment", "OUT_FOR_DELIVERY"): ("Out for delivery", "Your order #{id} is on its way."),
    ("payment", "PAID"): ("Payment received", "Payment for order #{id} was successful."),
    ("refund", "APPROVED"): ("Refund approved", "Your refund for order #{id} is approved and will be processed shortly."),
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


# (resource, status) -> stable event type the app routes on. Keep in sync with
# mobile/src/features/notifications/notificationRouting.ts.
_EVENT_TYPES: dict[tuple[str, str], str] = {
    ("order", "PENDING"): "ORDER_PLACED",
    ("order", "CONFIRMED"): "ORDER_CONFIRMED",
    ("order", "CANCELLED"): "ORDER_CANCELLED",
    ("order", "COMPLETED"): "ORDER_DELIVERED",
    ("fulfillment", "PACKED"): "ORDER_PACKED",
    ("fulfillment", "OUT_FOR_DELIVERY"): "OUT_FOR_DELIVERY",
    ("payment", "PAID"): "PAYMENT_RECEIVED",
    ("refund", "APPROVED"): "REFUND_INITIATED",
    ("refund", "REFUNDED"): "REFUND_COMPLETED",
}


def _claim_event(db: Session, dedupe_key: str, user_id: int, event_type: str) -> bool:
    """Record the event; False if it was already recorded (duplicate -> do not send)."""
    claimed = db.scalar(
        pg_insert(NotificationEvent)
        .values(dedupe_key=dedupe_key, user_id=user_id, event_type=event_type)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(NotificationEvent.id)
    )
    db.commit()
    return claimed is not None


def _send(
    user_id: int,
    title: str,
    body: str,
    data: dict,
    dedupe_key: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        if dedupe_key is not None and not _claim_event(db, dedupe_key, user_id, str(data.get("type", ""))):
            logger.info("PUSH_DUPLICATE_SKIPPED: user_id=%s key=%s", user_id, dedupe_key)
            return
        tokens = list(db.scalars(select(PushToken.token).where(PushToken.user_id == user_id)))
        if not tokens:
            # Nothing registered for this user: the app never reached POST /push-tokens.
            logger.info("PUSH_NO_TOKENS: user_id=%s (device never registered a token)", user_id)
            return
        messages = [
            {"to": t, "title": title, "body": body, "data": data, "sound": "default", "channelId": "orders"}
            for t in tokens
        ]
        resp = httpx.post(EXPO_PUSH_URL, json=messages, timeout=10)
        resp.raise_for_status()
        dead: list[str] = []
        ticket_ids: dict[str, str] = {}
        for token, ticket in zip(tokens, resp.json().get("data", []), strict=False):
            if ticket.get("status") != "error":
                if ticket.get("id"):
                    ticket_ids[ticket["id"]] = token
                continue
            error = (ticket.get("details") or {}).get("error")
            # Surface Expo's reason (e.g. InvalidCredentials / MismatchSenderId when FCM credentials
            # are missing for the app's EAS project) - previously every error except
            # DeviceNotRegistered was dropped silently.
            logger.warning(
                "PUSH_TICKET_ERROR: user_id=%s token=%s...%s error=%s message=%s",
                user_id, token[:18], token[-4:], error, ticket.get("message"),
            )
            if error == "DeviceNotRegistered":
                dead.append(token)
        if dead:
            db.execute(delete(PushToken).where(PushToken.token.in_(dead)))
            db.commit()
        if ticket_ids:
            logger.info("PUSH_ACCEPTED_BY_EXPO: user_id=%s tickets=%s", user_id, len(ticket_ids))
            if not settings.is_testing:
                timer = threading.Timer(_RECEIPT_DELAY_SECONDS, _check_receipts, args=(user_id, ticket_ids))
                timer.daemon = True
                timer.start()
    except Exception:  # noqa: BLE001 - push is best-effort
        logger.exception("PUSH_SEND_FAILED: user_id=%s", user_id)
    finally:
        db.close()


def _check_receipts(user_id: int, ticket_ids: dict[str, str]) -> None:
    """Log Expo's delivery receipts (never raises). A DeviceNotRegistered receipt drops the token."""
    db = SessionLocal()
    try:
        resp = httpx.post(EXPO_RECEIPTS_URL, json={"ids": list(ticket_ids)}, timeout=10)
        resp.raise_for_status()
        receipts = resp.json().get("data", {}) or {}
        dead: list[str] = []
        for ticket_id, receipt in receipts.items():
            if receipt.get("status") == "ok":
                logger.info("PUSH_RECEIPT_OK: user_id=%s", user_id)
                continue
            error = (receipt.get("details") or {}).get("error")
            logger.warning(
                "PUSH_RECEIPT_ERROR: user_id=%s error=%s message=%s", user_id, error, receipt.get("message")
            )
            if error == "DeviceNotRegistered" and ticket_id in ticket_ids:
                dead.append(ticket_ids[ticket_id])
        if dead:
            db.execute(delete(PushToken).where(PushToken.token.in_(dead)))
            db.commit()
    except Exception:  # noqa: BLE001 - diagnostics only
        logger.exception("PUSH_RECEIPT_CHECK_FAILED: user_id=%s", user_id)
    finally:
        db.close()


def notify_delivery_otp(*, user_id: int, order_id: int, otp: str, otp_row_id: int) -> None:
    """Push the COD delivery code to the customer. Reuses `_send` (best-effort,
    own thread/session, dedupe). The code is in the payload so the lock screen
    shows it; it is never logged by this module."""
    data = {"type": "DELIVERY_OTP", "orderId": order_id}
    threading.Thread(
        target=_send,
        args=(
            user_id,
            "Your delivery code",
            f"Share code {otp} with the delivery partner for order #{order_id}. Valid for "
            f"{settings.DELIVERY_OTP_EXPIRY_MINUTES} minutes. Do not share it with anyone else.",
            data,
            f"delivery_otp:{otp_row_id}",
        ),
        daemon=True,
    ).start()


def notify_user_status(*, resource: str, order_id: int, user_id: int, new_status: str) -> None:
    msg = _MESSAGES.get((resource, new_status))
    if msg is None:
        return
    title, body = msg
    event_type = _EVENT_TYPES[(resource, new_status)]
    # `orderId` stays for already-installed app versions; `type` drives newer ones.
    data = {"type": event_type, "orderId": order_id}
    threading.Thread(
        target=_send,
        args=(user_id, title, body.format(id=order_id), data, f"{resource}:{order_id}:{new_status}"),
        daemon=True,
    ).start()
