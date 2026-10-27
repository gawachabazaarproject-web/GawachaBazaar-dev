from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductStockReserve(Base):
    """The stock a product should keep in reserve, as ONE physical amount in the
    family's base unit (g / ml / pieces), the same whichever size is sold:
    5000 g = 20 x 250 g = 10 x 500 g = 5 x 1 kg. When a product has no row the
    legacy per-size rule applies (variant.reserve_level / default, in packs)."""

    __tablename__ = "product_stock_reserves"
    __table_args__ = (
        PrimaryKeyConstraint("product_id", "family", name="pk_product_stock_reserves"),
        CheckConstraint("reserve_base >= 0", name="ck_product_stock_reserves_base"),
    )

    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    family: Mapped[str] = mapped_column(String(20), nullable=False)
    reserve_base: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
