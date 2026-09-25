from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PasswordResetChallenge(Base):
    """A pending "forgot password" email-OTP challenge.

    Deliberately a separate model from LoginOtpChallenge rather than a
    shared table with a purpose column: the two are handed to entirely
    different endpoints (POST /auth/reset-password vs POST
    /auth/login/verify-otp) and a shared table risks a code issued for one
    purpose being replayable against the other if a future edit ever
    forgets to filter by purpose. Same code_hash/attempts/expires_at
    shape as LoginOtpChallenge and ContactChangeRequest - a 6-digit code's
    guessing-protection comes from attempts+expiry, not the hash algorithm.

    No ip_address/user_agent/device_name columns: unlike a login OTP,
    nothing downstream needs to know which device requested a reset.
    """

    __tablename__ = "password_reset_challenges"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'VERIFIED', 'EXPIRED')",
            name="ck_password_reset_challenges_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_password_reset_challenges_attempts"),
        Index("ix_password_reset_challenges_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
