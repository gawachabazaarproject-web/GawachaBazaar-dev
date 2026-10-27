"""Refer & Earn schemas. Every number the app shows (rewards, windows, minimum
order) comes from these responses - the client hard-codes none of them."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 50


class ReferralProgramInfo(BaseSchema):
    enabled: bool
    referrer_reward: Decimal
    referred_reward: Decimal
    min_order_value: Decimal
    qualify_window_days: int
    apply_window_days: int
    currency: str = "INR"


class ReferralStats(BaseSchema):
    total_referrals: int
    pending: int
    qualified: int
    rewarded: int
    reversed: int
    cancelled: int
    total_earned: Decimal


class ReferralMeResponse(BaseSchema):
    code: str | None
    share_message: str | None
    program: ReferralProgramInfo
    stats: ReferralStats
    # Whether *this* user can still type a friend's code, and why not.
    can_apply_code: bool
    already_referred: bool
    apply_blocked_reason: str | None = None


class ApplyReferralRequest(BaseSchema):
    # Exactly the characters a code can contain; case-insensitive.
    code: str = Field(..., min_length=6, max_length=16, pattern=r"^[A-Za-z0-9]+$")


class ApplyReferralResponse(BaseSchema):
    status: str
    referrer_display_name: str
    expires_at: datetime
    referred_reward: Decimal
    min_order_value: Decimal


class ReferralHistoryItem(BaseSchema):
    id: int
    referred_display_name: str
    status: str
    applied_at: datetime
    expires_at: datetime
    qualified_at: datetime | None = None
    rewarded_at: datetime | None = None
    reward_amount: Decimal | None = None


class ReferralHistoryResponse(BaseSchema):
    items: list[ReferralHistoryItem]
    total: int
    page: int
    page_size: int


class RewardLedgerItem(BaseSchema):
    id: int
    referral_id: int
    entry_type: str
    amount: Decimal
    beneficiary_role: str
    reason: str | None = None
    created_at: datetime


class RewardsResponse(BaseSchema):
    balance: Decimal
    currency: str = "INR"
    items: list[RewardLedgerItem]
    total: int
    page: int
    page_size: int


class AdminReferralItem(BaseSchema):
    id: int
    referrer_user_id: int
    referred_user_id: int
    status: str
    qualifying_order_id: int | None = None
    applied_at: datetime
    expires_at: datetime
    qualified_at: datetime | None = None
    rewarded_at: datetime | None = None
    reversed_at: datetime | None = None
    cancelled_at: datetime | None = None
    status_reason: str | None = None


class AdminReferralListResponse(BaseSchema):
    items: list[AdminReferralItem]
    total: int
    page: int
    page_size: int


class AdminReferralDetailResponse(AdminReferralItem):
    ledger: list[RewardLedgerItem]


class AdminReferralActionRequest(BaseSchema):
    reason: str = Field(..., min_length=3, max_length=300)
