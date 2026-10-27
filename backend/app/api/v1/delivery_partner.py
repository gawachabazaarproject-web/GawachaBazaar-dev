"""Delivery-partner routes.

* `partner_router`  (`/delivery-partner/...`)  - DELIVERY_PARTNER only, every row
  scoped to the caller (someone else's assignment is a 404).
* `admin_router`    (`/delivery-partners/...`) - staff, gated by `partners.*`
  permissions. Literal paths are declared before `/{user_id}`.
* `tracking_router` (`/orders/{order_id}/delivery-tracking`) - CUSTOMER, own order only.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, user_or_ip_key
from app.core.roles import CUSTOMER, DELIVERY_PARTNER
from app.dependencies.auth import require_permission, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.delivery_partner import (
    MAX_PAGE_SIZE,
    ActiveDeliveryItem,
    AdminCreatePartnerRequest,
    AdminEarningsSummaryItem,
    AdminPartnerListResponse,
    AdminUpdatePartnerRequest,
    AssignmentListResponse,
    AssignmentResponse,
    CodListResponse,
    CodReconcileRequest,
    CodSummaryItem,
    CustomerDeliveryOtpResponse,
    CustomerTrackingResponse,
    DeliverRequest,
    EarningsResponse,
    FailRequest,
    LocationAck,
    LocationUpdateRequest,
    OtpStatusSummary,
    PartnerMeResponse,
    PartnerProfileResponse,
    RejectRequest,
    SetAvailabilityRequest,
)
from app.services.delivery_assignment import DeliveryAssignmentService
from app.services.delivery_otp import DeliveryOtpService

_STATUS_RE = "^(ASSIGNED|ACCEPTED|PICKED_UP|OUT_FOR_DELIVERY|DELIVERED|FAILED|REJECTED|CANCELLED)$"
_ID = Query(default=None, ge=1, le=2**62)

partner_router = APIRouter()
admin_router = APIRouter()
tracking_router = APIRouter()


# ---------------------------------------------------------------------------
# Partner (self)
# ---------------------------------------------------------------------------


@partner_router.get("/me", response_model=PartnerMeResponse, summary="My partner profile and today's numbers")
def partner_me(
    user: User = Depends(require_roles(DELIVERY_PARTNER)), db: Session = Depends(get_db)
) -> PartnerMeResponse:
    return DeliveryAssignmentService(db).me(user)


@partner_router.patch(
    "/me/availability", response_model=PartnerMeResponse, summary="Go online / offline"
)
def partner_set_availability(
    payload: SetAvailabilityRequest,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> PartnerMeResponse:
    return DeliveryAssignmentService(db).set_availability(user, payload.availability)


@partner_router.get(
    "/assignments", response_model=AssignmentListResponse, summary="My deliveries (active or history)"
)
def partner_assignments(
    scope: str = Query(default="active", pattern="^(active|history)$"),
    status: str | None = Query(default=None, pattern=_STATUS_RE),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentListResponse:
    return DeliveryAssignmentService(db).list_for_partner(
        user, scope, status, date_from, date_to, page, page_size
    )


@partner_router.get(
    "/assignments/{assignment_id}", response_model=AssignmentResponse, summary="One of my deliveries"
)
def partner_assignment(
    assignment_id: int,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return DeliveryAssignmentService(db).get_for_partner(assignment_id, user)


@partner_router.post(
    "/assignments/{assignment_id}/accept", response_model=AssignmentResponse, summary="Accept (ASSIGNED -> ACCEPTED)"
)
def partner_accept(
    assignment_id: int,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return DeliveryAssignmentService(db).accept(assignment_id, user)


@partner_router.post(
    "/assignments/{assignment_id}/reject",
    response_model=AssignmentResponse,
    summary="Decline before accepting (back to the dispatch queue)",
)
def partner_reject(
    assignment_id: int,
    payload: RejectRequest,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return DeliveryAssignmentService(db).reject(assignment_id, user, payload.reason)


@partner_router.post(
    "/assignments/{assignment_id}/pickup", response_model=AssignmentResponse, summary="Picked up (ACCEPTED -> PICKED_UP)"
)
def partner_pickup(
    assignment_id: int,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return DeliveryAssignmentService(db).pickup(assignment_id, user)


@partner_router.post(
    "/assignments/{assignment_id}/out-for-delivery",
    response_model=AssignmentResponse,
    summary="Leave for the customer (PICKED_UP -> OUT_FOR_DELIVERY)",
)
def partner_out_for_delivery(
    assignment_id: int,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return DeliveryAssignmentService(db).out_for_delivery(assignment_id, user)


@partner_router.post(
    "/assignments/{assignment_id}/deliver",
    response_model=AssignmentResponse,
    summary="Complete the delivery; confirms COD cash (must equal the amount due)",
)
@limiter.limit("30/minute", key_func=user_or_ip_key)
def partner_deliver(
    request: Request,
    assignment_id: int,
    payload: DeliverRequest,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    # This is also the OTP verification endpoint: the code is checked inside the same
    # atomic transaction that completes the delivery (see DeliveryOtpService).
    return DeliveryAssignmentService(db).deliver(
        assignment_id, user, payload.cod_collected_amount, payload.otp
    )


@partner_router.post(
    "/assignments/{assignment_id}/otp/send",
    response_model=OtpStatusSummary,
    summary="At the door: send the COD delivery code to the customer (resend replaces it; rate limited)",
)
@limiter.limit("10/minute", key_func=user_or_ip_key)
def partner_send_delivery_otp(
    request: Request,
    assignment_id: int,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> OtpStatusSummary:
    return DeliveryOtpService(db).send_for_assignment(assignment_id, user)


@partner_router.post(
    "/assignments/{assignment_id}/fail",
    response_model=AssignmentResponse,
    summary="Delivery could not be completed (back to the dispatch queue)",
)
def partner_fail(
    assignment_id: int,
    payload: FailRequest,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return DeliveryAssignmentService(db).fail(assignment_id, user, payload.reason)


@partner_router.post(
    "/assignments/{assignment_id}/location",
    response_model=LocationAck,
    summary="Share current location (only during an active delivery; rate limited)",
)
@limiter.limit("120/minute", key_func=user_or_ip_key)
def partner_location(
    request: Request,
    assignment_id: int,
    payload: LocationUpdateRequest,
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> LocationAck:
    DeliveryAssignmentService(db).update_location(
        assignment_id, user, payload.latitude, payload.longitude, payload.accuracy_m
    )
    return LocationAck()


@partner_router.get("/earnings", response_model=EarningsResponse, summary="My earnings ledger")
def partner_earnings(
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(require_roles(DELIVERY_PARTNER)),
    db: Session = Depends(get_db),
) -> EarningsResponse:
    return DeliveryAssignmentService(db).earnings(user, date_from, date_to, page, page_size)


# ---------------------------------------------------------------------------
# Customer tracking
# ---------------------------------------------------------------------------


@tracking_router.get(
    "/{order_id}/delivery-tracking",
    response_model=CustomerTrackingResponse,
    summary="Where is my delivery (own order, only while it is being delivered)",
)
def order_delivery_tracking(
    order_id: int,
    user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> CustomerTrackingResponse:
    return DeliveryAssignmentService(db).customer_tracking(order_id, user.id)


@tracking_router.get(
    "/{order_id}/delivery-otp",
    response_model=CustomerDeliveryOtpResponse,
    summary="My COD delivery code (own order only; the code is shown only while active)",
)
@limiter.limit("60/minute", key_func=user_or_ip_key)
def order_delivery_otp(
    request: Request,
    order_id: int,
    user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> CustomerDeliveryOtpResponse:
    return DeliveryOtpService(db).customer_view(order_id, user.id)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


@admin_router.get("", response_model=AdminPartnerListResponse, summary="List delivery partners (partners.read)")
def admin_list_partners(
    status: str | None = Query(default=None, pattern="^(ACTIVE|INACTIVE|SUSPENDED)$"),
    availability: str | None = Query(default=None, pattern="^(OFFLINE|AVAILABLE|ON_DELIVERY)$"),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    _u: User = Depends(require_permission("partners.read")),
    db: Session = Depends(get_db),
) -> AdminPartnerListResponse:
    return DeliveryAssignmentService(db).admin_list_partners(status, availability, page, page_size)


@admin_router.post("", response_model=PartnerProfileResponse, status_code=201, summary="Create a partner profile (partners.manage)")
def admin_create_partner(
    payload: AdminCreatePartnerRequest,
    admin: User = Depends(require_permission("partners.manage")),
    db: Session = Depends(get_db),
) -> PartnerProfileResponse:
    return DeliveryAssignmentService(db).admin_create_partner(
        admin.id, payload.user_id, payload.vehicle_type, payload.vehicle_number, payload.phone
    )


@admin_router.get("/assignments", response_model=AssignmentListResponse, summary="All assignments (partners.read)")
def admin_assignments(
    status: str | None = Query(default=None, pattern=_STATUS_RE),
    partner_user_id: int | None = _ID,
    order_id: int | None = _ID,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    _u: User = Depends(require_permission("partners.read")),
    db: Session = Depends(get_db),
) -> AssignmentListResponse:
    return DeliveryAssignmentService(db).admin_list_assignments(
        status, partner_user_id, order_id, page, page_size
    )


@admin_router.get("/active", response_model=list[ActiveDeliveryItem], summary="Active deliveries with last position (partners.read)")
def admin_active(
    _u: User = Depends(require_permission("partners.read")), db: Session = Depends(get_db)
) -> list[ActiveDeliveryItem]:
    return DeliveryAssignmentService(db).admin_active_deliveries()


@admin_router.get("/cod", response_model=CodListResponse, summary="COD cash collected / outstanding (partners.read)")
def admin_cod(
    reconciled: bool | None = None,
    partner_user_id: int | None = _ID,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    _u: User = Depends(require_permission("partners.read")),
    db: Session = Depends(get_db),
) -> CodListResponse:
    return DeliveryAssignmentService(db).admin_cod_list(reconciled, partner_user_id, page, page_size)


@admin_router.post(
    "/assignments/{assignment_id}/cod-reconcile",
    response_model=CodSummaryItem,
    summary="Mark collected cash as handed over (partners.cod_reconcile)",
)
def admin_cod_reconcile(
    assignment_id: int,
    payload: CodReconcileRequest,
    admin: User = Depends(require_permission("partners.cod_reconcile")),
    db: Session = Depends(get_db),
) -> CodSummaryItem:
    return DeliveryAssignmentService(db).admin_cod_reconcile(assignment_id, admin.id, payload.note)


@admin_router.get("/earnings", response_model=list[AdminEarningsSummaryItem], summary="Earnings per partner (partners.read)")
def admin_earnings(
    date_from: date | None = None,
    date_to: date | None = None,
    _u: User = Depends(require_permission("partners.read")),
    db: Session = Depends(get_db),
) -> list[AdminEarningsSummaryItem]:
    return DeliveryAssignmentService(db).admin_earnings_summary(date_from, date_to)


@admin_router.patch("/{user_id}", response_model=PartnerProfileResponse, summary="Update a partner (partners.manage)")
def admin_update_partner(
    user_id: int,
    payload: AdminUpdatePartnerRequest,
    admin: User = Depends(require_permission("partners.manage")),
    db: Session = Depends(get_db),
) -> PartnerProfileResponse:
    return DeliveryAssignmentService(db).admin_update_partner(
        admin.id, user_id, payload.model_dump(exclude_unset=True)
    )
