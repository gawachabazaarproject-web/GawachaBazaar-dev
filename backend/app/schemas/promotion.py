"""Promotion domain schemas: admin management + the customer-facing
preview/evaluation shape. Kept in one file (mixing public and admin
sections) since this is a brand-new domain with no pre-existing
public/admin split to preserve - matches the convention already used by
`schemas/bulk_order.py` for the same reason.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 100

DiscountType = Literal["PERCENTAGE", "FIXED_AMOUNT"]
CustomerScope = Literal["ALL", "NEW_CUSTOMERS", "EXISTING_CUSTOMERS", "SPECIFIC"]
PromotionAdminStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "DISABLED"]
TargetType = Literal["PRODUCT", "CATEGORY"]


# ---------------------------------------------------------------------------
# Admin: targets / eligible customers (nested in create/update)
# ---------------------------------------------------------------------------


class PromotionTargetInput(BaseSchema):
    target_type: TargetType
    target_id: int = Field(..., gt=0)


class PromotionTargetResponse(BaseSchema):
    target_type: str
    target_id: int
    # Denormalized display name - resolved server-side (product/category
    # name), never stored redundantly on the target row itself.
    target_name: str | None = None


# ---------------------------------------------------------------------------
# Admin: create / update
# ---------------------------------------------------------------------------


class CreatePromotionRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None)
    customer_title: str | None = Field(default=None, max_length=150)
    customer_description: str | None = Field(default=None)
    code: str | None = Field(default=None, min_length=3, max_length=50)
    discount_type: DiscountType
    discount_value: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_order_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    customer_scope: CustomerScope = Field(default="ALL")
    eligible_customer_ids: list[int] = Field(default_factory=list)
    status: PromotionAdminStatus = Field(default="DRAFT")
    priority: int = Field(default=100, ge=1, le=1000)
    usage_limit_total: int | None = Field(default=None, gt=0)
    usage_limit_per_customer: int | None = Field(default=None, gt=0)
    starts_at: datetime
    ends_at: datetime | None = Field(default=None)
    targets: list[PromotionTargetInput] = Field(default_factory=list)

    @field_validator("discount_value")
    @classmethod
    def _validate_percentage_range(cls, v: Decimal, info) -> Decimal:
        # Cross-field percentage<=100 check also lives in the DB CHECK
        # constraint (ck_promotions_percentage_max) - this is the earlier,
        # friendlier validation error for the same rule.
        discount_type = info.data.get("discount_type")
        if discount_type == "PERCENTAGE" and v > 100:
            raise ValueError("A percentage discount cannot exceed 100.")
        return v

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None


class UpdatePromotionRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None)
    customer_title: str | None = Field(default=None, max_length=150)
    customer_description: str | None = Field(default=None)
    code: str | None = Field(default=None, min_length=3, max_length=50)
    discount_type: DiscountType | None = Field(default=None)
    discount_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_order_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    customer_scope: CustomerScope | None = Field(default=None)
    eligible_customer_ids: list[int] | None = Field(default=None)
    status: PromotionAdminStatus | None = Field(default=None)
    priority: int | None = Field(default=None, ge=1, le=1000)
    usage_limit_total: int | None = Field(default=None, gt=0)
    usage_limit_per_customer: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = Field(default=None)
    ends_at: datetime | None = Field(default=None)
    targets: list[PromotionTargetInput] | None = Field(default=None)

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None


# ---------------------------------------------------------------------------
# Admin: responses
# ---------------------------------------------------------------------------


class PromotionListItemResponse(BaseSchema):
    id: int
    name: str
    discount_type: str
    discount_value: Decimal
    code: str | None
    customer_scope: str
    admin_status: str
    effective_status: str
    priority: int
    usage_limit_total: int | None
    redemption_count: int
    starts_at: datetime
    ends_at: datetime | None
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class PromotionListResponse(BaseSchema):
    items: list[PromotionListItemResponse]
    page: int
    page_size: int
    total: int


class PromotionPerformanceResponse(BaseSchema):
    """Every figure is a real aggregate over `promotion_redemptions`/
    `orders` - never fabricated. `revenue_influenced` is explicitly labeled:
    it is the total order value (post-discount `total_amount`) of orders
    that redeemed this promotion, not a causal claim that the promotion
    generated that revenue.
    """

    redemption_count: int
    reversed_count: int
    total_discount_granted: Decimal
    revenue_influenced: Decimal
    average_order_value: Decimal | None


class PromotionDetailResponse(BaseSchema):
    id: int
    name: str
    description: str | None
    customer_title: str | None
    customer_description: str | None
    code: str | None
    discount_type: str
    discount_value: Decimal
    max_discount_amount: Decimal | None
    min_order_value: Decimal | None
    min_quantity: Decimal | None
    customer_scope: str
    eligible_customer_ids: list[int]
    admin_status: str
    effective_status: str
    stacking_policy: str
    priority: int
    usage_limit_total: int | None
    usage_limit_per_customer: int | None
    redemption_count: int
    starts_at: datetime
    ends_at: datetime | None
    targets: list[PromotionTargetResponse]
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    performance: PromotionPerformanceResponse


class PromotionRedemptionRowResponse(BaseSchema):
    id: int
    order_id: int
    order_number: str
    order_status: str
    customer_id: int
    customer_name: str
    discount_amount: Decimal
    order_total: Decimal
    status: str
    redeemed_at: datetime


class PromotionRedemptionListResponse(BaseSchema):
    items: list[PromotionRedemptionRowResponse]
    page: int
    page_size: int
    total: int


class PromotionsDashboardResponse(BaseSchema):
    active_count: int
    scheduled_count: int
    expired_count: int
    draft_count: int
    disabled_count: int
    paused_count: int
    total_redemptions: int
    total_discount_granted: Decimal
    ending_soon: list[PromotionListItemResponse]
    most_used: list[PromotionListItemResponse]


# ---------------------------------------------------------------------------
# Customer-facing: evaluate/preview a code against the caller's own cart
# ---------------------------------------------------------------------------


class EvaluatePromotionRequest(BaseSchema):
    promo_code: str | None = Field(default=None, max_length=50)


class PromotionEvaluationResponse(BaseSchema):
    """The one place a discount amount is ever computed for display before
    checkout - always via the same engine checkout itself uses
    (`PromotionService.evaluate_for_cart`), so a preview can never disagree
    with what checkout actually charges.
    """

    eligible: bool
    message: str
    promotion_id: int | None = None
    promotion_name: str | None = None
    applied_code: str | None = None
    subtotal: Decimal
    discount_amount: Decimal
    final_total: Decimal
