from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bulk_order_request import BulkOrderRequest
    from app.models.quote_version import QuoteVersion


class Quote(Base):
    """One quote thread per bulk order request.

    A thin container - the actual commercial content (price, terms,
    line items) lives in `QuoteVersion`/`QuoteItem`. Renegotiation never
    overwrites a sent quote; it creates a new `QuoteVersion`. See
    QuoteVersion for how "the current version" is determined.
    """

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_quotes_request_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bulk_order_requests.id", ondelete="RESTRICT"),
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
    request: Mapped["BulkOrderRequest"] = relationship(
        "BulkOrderRequest",
        back_populates="quote",
    )
    versions: Mapped[list["QuoteVersion"]] = relationship(
        "QuoteVersion",
        back_populates="quote",
    )
