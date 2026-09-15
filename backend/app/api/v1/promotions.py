"""Promotion domain routes: admin management (ADMIN-only, gated by the
granular `promotions.*` permissions in app/core/permissions.py). The
customer-facing preview lives under /cart (see cart.py's
POST /cart/evaluate-promo) since it operates on the caller's own cart,
not this router.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.promotion import (
    MAX_PAGE_SIZE,
    CreatePromotionRequest,
    PromotionDetailResponse,
    PromotionListResponse,
    PromotionRedemptionListResponse,
    PromotionsDashboardResponse,
    UpdatePromotionRequest,
)
from app.services.admin_audit import AdminAuditService
from app.services.promotion import PromotionService

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=PromotionsDashboardResponse,
    summary="Promotions overview: status counts, redemption totals, ending-soon/most-used",
)
def get_dashboard(
    current_user: User = Depends(require_permission("promotions.read")),
    db: Session = Depends(get_db),
) -> PromotionsDashboardResponse:
    return PromotionService(db).admin_dashboard()


@router.get(
    "",
    response_model=PromotionListResponse,
    summary="List/search/filter promotions",
)
def list_promotions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    admin_status: str | None = Query(default=None, description="DRAFT/ACTIVE/PAUSED/DISABLED"),
    effective_status: str | None = Query(
        default=None, description="DRAFT/SCHEDULED/ACTIVE/PAUSED/EXPIRED/DISABLED"
    ),
    q: str | None = Query(default=None, max_length=150, description="Name or code"),
    current_user: User = Depends(require_permission("promotions.read")),
    db: Session = Depends(get_db),
) -> PromotionListResponse:
    return PromotionService(db).admin_list_promotions(page, page_size, admin_status, effective_status, q)


@router.post(
    "",
    response_model=PromotionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a promotion (starts as DRAFT unless status is explicitly set)",
)
def create_promotion(
    payload: CreatePromotionRequest,
    current_user: User = Depends(require_permission("promotions.create")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return PromotionService(db).create_promotion(payload, current_user.id)


@router.get(
    "/{promotion_id}",
    response_model=PromotionDetailResponse,
    summary="Get full promotion detail including performance",
)
def get_promotion(
    promotion_id: int,
    current_user: User = Depends(require_permission("promotions.read")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return PromotionService(db).admin_get_promotion_detail(promotion_id)


@router.patch(
    "/{promotion_id}",
    response_model=PromotionDetailResponse,
    summary="Update a promotion's rules/schedule/targets",
)
def update_promotion(
    promotion_id: int,
    payload: UpdatePromotionRequest,
    current_user: User = Depends(require_permission("promotions.update")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return PromotionService(db).update_promotion(promotion_id, payload, current_user.id)


@router.post(
    "/{promotion_id}/duplicate",
    response_model=PromotionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a promotion as a new DRAFT (no code, no accrued usage)",
)
def duplicate_promotion(
    promotion_id: int,
    current_user: User = Depends(require_permission("promotions.manage_status")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return PromotionService(db).duplicate_promotion(promotion_id, current_user.id)


def _set_status(
    promotion_id: int, new_status: str, admin_user_id: int, db: Session
) -> PromotionDetailResponse:
    service = PromotionService(db)
    promotion = service.get_promotion_or_404(promotion_id)
    previous = promotion.status
    promotion.status = new_status
    AdminAuditService(db).record(
        admin_user_id=admin_user_id,
        action=f"promotion.{new_status.lower()}",
        resource_type="promotion",
        resource_id=promotion.id,
        previous_state=previous,
        new_state=new_status,
    )
    db.commit()
    return service.admin_get_promotion_detail(promotion_id)


@router.post(
    "/{promotion_id}/activate",
    response_model=PromotionDetailResponse,
    summary="Activate a promotion (DRAFT/PAUSED -> ACTIVE)",
)
def activate_promotion(
    promotion_id: int,
    current_user: User = Depends(require_permission("promotions.manage_status")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return _set_status(promotion_id, "ACTIVE", current_user.id, db)


@router.post(
    "/{promotion_id}/pause",
    response_model=PromotionDetailResponse,
    summary="Pause a promotion (ACTIVE -> PAUSED; no new redemptions until reactivated)",
)
def pause_promotion(
    promotion_id: int,
    current_user: User = Depends(require_permission("promotions.manage_status")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return _set_status(promotion_id, "PAUSED", current_user.id, db)


@router.post(
    "/{promotion_id}/disable",
    response_model=PromotionDetailResponse,
    summary="Disable a promotion permanently (any status -> DISABLED; never usable again, never deleted)",
)
def disable_promotion(
    promotion_id: int,
    current_user: User = Depends(require_permission("promotions.manage_status")),
    db: Session = Depends(get_db),
) -> PromotionDetailResponse:
    return _set_status(promotion_id, "DISABLED", current_user.id, db)


@router.get(
    "/{promotion_id}/redemptions",
    response_model=PromotionRedemptionListResponse,
    summary="Coupon usage history for one promotion",
)
def list_redemptions(
    promotion_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(require_permission("promotions.read")),
    db: Session = Depends(get_db),
) -> PromotionRedemptionListResponse:
    return PromotionService(db).list_redemptions(promotion_id, page, page_size)
