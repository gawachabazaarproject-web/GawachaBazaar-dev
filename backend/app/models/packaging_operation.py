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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.inventory_location import InventoryLocation
    from app.models.packaging_input import PackagingInput
    from app.models.packaging_output import PackagingOutput
    from app.models.user import User


class PackagingOperation(Base):
    """Commercial packaging and labeling operation converting raw inventory lots into retail packaging."""

    __tablename__ = "packaging_operations"
    __table_args__ = (
        UniqueConstraint(
            "packaging_code",
            name="uq_packaging_operations_packaging_code",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="ck_packaging_operations_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_packaging_operations_completed_at",
        ),
        Index("ix_packaging_operations_location_id", "location_id"),
        Index("ix_packaging_operations_status", "status"),
        Index("ix_packaging_operations_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    packaging_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    performed_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    location: Mapped["InventoryLocation"] = relationship(
        "InventoryLocation",
        back_populates="packaging_operations",
    )
    performed_by: Mapped["User"] = relationship(
        "User",
        back_populates="packaging_operations",
    )
    inputs: Mapped[list["PackagingInput"]] = relationship(
        "PackagingInput",
        back_populates="operation",
    )
    outputs: Mapped[list["PackagingOutput"]] = relationship(
        "PackagingOutput",
        back_populates="operation",
    )
