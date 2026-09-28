from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ad(Base):
    """A brand-advertising creative shown in the mobile app's small ads
    carousel (below the regular/wholesale toggle on Home). Distinct from
    Promotion (a discount rule applied at checkout) - this is purely
    display/link content, no pricing or redemption logic attached.

    `link_url` is a plain external URL (opened via the device's browser),
    not an internal deep link - brand ads point off-app by nature. Kept
    optional since a purely brand-awareness creative may have nowhere to
    link.
    """

    __tablename__ = "ads"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_ads_status"),
        Index("ix_ads_status_display_order", "status", "display_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(150), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
