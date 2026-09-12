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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.user import User


class SupplierEvaluation(Base):
    """Append-only, admin-entered supplier performance snapshot.

    Never updated in place and never collapsed into a single mutable
    "current score" column on `Supplier` - each evaluation is a dated
    record, mirroring the append-only pattern already used by
    `stock_movements`/`payment_transactions`. A dashboard's "current"
    rating is simply the most recent row (or an average across a window)
    computed at read time, not stored redundantly.

    All six dimensions share one 0-5 scale for simplicity (the spec's own
    dashboard example mixes a 0-5 "Quality: 4.8" with a percentage
    "Delivery: 96%" - deliberately not modeled here; per the explicit
    "do not over-engineer automated scoring yet" instruction, a uniform
    manual scale is used and any percentage-style display is a reporting
    concern, not a storage one).
    """

    __tablename__ = "supplier_evaluations"
    __table_args__ = (
        CheckConstraint(
            "quality_rating >= 0 AND quality_rating <= 5",
            name="ck_supplier_evaluations_quality_rating",
        ),
        CheckConstraint(
            "delivery_rating >= 0 AND delivery_rating <= 5",
            name="ck_supplier_evaluations_delivery_rating",
        ),
        CheckConstraint(
            "price_rating >= 0 AND price_rating <= 5",
            name="ck_supplier_evaluations_price_rating",
        ),
        CheckConstraint(
            "reliability_rating >= 0 AND reliability_rating <= 5",
            name="ck_supplier_evaluations_reliability_rating",
        ),
        CheckConstraint(
            "responsiveness_rating >= 0 AND responsiveness_rating <= 5",
            name="ck_supplier_evaluations_responsiveness_rating",
        ),
        CheckConstraint(
            "overall_rating >= 0 AND overall_rating <= 5",
            name="ck_supplier_evaluations_overall_rating",
        ),
        Index("ix_supplier_evaluations_supplier_id", "supplier_id"),
        Index("ix_supplier_evaluations_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evaluated_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quality_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    delivery_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    price_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    reliability_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    responsiveness_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    overall_rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="evaluations",
    )
    evaluated_by_user: Mapped["User"] = relationship(
        "User",
    )
