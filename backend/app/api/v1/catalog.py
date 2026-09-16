"""Catalog domain routes: public browsing (no auth) and ADMIN-only management."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.admin_catalog import (
    AdminCategoryDetailResponse,
    AdminCategoryListResponse,
    AdminProductDetailResponse,
    AdminProductListResponse,
    ProductActivityResponse,
)
from app.schemas.admin_catalog import MAX_PAGE_SIZE as ADMIN_MAX_PAGE_SIZE
from app.schemas.catalog import (
    MAX_PAGE_SIZE,
    CategoryDetailResponse,
    CategoryListResponse,
    CategoryResponse,
    CreateCategoryRequest,
    CreatePriceRequest,
    CreateProductImageRequest,
    CreateProductRequest,
    CreateProductVariantRequest,
    PriceResponse,
    ProductImageResponse,
    ProductListResponse,
    ProductResponse,
    ProductVariantResponse,
    UpdateCategoryRequest,
    UpdatePriceRequest,
    UpdateProductImageRequest,
    UpdateProductRequest,
    UpdateProductVariantRequest,
)
from app.services.catalog import CatalogService
from app.services.image_upload import upload_image

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin catalog reads - MUST be registered before the public `/products`
# routes below: `GET /products/admin` and `GET /products/{product_id}` are
# the same single-segment path shape, and FastAPI/Starlette match routes in
# registration order (see the identical fix already applied to
# app/api/v1/router.py for orders_staff_router vs orders_router). Listing
# these routes first means "admin" is tried as a literal before the
# customer catch-all ever gets a chance to swallow it as a product id.
# ---------------------------------------------------------------------------


@router.get(
    "/products/admin",
    response_model=AdminProductListResponse,
    summary="List/search/filter every product regardless of status (admin panel)",
)
def admin_list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=ADMIN_MAX_PAGE_SIZE),
    status_: str | None = Query(default=None, alias="status"),
    category_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=150, description="Product name or slug"),
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    updated_from: datetime | None = Query(default=None),
    updated_to: datetime | None = Query(default=None),
    current_user: User = Depends(require_permission("products.read")),
    db: Session = Depends(get_db),
) -> AdminProductListResponse:
    return CatalogService(db).admin_list_products(
        page,
        page_size,
        status_,
        category_id,
        q,
        price_min,
        price_max,
        created_from,
        created_to,
        updated_from,
        updated_to,
    )


@router.get(
    "/products/admin/{product_id}",
    response_model=AdminProductDetailResponse,
    summary="Get the complete admin detail for any product regardless of status",
)
def admin_get_product(
    product_id: int,
    current_user: User = Depends(require_permission("products.read")),
    db: Session = Depends(get_db),
) -> AdminProductDetailResponse:
    return CatalogService(db).admin_get_product_detail(product_id)


@router.get(
    "/products/admin/{product_id}/activity",
    response_model=ProductActivityResponse,
    summary="Real audit-log activity for this product and its variants/prices",
)
def admin_get_product_activity(
    product_id: int,
    current_user: User = Depends(require_permission("products.read")),
    db: Session = Depends(get_db),
) -> ProductActivityResponse:
    return CatalogService(db).admin_get_product_activity(product_id)


# `/categories/admin` vs `/categories/{category_id}` has the exact same
# registration-order hazard as `/products/admin` above - same fix.


@router.get(
    "/categories/admin",
    response_model=AdminCategoryListResponse,
    summary="List/search/filter every category regardless of status (admin panel)",
)
def admin_list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=ADMIN_MAX_PAGE_SIZE),
    status_: str | None = Query(default=None, alias="status"),
    parent_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=150, description="Category name or slug"),
    current_user: User = Depends(require_permission("categories.read")),
    db: Session = Depends(get_db),
) -> AdminCategoryListResponse:
    return CatalogService(db).admin_list_categories(page, page_size, status_, parent_id, q)


@router.get(
    "/categories/admin/{category_id}",
    response_model=AdminCategoryDetailResponse,
    summary="Get the complete admin detail for any category regardless of status",
)
def admin_get_category(
    category_id: int,
    current_user: User = Depends(require_permission("categories.read")),
    db: Session = Depends(get_db),
) -> AdminCategoryDetailResponse:
    return CatalogService(db).admin_get_category_detail(category_id)


@router.get(
    "/categories/admin/{category_id}/activity",
    response_model=ProductActivityResponse,
    summary="Real audit-log activity for this category",
)
def admin_get_category_activity(
    category_id: int,
    current_user: User = Depends(require_permission("categories.read")),
    db: Session = Depends(get_db),
) -> ProductActivityResponse:
    return CatalogService(db).admin_get_category_activity(category_id)


# ---------------------------------------------------------------------------
# Public catalog - no authentication required
# ---------------------------------------------------------------------------


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    summary="List active categories",
)
def list_categories(
    parent_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> CategoryListResponse:
    return CatalogService(db).list_public_categories(parent_id, page, page_size)


@router.get(
    "/categories/{category_id}",
    response_model=CategoryDetailResponse,
    summary="Get an active category (with direct active children)",
)
def get_category(
    category_id: int, db: Session = Depends(get_db)
) -> CategoryDetailResponse:
    return CatalogService(db).get_public_category(category_id)


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="List active products, optionally filtered by category and/or name search",
)
def list_products(
    category_id: int | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100, description="Case-insensitive name search"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    return CatalogService(db).list_public_products(category_id, page, page_size, q=q)


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Get an active product with images, active variants, and current prices",
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    return CatalogService(db).get_public_product(product_id)


# ---------------------------------------------------------------------------
# Admin catalog management - granular products.*/categories.* permissions
# (see app/core/permissions.py) - currently only ADMIN holds any of them,
# same effective access as the `require_roles(ADMIN)` this replaces.
# ---------------------------------------------------------------------------


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
def create_category(
    payload: CreateCategoryRequest,
    current_user: User = Depends(require_permission("categories.create")),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    return CatalogService(db).create_category(payload, current_user.id)


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category (including lifecycle status)",
)
def update_category(
    category_id: int,
    payload: UpdateCategoryRequest,
    current_user: User = Depends(require_permission("categories.update")),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    return CatalogService(db).update_category(category_id, payload, current_user.id)


@router.post(
    "/categories/{category_id}/image",
    response_model=CategoryResponse,
    summary="Upload (or replace) a category's image via Cloudinary",
)
def upload_category_image(
    category_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("categories.update")),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    service = CatalogService(db)
    service.get_category_or_404(category_id)
    result = upload_image(file, folder=f"gawachabazaar/categories/{category_id}")
    return service.update_category(
        category_id, UpdateCategoryRequest(image_url=result["secure_url"]), current_user.id
    )


@router.delete(
    "/categories/{category_id}/image",
    response_model=CategoryResponse,
    summary="Remove a category's image",
)
def delete_category_image(
    category_id: int,
    current_user: User = Depends(require_permission("categories.update")),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    return CatalogService(db).update_category(
        category_id, UpdateCategoryRequest(image_url=None), current_user.id
    )


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def create_product(
    payload: CreateProductRequest,
    current_user: User = Depends(require_permission("products.create")),
    db: Session = Depends(get_db),
) -> ProductResponse:
    return CatalogService(db).create_product(payload, current_user.id)


@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Update a product (including lifecycle status)",
)
def update_product(
    product_id: int,
    payload: UpdateProductRequest,
    current_user: User = Depends(require_permission("products.update")),
    db: Session = Depends(get_db),
) -> ProductResponse:
    return CatalogService(db).update_product(product_id, payload, current_user.id)


@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product variant",
)
def create_variant(
    product_id: int,
    payload: CreateProductVariantRequest,
    current_user: User = Depends(require_permission("products.update")),
    db: Session = Depends(get_db),
) -> ProductVariantResponse:
    return CatalogService(db).create_variant(product_id, payload, current_user.id)


@router.patch(
    "/variants/{variant_id}",
    response_model=ProductVariantResponse,
    summary="Update a product variant (including lifecycle status)",
)
def update_variant(
    variant_id: int,
    payload: UpdateProductVariantRequest,
    current_user: User = Depends(require_permission("products.update")),
    db: Session = Depends(get_db),
) -> ProductVariantResponse:
    return CatalogService(db).update_variant(variant_id, payload, current_user.id)


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product image",
)
def create_image(
    product_id: int,
    payload: CreateProductImageRequest,
    current_user: User = Depends(require_permission("products.manage_media")),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    return CatalogService(db).create_image(product_id, payload, current_user.id)


@router.patch(
    "/images/{image_id}",
    response_model=ProductImageResponse,
    summary="Update a product image, including primary image handoff",
)
def update_image(
    image_id: int,
    payload: UpdateProductImageRequest,
    current_user: User = Depends(require_permission("products.manage_media")),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    return CatalogService(db).update_image(image_id, payload, current_user.id)


@router.delete(
    "/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product image",
)
def delete_image(
    image_id: int,
    current_user: User = Depends(require_permission("products.manage_media")),
    db: Session = Depends(get_db),
) -> None:
    CatalogService(db).delete_image(image_id, current_user.id)


@router.post(
    "/products/{product_id}/images/upload",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a product image via Cloudinary and attach it to the product",
)
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None),
    is_primary: bool = Form(default=False),
    current_user: User = Depends(require_permission("products.manage_media")),
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    service = CatalogService(db)
    service.get_product_or_404(product_id)
    result = upload_image(file, folder=f"gawachabazaar/products/{product_id}")
    return service.create_image(
        product_id,
        CreateProductImageRequest(
            image_url=result["secure_url"], alt_text=alt_text, is_primary=is_primary
        ),
        current_user.id,
    )


@router.post(
    "/variants/{variant_id}/prices",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new price for a variant (preserves price history)",
)
def create_price(
    variant_id: int,
    payload: CreatePriceRequest,
    current_user: User = Depends(require_permission("products.manage_pricing")),
    db: Session = Depends(get_db),
) -> PriceResponse:
    return CatalogService(db).create_price(variant_id, payload, current_user.id)


@router.patch(
    "/prices/{price_id}",
    response_model=PriceResponse,
    summary="Activate/deactivate or end a price's validity window",
)
def update_price(
    price_id: int,
    payload: UpdatePriceRequest,
    current_user: User = Depends(require_permission("products.manage_pricing")),
    db: Session = Depends(get_db),
) -> PriceResponse:
    return CatalogService(db).update_price(price_id, payload, current_user.id)
