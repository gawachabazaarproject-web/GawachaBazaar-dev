from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ContactChangeRequest(Base):
    """A pending/resolved admin-initiated email or phone change for a
    customer. The new value is never written to `users.email`/`users.phone`
    until whoever controls the new address/number proves it by returning
    the code sent there (see app/services/contact_change.py) - this is what
    makes it safe for an admin to change a customer's login identity at
    all, unlike a raw PATCH of the field.

    `code_hash` is a SHA-256 digest, never the raw code - same precedent as
    `auth_sessions.refresh_token_hash`. Guessing protection comes from
    `attempts` + `expires_at`, not the hash algorithm, since a 6-digit code
    has far less entropy than a refresh token.
    """

    __tablename__ = "contact_change_requests"
    __table_args__ = (
        CheckConstraint("field IN ('EMAIL', 'PHONE')", name="ck_contact_change_requests_field"),
        CheckConstraint(
            "status IN ('PENDING', 'VERIFIED', 'EXPIRED', 'CANCELLED')",
            name="ck_contact_change_requests_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_contact_change_requests_attempts"),
        Index("ix_contact_change_requests_user_id", "user_id"),
        Index(
            "uq_contact_change_requests_pending",
            "user_id",
            "field",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(20), nullable=False)
    new_value: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    requested_by_admin_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    requested_by: Mapped["User"] = relationship("User", foreign_keys=[requested_by_admin_user_id])
