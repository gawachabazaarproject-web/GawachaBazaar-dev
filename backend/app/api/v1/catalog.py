"""Catalog domain routes: public browsing (no auth) and ADMIN-only management."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.roles import ADMIN
from app.dependencies.auth import require_roles
from app.dependencies.database import get_db
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

router = APIRouter()

_admin_only = [Depends(require_roles(ADMIN))]


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
    summary="List active products",
)
def list_products(
    category_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    return CatalogService(db).list_public_products(category_id, page, page_size)


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Get an active product with images, active variants, and current prices",
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    return CatalogService(db).get_public_product(product_id)


# ---------------------------------------------------------------------------
# Admin catalog management - ADMIN role required
# ---------------------------------------------------------------------------


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
    dependencies=_admin_only,
)
def create_category(
    payload: CreateCategoryRequest, db: Session = Depends(get_db)
) -> CategoryResponse:
    return CatalogService(db).create_category(payload)


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category (including lifecycle status)",
    dependencies=_admin_only,
)
def update_category(
    category_id: int, payload: UpdateCategoryRequest, db: Session = Depends(get_db)
) -> CategoryResponse:
    return CatalogService(db).update_category(category_id, payload)


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
    dependencies=_admin_only,
)
def create_product(
    payload: CreateProductRequest, db: Session = Depends(get_db)
) -> ProductResponse:
    return CatalogService(db).create_product(payload)


@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Update a product (including lifecycle status)",
    dependencies=_admin_only,
)
def update_product(
    product_id: int, payload: UpdateProductRequest, db: Session = Depends(get_db)
) -> ProductResponse:
    return CatalogService(db).update_product(product_id, payload)


@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product variant",
    dependencies=_admin_only,
)
def create_variant(
    product_id: int,
    payload: CreateProductVariantRequest,
    db: Session = Depends(get_db),
) -> ProductVariantResponse:
    return CatalogService(db).create_variant(product_id, payload)


@router.patch(
    "/variants/{variant_id}",
    response_model=ProductVariantResponse,
    summary="Update a product variant (including lifecycle status)",
    dependencies=_admin_only,
)
def update_variant(
    variant_id: int,
    payload: UpdateProductVariantRequest,
    db: Session = Depends(get_db),
) -> ProductVariantResponse:
    return CatalogService(db).update_variant(variant_id, payload)


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product image",
    dependencies=_admin_only,
)
def create_image(
    product_id: int,
    payload: CreateProductImageRequest,
    db: Session = Depends(get_db),
) -> ProductImageResponse:
    return CatalogService(db).create_image(product_id, payload)


@router.patch(
    "/images/{image_id}",
    response_model=ProductImageResponse,
    summary="Update a product image, including primary image handoff",
    dependencies=_admin_only,
)
def update_image(
    image_id: int, payload: UpdateProductImageRequest, db: Session = Depends(get_db)
) -> ProductImageResponse:
    return CatalogService(db).update_image(image_id, payload)


@router.delete(
    "/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product image",
    dependencies=_admin_only,
)
def delete_image(image_id: int, db: Session = Depends(get_db)) -> None:
    CatalogService(db).delete_image(image_id)


@router.post(
    "/variants/{variant_id}/prices",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new price for a variant (preserves price history)",
    dependencies=_admin_only,
)
def create_price(
    variant_id: int, payload: CreatePriceRequest, db: Session = Depends(get_db)
) -> PriceResponse:
    return CatalogService(db).create_price(variant_id, payload)


@router.patch(
    "/prices/{price_id}",
    response_model=PriceResponse,
    summary="Activate/deactivate or end a price's validity window",
    dependencies=_admin_only,
)
def update_price(
    price_id: int, payload: UpdatePriceRequest, db: Session = Depends(get_db)
) -> PriceResponse:
    return CatalogService(db).update_price(price_id, payload)
