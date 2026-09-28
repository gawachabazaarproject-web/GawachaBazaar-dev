"""Brand-advertising creative management - see app/models/ad.py."""

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessValidationError, NotFoundError
from app.models.ad import Ad
from app.schemas.ad import (
    AdminAdDetailResponse,
    AdminAdListItemResponse,
    AdResponse,
    CreateAdRequest,
    UpdateAdRequest,
)
from app.services.admin_audit import AdminAuditService

_VALID_STATUSES = ("ACTIVE", "INACTIVE")


class AdService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_ads(self) -> list[AdResponse]:
        ads = (
            self.db.query(Ad)
            .filter(Ad.status == "ACTIVE")
            .order_by(Ad.display_order.asc(), Ad.id.asc())
            .all()
        )
        return [
            AdResponse(id=a.id, brand_name=a.brand_name, image_url=a.image_url, link_url=a.link_url)
            for a in ads
        ]

    def admin_list_ads(self) -> list[AdminAdListItemResponse]:
        ads = self.db.query(Ad).order_by(Ad.display_order.asc(), Ad.id.asc()).all()
        return [self._to_list_item(a) for a in ads]

    def admin_get_ad_detail(self, ad_id: int) -> AdminAdDetailResponse:
        ad = self._get_or_404(ad_id)
        item = self._to_list_item(ad)
        return AdminAdDetailResponse(**item.model_dump(), updated_at=ad.updated_at)

    def admin_create_ad(
        self, image_url: str, data: CreateAdRequest, admin_user_id: int
    ) -> AdminAdDetailResponse:
        ad = Ad(
            brand_name=data.brand_name,
            image_url=image_url,
            link_url=data.link_url or None,
            display_order=data.display_order,
            status="ACTIVE",
        )
        self.db.add(ad)
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="ad.create",
            resource_type="ad",
            resource_id=ad.id,
            reason=f"brand={data.brand_name}",
        )
        self.db.commit()
        return self.admin_get_ad_detail(ad.id)

    def admin_update_ad(
        self, ad_id: int, data: UpdateAdRequest, admin_user_id: int
    ) -> AdminAdDetailResponse:
        ad = self._get_or_404(ad_id)
        if data.status is not None and data.status not in _VALID_STATUSES:
            raise BusinessValidationError(f"Invalid status '{data.status}'.")

        if data.brand_name is not None:
            ad.brand_name = data.brand_name
        if data.link_url is not None:
            ad.link_url = data.link_url or None  # "" clears the link
        if data.display_order is not None:
            ad.display_order = data.display_order
        if data.status is not None:
            ad.status = data.status

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="ad.update",
            resource_type="ad",
            resource_id=ad.id,
        )
        self.db.commit()
        return self.admin_get_ad_detail(ad.id)

    def admin_replace_image(self, ad_id: int, image_url: str, admin_user_id: int) -> AdminAdDetailResponse:
        ad = self._get_or_404(ad_id)
        ad.image_url = image_url
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="ad.image.replace",
            resource_type="ad",
            resource_id=ad.id,
        )
        self.db.commit()
        return self.admin_get_ad_detail(ad.id)

    def admin_delete_ad(self, ad_id: int, admin_user_id: int) -> None:
        ad = self._get_or_404(ad_id)
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="ad.delete",
            resource_type="ad",
            resource_id=ad.id,
            reason=f"brand={ad.brand_name}",
        )
        self.db.delete(ad)
        self.db.commit()

    # ------------------------------------------------------------------
    def _get_or_404(self, ad_id: int) -> Ad:
        ad = self.db.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            raise NotFoundError("Ad not found.")
        return ad

    @staticmethod
    def _to_list_item(ad: Ad) -> AdminAdListItemResponse:
        return AdminAdListItemResponse(
            id=ad.id,
            brand_name=ad.brand_name,
            image_url=ad.image_url,
            link_url=ad.link_url,
            display_order=ad.display_order,
            status=ad.status,
            created_at=ad.created_at,
        )
