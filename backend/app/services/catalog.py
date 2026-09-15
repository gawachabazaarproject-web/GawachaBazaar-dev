"""Catalog domain service: categories, products, variants, images, prices.

Handles public (active-only) catalog browsing plus ADMIN-only catalog
management. Services return schema instances directly (matching the
convention already established by AuthService), so routes stay one-liners.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.category import Category
from app.models.inventory_lot import InventoryLot
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.user import User
from app.schemas.admin_catalog import (
    AdminCategoryDetailResponse,
    AdminCategoryListItemResponse,
    AdminCategoryListResponse,
    AdminProductDetailResponse,
    AdminProductListItemResponse,
    AdminProductListResponse,
    ProductActivityEntryResponse,
    ProductActivityResponse,
    VariantStockResponse,
)
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
from app.services.admin_audit import AdminAuditService
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
        self, category_id: int | None, page: int, page_size: int, *, q: str | None = None
    ) -> ProductListResponse:
        query = self.db.query(Product).filter(Product.status == _ACTIVE)
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)
        if q is not None:
            # Phase 20 addition: the smallest possible backend change to
            # support the mobile search screen - no full-text search
            # engine, just a case-insensitive name filter, consistent with
            # the "do not invent a complex search engine" instruction.
            query = query.filter(Product.name.ilike(f"%{q}%"))

        total = query.count()
        products = (
            query.order_by(Product.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Product.images), selectinload(Product.variants))
            .all()
        )

        # Phase 20 addition: browsing grids (Home/Category/Search) need a
        # real price and a real addable variant, not just name/image - the
        # smallest correct fix is resolving each product's lowest-id ACTIVE
        # variant once and exposing both its current price and its id, so
        # "Add to cart" works directly from a grid card without a second
        # round trip to the full product-detail endpoint.
        default_variant_by_product: dict[int, ProductVariant] = {}
        for p in products:
            active_variants = sorted(
                (v for v in p.variants if v.status == _ACTIVE), key=lambda v: v.id
            )
            if active_variants:
                default_variant_by_product[p.id] = active_variants[0]

        current_prices = self._get_current_prices_for_variants(
            [v.id for v in default_variant_by_product.values()]
        )

        items = []
        for p in products:
            primary = next((i for i in p.images if i.is_primary), None)
            default_variant = default_variant_by_product.get(p.id)
            price = current_prices.get(default_variant.id) if default_variant else None
            items.append(
                ProductSummaryResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    category_id=p.category_id,
                    status=p.status,
                    primary_image_url=primary.image_url if primary else None,
                    starting_price=PriceResponse.model_validate(price) if price else None,
                    default_variant_id=default_variant.id if default_variant else None,
                    default_variant_unit=default_variant.unit if default_variant else None,
                    default_variant_quantity=default_variant.quantity if default_variant else None,
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

    def create_category(
        self, data: CreateCategoryRequest, admin_user_id: int
    ) -> CategoryResponse:
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
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="category.create",
            resource_type="category",
            resource_id=category.id,
            new_state=category.status,
        )
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
        self, category_id: int, data: UpdateCategoryRequest, admin_user_id: int
    ) -> CategoryResponse:
        category = self.get_category_or_404(category_id)
        update_data = data.model_dump(exclude_unset=True)
        previous_status = category.status

        if "parent_id" in update_data and update_data["parent_id"] is not None:
            if update_data["parent_id"] == category_id:
                raise BusinessValidationError(
                    "A category cannot be its own parent."
                )
            self.get_category_or_404(update_data["parent_id"])

        for field, value in update_data.items():
            setattr(category, field, value)

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="category.update",
            resource_type="category",
            resource_id=category.id,
            previous_state=previous_status,
            new_state=category.status,
        )
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
    # Admin: Category list/detail (Admin Panel Phase 9) - unscoped by
    # status, unlike list_public_categories/get_public_category above.
    # ------------------------------------------------------------------

    def admin_list_categories(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        parent_id: int | None = None,
        q: str | None = None,
    ) -> AdminCategoryListResponse:
        parent = aliased(Category)
        query = self.db.query(Category, parent.name).outerjoin(parent, Category.parent_id == parent.id)

        if status:
            query = query.filter(Category.status == status)
        if parent_id is not None:
            query = query.filter(Category.parent_id == parent_id)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Category.name.ilike(like), Category.slug.ilike(like)))

        total = query.count()
        rows = (
            query.order_by(Category.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        if not rows:
            return AdminCategoryListResponse(items=[], page=page, page_size=page_size, total=total)

        category_ids = [c.id for c, _ in rows]
        product_counts = dict(
            self.db.query(Product.category_id, func.count(Product.id))
            .filter(Product.category_id.in_(category_ids))
            .group_by(Product.category_id)
            .all()
        )
        child_counts = dict(
            self.db.query(Category.parent_id, func.count(Category.id))
            .filter(Category.parent_id.in_(category_ids))
            .group_by(Category.parent_id)
            .all()
        )

        items = [
            AdminCategoryListItemResponse(
                id=c.id,
                name=c.name,
                slug=c.slug,
                description=c.description,
                parent_id=c.parent_id,
                parent_name=parent_name,
                status=c.status,
                product_count=product_counts.get(c.id, 0),
                child_count=child_counts.get(c.id, 0),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c, parent_name in rows
        ]
        return AdminCategoryListResponse(items=items, page=page, page_size=page_size, total=total)

    def admin_get_category_detail(self, category_id: int) -> AdminCategoryDetailResponse:
        category = self.get_category_or_404(category_id)
        parent_name = None
        if category.parent_id is not None:
            parent = self.db.query(Category).filter(Category.id == category.parent_id).first()
            parent_name = parent.name if parent else None

        children = (
            self.db.query(Category)
            .filter(Category.parent_id == category_id)
            .order_by(Category.name)
            .all()
        )
        product_count = (
            self.db.query(func.count(Product.id)).filter(Product.category_id == category_id).scalar() or 0
        )

        return AdminCategoryDetailResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            parent_id=category.parent_id,
            parent_name=parent_name,
            status=category.status,
            product_count=product_count,
            created_at=category.created_at,
            updated_at=category.updated_at,
            children=[CategoryResponse.model_validate(c) for c in children],
        )

    def admin_get_category_activity(self, category_id: int) -> ProductActivityResponse:
        self.get_category_or_404(category_id)
        rows = (
            self.db.query(AdminActionLog, User.name)
            .join(User, AdminActionLog.admin_user_id == User.id)
            .filter(AdminActionLog.resource_type == "category", AdminActionLog.resource_id == category_id)
            .order_by(AdminActionLog.created_at.desc(), AdminActionLog.id.desc())
            .limit(100)
            .all()
        )
        return ProductActivityResponse(
            items=[
                ProductActivityEntryResponse(
                    id=log.id,
                    action=log.action,
                    resource_type=log.resource_type,
                    resource_id=log.resource_id,
                    previous_state=log.previous_state,
                    new_state=log.new_state,
                    reason=log.reason,
                    admin_name=admin_name,
                    created_at=log.created_at,
                )
                for log, admin_name in rows
            ]
        )

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

    def create_product(
        self, data: CreateProductRequest, admin_user_id: int
    ) -> ProductResponse:
        self.get_category_or_404(data.category_id)

        product = Product(
            category_id=data.category_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            status=data.status,
        )
        self.db.add(product)
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.create",
            resource_type="product",
            resource_id=product.id,
            new_state=product.status,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A product with this slug already exists.") from exc
        self.db.refresh(product)

        full = self.get_product_or_404(product.id)
        return self._to_product_response(full, public_only_variants=False)

    def update_product(
        self, product_id: int, data: UpdateProductRequest, admin_user_id: int
    ) -> ProductResponse:
        product = self.get_product_or_404(product_id)
        update_data = data.model_dump(exclude_unset=True)
        previous_status = product.status

        if "category_id" in update_data:
            self.get_category_or_404(update_data["category_id"])

        for field, value in update_data.items():
            setattr(product, field, value)

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.update",
            resource_type="product",
            resource_id=product.id,
            previous_state=previous_status,
            new_state=product.status,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A product with this slug already exists.") from exc
        self.db.refresh(product)

        full = self.get_product_or_404(product.id)
        return self._to_product_response(full, public_only_variants=False)

    # ------------------------------------------------------------------
    # Admin: Product list/detail (Admin Panel Phase 6/7) - unscoped by
    # status, unlike the public browsing methods above. `get_product_or_404`
    # is already status-unfiltered (it's what create_product/update_product
    # use internally), so the detail read below simply reuses it rather
    # than duplicating the query.
    # ------------------------------------------------------------------

    def admin_list_products(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        category_id: int | None = None,
        q: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> AdminProductListResponse:
        query = self.db.query(Product).join(Category, Product.category_id == Category.id)

        if status:
            query = query.filter(Product.status == status)
        if category_id:
            query = query.filter(Product.category_id == category_id)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Product.name.ilike(like), Product.slug.ilike(like)))
        if created_from:
            query = query.filter(Product.created_at >= created_from)
        if created_to:
            query = query.filter(Product.created_at <= created_to)
        if updated_from:
            query = query.filter(Product.updated_at >= updated_from)
        if updated_to:
            query = query.filter(Product.updated_at <= updated_to)

        if price_min is not None or price_max is not None:
            # Price lives on Price rows via variant, not on Product itself -
            # filter by each candidate product's lowest current-active
            # variant price (the same "starting price" concept
            # ProductSummaryResponse already exposes publicly), reusing
            # get_current_prices_for_variants rather than re-deriving
            # "current price" logic here.
            candidate_ids = [pid for (pid,) in query.with_entities(Product.id).all()]
            variant_to_product: dict[int, int] = {}
            if candidate_ids:
                for v_id, p_id in (
                    self.db.query(ProductVariant.id, ProductVariant.product_id)
                    .filter(ProductVariant.product_id.in_(candidate_ids))
                    .all()
                ):
                    variant_to_product[v_id] = p_id
            current_prices = self._get_current_prices_for_variants(list(variant_to_product.keys()))
            min_price_by_product: dict[int, Decimal] = {}
            for v_id, price_row in current_prices.items():
                p_id = variant_to_product[v_id]
                if p_id not in min_price_by_product or price_row.price < min_price_by_product[p_id]:
                    min_price_by_product[p_id] = price_row.price
            matching_ids = [
                pid
                for pid, price in min_price_by_product.items()
                if (price_min is None or price >= price_min)
                and (price_max is None or price <= price_max)
            ]
            query = query.filter(Product.id.in_(matching_ids))

        total = query.count()
        products = (
            query.order_by(Product.updated_at.desc(), Product.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(
                selectinload(Product.images),
                selectinload(Product.variants),
                joinedload(Product.category),
            )
            .all()
        )

        if not products:
            return AdminProductListResponse(items=[], page=page, page_size=page_size, total=total)

        all_variant_ids = [v.id for p in products for v in p.variants]
        current_prices = self._get_current_prices_for_variants(all_variant_ids)
        active_variant_ids = [v.id for p in products for v in p.variants if v.status == _ACTIVE]
        stock_by_variant = self._get_available_stock_for_variants(active_variant_ids)

        items = []
        for p in products:
            primary = next((i for i in p.images if i.is_primary), None)
            active_variants = sorted(
                (v for v in p.variants if v.status == _ACTIVE), key=lambda v: v.id
            )
            default_variant = active_variants[0] if active_variants else None
            price_row = current_prices.get(default_variant.id) if default_variant else None
            total_stock = sum(
                (stock_by_variant.get(v.id, Decimal("0")) for v in active_variants),
                Decimal("0"),
            )
            items.append(
                AdminProductListItemResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    category_id=p.category_id,
                    category_name=p.category.name,
                    status=p.status,
                    primary_image_url=primary.image_url if primary else None,
                    price=price_row.price if price_row else None,
                    currency=price_row.currency if price_row else None,
                    variant_count=len(p.variants),
                    total_available_stock=total_stock,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return AdminProductListResponse(items=items, page=page, page_size=page_size, total=total)

    def admin_get_product_detail(self, product_id: int) -> AdminProductDetailResponse:
        product = self.get_product_or_404(product_id)
        base = self._to_product_response(product, public_only_variants=False)

        variant_ids = [v.id for v in product.variants]
        stock_by_variant = self._get_available_stock_for_variants(variant_ids)
        variant_stock = [
            VariantStockResponse(
                variant_id=v.id,
                variant_name=v.name,
                sku=v.sku,
                status=v.status,
                available_quantity=stock_by_variant.get(v.id, Decimal("0")),
            )
            for v in product.variants
        ]

        return AdminProductDetailResponse(
            id=base.id,
            name=base.name,
            slug=base.slug,
            description=base.description,
            status=base.status,
            created_at=product.created_at,
            updated_at=product.updated_at,
            category=base.category,
            images=base.images,
            variants=base.variants,
            variant_stock=variant_stock,
        )

    def admin_get_product_activity(self, product_id: int) -> ProductActivityResponse:
        """Real activity feed, read straight from `admin_action_logs` - no
        synthesized history. Covers the product's own log rows plus its
        variants' and their prices' rows (a price's `resource_id` is the
        Price row's id; each Price is looked up back to a variant of this
        product to decide inclusion).
        """
        product = self.get_product_or_404(product_id)
        variant_ids = [v.id for v in product.variants]
        price_ids = (
            [pid for (pid,) in self.db.query(Price.id).filter(Price.variant_id.in_(variant_ids)).all()]
            if variant_ids
            else []
        )

        conditions = [
            (AdminActionLog.resource_type == "product") & (AdminActionLog.resource_id == product_id)
        ]
        if variant_ids:
            conditions.append(
                (AdminActionLog.resource_type == "product_variant")
                & (AdminActionLog.resource_id.in_(variant_ids))
            )
        if price_ids:
            conditions.append(
                (AdminActionLog.resource_type == "price") & (AdminActionLog.resource_id.in_(price_ids))
            )

        rows = (
            self.db.query(AdminActionLog, User.name)
            .join(User, AdminActionLog.admin_user_id == User.id)
            .filter(or_(*conditions))
            .order_by(AdminActionLog.created_at.desc(), AdminActionLog.id.desc())
            .limit(100)
            .all()
        )
        return ProductActivityResponse(
            items=[
                ProductActivityEntryResponse(
                    id=log.id,
                    action=log.action,
                    resource_type=log.resource_type,
                    resource_id=log.resource_id,
                    previous_state=log.previous_state,
                    new_state=log.new_state,
                    reason=log.reason,
                    admin_name=admin_name,
                    created_at=log.created_at,
                )
                for log, admin_name in rows
            ]
        )

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
        self, product_id: int, data: CreateProductVariantRequest, admin_user_id: int
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
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.variant.create",
            resource_type="product_variant",
            resource_id=variant.id,
            new_state=variant.status,
            reason=f"product_id={product_id}",
        )
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
        self, variant_id: int, data: UpdateProductVariantRequest, admin_user_id: int
    ) -> ProductVariantResponse:
        variant = self.get_variant_or_404(variant_id)
        update_data = data.model_dump(exclude_unset=True)
        previous_status = variant.status
        for field, value in update_data.items():
            setattr(variant, field, value)

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.variant.update",
            resource_type="product_variant",
            resource_id=variant.id,
            previous_state=previous_status,
            new_state=variant.status,
        )
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
        self, product_id: int, data: CreateProductImageRequest, admin_user_id: int
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
        self.db.flush()
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.image.create",
            resource_type="product_image",
            resource_id=image.id,
            reason=f"product_id={product_id}",
        )
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
        self, image_id: int, data: UpdateProductImageRequest, admin_user_id: int
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

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.image.update",
            resource_type="product_image",
            resource_id=image.id,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Could not set primary image due to a conflicting update."
            ) from exc
        self.db.refresh(image)
        return ProductImageResponse.model_validate(image)

    def delete_image(self, image_id: int, admin_user_id: int) -> None:
        image = self.get_image_or_404(image_id)
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.image.delete",
            resource_type="product_image",
            resource_id=image.id,
            reason=f"product_id={image.product_id}",
        )
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
        self, variant_id: int, data: CreatePriceRequest, admin_user_id: int
    ) -> PriceResponse:
        variant = self.get_variant_or_404(variant_id)
        previous = self._get_current_prices_for_variants([variant_id]).get(variant_id)

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
        self.db.flush()
        # Price is business-critical: the audit record captures both the
        # previous authoritative price and the new one, not just "a price
        # changed" - this is the one place a bare status string isn't
        # enough context for what actually happened.
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.price.create",
            resource_type="price",
            resource_id=price.id,
            previous_state=f"{previous.price} {previous.currency}" if previous else None,
            new_state=f"{price.price} {price.currency}",
            reason=f"variant_id={variant_id} sku={variant.sku}",
        )
        self.db.commit()
        self.db.refresh(price)
        return PriceResponse.model_validate(price)

    def update_price(
        self, price_id: int, data: UpdatePriceRequest, admin_user_id: int
    ) -> PriceResponse:
        price = self.get_price_or_404(price_id)
        update_data = data.model_dump(exclude_unset=True)

        if update_data.get("valid_to") is not None:
            if update_data["valid_to"] < price.valid_from:
                raise BusinessValidationError(
                    "valid_to cannot be before valid_from."
                )

        for field, value in update_data.items():
            setattr(price, field, value)

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.price.update",
            resource_type="price",
            resource_id=price.id,
            reason=f"variant_id={price.variant_id}",
        )
        self.db.commit()
        self.db.refresh(price)
        return PriceResponse.model_validate(price)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_available_stock_for_variants(
        self, variant_ids: list[int]
    ) -> dict[int, Decimal]:
        """Sums `quantity - reserved_quantity` across ACTIVE inventory lots
        per variant - the exact same arithmetic InventoryLot's own docstring
        defines as "available" (see app/models/inventory_lot.py). Read-only:
        Products never mutates inventory, only displays it (see the
        admin-panel Products spec's explicit "don't duplicate inventory
        management inside Products" rule) - adjustments happen through the
        Inventory module.
        """
        if not variant_ids:
            return {}
        rows = (
            self.db.query(
                InventoryLot.variant_id,
                func.sum(InventoryLot.quantity - InventoryLot.reserved_quantity),
            )
            .filter(InventoryLot.variant_id.in_(variant_ids), InventoryLot.status == "ACTIVE")
            .group_by(InventoryLot.variant_id)
            .all()
        )
        return {variant_id: (total or Decimal("0")) for variant_id, total in rows}

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
