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
    from app.models.inventory_reservation_item import InventoryReservationItem
    from app.models.order import Order


class InventoryReservation(Base):
    """One inventory hold per order, created atomically with checkout.

    Exactly one reservation ever exists per order (UNIQUE(order_id)) - a
    reservation is never deleted and never re-created; its lifecycle is
    entirely captured by `status` moving ACTIVE -> {COMMITTED, RELEASED,
    EXPIRED}. See app/services/reservation_state.py for the transition
    rules and app/services/inventory_reservation.py for the locking
    algorithm that enforces them under concurrency.
    """

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_inventory_reservations_order_id"),
        CheckConstraint(
            "status IN ('ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED')",
            name="ck_inventory_reservations_status",
        ),
        Index("ix_inventory_reservations_status", "status"),
        Index("ix_inventory_reservations_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="reservation",
    )
    items: Mapped[list["InventoryReservationItem"]] = relationship(
        "InventoryReservationItem",
        back_populates="reservation",
    )
