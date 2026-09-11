"""Fulfillment domain routes: internal staff + delivery partner only
(ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER).

No customer-facing fulfillment endpoint exists in this phase - the
customer-facing order/payment/reservation contracts are unchanged.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, DELIVERY_PARTNER, HUB_STAFF, OPERATIONS
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.fulfillment import FulfillmentResponse, UpdateFulfillmentStatusRequest
from app.services.fulfillment import FulfillmentService

router = APIRouter(
    dependencies=[Depends(require_roles(ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER))]
)


@router.get(
    "/{fulfillment_id}",
    response_model=FulfillmentResponse,
    summary="Get a fulfillment",
)
def get_fulfillment(
    fulfillment_id: int, db: Session = Depends(get_db)
) -> FulfillmentResponse:
    fulfillment = FulfillmentService(db).get_fulfillment_or_404(fulfillment_id)
    return FulfillmentResponse.model_validate(fulfillment)


@router.post(
    "/{fulfillment_id}/status",
    response_model=FulfillmentResponse,
    summary="Advance fulfillment status one step (PICKING/PACKED/READY_FOR_DELIVERY/OUT_FOR_DELIVERY)",
)
def update_fulfillment_status(
    fulfillment_id: int,
    payload: UpdateFulfillmentStatusRequest,
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).update_status(fulfillment_id, payload.status)


@router.post(
    "/{fulfillment_id}/deliver",
    response_model=FulfillmentResponse,
    summary="Confirm delivery - the only action that consumes physical inventory",
)
def confirm_delivery(
    fulfillment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FulfillmentResponse:
    return FulfillmentService(db).confirm_delivery(fulfillment_id, current_user.id)
