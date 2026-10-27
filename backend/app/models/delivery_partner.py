"""Delivery partner system: profile, assignments, location, earnings ledger.

* `delivery_partner_profiles` - operational profile of a user holding the
  DELIVERY_PARTNER role (status + availability + vehicle + phone).
* `delivery_assignments` - one row per (order, partner) attempt. A partial
  unique index allows at most ONE active assignment per order; a reassignment
  closes the old row (status CANCELLED/REJECTED) and inserts a new one, so
  history is preserved. COD collection facts live here, server-owned.
* `delivery_partner_locations` - latest position only (one row per assignment,
  upserted); no unbounded history.
* `delivery_partner_earnings` - append-only ledger of what a partner earned,
  separate from (and never derived from) the customer's delivery fee.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DDL,
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PARTNER_STATUSES = ("ACTIVE", "INACTIVE", "SUSPENDED")
PARTNER_AVAILABILITY = ("OFFLINE", "AVAILABLE", "ON_DELIVERY")
ASSIGNMENT_STATUSES = (
    "ASSIGNED",
    "ACCEPTED",
    "PICKED_UP",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "FAILED",
    "REJECTED",
    "CANCELLED",
)
ACTIVE_ASSIGNMENT_STATUSES = ("ASSIGNED", "ACCEPTED", "PICKED_UP", "OUT_FOR_DELIVERY")
COD_STATUSES = ("NOT_APPLICABLE", "COD_PENDING", "COD_COLLECTED", "COD_FAILED")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class DeliveryPartnerProfile(Base):
    __tablename__ = "delivery_partner_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_delivery_partner_profiles_user_id"),
        CheckConstraint(f"status IN ({_in(PARTNER_STATUSES)})", name="ck_dpp_status"),
        CheckConstraint(
            f"availability IN ({_in(PARTNER_AVAILABILITY)})", name="ck_dpp_availability"
        ),
        CheckConstraint(
            "vehicle_type IN ('BIKE', 'SCOOTER', 'BICYCLE', 'VAN', 'OTHER')", name="ck_dpp_vehicle"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="ACTIVE")
    availability: Mapped[str] = mapped_column(String(12), nullable=False, server_default="OFFLINE")
    vehicle_type: Mapped[str] = mapped_column(String(10), nullable=False, server_default="BIKE")
    vehicle_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"
    __table_args__ = (
        CheckConstraint(f"status IN ({_in(ASSIGNMENT_STATUSES)})", name="ck_da_status"),
        CheckConstraint(f"cod_status IN ({_in(COD_STATUSES)})", name="ck_da_cod_status"),
        CheckConstraint("cod_expected_amount >= 0", name="ck_da_cod_expected"),
        CheckConstraint(
            "cod_status <> 'COD_COLLECTED' OR cod_collected_amount = cod_expected_amount",
            name="ck_da_cod_collected_exact",
        ),
        CheckConstraint(
            "status <> 'DELIVERED' OR cod_status IN ('NOT_APPLICABLE', 'COD_COLLECTED')",
            name="ck_da_delivered_cod_settled",
        ),
        Index(
            "uq_delivery_assignments_one_active_per_order",
            "order_id",
            unique=True,
            postgresql_where=text(f"status IN ({_in(ACTIVE_ASSIGNMENT_STATUSES)})"),
        ),
        Index("ix_delivery_assignments_partner_status", "partner_user_id", "status"),
        Index("ix_delivery_assignments_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    fulfillment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("fulfillments.id", ondelete="RESTRICT"), nullable=False
    )
    partner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ASSIGNED")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    out_for_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # COD: the expected amount is copied from the payment by the server when the
    # assignment is created; the partner can only confirm exactly that amount.
    cod_status: Mapped[str] = mapped_column(
        String(15), nullable=False, server_default="NOT_APPLICABLE"
    )
    cod_expected_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    cod_collected_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cod_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cod_reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cod_reconciled_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DeliveryPartnerLocation(Base):
    """Latest known position for an active assignment (upserted, never appended)."""

    __tablename__ = "delivery_partner_locations"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_dpl_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_dpl_lng"),
    )

    assignment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_assignments.id", ondelete="CASCADE"), primary_key=True
    )
    partner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeliveryPartnerEarning(Base):
    __tablename__ = "delivery_partner_earnings"
    __table_args__ = (
        UniqueConstraint("assignment_id", "entry_type", name="uq_dpe_assignment_entry"),
        CheckConstraint("entry_type IN ('EARNING', 'REVERSAL')", name="ck_dpe_type"),
        CheckConstraint(
            "(entry_type = 'EARNING' AND amount >= 0) OR (entry_type = 'REVERSAL' AND amount <= 0)",
            name="ck_dpe_sign",
        ),
        Index("ix_dpe_partner", "partner_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_assignments.id", ondelete="RESTRICT"), nullable=False
    )
    partner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Snapshot of how the amount was computed, so a later rule change cannot rewrite history.
    rule_version: Mapped[str] = mapped_column(String(30), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    per_km_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    billable_km: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cod_bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


EARNINGS_IMMUTABLE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION gb_partner_earnings_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'delivery_partner_earnings is append-only';
END;
$$ LANGUAGE plpgsql
"""
EARNINGS_IMMUTABLE_TRIGGER_SQL = """
CREATE TRIGGER trg_partner_earnings_immutable
BEFORE UPDATE OR DELETE ON delivery_partner_earnings
FOR EACH ROW EXECUTE FUNCTION gb_partner_earnings_immutable()
"""
event.listen(
    DeliveryPartnerEarning.__table__,
    "after_create",
    DDL(EARNINGS_IMMUTABLE_FUNCTION_SQL).execute_if(dialect="postgresql"),
)
event.listen(
    DeliveryPartnerEarning.__table__,
    "after_create",
    DDL(EARNINGS_IMMUTABLE_TRIGGER_SQL).execute_if(dialect="postgresql"),
)
