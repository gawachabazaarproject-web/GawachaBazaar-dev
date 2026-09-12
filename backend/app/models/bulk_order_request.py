from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.bulk_order_request_item import BulkOrderRequestItem
    from app.models.order import Order
    from app.models.quote import Quote
    from app.models.user import User


class BulkOrderRequest(Base):
    """A customer's bulk/custom commerce request.

    Deliberately NOT an Order - see app/services/bulk_order.py and
    ARCHITECTURE.md: a request never touches the Order/Payment/
    Reservation/Fulfillment machinery until it is explicitly converted,
    after the customer has accepted a quote. This is what keeps
    abandoned/rejected requests from polluting the order system.

    `address_id` references the customer's live `Address` while still a
    request (mutable - the customer might update it before conversion);
    at conversion time the existing OrderAddress snapshot behavior
    (Phase 13) is reused unchanged, exactly as retail checkout does.
    """

    __tablename__ = "bulk_order_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTED', 'UNDER_REVIEW', 'QUOTED', 'CUSTOMER_ACCEPTED', "
            "'CONVERTED_TO_ORDER', 'REJECTED', 'CANCELLED', 'EXPIRED')",
            name="ck_bulk_order_requests_status",
        ),
        # Database-level idempotency backstop for conversion - a request
        # converts to at most one Order, enforced by Postgres, never by
        # the Python status check alone (see BulkOrderService.convert_to_order).
        UniqueConstraint("order_id", name="uq_bulk_order_requests_order_id"),
        Index("ix_bulk_order_requests_customer_user_id", "customer_user_id"),
        Index("ix_bulk_order_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    customer_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    address_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("addresses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    requested_delivery_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    admin_notes: Mapped[str | None] = mapped_column(
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
    customer: Mapped["User"] = relationship(
        "User",
    )
    address: Mapped["Address | None"] = relationship(
        "Address",
    )
    order: Mapped["Order | None"] = relationship(
        "Order",
    )
    items: Mapped[list["BulkOrderRequestItem"]] = relationship(
        "BulkOrderRequestItem",
        back_populates="request",
    )
    quote: Mapped["Quote | None"] = relationship(
        "Quote",
        back_populates="request",
        uselist=False,
    )
