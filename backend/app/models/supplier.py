from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
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
    from app.models.supplier_evaluation import SupplierEvaluation
    from app.models.supplier_product import SupplierProduct


class Supplier(Base):
    """Independent business entity GawachaBazaar purchases inventory from.

    Deliberately NOT a User: a supplier is a business record maintained by
    internal staff, not an authentication identity. `Batch.supplier_id`
    (Phase 17) is the new, preferred way to record a batch's origin,
    coexisting with the legacy `Batch.wholesaler_user_id` (Phase 8.1) -
    see the Phase 17 migration docstring for why both exist together.
    """

    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_suppliers_status",
        ),
        Index("ix_suppliers_status", "status"),
        Index("ix_suppliers_business_name", "business_name"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    business_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    contact_person: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    address_line_1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
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
    products: Mapped[list["SupplierProduct"]] = relationship(
        "SupplierProduct",
        back_populates="supplier",
    )
    evaluations: Mapped[list["SupplierEvaluation"]] = relationship(
        "SupplierEvaluation",
        back_populates="supplier",
    )
    batches: Mapped[list["Batch"]] = relationship(
        "Batch",
        back_populates="supplier",
    )
