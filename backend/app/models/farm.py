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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.user import User


class Farm(Base):
    """Agricultural farm or production holding."""

    __tablename__ = "farms"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')",
            name="ck_farms_status",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90.0 AND latitude <= 90.0)",
            name="ck_farms_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180.0 AND longitude <= 180.0)",
            name="ck_farms_longitude",
        ),
        Index("ix_farms_owner_user_id", "owner_user_id"),
        Index("ix_farms_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(150),
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
    village: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    district: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    postal_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    contact_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
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

    # Authoritative ORM relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="farms",
    )
    batches: Mapped[list["Batch"]] = relationship(
        "Batch",
        back_populates="farm",
    )
