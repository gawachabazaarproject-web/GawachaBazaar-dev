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
    from app.models.payment import Payment
    from app.models.refund import Refund


class PaymentTransaction(Base):
    """Append-oriented record of an individual payment or refund attempt.

    `transaction_type='REFUND'` (Phase 18) records one gateway refund
    attempt exactly the way 'PAYMENT' already records one gateway payment
    attempt - same status vocabulary, same append-only history, same
    `payment_id` (the payment being refunded). `refund_id` additionally
    links a REFUND-type row to the `refunds` approval-workflow row it
    belongs to (NULL for PAYMENT-type rows). An old PAYMENT row is never
    edited into a refund - this is always a new row.
    """

    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_payment_transactions_idempotency_key",
        ),
        CheckConstraint(
            "transaction_type IN ('PAYMENT', 'REFUND')",
            name="ck_payment_transactions_transaction_type",
        ),
        CheckConstraint(
            "status IN ('INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="ck_payment_transactions_status",
        ),
        CheckConstraint("amount > 0", name="ck_payment_transactions_amount"),
        Index("ix_payment_transactions_payment_id", "payment_id"),
        Index("ix_payment_transactions_status", "status"),
        Index(
            "ix_payment_transactions_gateway_transaction_id",
            "gateway_transaction_id",
        ),
        Index("ix_payment_transactions_refund_id", "refund_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    payment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    refund_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("refunds.id", ondelete="RESTRICT"),
        nullable=True,
    )
    transaction_type: Mapped[str] = mapped_column(
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
    gateway_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    gateway_transaction_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    gateway_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="transactions",
    )
    refund: Mapped["Refund | None"] = relationship(
        "Refund",
    )
