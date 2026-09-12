from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.quote import Quote
    from app.models.quote_item import QuoteItem
    from app.models.user import User


class QuoteVersion(Base):
    """One revision of a quote's commercial terms.

    Never mutated after creation (except its `status` transition) and
    never deleted - a renegotiation always inserts a new row with the
    next `version_number`. Lifecycle (`app/services/quote_state.py`):
    `DRAFT` (admin is still preparing pricing, not yet visible to the
    customer) -> `SENT` (the customer's current, actionable quote) ->
    `SUPERSEDED` (a newer version was sent), `ACCEPTED`, `REJECTED`, or
    `EXPIRED` (past `valid_until`, detected lazily) - all terminal, all
    immutable once reached. `CANCELLED` covers admin withdrawing a
    DRAFT/SENT version outright. The "current" version for a quote is
    simply the one with `status = 'SENT'` - never cached redundantly.
    """

    __tablename__ = "quote_versions"
    __table_args__ = (
        UniqueConstraint(
            "quote_id", "version_number", name="uq_quote_versions_quote_version"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'SENT', 'SUPERSEDED', 'ACCEPTED', 'REJECTED', "
            "'EXPIRED', 'CANCELLED')",
            name="ck_quote_versions_status",
        ),
        CheckConstraint("version_number > 0", name="ck_quote_versions_version_number"),
        Index("ix_quote_versions_quote_id", "quote_id"),
        Index("ix_quote_versions_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    quote_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    valid_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    quote: Mapped["Quote"] = relationship(
        "Quote",
        back_populates="versions",
    )
    items: Mapped[list["QuoteItem"]] = relationship(
        "QuoteItem",
        back_populates="quote_version",
    )
    created_by_user: Mapped["User"] = relationship(
        "User",
    )
