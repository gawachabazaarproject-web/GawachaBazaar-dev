from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.payment import Payment
    from app.models.user import User


class Refund(Base):
    """Refund-approval workflow for one cancelled, previously-PAID order.

    One row per order (UNIQUE(order_id)) - Phase 18 does not support
    partial/multiple refunds per order. Created (PENDING_APPROVAL) at the
    moment a customer/admin cancels an order whose payment is PAID; never
    created for COD (no payment collected) or for an online payment that
    never reached PAID. See app/services/refund.py and
    app/services/refund_state.py for the approval lifecycle and
    app/models/payment_transaction.py (transaction_type='REFUND') for the
    append-only gateway-attempt history this refund's processing produces.

    `amount`/`currency` are copied from `Payment` at creation time, never
    client-supplied and never recomputed later - this row is history, not
    a live view onto Payment.
    """

    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_refunds_order_id"),
        CheckConstraint(
            "status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED', "
            "'PROCESSING', 'REFUNDED', 'FAILED')",
            name="ck_refunds_status",
        ),
        CheckConstraint("amount > 0", name="ck_refunds_amount"),
        Index("ix_refunds_status", "status"),
        Index("ix_refunds_payment_id", "payment_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="refund",
    )
    payment: Mapped["Payment"] = relationship(
        "Payment",
    )
    approved_by: Mapped["User | None"] = relationship(
        "User",
    )
