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
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.promotion_eligible_customer import PromotionEligibleCustomer
    from app.models.promotion_redemption import PromotionRedemption
    from app.models.promotion_target import PromotionTarget
    from app.models.user import User


class Promotion(Base):
    """A configurable discount rule: percentage or fixed-amount off,
    optionally coupon-gated, optionally scoped to products/categories/a
    customer segment, with usage limits and a validity window.

    `status` is the admin-set control (DRAFT/ACTIVE/PAUSED/DISABLED).
    Whether a promotion is currently SCHEDULED or EXPIRED is a function of
    `starts_at`/`ends_at` vs now() computed at read time (see
    app/services/promotion_state.py) - never persisted, so it can never
    drift from the clock.
    """

    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')",
            name="ck_promotions_discount_type",
        ),
        CheckConstraint("discount_value > 0", name="ck_promotions_discount_value"),
        CheckConstraint(
            "discount_type != 'PERCENTAGE' OR discount_value <= 100",
            name="ck_promotions_percentage_max",
        ),
        CheckConstraint(
            "customer_scope IN ('ALL', 'NEW_CUSTOMERS', 'EXISTING_CUSTOMERS', 'SPECIFIC')",
            name="ck_promotions_customer_scope",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'PAUSED', 'DISABLED')",
            name="ck_promotions_status",
        ),
        CheckConstraint("stacking_policy IN ('SINGLE_BEST')", name="ck_promotions_stacking_policy"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_promotions_ends_at"),
        CheckConstraint(
            "usage_limit_total IS NULL OR usage_limit_total > 0",
            name="ck_promotions_usage_limit_total",
        ),
        CheckConstraint(
            "usage_limit_per_customer IS NULL OR usage_limit_per_customer > 0",
            name="ck_promotions_usage_limit_per_customer",
        ),
        Index("uq_promotions_code", "code", unique=True, postgresql_where=text("code IS NOT NULL")),
        Index("ix_promotions_status", "status"),
        Index("ix_promotions_starts_at", "starts_at"),
        Index("ix_promotions_ends_at", "ends_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_order_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    customer_scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ALL")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    stacking_policy: Mapped[str] = mapped_column(String(20), nullable=False, server_default="SINGLE_BEST")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    usage_limit_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_limit_per_customer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redemption_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    created_by: Mapped["User"] = relationship("User")
    targets: Mapped[list["PromotionTarget"]] = relationship(
        "PromotionTarget", back_populates="promotion", cascade="all, delete-orphan"
    )
    eligible_customers: Mapped[list["PromotionEligibleCustomer"]] = relationship(
        "PromotionEligibleCustomer", back_populates="promotion", cascade="all, delete-orphan"
    )
    redemptions: Mapped[list["PromotionRedemption"]] = relationship(
        "PromotionRedemption", back_populates="promotion"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="promotion")
