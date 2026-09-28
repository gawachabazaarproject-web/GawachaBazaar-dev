"""Admin dashboard: a live operational snapshot for the Admin panel's home
page. Read-only aggregates over existing tables - no new state.

"Today" is the business day in India Standard Time (the platform serves
Nagpur): UTC+05:30 with no daylight saving, so a fixed offset is exact and
avoids depending on an OS timezone database inside the container.
"""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fulfillment import Fulfillment
from app.models.inventory_lot import InventoryLot
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.refund import Refund
from app.models.user import User
from app.schemas.dashboard import (
    DashboardAttentionOrderResponse,
    DashboardDeliveryIssueResponse,
    DashboardLowStockResponse,
    DashboardSummaryResponse,
    DashboardTilesResponse,
)
from app.services.inventory import DEFAULT_LOW_STOCK_THRESHOLD

BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), name="IST")

# Operational thresholds for the "needs attention" panels - display rules,
# not business rules (nothing is blocked or changed by them).
UNPICKED_AFTER = timedelta(minutes=30)
ASSIGNED_NOT_DISPATCHED_AFTER = timedelta(hours=2)
OUT_FOR_DELIVERY_TOO_LONG_AFTER = timedelta(hours=3)
LIST_LIMIT = 8

_OPEN_FULFILLMENT_STATUSES = ("PENDING", "PICKING", "PACKED", "READY_FOR_DELIVERY", "ASSIGNED")


def business_day_start(now: datetime) -> datetime:
    """Midnight IST of `now`'s business day, as an aware UTC datetime."""
    local = now.astimezone(BUSINESS_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, now: datetime) -> DashboardSummaryResponse:
        day_start = business_day_start(now)
        low_stock_rows = self._low_stock()
        return DashboardSummaryResponse(
            generated_at=now,
            day_start=day_start,
            tiles=self._tiles(day_start),
            refunds_pending_approval=self.db.query(func.count(Refund.id))
            .filter(Refund.status == "PENDING_APPROVAL")
            .scalar(),
            attention=self._unpicked_orders(now),
            low_stock_count=len(low_stock_rows),
            low_stock=low_stock_rows[:LIST_LIMIT],
            delivery_issues=self._delivery_issues(now),
        )

    def _tiles(self, day_start: datetime) -> DashboardTilesResponse:
        count = func.count
        return DashboardTilesResponse(
            orders_today=self.db.query(count(Order.id)).filter(Order.placed_at >= day_start).scalar(),
            # Money actually received today: online captures plus COD cash
            # collected at delivery (both land as Payment PAID + paid_at).
            collected_today=self.db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.status == "PAID", Payment.paid_at >= day_start)
            .scalar(),
            currency="INR",
            to_fulfil=self.db.query(count(Fulfillment.id))
            .join(Order, Order.id == Fulfillment.order_id)
            .filter(Fulfillment.status.in_(_OPEN_FULFILLMENT_STATUSES), Order.status == "CONFIRMED")
            .scalar(),
            out_for_delivery=self.db.query(count(Fulfillment.id))
            .filter(Fulfillment.status == "OUT_FOR_DELIVERY")
            .scalar(),
            delivered_today=self.db.query(count(Fulfillment.id))
            .filter(Fulfillment.delivered_at >= day_start)
            .scalar(),
            cancelled_today=self.db.query(count(Order.id)).filter(Order.cancelled_at >= day_start).scalar(),
        )

    def _unpicked_orders(self, now: datetime) -> list[DashboardAttentionOrderResponse]:
        rows = (
            self.db.query(Order, Fulfillment.created_at)
            .join(Fulfillment, Fulfillment.order_id == Order.id)
            .filter(
                Order.status == "CONFIRMED",
                Fulfillment.status == "PENDING",
                Fulfillment.created_at <= now - UNPICKED_AFTER,
            )
            .order_by(Fulfillment.created_at.asc())
            .limit(LIST_LIMIT)
            .all()
        )
        return [
            DashboardAttentionOrderResponse(
                order_id=order.id,
                order_number=order.order_number,
                reason="Confirmed but picking hasn't started",
                since=since,
                total_amount=order.total_amount,
            )
            for order, since in rows
        ]

    def _low_stock(self) -> list[DashboardLowStockResponse]:
        """Per variant, summed across every active lot - one nearly-empty lot
        is not "low stock" if another lot of the same variant is full."""
        available = func.sum(InventoryLot.quantity - InventoryLot.reserved_quantity)
        rows = (
            self.db.query(
                ProductVariant.id, Product.name, ProductVariant.name, ProductVariant.unit, available
            )
            .join(InventoryLot, InventoryLot.variant_id == ProductVariant.id)
            .join(Product, Product.id == ProductVariant.product_id)
            .filter(InventoryLot.status != "INACTIVE", ProductVariant.status == "ACTIVE")
            .group_by(ProductVariant.id, Product.name, ProductVariant.name, ProductVariant.unit)
            .having(available < DEFAULT_LOW_STOCK_THRESHOLD)
            .order_by(available.asc())
            .all()
        )
        return [
            DashboardLowStockResponse(
                variant_id=variant_id,
                product_name=product_name,
                variant_name=variant_name,
                unit=unit,
                available=max(Decimal(avail), Decimal("0")),
            )
            for variant_id, product_name, variant_name, unit, avail in rows
        ]

    def _delivery_issues(self, now: datetime) -> list[DashboardDeliveryIssueResponse]:
        stuck_assigned = (Fulfillment.status == "ASSIGNED") & (
            Fulfillment.assigned_at <= now - ASSIGNED_NOT_DISPATCHED_AFTER
        )
        stuck_out = (Fulfillment.status == "OUT_FOR_DELIVERY") & (
            Fulfillment.updated_at <= now - OUT_FOR_DELIVERY_TOO_LONG_AFTER
        )
        rows = (
            self.db.query(Fulfillment, Order.order_number, User.name)
            .join(Order, Order.id == Fulfillment.order_id)
            .outerjoin(User, User.id == Fulfillment.delivery_partner_user_id)
            .filter(stuck_assigned | stuck_out)
            .order_by(Fulfillment.updated_at.asc())
            .limit(LIST_LIMIT)
            .all()
        )
        return [
            DashboardDeliveryIssueResponse(
                fulfillment_id=fulfillment.id,
                order_id=fulfillment.order_id,
                order_number=order_number,
                status=fulfillment.status,
                since=(
                    fulfillment.assigned_at
                    if fulfillment.status == "ASSIGNED" and fulfillment.assigned_at
                    else fulfillment.updated_at
                ),
                delivery_partner_name=partner_name,
            )
            for fulfillment, order_number, partner_name in rows
        ]
