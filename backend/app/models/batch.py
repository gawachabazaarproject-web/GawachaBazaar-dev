from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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
    from app.models.farm import Farm
    from app.models.product import Product
    from app.models.quality_check import QualityCheck


class Batch(Base):
    """Harvest lot of fresh agricultural produce."""

    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("batch_code", name="uq_batches_batch_code"),
        CheckConstraint("quantity > 0", name="ck_batches_quantity"),
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= harvest_date",
            name="ck_batches_expiry_date",
        ),
        CheckConstraint(
            "status IN ('HARVESTED', 'COLLECTED', 'SORTED', 'GRADED', 'APPROVED', 'REJECTED', 'EXPIRED')",
            name="ck_batches_status",
        ),
        CheckConstraint(
            "unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'CRATE')",
            name="ck_batches_unit",
        ),
        Index("ix_batches_farm_id", "farm_id"),
        Index("ix_batches_product_id", "product_id"),
        Index("ix_batches_harvest_date", "harvest_date"),
        Index("ix_batches_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    farm_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    batch_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    harvest_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
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

    # Authoritative ORM relationships
    farm: Mapped["Farm"] = relationship(
        "Farm",
        back_populates="batches",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="batches",
    )
    quality_checks: Mapped[list["QualityCheck"]] = relationship(
        "QualityCheck",
        back_populates="batch",
    )
