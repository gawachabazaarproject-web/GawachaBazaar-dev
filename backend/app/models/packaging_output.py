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
    Integer,
    Numeric,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.inventory_lot import InventoryLot
    from app.models.packaging_operation import PackagingOperation


class PackagingOutput(Base):
    """Packaged output linked to a receiving inventory lot."""

    __tablename__ = "packaging_outputs"
    __table_args__ = (
        CheckConstraint(
            "package_count > 0",
            name="ck_packaging_outputs_package_count",
        ),
        CheckConstraint(
            "total_quantity > 0",
            name="ck_packaging_outputs_total_quantity",
        ),
        Index(
            "ix_packaging_outputs_packaging_operation_id",
            "packaging_operation_id",
        ),
        Index("ix_packaging_outputs_inventory_lot_id", "inventory_lot_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    packaging_operation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("packaging_operations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inventory_lot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_lots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    package_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    operation: Mapped["PackagingOperation"] = relationship(
        "PackagingOperation",
        back_populates="outputs",
    )
    inventory_lot: Mapped["InventoryLot"] = relationship(
        "InventoryLot",
    )
