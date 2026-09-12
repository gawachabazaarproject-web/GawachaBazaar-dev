"""Fulfillment domain routes.

Unlike most routers in this codebase, roles differ PER ENDPOINT rather
than uniformly at the router level, so `require_roles(...)` is applied as
a route-level dependency (returning the authenticated `current_user`)
instead of a single blanket `dependencies=[...]` on the router:

- Warehouse progression (`/status`) and dispatch assignment (`/assign`):
  ADMIN, HUB_STAFF, OPERATIONS - the staff who pick/pack/stage/dispatch.
- Delivery-in-transit actions (`/out-for-delivery`, `/deliver`): ADMIN,
  DELIVERY_PARTNER - HUB_STAFF/OPERATIONS are deliberately excluded here;
  see app/services/fulfillment.py's module docstring. Ownership (the
  caller must BE the assigned partner, unless ADMIN) is enforced in the
  service, since it depends on data, not just role membership.
- Reads (`GET /fulfillments`, `GET /fulfillments/{id}`): all four roles,
  scoped in the service - a DELIVERY_PARTNER sees only their own
  assignments.

No customer-facing route lives in this router - the customer-facing
fulfillment view is `GET /orders/{order_id}/fulfillment` on the existing
orders router, returning the safe `CustomerFulfillmentResponse` shape.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, DELIVERY_PARTNER, HUB_STAFF, OPERATIONS
from app.dependencies.auth import require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.fulfillment import (
    MAX_PAGE_SIZE,
    AssignDeliveryPartnerRequest,
    FulfillmentListResponse,
    FulfillmentOrderDetailResponse,
    FulfillmentResponse,
    UpdateFulfillmentStatusRequest,
)
from app.services.fulfillment import FulfillmentService

router = APIRouter()

_WAREHOUSE_ROLES = (ADMIN, HUB_STAFF, OPERATIONS)
_DELIVERY_ROLES = (ADMIN, DELIVERY_PARTNER)
_ANY_FULFILLMENT_ROLE = (ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER)


@router.get(
    "",
    response_model=FulfillmentListResponse,
    summary="List fulfillments (staff see all, a delivery partner sees only their own assignments)",
)
def list_fulfillments(
    status_: str | None = Query(default=None, alias="status"),
    delivery_partner_user_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_roles(*_ANY_FULFILLMENT_ROLE)),
    db: Session = Depends(get_db),
) -> FulfillmentListResponse:
    return FulfillmentService(db).list_fulfillments(
        current_user,
        status=status_,
        delivery_partner_user_id=delivery_partner_user_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{fulfillment_id}",
    response_model=FulfillmentResponse,
    summary="Get a fulfillment (a delivery partner may only view their own assignment)",
)
def get_fulfillment(
    fulfillment_id: int,
    current_user: User = Depends(require_roles(*_ANY_FULFILLMENT_ROLE)),
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).get_fulfillment_or_404(fulfillment_id, current_user)


@router.get(
    "/{fulfillment_id}/order",
    response_model=FulfillmentOrderDetailResponse,
    summary=(
        "Get what to pick/pack and where to deliver for a fulfillment "
        "(order items, address, customer name, payment method/amount) - "
        "a delivery partner may only view their own assignment"
    ),
)
def get_fulfillment_order_detail(
    fulfillment_id: int,
    current_user: User = Depends(require_roles(*_ANY_FULFILLMENT_ROLE)),
    db: Session = Depends(get_db),
) -> FulfillmentOrderDetailResponse:
    return FulfillmentService(db).get_fulfillment_order_detail(fulfillment_id, current_user)


@router.post(
    "/{fulfillment_id}/status",
    response_model=FulfillmentResponse,
    summary="Advance warehouse status one step (PICKING/PACKED/READY_FOR_DELIVERY)",
)
def update_fulfillment_status(
    fulfillment_id: int,
    payload: UpdateFulfillmentStatusRequest,
    _current_user: User = Depends(require_roles(*_WAREHOUSE_ROLES)),
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).update_status(fulfillment_id, payload.status)


@router.post(
    "/{fulfillment_id}/assign",
    response_model=FulfillmentResponse,
    summary="Assign a delivery partner (READY_FOR_DELIVERY -> ASSIGNED)",
)
def assign_delivery_partner(
    fulfillment_id: int,
    payload: AssignDeliveryPartnerRequest,
    _current_user: User = Depends(require_roles(*_WAREHOUSE_ROLES)),
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).assign_delivery_partner(
        fulfillment_id, payload.delivery_partner_user_id
    )


@router.post(
    "/{fulfillment_id}/out-for-delivery",
    response_model=FulfillmentResponse,
    summary="Mark out for delivery (ASSIGNED -> OUT_FOR_DELIVERY; assigned partner or ADMIN only)",
)
def mark_out_for_delivery(
    fulfillment_id: int,
    current_user: User = Depends(require_roles(*_DELIVERY_ROLES)),
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).mark_out_for_delivery(fulfillment_id, current_user)


@router.post(
    "/{fulfillment_id}/deliver",
    response_model=FulfillmentResponse,
    summary="Confirm delivery - the only action that consumes physical inventory",
)
def confirm_delivery(
    fulfillment_id: int,
    current_user: User = Depends(require_roles(*_DELIVERY_ROLES)),
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).confirm_delivery(fulfillment_id, current_user)
