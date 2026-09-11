"""Fulfillment domain schemas.

Client controls only the target status for a progression update - DELIVERED
is never accepted here (see POST /fulfillments/{id}/deliver, which takes no
body: physical consumption is derived entirely from the order's committed
reservation, never from client-supplied quantities or lot references).
"""

from datetime import datetime
from typing import Literal

from app.schemas.base import BaseSchema

FulfillmentProgressStatus = Literal[
    "PICKING", "PACKED", "READY_FOR_DELIVERY", "OUT_FOR_DELIVERY"
]


class UpdateFulfillmentStatusRequest(BaseSchema):
    status: FulfillmentProgressStatus


class FulfillmentResponse(BaseSchema):
    id: int
    order_id: int
    status: str
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
