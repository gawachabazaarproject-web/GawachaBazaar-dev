"""Catalog domain schemas: categories, products, variants, images, prices."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.base import BaseSchema

CategoryStatus = Literal["ACTIVE", "INACTIVE", "ARCHIVED"]
ProductStatus = Literal["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]
VariantStatus = Literal["ACTIVE", "INACTIVE", "ARCHIVED"]
VariantUnit = Literal["KG", "G", "L", "ML", "UNIT", "DOZEN", "BOX", "PACK"]

MAX_PAGE_SIZE = 100

# Category tile label colour (matches the app's textPrimary token); a tile
# background must keep WCAG AA contrast (4.5:1) against it.
_TILE_TEXT_RGB = (0x14, 0x33, 0x26)
_MIN_TILE_CONTRAST = 4.5


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def validate_tile_color(value: str | None) -> str | None:
    """`#RRGGBB` with enough contrast for the tile's dark label text."""
    if value is None or value == "":
        return None
    if len(value) != 7 or value[0] != "#":
        raise ValueError("Colour must look like #RRGGBB.")
    try:
        rgb = (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    except ValueError as exc:
        raise ValueError("Colour must look like #RRGGBB.") from exc
    lighter, darker = sorted((_luminance(rgb), _luminance(_TILE_TEXT_RGB)), reverse=True)
    if (lighter + 0.05) / (darker + 0.05) < _MIN_TILE_CONTRAST:
        raise ValueError("This colour is too dark - the category name would be hard to read.")
    return value.upper()


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CreateCategoryRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=180)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None)
    status: CategoryStatus = Field(default="ACTIVE")
    image_url: str | None = Field(default=None, max_length=2048)
    background_color: str | None = Field(default=None, max_length=7)
    badge_text: str | None = Field(default=None, max_length=24)
    show_on_homepage: bool = Field(default=True)
    show_in_catalog: bool = Field(default=True)
    is_featured: bool = Field(default=False)

    @field_validator("background_color")
    @classmethod
    def _check_color(cls, v: str | None) -> str | None:
        return validate_tile_color(v)

    @field_validator("badge_text")
    @classmethod
    def _clean_badge(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None


class UpdateCategoryRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None)
    parent_id: int | None = Field(default=None)
    status: CategoryStatus | None = Field(default=None)
    # Same "plain URL field" precedent as ProductImage.image_url - the
    # image upload/delete routes in api/v1/catalog.py construct this same
    # request internally with a Cloudinary-issued secure_url (or None to
    # clear it), reusing update_category's existing generic
    # `model_dump(exclude_unset=True)` + setattr loop rather than a
    # separate code path.
    image_url: str | None = Field(default=None, max_length=2048)
    background_color: str | None = Field(default=None, max_length=7)
    badge_text: str | None = Field(default=None, max_length=24)
    show_on_homepage: bool | None = Field(default=None)
    show_in_catalog: bool | None = Field(default=None)
    is_featured: bool | None = Field(default=None)

    @field_validator("background_color")
    @classmethod
    def _check_color(cls, v: str | None) -> str | None:
        return validate_tile_color(v)

    @field_validator("badge_text")
    @classmethod
    def _clean_badge(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None

    @model_validator(mode="after")
    def _flags_not_null(self) -> "UpdateCategoryRequest":
        for name in ("show_on_homepage", "show_in_catalog", "is_featured"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


class ReorderCategoriesRequest(BaseSchema):
    """Sibling categories (same parent) in the order they should display."""

    ids: list[int] = Field(..., min_length=1, max_length=500)


class CategoryResponse(BaseSchema):
    id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    parent_id: int | None
    status: str
    sort_order: int = 0
    # Storefront tile styling / visibility (defaults keep old rows unchanged).
    background_color: str | None = None
    badge_text: str | None = None
    show_on_homepage: bool = True
    show_in_catalog: bool = True
    is_featured: bool = False
    created_at: datetime
    # Active subcategories - filled in by the public list/detail reads;
    # 0 wherever a category is merely embedded (e.g. on a product).
    child_count: int = 0
    # Active products in this category plus its active subcategories.
    product_count: int = 0


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
    reserve_level: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    status: VariantStatus = Field(default="ACTIVE")


class UpdateProductVariantRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    unit: VariantUnit | None = Field(default=None)
    quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=3
    )
    # Stock to keep in reserve; send null to go back to the default.
    reserve_level: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    status: VariantStatus | None = Field(default=None)


class ProductVariantResponse(BaseSchema):
    id: int
    name: str
    sku: str
    unit: str
    quantity: Decimal
    status: str
    current_price: PriceResponse | None = None
    # False when no ACTIVE inventory lot has unreserved stock - the app greys
    # the item out and disables ordering. Defaults True where stock is not
    # computed (admin variant writes).
    in_stock: bool = True


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


class CreateProductRequest(BaseSchema):
    category_id: int
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=180)
    description: str | None = Field(default=None)
    status: ProductStatus = Field(default="DRAFT")
    # Also list the product under these categories (besides the main one).
    extra_category_ids: list[int] = Field(default_factory=list)


class UpdateProductRequest(BaseSchema):
    category_id: int | None = Field(default=None)
    # Replaces the whole list of additional categories when sent.
    extra_category_ids: list[int] | None = Field(default=None)
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
    starting_price: PriceResponse | None = None
    default_variant_id: int | None = None
    default_variant_unit: str | None = None
    default_variant_quantity: Decimal | None = None
    # Whether the default variant has stock available to order.
    in_stock: bool = True


class ProductResponse(BaseSchema):
    """Full product detail: category, images, and sellable variants with pricing."""

    id: int
    name: str
    slug: str
    description: str | None
    status: str
    category: CategoryResponse
    extra_categories: list[CategoryResponse] = Field(default_factory=list)
    images: list[ProductImageResponse]
    variants: list[ProductVariantResponse]


class ProductListResponse(BaseSchema):
    items: list[ProductSummaryResponse]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Quick create: a whole product (sizes, prices, photo, opening stock) in one
# transaction. Either everything is saved or nothing is.
# ---------------------------------------------------------------------------


class QuickSizeInput(BaseSchema):
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    unit: VariantUnit
    # Price of ONE whole pack of this size.
    price: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    # Left out = made from the web address and the size ("TOMATO-250-G").
    sku: str | None = Field(default=None, min_length=1, max_length=100)


class QuickStockInput(BaseSchema):
    """Opening stock: either an amount (kg / L / pieces) or a number of packs
    of the first size."""

    location_id: int = Field(..., gt=0)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    amount_unit: Literal["KG", "G", "L", "ML", "UNIT", "DOZEN"] | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    expiry_date: date | None = None

    @model_validator(mode="after")
    def _amount_or_packs(self) -> "QuickStockInput":
        if self.quantity is not None and (self.amount is not None or self.amount_unit is not None):
            raise ValueError("Send either quantity (packs) or amount with amount_unit, not both.")
        if self.quantity is None and (self.amount is None or self.amount_unit is None):
            raise ValueError("Send quantity (packs) or both amount and amount_unit.")
        return self


class QuickCreateProductRequest(BaseSchema):
    category_id: int
    name: str = Field(..., min_length=1, max_length=150)
    # Left out = made from the name and made unique.
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None)
    # DRAFT = saved but not shown to customers; ACTIVE = published.
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"
    extra_category_ids: list[int] = Field(default_factory=list)
    # An already uploaded photo (the upload endpoint returns one).
    image_url: str | None = Field(default=None, min_length=1, max_length=2048)
    sizes: list[QuickSizeInput] = Field(..., min_length=1, max_length=20)
    stock: QuickStockInput | None = None
