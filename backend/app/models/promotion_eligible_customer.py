from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.promotion import Promotion
    from app.models.user import User


class PromotionEligibleCustomer(Base):
    """Explicit customer allow-list, used only when a promotion's
    `customer_scope` is 'SPECIFIC'. Irrelevant (never consulted) for any
    other scope value - see app/services/promotion.py's eligibility check.
    """

    __tablename__ = "promotion_eligible_customers"
    __table_args__ = (
        UniqueConstraint("promotion_id", "user_id", name="uq_promotion_eligible_customers_unique"),
        Index("ix_promotion_eligible_customers_promotion_id", "promotion_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    promotion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="eligible_customers")
    user: Mapped["User"] = relationship("User")
