from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.batch import Batch
    from app.models.cart import Cart
    from app.models.farm import Farm
    from app.models.order import Order
    from app.models.packaging_operation import PackagingOperation
    from app.models.quality_check import QualityCheck
    from app.models.user_role import UserRole


class User(Base):
    """User account identity."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')",
            name="ck_users_status",
        ),
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
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        server_default="ACTIVE",
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

    # Phase 1: Authoritative 1:N relationships
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    addresses: Mapped[list["Address"]] = relationship(
        "Address",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Phase 2: Farm & Quality Check relationships (restricted deletion)
    farms: Mapped[list["Farm"]] = relationship(
        "Farm",
        back_populates="owner",
    )
    quality_checks_performed: Mapped[list["QualityCheck"]] = relationship(
        "QualityCheck",
        back_populates="checked_by_user",
    )
    packaging_operations: Mapped[list["PackagingOperation"]] = relationship(
        "PackagingOperation",
        back_populates="performed_by",
    )

    # Phase 8.1: Wholesaler supplied batches (restricted deletion)
    batches_supplied: Mapped[list["Batch"]] = relationship(
        "Batch",
        back_populates="wholesaler",
        passive_deletes=True,
    )

    # Phase 6: Cart & Order relationships (restricted deletion)
    carts: Mapped[list["Cart"]] = relationship(
        "Cart",
        back_populates="user",
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        foreign_keys="Order.user_id",
    )
