from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.payment_transaction import PaymentTransaction


class PaymentWebhookEvent(Base):
    """Durable webhook idempotency/deduplication record.

    Exists primarily so at-least-once gateway webhook delivery can never
    cause a payment event to be processed twice, even under concurrent
    delivery across multiple workers - `UNIQUE(gateway_name, event_id)` is
    the actual safety mechanism; this table is not a general-purpose event
    log. Raw webhook payloads are deliberately not stored by default (only
    a hash, for tamper-evidence/debugging correlation) - see Phase 14
    architecture doc.
    """

    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "gateway_name", "event_id", name="uq_payment_webhook_events_gateway_event"
        ),
        CheckConstraint(
            "status IN ('RECEIVED', 'PROCESSED', 'FAILED')",
            name="ck_payment_webhook_events_status",
        ),
        Index("ix_payment_webhook_events_payment_transaction_id", "payment_transaction_id"),
        Index("ix_payment_webhook_events_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    gateway_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    payment_transaction_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    payload_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    payment_transaction: Mapped["PaymentTransaction | None"] = relationship(
        "PaymentTransaction",
    )
