from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    from app.models.product import Product


class ProductImage(Base):
    """Product media asset with single primary image constraint."""

    __tablename__ = "product_images"
    __table_args__ = (
        CheckConstraint(
            "sort_order >= 0",
            name="ck_product_images_sort_order",
        ),
        Index("ix_product_images_product_id", "product_id"),
        Index(
            "uq_product_images_product_primary",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    alt_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        default=False,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="images",
    )
