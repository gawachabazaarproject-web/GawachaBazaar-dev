"""Catalog domain schemas: categories, products, variants, images, prices."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

CategoryStatus = Literal["ACTIVE", "INACTIVE", "ARCHIVED"]
ProductStatus = Literal["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]
VariantStatus = Literal["ACTIVE", "INACTIVE", "ARCHIVED"]
VariantUnit = Literal["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "PACK"]

MAX_PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CreateCategoryRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=180)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None)
    status: CategoryStatus = Field(default="ACTIVE")


class UpdateCategoryRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None)
    status: CategoryStatus | None = Field(default=None)


class CategoryResponse(BaseSchema):
    id: int
    name: str
    slug: str
    description: str | None
    parent_id: int | None
    status: str
    created_at: datetime


class CategoryDetailResponse(CategoryResponse):
    children: list[CategoryResponse] = Field(default_factory=list)


class CategoryListResponse(BaseSchema):
    items: list[CategoryResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Product Image
# ---------------------------------------------------------------------------


class CreateProductImageRequest(BaseSchema):
    image_url: str = Field(..., min_length=1, max_length=2048)
    alt_text: str | None = Field(default=None, max_length=255)
    is_primary: bool = Field(default=False)
    sort_order: int = Field(default=0, ge=0)


class UpdateProductImageRequest(BaseSchema):
    image_url: str | None = Field(default=None, min_length=1, max_length=2048)
    alt_text: str | None = Field(default=None, max_length=255)
    is_primary: bool | None = Field(default=None)
    sort_order: int | None = Field(default=None, ge=0)


class ProductImageResponse(BaseSchema):
    id: int
    image_url: str
    alt_text: str | None
    is_primary: bool
    sort_order: int


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------


class CreatePriceRequest(BaseSchema):
    price: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    valid_from: datetime | None = Field(default=None)
    valid_to: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)


class UpdatePriceRequest(BaseSchema):
    """Only validity/activation may change - price history is never rewritten."""

    is_active: bool | None = Field(default=None)
    valid_to: datetime | None = Field(default=None)


class PriceResponse(BaseSchema):
    id: int
    variant_id: int
    price: Decimal
    currency: str
    valid_from: datetime
    valid_to: datetime | None
    is_active: bool


# ---------------------------------------------------------------------------
# Product Variant
# ---------------------------------------------------------------------------


class CreateProductVariantRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    sku: str = Field(..., min_length=1, max_length=100)
    unit: VariantUnit
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    status: VariantStatus = Field(default="ACTIVE")


class UpdateProductVariantRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    unit: VariantUnit | None = Field(default=None)
    quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=3
    )
    status: VariantStatus | None = Field(default=None)


class ProductVariantResponse(BaseSchema):
    id: int
    name: str
    sku: str
    unit: str
    quantity: Decimal
    status: str
    current_price: PriceResponse | None = None


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


class CreateProductRequest(BaseSchema):
    category_id: int
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=180)
    description: str | None = Field(default=None)
    status: ProductStatus = Field(default="DRAFT")


class UpdateProductRequest(BaseSchema):
    category_id: int | None = Field(default=None)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None)
    status: ProductStatus | None = Field(default=None)


class ProductSummaryResponse(BaseSchema):
    """Lightweight shape used in paginated product listings."""

    id: int
    name: str
    slug: str
    category_id: int
    status: str
    primary_image_url: str | None = None


class ProductResponse(BaseSchema):
    """Full product detail: category, images, and sellable variants with pricing."""

    id: int
    name: str
    slug: str
    description: str | None
    status: str
    category: CategoryResponse
    images: list[ProductImageResponse]
    variants: list[ProductVariantResponse]


class ProductListResponse(BaseSchema):
    items: list[ProductSummaryResponse]
    page: int
    page_size: int
    total: int
