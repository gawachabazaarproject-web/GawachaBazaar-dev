"""Brand-advertising creative schemas - see app/models/ad.py. Distinct
from Promotion (a discount rule); this is display/link content only.
"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class AdResponse(BaseSchema):
    """Customer-facing shape - only ever ACTIVE ads, ordered by
    display_order. No status/timestamps leaked to the app."""

    id: int
    brand_name: str
    image_url: str
    link_url: str | None
    title: str | None = None
    subtitle: str | None = None


class AdminAdListItemResponse(BaseSchema):
    id: int
    brand_name: str
    image_url: str
    link_url: str | None
    title: str | None = None
    subtitle: str | None = None
    display_order: int
    status: str
    created_at: datetime


class AdminAdDetailResponse(AdminAdListItemResponse):
    updated_at: datetime


class CreateAdRequest(BaseSchema):
    brand_name: str = Field(..., min_length=1, max_length=150)
    link_url: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=80)
    subtitle: str | None = Field(default=None, max_length=140)
    display_order: int = Field(default=0)


class UpdateAdRequest(BaseSchema):
    brand_name: str | None = Field(default=None, min_length=1, max_length=150)
    link_url: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=80)
    subtitle: str | None = Field(default=None, max_length=140)
    display_order: int | None = Field(default=None)
    status: str | None = Field(default=None, description="ACTIVE or INACTIVE")
