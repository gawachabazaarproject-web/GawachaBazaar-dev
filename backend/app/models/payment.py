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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.payment_transaction import PaymentTransaction


class Payment(Base):
    """Payment obligation for a customer purchase order."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_id"),
        UniqueConstraint(
            "gateway_name",
            "gateway_order_id",
            name="uq_payments_gateway_name_order_id",
        ),
        CheckConstraint(
            "payment_method IN ('UPI', 'COD')",
            name="ck_payments_payment_method",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PAID', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_payment_method", "payment_method"),
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
    payment_method: Mapped[str] = mapped_column(
        String(30),
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
    # Gateway-level order/session reference, created once per payment
    # obligation on first UPI initiation and reused across retry attempts
    # within that same obligation (distinct from
    # payment_transactions.gateway_transaction_id, which is per-attempt).
    # Always NULL for COD. Added in Phase 14.
    gateway_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    gateway_order_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
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
        back_populates="payment",
    )
    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        "PaymentTransaction",
        back_populates="payment",
    )
