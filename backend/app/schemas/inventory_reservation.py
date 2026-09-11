"""Inventory reservation domain schemas.

`InventoryReservationResponse` is the safe, customer-facing shape (no lot
IDs, no warehouse detail) - used for both the customer's
GET /orders/{id}/reservation and the ops list/summary views.
`InventoryReservationDetailResponse` adds the internal FIFO allocation
(order_item_id / inventory_lot_id / quantity per row) and is only ever
returned from the ADMIN/HUB_STAFF/OPERATIONS-only detail endpoint.
"""

from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100


class InventoryReservationResponse(BaseSchema):
    id: int
    order_id: int
    status: str
    expires_at: datetime
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InventoryReservationItemResponse(BaseSchema):
    id: int
    order_item_id: int
    inventory_lot_id: int
    quantity: Decimal
    created_at: datetime


class InventoryReservationDetailResponse(InventoryReservationResponse):
    items: list[InventoryReservationItemResponse]


class InventoryReservationListResponse(BaseSchema):
    items: list[InventoryReservationResponse]
    page: int
    page_size: int
    total: int
