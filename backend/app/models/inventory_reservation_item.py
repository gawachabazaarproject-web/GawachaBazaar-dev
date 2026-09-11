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
    from app.models.inventory_reservation import InventoryReservation
    from app.models.order_item import OrderItem


class InventoryReservationItem(Base):
    """The FIFO allocation join: how much of one order item was reserved
    from one inventory lot.

    One order item may span multiple lots (multiple rows here sharing the
    same order_item_id). This is also the exact allocation delivery
    confirmation replays to decide which lots to physically decrement -
    it is never recomputed at delivery time. Append-only: rows are never
    updated or deleted after creation.
    """

    __tablename__ = "inventory_reservation_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inventory_reservation_items_quantity"),
        Index("ix_inventory_reservation_items_reservation_id", "reservation_id"),
        Index("ix_inventory_reservation_items_order_item_id", "order_item_id"),
        Index("ix_inventory_reservation_items_inventory_lot_id", "inventory_lot_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_reservations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_items.id", ondelete="RESTRICT"),
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
    reservation: Mapped["InventoryReservation"] = relationship(
        "InventoryReservation",
        back_populates="items",
    )
    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem",
    )
    inventory_lot: Mapped["InventoryLot"] = relationship(
        "InventoryLot",
    )
