"""Admin dashboard ("Today at Gawacha Bazaar") schemas.

Every number here is computed live from Order/Payment/Fulfillment/
InventoryLot/Refund rows by DashboardService - nothing is cached or
estimated.
"""

from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema


class DashboardTilesResponse(BaseSchema):
    orders_today: int
    collected_today: Decimal
    currency: str
    to_fulfil: int
    out_for_delivery: int
    delivered_today: int
    cancelled_today: int


class DashboardAttentionOrderResponse(BaseSchema):
    order_id: int
    order_number: str
    reason: str
    since: datetime
    total_amount: Decimal


class DashboardLowStockResponse(BaseSchema):
    variant_id: int
    product_name: str
    variant_name: str
    unit: str
    available: Decimal


class DashboardDeliveryIssueResponse(BaseSchema):
    fulfillment_id: int
    order_id: int
    order_number: str
    status: str
    since: datetime
    delivery_partner_name: str | None


class DashboardSummaryResponse(BaseSchema):
    generated_at: datetime
    day_start: datetime
    tiles: DashboardTilesResponse
    refunds_pending_approval: int
    attention: list[DashboardAttentionOrderResponse]
    low_stock_count: int
    low_stock: list[DashboardLowStockResponse]
    delivery_issues: list[DashboardDeliveryIssueResponse]
