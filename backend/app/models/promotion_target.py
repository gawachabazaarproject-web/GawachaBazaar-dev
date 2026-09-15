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
    from app.models.promotion import Promotion


class PromotionTarget(Base):
    """Scopes a promotion to a specific product or category.

    Polymorphic like `stock_movements.reference_type/reference_id`
    elsewhere in this schema, rather than two nullable FK columns - a
    promotion with zero rows here applies cart-wide (subject to its other
    eligibility rules), which is the deliberate default, not a bug.
    """

    __tablename__ = "promotion_targets"
    __table_args__ = (
        CheckConstraint("target_type IN ('PRODUCT', 'CATEGORY')", name="ck_promotion_targets_target_type"),
        UniqueConstraint("promotion_id", "target_type", "target_id", name="uq_promotion_targets_unique"),
        Index("ix_promotion_targets_promotion_id", "promotion_id"),
        Index("ix_promotion_targets_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    promotion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="targets")
