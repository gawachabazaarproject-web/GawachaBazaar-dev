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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.user import User


class QualityCheck(Base):
    """Point-in-time quality inspection record for a produce batch."""

    __tablename__ = "quality_checks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PASSED', 'FAILED')",
            name="ck_quality_checks_status",
        ),
        Index("ix_quality_checks_batch_id", "batch_id"),
        Index("ix_quality_checks_checked_by_user_id", "checked_by_user_id"),
        Index("ix_quality_checks_checked_on", "checked_on"),
        Index("ix_quality_checks_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    checked_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    checked_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
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

    # Authoritative ORM relationships
    batch: Mapped["Batch"] = relationship(
        "Batch",
        back_populates="quality_checks",
    )
    checked_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="quality_checks_performed",
    )
