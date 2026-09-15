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


class LoginOtpChallenge(Base):
    """A pending email-OTP second factor for a customer/wholesaler login.

    Created by AuthService.authenticate() the moment identifier+password
    are verified correct - password proves *something you know*, this adds
    *something you have* (access to the account's registered email) before
    a session/access token is ever issued. Staff roles (ADMIN, OPERATIONS,
    HUB_STAFF, DELIVERY_PARTNER, SUPPORT) skip this entirely (see
    app/core/roles.py STAFF_ROLES) - the Admin panel's login is unaffected.

    `challenge_token` is an opaque, unguessable (32-byte) lookup key handed
    to the client so it never has to expose or guess this row's primary
    key - but it is not itself the credential. Storing it in plaintext is
    safe: knowing it lets you attempt a code guess against `code_hash`
    (rate-limited by `attempts`), not log in outright, so it does not need
    the same hashed-at-rest treatment as `auth_sessions.refresh_token_hash`.

    `code_hash` mirrors `ContactChangeRequest.code_hash` exactly - a SHA-256
    digest, with `attempts` + `expires_at` (not the hash algorithm) doing
    the actual guessing-protection work, since a 6-digit code has far less
    entropy than a refresh token.
    """

    __tablename__ = "login_otp_challenges"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'VERIFIED', 'EXPIRED')",
            name="ck_login_otp_challenges_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_login_otp_challenges_attempts"),
        Index("ix_login_otp_challenges_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    challenge_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    # Captured from the original /auth/login call so the AuthSession created
    # on successful verification reflects the client that actually logged
    # in, not whichever client happened to submit the code.
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
