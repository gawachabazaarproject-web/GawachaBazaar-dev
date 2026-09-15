"""Promotion effective-status computation.

Mirrors the pure-logic pattern of order_state.py/payment_state.py: no
DB/HTTP dependencies. `Promotion.status` is the admin-set control
(DRAFT/ACTIVE/PAUSED/DISABLED, stored); the customer-facing
SCHEDULED/ACTIVE/EXPIRED split is a pure function of that stored status
plus `starts_at`/`ends_at` vs "now" - computed at read time everywhere
(admin list/detail, checkout eligibility, dashboard counts), never stored,
so it can never drift from the clock and never needs a background job.

An admin-DRAFT/PAUSED/DISABLED promotion stays exactly that regardless of
its dates - arriving at `starts_at` does not silently make a DRAFT
promotion live. Only an admin-ACTIVE promotion's effective status moves
through SCHEDULED -> ACTIVE -> EXPIRED as time passes.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PromotionAdminStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


class PromotionEffectiveStatus(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class PromotionLike:
    """The three fields effective-status computation needs - callers pass
    either a real `Promotion` ORM object or this lightweight shape."""

    status: str
    starts_at: datetime
    ends_at: datetime | None


def compute_effective_status(promotion: PromotionLike, now: datetime) -> PromotionEffectiveStatus:
    if promotion.status == PromotionAdminStatus.DRAFT:
        return PromotionEffectiveStatus.DRAFT
    if promotion.status == PromotionAdminStatus.PAUSED:
        return PromotionEffectiveStatus.PAUSED
    if promotion.status == PromotionAdminStatus.DISABLED:
        return PromotionEffectiveStatus.DISABLED

    # status == ACTIVE (admin-enabled) - dates decide the customer-facing view.
    if now < promotion.starts_at:
        return PromotionEffectiveStatus.SCHEDULED
    if promotion.ends_at is not None and now > promotion.ends_at:
        return PromotionEffectiveStatus.EXPIRED
    return PromotionEffectiveStatus.ACTIVE


def is_currently_redeemable(promotion: PromotionLike, now: datetime) -> bool:
    """True only when a customer could actually apply this promotion right
    now - i.e. its effective status is ACTIVE. Every other effective
    status (including admin-ACTIVE-but-not-yet-started/already-ended)
    means "not applicable today".
    """
    return compute_effective_status(promotion, now) == PromotionEffectiveStatus.ACTIVE
