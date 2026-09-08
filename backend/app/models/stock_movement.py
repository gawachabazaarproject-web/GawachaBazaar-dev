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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.inventory_lot import InventoryLot
    from app.models.user import User


class StockMovement(Base):
    """Immutable-style operational inventory audit ledger."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('RECEIPT', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', "
            "'DAMAGE', 'WASTE', 'TRANSFER_IN', 'TRANSFER_OUT', 'DISPATCH')",
            name="ck_stock_movements_movement_type",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_stock_movements_quantity",
        ),
        Index("ix_stock_movements_inventory_lot_id", "inventory_lot_id"),
        Index("ix_stock_movements_performed_by_user_id", "performed_by_user_id"),
        Index("ix_stock_movements_movement_type", "movement_type"),
        Index("ix_stock_movements_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    inventory_lot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_lots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    reference_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    performed_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    inventory_lot: Mapped["InventoryLot"] = relationship(
        "InventoryLot",
        back_populates="movements",
    )
    performed_by_user: Mapped["User"] = relationship(
        "User",
    )
