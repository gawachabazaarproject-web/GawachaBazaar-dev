from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationEvent(Base):
    """One row per push the backend has decided to send, keyed by the business
    event (e.g. ``order:42:CONFIRMED``). The unique key makes sending
    idempotent: a retried request or a repeated status event cannot push twice."""

    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
