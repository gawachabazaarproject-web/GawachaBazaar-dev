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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.inventory_location import InventoryLocation
    from app.models.product_variant import ProductVariant
    from app.models.stock_movement import StockMovement


class InventoryLot(Base):
    """Current physical inventory balance for Batch + Product Variant + Location."""

    __tablename__ = "inventory_lots"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "variant_id",
            "location_id",
            name="uq_inventory_lots_batch_variant_location",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_inventory_lots_quantity",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'DEPLETED')",
            name="ck_inventory_lots_status",
        ),
        Index("ix_inventory_lots_batch_id", "batch_id"),
        Index("ix_inventory_lots_variant_id", "variant_id"),
        Index("ix_inventory_lots_location_id", "location_id"),
        Index("ix_inventory_lots_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
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

    # Relationships
    batch: Mapped["Batch"] = relationship(
        "Batch",
    )
    variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant",
    )
    location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        back_populates="lots",
    )
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement",
        back_populates="inventory_lot",
    )
