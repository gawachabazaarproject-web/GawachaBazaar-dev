"""Home hero-carousel slide management - see app/models/home_slide.py."""

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessValidationError, NotFoundError
from app.models.home_slide import HomeSlide
from app.schemas.home_slide import AdminHomeSlideResponse, HomeSlideResponse, UpdateHomeSlideRequest
from app.services.admin_audit import AdminAuditService

_VALID_STATUSES = ("ACTIVE", "INACTIVE")


class HomeSlideService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> list[HomeSlideResponse]:
        rows = (
            self.db.query(HomeSlide)
            .filter(HomeSlide.status == "ACTIVE")
            .order_by(HomeSlide.display_order.asc(), HomeSlide.id.asc())
            .all()
        )
        return [HomeSlideResponse.model_validate(r, from_attributes=True) for r in rows]

    def admin_list(self) -> list[AdminHomeSlideResponse]:
        rows = self.db.query(HomeSlide).order_by(HomeSlide.display_order.asc(), HomeSlide.id.asc()).all()
        return [AdminHomeSlideResponse.model_validate(r, from_attributes=True) for r in rows]

    def admin_create(
        self,
        *,
        image_url: str,
        label: str,
        title: str,
        script_suffix: str | None,
        body: str,
        cta_label: str,
        link_url: str | None,
        display_order: int,
        admin_user_id: int,
    ) -> AdminHomeSlideResponse:
        if not label.strip() or not title.strip():
            raise BusinessValidationError("Label and title are required.")
        slide = HomeSlide(
            label=label.strip(),
            title=title.strip(),
            script_suffix=(script_suffix or "").strip() or None,
            body=body.strip(),
            image_url=image_url,
            cta_label=cta_label.strip(),
            link_url=(link_url or "").strip() or None,
            display_order=display_order,
            status="ACTIVE",
        )
        self.db.add(slide)
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="home_slide.create",
            resource_type="home_slide",
            resource_id=slide.id,
            reason=f"title={slide.title}",
        )
        self.db.commit()
        self.db.refresh(slide)
        return AdminHomeSlideResponse.model_validate(slide, from_attributes=True)

    def admin_update(
        self, slide_id: int, data: UpdateHomeSlideRequest, admin_user_id: int
    ) -> AdminHomeSlideResponse:
        slide = self._get_or_404(slide_id)
        if data.status is not None and data.status not in _VALID_STATUSES:
            raise BusinessValidationError(f"Invalid status '{data.status}'.")
        for field in ("label", "title", "body", "cta_label", "display_order", "status"):
            value = getattr(data, field)
            if value is not None:
                setattr(slide, field, value.strip() if isinstance(value, str) else value)
        if data.script_suffix is not None:
            slide.script_suffix = data.script_suffix.strip() or None  # "" clears it
        if data.link_url is not None:
            slide.link_url = data.link_url.strip() or None  # "" clears it
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="home_slide.update",
            resource_type="home_slide",
            resource_id=slide.id,
        )
        self.db.commit()
        self.db.refresh(slide)
        return AdminHomeSlideResponse.model_validate(slide, from_attributes=True)

    def admin_replace_image(
        self, slide_id: int, image_url: str, admin_user_id: int
    ) -> AdminHomeSlideResponse:
        slide = self._get_or_404(slide_id)
        slide.image_url = image_url
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="home_slide.image.replace",
            resource_type="home_slide",
            resource_id=slide.id,
        )
        self.db.commit()
        self.db.refresh(slide)
        return AdminHomeSlideResponse.model_validate(slide, from_attributes=True)

    def admin_delete(self, slide_id: int, admin_user_id: int) -> None:
        slide = self._get_or_404(slide_id)
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="home_slide.delete",
            resource_type="home_slide",
            resource_id=slide.id,
            reason=f"title={slide.title}",
        )
        self.db.delete(slide)
        self.db.commit()

    def _get_or_404(self, slide_id: int) -> HomeSlide:
        slide = self.db.query(HomeSlide).filter(HomeSlide.id == slide_id).first()
        if not slide:
            raise NotFoundError("Slide not found.")
        return slide
