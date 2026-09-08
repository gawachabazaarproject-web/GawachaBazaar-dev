from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.inventory_lot import InventoryLot


class InventoryLocation(Base):
    """Physical storage location where inventory is held."""

    __tablename__ = "inventory_locations"
    __table_args__ = (
        UniqueConstraint("code", name="uq_inventory_locations_code"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_inventory_locations_status",
        ),
        Index("ix_inventory_locations_type", "type"),
        Index("ix_inventory_locations_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    address_line_1: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    postal_code: Mapped[str] = mapped_column(
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

    # Relationships
    lots: Mapped[list["InventoryLot"]] = relationship(
        "InventoryLot",
        back_populates="location",
    )
