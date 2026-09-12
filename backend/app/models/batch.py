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
    from app.models.supplier import Supplier
    from app.models.user import User


class Batch(Base):
    """Harvest lot of fresh agricultural produce.

    Phase 17: `supplier_id` is the new, preferred way to record who
    supplied this batch (an independent `Supplier` business record, no
    login required). `wholesaler_user_id` (Phase 8.1: a `User` holding
    the WHOLESALER role) is kept for full backward compatibility - it is
    still a valid way to record origin, just no longer the only one. See
    `ck_batches_supplier_or_wholesaler`: at least one of the two is
    always required, so no batch ever loses a traceable origin. Fully
    deprecating `wholesaler_user_id` is an explicit future stage, not
    attempted in Phase 17.
    """

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
        CheckConstraint(
            "wholesaler_user_id IS NOT NULL OR supplier_id IS NOT NULL",
            name="ck_batches_supplier_or_wholesaler",
        ),
        CheckConstraint(
            "purchase_price IS NULL OR purchase_price > 0",
            name="ck_batches_purchase_price",
        ),
        Index("ix_batches_wholesaler_user_id", "wholesaler_user_id"),
        Index("ix_batches_supplier_id", "supplier_id"),
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
    wholesaler_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    supplier_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    farm_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=True,
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
    # Phase 17: procurement facts Batch didn't previously capture. All
    # nullable - historical batches predating this phase have none of
    # these, and a batch may still be entered without full procurement
    # paperwork (e.g. mid-negotiation).
    purchase_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    purchase_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    receiving_reference: Mapped[str | None] = mapped_column(
        String(100),
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

    # Authoritative ORM relationships
    wholesaler: Mapped["User | None"] = relationship(
        "User",
        back_populates="batches_supplied",
    )
    supplier: Mapped["Supplier | None"] = relationship(
        "Supplier",
        back_populates="batches",
    )
    farm: Mapped["Farm | None"] = relationship(
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
