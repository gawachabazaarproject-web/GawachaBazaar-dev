from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AdminActionLog(Base):
    """Immutable-style audit ledger for admin-panel mutations.

    Same append-only pattern as `stock_movements`: no update or delete
    endpoint exists or should ever exist for this table, only create +
    list/read. `resource_type`/`resource_id` are a deliberately generic
    polymorphic reference (mirroring `stock_movements.reference_type/id`)
    so every future admin module (products, inventory, promotions, ...)
    logs into this one table instead of each growing its own bespoke audit
    columns the way `orders.cancelled_by_user_id` and
    `refunds.approved_by_user_id` already do. Those per-domain columns are
    left as-is (still authoritative for their own tables) - this table is
    for the cross-module "what did admins do, when, across the whole
    platform" view the Audit Log admin module will eventually read from.
    """

    __tablename__ = "admin_action_logs"
    __table_args__ = (
        Index("ix_admin_action_logs_admin_user_id", "admin_user_id"),
        Index("ix_admin_action_logs_resource", "resource_type", "resource_id"),
        Index("ix_admin_action_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    admin_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    resource_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    previous_state: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    new_state: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    admin_user: Mapped["User"] = relationship(
        "User",
    )
