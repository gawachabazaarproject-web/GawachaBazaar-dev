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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bulk_order_request_item import BulkOrderRequestItem
    from app.models.product_variant import ProductVariant
    from app.models.quote_version import QuoteVersion


class QuoteItem(Base):
    """One priced line within a specific quote version.

    Unlike the request item it prices (`BulkOrderRequestItem`, which may
    be a loose catalog-product-or-custom-text ask), a quote item commits
    to a concrete, sellable `product_variants.id` - required so
    conversion to a real `Order`/`OrderItem` (Phase 13) never has to
    guess which SKU was actually agreed upon.
    """

    __tablename__ = "quote_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quote_items_quantity"),
        CheckConstraint("unit_price > 0", name="ck_quote_items_unit_price"),
        CheckConstraint("total_price >= 0", name="ck_quote_items_total_price"),
        Index("ix_quote_items_quote_version_id", "quote_version_id"),
        Index("ix_quote_items_request_item_id", "request_item_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    quote_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quote_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bulk_order_request_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    quote_version: Mapped["QuoteVersion"] = relationship(
        "QuoteVersion",
        back_populates="items",
    )
    request_item: Mapped["BulkOrderRequestItem"] = relationship(
        "BulkOrderRequestItem",
    )
    variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant",
    )
