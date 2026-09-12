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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bulk_order_request import BulkOrderRequest
    from app.models.product import Product


class BulkOrderRequestItem(Base):
    """One requested line item within a bulk/custom order request.

    `product_id` is nullable specifically to support a fully custom ask
    for something not yet in the catalog (Phase 17 spec Mode B) - exactly
    one of `product_id` / `custom_item_name` must be set (CHECK). This is
    intentionally looser than `quote_items` (Phase 17), which commits to
    a concrete, sellable `product_variants.id` once admin prices it.
    """

    __tablename__ = "bulk_order_request_items"
    __table_args__ = (
        CheckConstraint(
            "unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'CRATE')",
            name="ck_bulk_order_request_items_unit",
        ),
        CheckConstraint(
            "requested_quantity > 0", name="ck_bulk_order_request_items_quantity"
        ),
        CheckConstraint(
            "(product_id IS NOT NULL) OR (custom_item_name IS NOT NULL)",
            name="ck_bulk_order_request_items_product_or_custom",
        ),
        Index("ix_bulk_order_request_items_request_id", "request_id"),
        Index("ix_bulk_order_request_items_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bulk_order_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
    )
    custom_item_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    requested_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    request: Mapped["BulkOrderRequest"] = relationship(
        "BulkOrderRequest",
        back_populates="items",
    )
    product: Mapped["Product | None"] = relationship(
        "Product",
    )
