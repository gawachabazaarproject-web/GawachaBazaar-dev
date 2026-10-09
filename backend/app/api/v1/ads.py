"""Brand-advertising creatives - a public read endpoint for the mobile
app's ads carousel, plus ADMIN-gated management. See app/models/ad.py.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.ad import (
    AdminAdDetailResponse,
    AdminAdListItemResponse,
    AdResponse,
    CreateAdRequest,
    UpdateAdRequest,
)
from app.services.ad import AdService
from app.services.image_upload import upload_image

router = APIRouter()


@router.get("", response_model=list[AdResponse], summary="List Active Ads")
def list_ads(db: Session = Depends(get_db)) -> list[AdResponse]:
    return AdService(db).list_active_ads()


@router.get(
    "/admin", response_model=list[AdminAdListItemResponse], summary="Admin: List All Ads"
)
def admin_list_ads(
    current_user: User = Depends(require_permission("ads.read")),
    db: Session = Depends(get_db),
) -> list[AdminAdListItemResponse]:
    return AdService(db).admin_list_ads()


@router.get(
    "/admin/{ad_id}", response_model=AdminAdDetailResponse, summary="Admin: Get Ad Detail"
)
def admin_get_ad(
    ad_id: int,
    current_user: User = Depends(require_permission("ads.read")),
    db: Session = Depends(get_db),
) -> AdminAdDetailResponse:
    return AdService(db).admin_get_ad_detail(ad_id)


@router.post(
    "/admin",
    response_model=AdminAdDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Create Ad (with creative image)",
)
def admin_create_ad(
    brand_name: str = Form(...),
    link_url: str | None = Form(default=None),
    title: str | None = Form(default=None),
    subtitle: str | None = Form(default=None),
    display_order: int = Form(default=0),
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> AdminAdDetailResponse:
    result = upload_image(file, folder="gawachabazaar/ads")
    data = CreateAdRequest(
        brand_name=brand_name,
        link_url=link_url,
        title=title,
        subtitle=subtitle,
        display_order=display_order,
    )
    return AdService(db).admin_create_ad(result["secure_url"], data, current_user.id)


@router.post(
    "/admin/{ad_id}/image",
    response_model=AdminAdDetailResponse,
    summary="Admin: Replace Ad Creative Image",
)
def admin_replace_ad_image(
    ad_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> AdminAdDetailResponse:
    result = upload_image(file, folder="gawachabazaar/ads")
    return AdService(db).admin_replace_image(ad_id, result["secure_url"], current_user.id)


@router.patch(
    "/admin/{ad_id}", response_model=AdminAdDetailResponse, summary="Admin: Update Ad"
)
def admin_update_ad(
    ad_id: int,
    payload: UpdateAdRequest,
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> AdminAdDetailResponse:
    return AdService(db).admin_update_ad(ad_id, payload, current_user.id)


@router.delete("/admin/{ad_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Admin: Delete Ad")
def admin_delete_ad(
    ad_id: int,
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> None:
    AdService(db).admin_delete_ad(ad_id, current_user.id)
