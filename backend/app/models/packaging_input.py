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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.inventory_lot import InventoryLot
    from app.models.packaging_operation import PackagingOperation


class PackagingInput(Base):
    """Source inventory lot consumed in a packaging operation."""

    __tablename__ = "packaging_inputs"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_packaging_inputs_quantity",
        ),
        Index("ix_packaging_inputs_packaging_operation_id", "packaging_operation_id"),
        Index("ix_packaging_inputs_inventory_lot_id", "inventory_lot_id"),
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
    quantity: Mapped[Decimal] = mapped_column(
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
        back_populates="inputs",
    )
    inventory_lot: Mapped["InventoryLot"] = relationship(
        "InventoryLot",
    )
