"""Home hero-carousel slides - public read for the mobile app, plus
ADMIN-gated management (reuses the ads.* permissions: same marketing
content area). See app/models/home_slide.py."""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.home_slide import (
    AdminHomeSlideResponse,
    HomeSlideResponse,
    UpdateHomeSlideRequest,
)
from app.services.home_slide import HomeSlideService
from app.services.image_upload import upload_image

router = APIRouter()


@router.get("", response_model=list[HomeSlideResponse], summary="List Active Home Slides")
def list_home_slides(db: Session = Depends(get_db)) -> list[HomeSlideResponse]:
    return HomeSlideService(db).list_active()


@router.get(
    "/admin", response_model=list[AdminHomeSlideResponse], summary="Admin: List All Home Slides"
)
def admin_list_home_slides(
    current_user: User = Depends(require_permission("ads.read")),
    db: Session = Depends(get_db),
) -> list[AdminHomeSlideResponse]:
    return HomeSlideService(db).admin_list()


@router.post(
    "/admin",
    response_model=AdminHomeSlideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Create Home Slide (with image)",
)
def admin_create_home_slide(
    label: str = Form(...),
    title: str = Form(...),
    script_suffix: str | None = Form(default=None),
    body: str = Form(default=""),
    cta_label: str = Form(default=""),
    link_url: str | None = Form(default=None),
    display_order: int = Form(default=0),
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> AdminHomeSlideResponse:
    result = upload_image(file, folder="gawachabazaar/home-slides")
    return HomeSlideService(db).admin_create(
        image_url=result["secure_url"],
        label=label,
        title=title,
        script_suffix=script_suffix,
        body=body,
        cta_label=cta_label,
        link_url=link_url,
        display_order=display_order,
        admin_user_id=current_user.id,
    )


@router.post(
    "/admin/{slide_id}/image",
    response_model=AdminHomeSlideResponse,
    summary="Admin: Replace Home Slide Image",
)
def admin_replace_home_slide_image(
    slide_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> AdminHomeSlideResponse:
    result = upload_image(file, folder="gawachabazaar/home-slides")
    return HomeSlideService(db).admin_replace_image(slide_id, result["secure_url"], current_user.id)


@router.patch(
    "/admin/{slide_id}", response_model=AdminHomeSlideResponse, summary="Admin: Update Home Slide"
)
def admin_update_home_slide(
    slide_id: int,
    payload: UpdateHomeSlideRequest,
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> AdminHomeSlideResponse:
    return HomeSlideService(db).admin_update(slide_id, payload, current_user.id)


@router.delete(
    "/admin/{slide_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Admin: Delete Home Slide"
)
def admin_delete_home_slide(
    slide_id: int,
    current_user: User = Depends(require_permission("ads.manage")),
    db: Session = Depends(get_db),
) -> None:
    HomeSlideService(db).admin_delete(slide_id, current_user.id)
