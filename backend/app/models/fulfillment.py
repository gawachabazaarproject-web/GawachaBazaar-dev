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
    from app.models.inventory_location import InventoryLocation
    from app.models.order import Order
    from app.models.user import User


class Fulfillment(Base):
    """Order-level fulfillment state, created once a reservation is
    COMMITTED (i.e. the order is CONFIRMED). One fulfillment per order.

    Tracks the warehouse-to-doorstep pipeline (PENDING -> PICKING ->
    PACKED -> READY_FOR_DELIVERY -> ASSIGNED -> OUT_FOR_DELIVERY ->
    DELIVERED). Only the DELIVERED transition consumes physical inventory
    - see app/services/fulfillment.py. Per-item picking detail, routing,
    and proof-of-delivery remain out of scope (Phase 16).

    `delivery_partner_user_id` (Phase 16) is a User holding the
    DELIVERY_PARTNER role - not a dedicated `delivery_partners` table,
    consistent with the existing Wholesaler model (Phase 8.1: a role
    membership, not a profile table, unless dedicated attributes are
    ever needed).

    `inventory_location_id` (Phase 16) records the single location the
    reservation actually allocated from, ONLY when unambiguous.
    Reservations pool inventory lots across ALL locations for a variant
    (Phase 15 design), so an allocation can legitimately span multiple
    locations - in that case this stays NULL rather than recording a
    misleading single location. See InventoryReservationService.
    """

    __tablename__ = "fulfillments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_fulfillments_order_id"),
        CheckConstraint(
            "status IN ('PENDING', 'PICKING', 'PACKED', 'READY_FOR_DELIVERY', "
            "'ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED')",
            name="ck_fulfillments_status",
        ),
        Index("ix_fulfillments_status", "status"),
        Index("ix_fulfillments_delivery_partner_user_id", "delivery_partner_user_id"),
        Index("ix_fulfillments_inventory_location_id", "inventory_location_id"),
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
    delivery_partner_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    inventory_location_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
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
        back_populates="fulfillment",
    )
    delivery_partner: Mapped["User | None"] = relationship(
        "User",
    )
    inventory_location: Mapped["InventoryLocation | None"] = relationship(
        "InventoryLocation",
    )
