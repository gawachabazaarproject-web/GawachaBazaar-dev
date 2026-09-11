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
    from app.models.order import Order


class Fulfillment(Base):
    """Order-level fulfillment state, created once a reservation is
    COMMITTED (i.e. the order is CONFIRMED). One fulfillment per order.

    Tracks the coarse warehouse-to-doorstep pipeline
    (PENDING -> PICKING -> PACKED -> READY_FOR_DELIVERY -> OUT_FOR_DELIVERY
    -> DELIVERED). Only the DELIVERED transition consumes physical
    inventory - see app/services/fulfillment.py. Per-item picking detail,
    delivery partner assignment, routing, and proof-of-delivery are all
    out of scope for this phase.
    """

    __tablename__ = "fulfillments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_fulfillments_order_id"),
        CheckConstraint(
            "status IN ('PENDING', 'PICKING', 'PACKED', 'READY_FOR_DELIVERY', "
            "'OUT_FOR_DELIVERY', 'DELIVERED')",
            name="ck_fulfillments_status",
        ),
        Index("ix_fulfillments_status", "status"),
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
