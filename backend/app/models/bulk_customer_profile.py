from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class BulkCustomerProfile(Base):
    """Optional B2B profile attached to an existing CUSTOMER identity.

    Not a new role, not a new auth flow - a bulk customer is a User with
    the existing CUSTOMER role that also happens to have one of these
    profiles. One profile per user.
    """

    __tablename__ = "bulk_customer_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_bulk_customer_profiles_user_id"),
        CheckConstraint(
            "business_type IN ('RESTAURANT', 'HOTEL', 'CATERER', 'RETAILER', "
            "'OFFICE', 'INSTITUTION', 'EVENT', 'OTHER')",
            name="ck_bulk_customer_profiles_business_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    business_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    contact_person: Mapped[str | None] = mapped_column(
        String(150),
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
    user: Mapped["User"] = relationship(
        "User",
    )
