from sqlalchemy import BigInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductCategory(Base):
    """Additional category placements for a product.

    `products.category_id` is the product's main category; a row here lists
    the product under one more category or subcategory as well.
    """

    __tablename__ = "product_categories"
    __table_args__ = (Index("ix_product_categories_category_id", "category_id"),)

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), primary_key=True
    )
