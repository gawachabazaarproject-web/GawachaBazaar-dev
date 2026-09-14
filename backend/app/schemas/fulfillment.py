"""Fulfillment domain schemas.

Client controls only the target status for a warehouse progress update -
ASSIGNED, OUT_FOR_DELIVERY, and DELIVERED are never accepted here, each
having its own dedicated endpoint with its own extra validation
(assignment target, delivery-partner ownership, server-derived
consumption). `POST /fulfillments/{id}/deliver` takes no body at all:
physical consumption is derived entirely from the order's committed
reservation, never from client-supplied quantities or lot references.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.order import OrderAddressResponse, OrderItemResponse

MAX_PAGE_SIZE = 100

FulfillmentProgressStatus = Literal["PICKING", "PACKED", "READY_FOR_DELIVERY"]


class UpdateFulfillmentStatusRequest(BaseSchema):
    status: FulfillmentProgressStatus


class AssignDeliveryPartnerRequest(BaseSchema):
    """The target user must exist and hold the DELIVERY_PARTNER role -
    validated server-side, never trusted from the client beyond the id.
    """

    delivery_partner_user_id: int = Field(..., gt=0)


class FulfillmentResponse(BaseSchema):
    """Operations/admin/delivery-partner facing - full operational detail."""

    id: int
    order_id: int
    status: str
    delivery_partner_user_id: int | None
    inventory_location_id: int | None
    assigned_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FulfillmentListResponse(BaseSchema):
    items: list[FulfillmentResponse]
    page: int
    page_size: int
    total: int


class CustomerFulfillmentResponse(BaseSchema):
    """Customer-facing shape for GET /orders/{order_id}/fulfillment - no
    delivery partner user id, no inventory location, no internal lot or
    reservation detail.
    """

    status: str
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FulfillmentOrderDetailResponse(BaseSchema):
    """Phase 19 addition: staff/delivery-partner facing bridge from a
    Fulfillment to the Order it fulfills - the FulfillmentResponse shape
    above deliberately carries only `order_id`, so without this there was
    no way for warehouse staff to know what to pick/pack or for a delivery
    partner to know where to deliver or (for COD) how much to collect.
    Same ownership scoping as GET /fulfillments/{id}
    (FulfillmentService.get_fulfillment_or_404): a DELIVERY_PARTNER only
    ever sees this for a fulfillment actually assigned to them.
    """

    fulfillment_id: int
    order_id: int
    order_number: str
    customer_name: str
    total_amount: Decimal
    currency: str
    payment_method: str | None
    payment_status: str | None
    items: list[OrderItemResponse]
    address: OrderAddressResponse | None
