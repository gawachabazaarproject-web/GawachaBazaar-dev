"""Refer & Earn routes.

Customer routes (`/me`, `/apply`, `/history`, `/rewards`) are CUSTOMER-only and
always scoped to the caller: nothing in them takes a user id. Admin routes live
under `/admin` and are gated by `referrals.read` / `referrals.manage`.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, user_or_ip_key
from app.core.roles import CUSTOMER
from app.dependencies.auth import require_permission, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.referral import (
    MAX_PAGE_SIZE,
    AdminReferralActionRequest,
    AdminReferralDetailResponse,
    AdminReferralListResponse,
    ApplyReferralRequest,
    ApplyReferralResponse,
    ReferralHistoryResponse,
    ReferralMeResponse,
    RewardsResponse,
)
from app.services.referral import ReferralService

router = APIRouter()


@router.get("/me", response_model=ReferralMeResponse, summary="My referral code, program rules and stats")
@limiter.limit("60/minute", key_func=user_or_ip_key)
def my_referral(
    request: Request,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> ReferralMeResponse:
    return ReferralService(db).me(current_user)


@router.post(
    "/apply",
    response_model=ApplyReferralResponse,
    summary="Apply a friend's referral code (once, before the first order)",
)
@limiter.limit("10/minute", key_func=user_or_ip_key)
def apply_referral(
    request: Request,
    payload: ApplyReferralRequest,
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> ApplyReferralResponse:
    return ReferralService(db).apply(current_user, payload.code)


@router.get("/history", response_model=ReferralHistoryResponse, summary="People I referred")
def referral_history(
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> ReferralHistoryResponse:
    return ReferralService(db).history(current_user.id, page, page_size)


@router.get("/rewards", response_model=RewardsResponse, summary="My reward ledger and balance")
def referral_rewards(
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_roles(CUSTOMER)),
    db: Session = Depends(get_db),
) -> RewardsResponse:
    return ReferralService(db).rewards(current_user.id, page, page_size)


@router.get(
    "/admin",
    response_model=AdminReferralListResponse,
    summary="Admin: list referrals (referrals.read)",
)
def admin_list_referrals(
    status: str | None = Query(
        default=None, pattern="^(PENDING|QUALIFIED|REWARDED|REVERSED|CANCELLED)$"
    ),
    user_id: int | None = Query(default=None, ge=1, le=2**62),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    _admin: User = Depends(require_permission("referrals.read")),
    db: Session = Depends(get_db),
) -> AdminReferralListResponse:
    return ReferralService(db).admin_list(status, user_id, page, page_size)


@router.get(
    "/admin/{referral_id}",
    response_model=AdminReferralDetailResponse,
    summary="Admin: referral with its ledger (referrals.read)",
)
def admin_get_referral(
    referral_id: int,
    _admin: User = Depends(require_permission("referrals.read")),
    db: Session = Depends(get_db),
) -> AdminReferralDetailResponse:
    return ReferralService(db).admin_get(referral_id)


@router.post(
    "/admin/{referral_id}/reverse",
    response_model=AdminReferralDetailResponse,
    summary="Admin: reverse rewards / cancel a referral (referrals.manage)",
)
def admin_reverse_referral(
    referral_id: int,
    payload: AdminReferralActionRequest,
    admin: User = Depends(require_permission("referrals.manage")),
    db: Session = Depends(get_db),
) -> AdminReferralDetailResponse:
    return ReferralService(db).admin_reverse(referral_id, payload.reason, admin.id)
