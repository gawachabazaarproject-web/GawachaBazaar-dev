from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.supplier import Supplier


class SupplierProduct(Base):
    """Many-to-many: which products a supplier can supply.

    Deliberately carries no selling/purchase price - catalog selling
    price lives in `prices` (customer-facing) and is a different concept
    from what GawachaBazaar pays a supplier (see `batches.purchase_price`
    for the per-batch procurement cost actually paid).
    """

    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "product_id", name="uq_supplier_products_supplier_product"
        ),
        Index("ix_supplier_products_supplier_id", "supplier_id"),
        Index("ix_supplier_products_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    supplier_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="products",
    )
    product: Mapped["Product"] = relationship(
        "Product",
    )
