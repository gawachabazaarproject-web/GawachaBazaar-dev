from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product_variant import ProductVariant


class Price(Base):
    """Historical and active pricing record for a product variant."""

    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_prices_price"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_prices_valid_to",
        ),
        Index("ix_prices_variant_id", "variant_id"),
        Index("ix_prices_valid_from", "valid_from"),
        Index("ix_prices_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant",
        back_populates="prices",
    )
