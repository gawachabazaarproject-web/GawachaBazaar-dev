"""Home hero-carousel slide schemas - see app/models/home_slide.py."""

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class HomeSlideResponse(BaseSchema):
    """Customer-facing shape - only ACTIVE slides, ordered."""

    id: int
    label: str
    title: str
    script_suffix: str | None
    body: str
    image_url: str
    cta_label: str
    link_url: str | None


class AdminHomeSlideResponse(HomeSlideResponse):
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class UpdateHomeSlideRequest(BaseSchema):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=150)
    script_suffix: str | None = Field(default=None, max_length=150)
    body: str | None = Field(default=None, max_length=1000)
    cta_label: str | None = Field(default=None, max_length=80)
    link_url: str | None = Field(default=None, max_length=2000)
    display_order: int | None = Field(default=None)
    status: str | None = Field(default=None, description="ACTIVE or INACTIVE")
