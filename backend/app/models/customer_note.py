from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class CustomerNote(Base):
    """Internal admin/support note about a customer - never shown to the
    customer, distinguished from any customer-visible messaging (there is
    none in this codebase today). Editable in place: a note is working
    support context, not an immutable historical fact - edits are what the
    admin-panel audit log records (before/after text), not something this
    row itself versions.
    """

    __tablename__ = "customer_notes"
    __table_args__ = (Index("ix_customer_notes_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    author_admin_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    author: Mapped["User"] = relationship("User", foreign_keys=[author_admin_user_id])
