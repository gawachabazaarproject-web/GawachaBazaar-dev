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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.promotion import Promotion
    from app.models.user import User


class PromotionRedemption(Base):
    """One row per order a promotion was actually applied to - the
    authoritative usage-accounting and analytics source (never derived
    from Order.promotion_id alone, since that column only ever reflects
    the CURRENT snapshot; this table is what "reverse on cancellation"
    actually mutates). UNIQUE(order_id): under the SINGLE_BEST stacking
    policy an order carries at most one promotion, ever.

    `status` moves APPLIED -> REVERSED when the order is cancelled (see
    OrderService._cancel_locked_order) - reversal frees the promotion's
    global/per-customer usage limit for reuse, matching how this
    codebase already treats cancellation everywhere else (inventory
    reservation released, refund created) as "undo this order's effects",
    not "pretend it never existed" - the row is never deleted.
    """

    __tablename__ = "promotion_redemptions"
    __table_args__ = (
        CheckConstraint("discount_amount >= 0", name="ck_promotion_redemptions_discount_amount"),
        CheckConstraint("status IN ('APPLIED', 'REVERSED')", name="ck_promotion_redemptions_status"),
        UniqueConstraint("order_id", name="uq_promotion_redemptions_order_id"),
        Index("ix_promotion_redemptions_promotion_id", "promotion_id"),
        Index("ix_promotion_redemptions_customer_user_id", "customer_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    promotion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("promotions.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    customer_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="APPLIED")
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="redemptions")
    order: Mapped["Order"] = relationship("Order")
    customer: Mapped["User"] = relationship("User")
