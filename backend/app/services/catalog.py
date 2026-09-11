"""Catalog domain service: categories, products, variants, images, prices.

Handles public (active-only) catalog browsing plus ADMIN-only catalog
management. Services return schema instances directly (matching the
convention already established by AuthService), so routes stay one-liners.
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.category import Category
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.schemas.catalog import (
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
    ProductSummaryResponse,
    ProductVariantResponse,
    UpdateCategoryRequest,
    UpdatePriceRequest,
    UpdateProductImageRequest,
    UpdateProductRequest,
    UpdateProductVariantRequest,
)
from app.services.pricing import get_current_prices_for_variants

_ACTIVE = "ACTIVE"


class CatalogService:
    """Category/Product/Variant/Image/Price business logic and queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public catalog (active-only)
    # ------------------------------------------------------------------

    def list_public_categories(
        self, parent_id: int | None, page: int, page_size: int
    ) -> CategoryListResponse:
        query = self.db.query(Category).filter(Category.status == _ACTIVE)
        if parent_id is not None:
            query = query.filter(Category.parent_id == parent_id)

        total = query.count()
        items = (
            query.order_by(Category.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return CategoryListResponse(
            items=[CategoryResponse.model_validate(c) for c in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_public_category(self, category_id: int) -> CategoryDetailResponse:
        category = (
            self.db.query(Category)
            .filter(Category.id == category_id, Category.status == _ACTIVE)
            .first()
        )
        if not category:
            raise NotFoundError("Category not found.")

        children = (
            self.db.query(Category)
            .filter(Category.parent_id == category_id, Category.status == _ACTIVE)
            .order_by(Category.name)
            .all()
        )
        return CategoryDetailResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            parent_id=category.parent_id,
            status=category.status,
            created_at=category.created_at,
            children=[CategoryResponse.model_validate(c) for c in children],
        )

    def list_public_products(
        self, category_id: int | None, page: int, page_size: int
    ) -> ProductListResponse:
        query = self.db.query(Product).filter(Product.status == _ACTIVE)
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)

        total = query.count()
        products = (
            query.order_by(Product.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Product.images))
            .all()
        )

        items = []
        for p in products:
            primary = next((i for i in p.images if i.is_primary), None)
            items.append(
                ProductSummaryResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    category_id=p.category_id,
                    status=p.status,
                    primary_image_url=primary.image_url if primary else None,
                )
            )
        return ProductListResponse(
            items=items, page=page, page_size=page_size, total=total
        )

    def get_public_product(self, product_id: int) -> ProductResponse:
        product = (
            self.db.query(Product)
            .options(
                joinedload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants),
            )
            .filter(Product.id == product_id, Product.status == _ACTIVE)
            .first()
        )
        if not product:
            raise NotFoundError("Product not found.")
        return self._to_product_response(product, public_only_variants=True)

    # ------------------------------------------------------------------
    # Admin: Category management
    # ------------------------------------------------------------------

    def get_category_or_404(self, category_id: int) -> Category:
        category = self.db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise NotFoundError("Category not found.")
        return category

    def create_category(self, data: CreateCategoryRequest) -> CategoryResponse:
        if data.parent_id is not None:
            self.get_category_or_404(data.parent_id)

        category = Category(
            parent_id=data.parent_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            status=data.status,
        )
        self.db.add(category)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A category with this slug already exists."
            ) from exc
        self.db.refresh(category)
        return CategoryResponse.model_validate(category)

    def update_category(
        self, category_id: int, data: UpdateCategoryRequest
    ) -> CategoryResponse:
        category = self.get_category_or_404(category_id)
        update_data = data.model_dump(exclude_unset=True)

        if "parent_id" in update_data and update_data["parent_id"] is not None:
            if update_data["parent_id"] == category_id:
                raise BusinessValidationError(
                    "A category cannot be its own parent."
                )
            self.get_category_or_404(update_data["parent_id"])

        for field, value in update_data.items():
            setattr(category, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A category with this slug already exists."
            ) from exc
        self.db.refresh(category)
        return CategoryResponse.model_validate(category)

    # ------------------------------------------------------------------
    # Admin: Product management
    # ------------------------------------------------------------------

    def get_product_or_404(self, product_id: int) -> Product:
        product = (
            self.db.query(Product)
            .options(
                joinedload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants),
            )
            .filter(Product.id == product_id)
            .first()
        )
        if not product:
            raise NotFoundError("Product not found.")
        return product

    def create_product(self, data: CreateProductRequest) -> ProductResponse:
        self.get_category_or_404(data.category_id)

        product = Product(
            category_id=data.category_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            status=data.status,
        )
        self.db.add(product)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A product with this slug already exists.") from exc
        self.db.refresh(product)

        full = self.get_product_or_404(product.id)
        return self._to_product_response(full, public_only_variants=False)

    def update_product(
        self, product_id: int, data: UpdateProductRequest
    ) -> ProductResponse:
        product = self.get_product_or_404(product_id)
        update_data = data.model_dump(exclude_unset=True)

        if "category_id" in update_data:
            self.get_category_or_404(update_data["category_id"])

        for field, value in update_data.items():
            setattr(product, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A product with this slug already exists.") from exc
        self.db.refresh(product)

        full = self.get_product_or_404(product.id)
        return self._to_product_response(full, public_only_variants=False)

    # ------------------------------------------------------------------
    # Admin: Variant management
    # ------------------------------------------------------------------

    def get_variant_or_404(self, variant_id: int) -> ProductVariant:
        variant = (
            self.db.query(ProductVariant)
            .filter(ProductVariant.id == variant_id)
            .first()
        )
        if not variant:
            raise NotFoundError("Product variant not found.")
        return variant

    def create_variant(
        self, product_id: int, data: CreateProductVariantRequest
    ) -> ProductVariantResponse:
        self.get_product_or_404(product_id)

        variant = ProductVariant(
            product_id=product_id,
            name=data.name,
            sku=data.sku,
            unit=data.unit,
            quantity=data.quantity,
            status=data.status,
        )
        self.db.add(variant)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A product variant with this SKU already exists."
            ) from exc
        self.db.refresh(variant)
        return self._to_variant_response(variant)

    def update_variant(
        self, variant_id: int, data: UpdateProductVariantRequest
    ) -> ProductVariantResponse:
        variant = self.get_variant_or_404(variant_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(variant, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A product variant with this SKU already exists."
            ) from exc
        self.db.refresh(variant)
        return self._to_variant_response(variant)

    # ------------------------------------------------------------------
    # Admin: Image management
    # ------------------------------------------------------------------

    def get_image_or_404(self, image_id: int) -> ProductImage:
        image = (
            self.db.query(ProductImage).filter(ProductImage.id == image_id).first()
        )
        if not image:
            raise NotFoundError("Product image not found.")
        return image

    def create_image(
        self, product_id: int, data: CreateProductImageRequest
    ) -> ProductImageResponse:
        self.get_product_or_404(product_id)

        # Unset any existing primary image before inserting, in the same
        # transaction as the insert, so the partial unique index on
        # (product_id) WHERE is_primary is never violated and the two
        # writes commit or roll back together.
        if data.is_primary:
            self.db.query(ProductImage).filter(
                ProductImage.product_id == product_id,
                ProductImage.is_primary.is_(True),
            ).update({"is_primary": False})

        image = ProductImage(
            product_id=product_id,
            image_url=data.image_url,
            alt_text=data.alt_text,
            is_primary=data.is_primary,
            sort_order=data.sort_order,
        )
        self.db.add(image)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not set primary image due to a conflicting update."
            ) from exc
        self.db.refresh(image)
        return ProductImageResponse.model_validate(image)

    def update_image(
        self, image_id: int, data: UpdateProductImageRequest
    ) -> ProductImageResponse:
        image = self.get_image_or_404(image_id)
        update_data = data.model_dump(exclude_unset=True)

        if update_data.get("is_primary") is True:
            self.db.query(ProductImage).filter(
                ProductImage.product_id == image.product_id,
                ProductImage.is_primary.is_(True),
                ProductImage.id != image.id,
            ).update({"is_primary": False})

        for field, value in update_data.items():
            setattr(image, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not set primary image due to a conflicting update."
            ) from exc
        self.db.refresh(image)
        return ProductImageResponse.model_validate(image)

    def delete_image(self, image_id: int) -> None:
        image = self.get_image_or_404(image_id)
        self.db.delete(image)
        self.db.commit()

    # ------------------------------------------------------------------
    # Admin: Price management
    # ------------------------------------------------------------------

    def get_price_or_404(self, price_id: int) -> Price:
        price = self.db.query(Price).filter(Price.id == price_id).first()
        if not price:
            raise NotFoundError("Price not found.")
        return price

    def create_price(
        self, variant_id: int, data: CreatePriceRequest
    ) -> PriceResponse:
        self.get_variant_or_404(variant_id)

        valid_from = data.valid_from or datetime.now(UTC)
        if data.valid_to is not None and data.valid_to < valid_from:
            raise BusinessValidationError("valid_to cannot be before valid_from.")

        price = Price(
            variant_id=variant_id,
            price=data.price,
            currency=data.currency,
            valid_from=valid_from,
            valid_to=data.valid_to,
            is_active=data.is_active,
        )
        self.db.add(price)
        self.db.commit()
        self.db.refresh(price)
        return PriceResponse.model_validate(price)

    def update_price(self, price_id: int, data: UpdatePriceRequest) -> PriceResponse:
        price = self.get_price_or_404(price_id)
        update_data = data.model_dump(exclude_unset=True)

        if update_data.get("valid_to") is not None:
            if update_data["valid_to"] < price.valid_from:
                raise BusinessValidationError(
                    "valid_to cannot be before valid_from."
                )

        for field, value in update_data.items():
            setattr(price, field, value)

        self.db.commit()
        self.db.refresh(price)
        return PriceResponse.model_validate(price)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_current_prices_for_variants(
        self, variant_ids: list[int]
    ) -> dict[int, Price]:
        """Resolve the single current price per variant.

        Extracted to app.services.pricing in Phase 13 so Cart/Order services
        can reuse the exact same rule instead of duplicating it. This method
        stays as a thin wrapper so existing call sites within this file are
        unaffected.
        """
        return get_current_prices_for_variants(self.db, variant_ids)

    def _to_variant_response(
        self, variant: ProductVariant, current_price: Price | None = None
    ) -> ProductVariantResponse:
        if current_price is None:
            current_price = self._get_current_prices_for_variants([variant.id]).get(
                variant.id
            )
        return ProductVariantResponse(
            id=variant.id,
            name=variant.name,
            sku=variant.sku,
            unit=variant.unit,
            quantity=variant.quantity,
            status=variant.status,
            current_price=(
                PriceResponse.model_validate(current_price)
                if current_price
                else None
            ),
        )

    def _to_product_response(
        self, product: Product, *, public_only_variants: bool
    ) -> ProductResponse:
        variants = (
            [v for v in product.variants if v.status == _ACTIVE]
            if public_only_variants
            else list(product.variants)
        )
        prices_by_variant = self._get_current_prices_for_variants(
            [v.id for v in variants]
        )
        variant_responses = [
            self._to_variant_response(v, prices_by_variant.get(v.id))
            for v in variants
        ]
        images = sorted(product.images, key=lambda i: (not i.is_primary, i.sort_order))

        return ProductResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            description=product.description,
            status=product.status,
            category=CategoryResponse.model_validate(product.category),
            images=[ProductImageResponse.model_validate(i) for i in images],
            variants=variant_responses,
        )
