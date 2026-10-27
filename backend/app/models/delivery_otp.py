"""Delivery OTP: a one-time code the customer reads out to the delivery partner
to prove a COD order really reached them.

Security design (see docs/05-domains/COD_OPERATIONS.md):
* The plaintext code is NEVER stored. `otp_hash` is an HMAC-SHA256 keyed with a
  server secret over (order, assignment, code), so a leaked table cannot be
  brute-forced offline (a bare hash of 6 digits falls in microseconds).
* `otp_encrypted` is the same code Fernet-encrypted with a key derived from that
  secret. It exists only so the OWNING customer can read the code in the app
  while it is active; it is set to NULL the moment the code is verified,
  invalidated or locked.
* At most one ACTIVE row per order (partial unique index). A new code
  invalidates the previous one. Attempts are counted in the row.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryOtp(Base):
    __tablename__ = "delivery_otps"
    __table_args__ = (
        CheckConstraint("attempts >= 0 AND attempts <= max_attempts", name="ck_delivery_otps_attempts"),
        CheckConstraint("max_attempts >= 1", name="ck_delivery_otps_max_attempts"),
        # one ACTIVE (neither verified nor invalidated) code per order
        Index(
            "uq_delivery_otps_one_active_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("verified_at IS NULL AND invalidated_at IS NULL"),
        ),
        Index("ix_delivery_otps_order_created", "order_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    # The assignment the code was issued for: a reassignment invalidates it.
    assignment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_assignments.id", ondelete="CASCADE"), nullable=False
    )
    otp_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    otp_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
