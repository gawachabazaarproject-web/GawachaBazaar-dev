"""Delivery-partner schemas. Money (COD expected amount, earnings) is always
server-produced; the only amount a partner ever sends is the COD cash they
physically collected, and it must equal the server's expected amount exactly."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 50

VehicleType = Literal["BIKE", "SCOOTER", "BICYCLE", "VAN", "OTHER"]
PartnerStatus = Literal["ACTIVE", "INACTIVE", "SUSPENDED"]


class PartnerProfileResponse(BaseSchema):
    user_id: int
    name: str | None = None
    status: str
    availability: str
    vehicle_type: str
    vehicle_number: str | None = None
    phone: str | None = None


class PartnerMeResponse(PartnerProfileResponse):
    active_assignments: int
    delivered_today: int
    earned_today: Decimal


class SetAvailabilityRequest(BaseSchema):
    # ON_DELIVERY is derived from active assignments and can never be set by the client.
    availability: Literal["OFFLINE", "AVAILABLE"]


class AssignmentAddress(BaseSchema):
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AssignmentItem(BaseSchema):
    name: str
    quantity: Decimal
    unit: str | None = None


class AssignmentResponse(BaseSchema):
    id: int
    order_id: int
    order_number: str
    fulfillment_id: int
    partner_user_id: int
    status: str
    assigned_at: datetime
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    out_for_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    cod_status: str
    cod_expected_amount: Decimal
    cod_collected_amount: Decimal | None = None
    cod_collected_at: datetime | None = None
    customer_name: str | None = None
    address: AssignmentAddress | None = None
    items: list[AssignmentItem] = []
    maps_url: str | None = None
    earning_amount: Decimal | None = None


class AssignmentListResponse(BaseSchema):
    items: list[AssignmentResponse]
    total: int
    page: int
    page_size: int


class RejectRequest(BaseSchema):
    reason: str = Field(..., min_length=3, max_length=300)


class FailRequest(BaseSchema):
    reason: str = Field(..., min_length=3, max_length=300)


class DeliverRequest(BaseSchema):
    # Required (and checked against the server's expected amount) for COD orders.
    cod_collected_amount: Decimal | None = Field(default=None, ge=0, le=Decimal("10000000"))


class LocationUpdateRequest(BaseSchema):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class LocationAck(BaseSchema):
    accepted: bool = True


class EarningItem(BaseSchema):
    id: int
    assignment_id: int
    order_id: int
    entry_type: str
    amount: Decimal
    rule_version: str
    base_amount: Decimal
    per_km_amount: Decimal
    billable_km: int
    cod_bonus: Decimal
    created_at: datetime


class EarningsResponse(BaseSchema):
    total: Decimal
    count: int
    items: list[EarningItem]
    page: int
    page_size: int
    currency: str = "INR"


class CustomerTrackingResponse(BaseSchema):
    tracking_available: bool
    status: str | None = None
    partner_first_name: str | None = None
    vehicle_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_updated_at: datetime | None = None


# ---- admin ---------------------------------------------------------------


class AdminCreatePartnerRequest(BaseSchema):
    user_id: int = Field(..., ge=1)
    vehicle_type: VehicleType = "BIKE"
    vehicle_number: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[0-9 \-]{7,20}$")


class AdminUpdatePartnerRequest(BaseSchema):
    status: PartnerStatus | None = None
    vehicle_type: VehicleType | None = None
    vehicle_number: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[0-9 \-]{7,20}$")


class AdminPartnerListResponse(BaseSchema):
    items: list[PartnerProfileResponse]
    total: int
    page: int
    page_size: int


class ReassignRequest(BaseSchema):
    delivery_partner_user_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=3, max_length=300)


class CodReconcileRequest(BaseSchema):
    note: str | None = Field(default=None, max_length=300)


class CodSummaryItem(BaseSchema):
    assignment_id: int
    order_id: int
    partner_user_id: int
    cod_status: str
    cod_expected_amount: Decimal
    cod_collected_amount: Decimal | None = None
    cod_collected_at: datetime | None = None
    cod_reconciled_at: datetime | None = None


class CodListResponse(BaseSchema):
    items: list[CodSummaryItem]
    total: int
    outstanding_amount: Decimal
    page: int
    page_size: int


class ActiveDeliveryItem(BaseSchema):
    assignment_id: int
    order_id: int
    partner_user_id: int
    status: str
    latitude: float | None = None
    longitude: float | None = None
    location_updated_at: datetime | None = None


class AdminEarningsSummaryItem(BaseSchema):
    partner_user_id: int
    total: Decimal
    deliveries: int
