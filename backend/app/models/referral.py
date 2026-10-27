"""Refer & Earn: referral codes, referrals and the immutable reward ledger.

* `referral_codes` - one random, non-guessable code per user (upper-case,
  unique). It is NOT derived from the user id or any internal id.
* `referrals` - one row per referred user (UNIQUE referred_user_id: a user can
  be referred once, ever). Status PENDING -> QUALIFIED -> REWARDED -> REVERSED,
  or PENDING -> CANCELLED.
* `referral_reward_ledger` - append-only. There is no balance column anywhere:
  a balance is SUM(amount). A database trigger rejects UPDATE and DELETE, and
  UNIQUE(referral_id, beneficiary_user_id, entry_type) makes a double reward
  (or double reversal) impossible even under concurrent requests.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DDL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

REFERRAL_STATUSES = ("PENDING", "QUALIFIED", "REWARDED", "REVERSED", "CANCELLED")


class ReferralCode(Base):
    __tablename__ = "referral_codes"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_referral_codes_user_id"),
        UniqueConstraint("code", name="uq_referral_codes_code"),
        CheckConstraint("code = upper(code)", name="ck_referral_codes_upper"),
        CheckConstraint("char_length(code) >= 6", name="ck_referral_codes_length"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
        UniqueConstraint("qualifying_order_id", name="uq_referrals_qualifying_order_id"),
        CheckConstraint(
            "status IN ('PENDING', 'QUALIFIED', 'REWARDED', 'REVERSED', 'CANCELLED')",
            name="ck_referrals_status",
        ),
        CheckConstraint("referrer_user_id <> referred_user_id", name="ck_referrals_no_self"),
        Index("ix_referrals_referrer_user_id", "referrer_user_id"),
        Index("ix_referrals_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    referred_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    referral_code_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("referral_codes.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    qualifying_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ReferralRewardLedger(Base):
    __tablename__ = "referral_reward_ledger"
    __table_args__ = (
        UniqueConstraint(
            "referral_id", "beneficiary_user_id", "entry_type", name="uq_referral_ledger_once"
        ),
        CheckConstraint("entry_type IN ('REWARD', 'REVERSAL')", name="ck_referral_ledger_type"),
        CheckConstraint(
            "beneficiary_role IN ('REFERRER', 'REFERRED')", name="ck_referral_ledger_role"
        ),
        CheckConstraint(
            "(entry_type = 'REWARD' AND amount > 0) OR (entry_type = 'REVERSAL' AND amount < 0)",
            name="ck_referral_ledger_sign",
        ),
        Index("ix_referral_ledger_beneficiary", "beneficiary_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    referral_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("referrals.id", ondelete="RESTRICT"), nullable=False
    )
    beneficiary_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    beneficiary_role: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Append-only enforced by the database, whatever the application does. The same
# SQL is in the Alembic revision.
LEDGER_IMMUTABLE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION gb_referral_ledger_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'referral_reward_ledger is append-only';
END;
$$ LANGUAGE plpgsql
"""
LEDGER_IMMUTABLE_TRIGGER_SQL = """
CREATE TRIGGER trg_referral_ledger_immutable
BEFORE UPDATE OR DELETE ON referral_reward_ledger
FOR EACH ROW EXECUTE FUNCTION gb_referral_ledger_immutable()
"""
event.listen(
    ReferralRewardLedger.__table__,
    "after_create",
    DDL(LEDGER_IMMUTABLE_FUNCTION_SQL).execute_if(dialect="postgresql"),
)
event.listen(
    ReferralRewardLedger.__table__,
    "after_create",
    DDL(LEDGER_IMMUTABLE_TRIGGER_SQL).execute_if(dialect="postgresql"),
)
