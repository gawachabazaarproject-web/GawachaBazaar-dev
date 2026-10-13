from datetime import datetime
from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CheckoutSession(Base):
    """A pay-first online checkout in progress.

    For online payment the customer pays BEFORE any order exists: starting
    checkout prices the cart, creates a Razorpay order for that amount and
    records it here - no Order, no stock reservation, the cart untouched. Only
    once Razorpay confirms the payment is the order created (and confirmed)
    from the cart. Abandoning or failing a payment therefore leaves no order
    behind and the cart intact.

    Status: PENDING (awaiting payment) -> COMPLETED (order placed) |
    REFUNDED / REFUND_FAILED (paid but the order could not be placed, e.g.
    stock ran out or prices changed, so the money was/should be returned).
    """

    __tablename__ = "checkout_sessions"
    __table_args__ = (
        UniqueConstraint("gateway_name", "gateway_order_id", name="uq_checkout_sessions_gateway_order"),
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'REFUNDED', 'REFUND_FAILED')",
            name="ck_checkout_sessions_status",
        ),
        CheckConstraint("amount > 0", name="ck_checkout_sessions_amount"),
        Index("ix_checkout_sessions_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    address_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promo_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gateway_name: Mapped[str] = mapped_column(String(30), nullable=False)
    gateway_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
