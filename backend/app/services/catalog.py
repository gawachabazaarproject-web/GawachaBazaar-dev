"""Catalog domain service: categories, products, variants, images, prices.

Handles public (active-only) catalog browsing plus ADMIN-only catalog
management. Services return schema instances directly (matching the
convention already established by AuthService), so routes stay one-liners.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select, union
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

from app.exceptions.base import BusinessValidationError, ConflictError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.batch import Batch
from app.models.bulk_order_request_item import BulkOrderRequestItem
from app.models.cart_item import CartItem
from app.models.category import Category
from app.models.inventory_lot import InventoryLot
from app.models.inventory_reservation_item import InventoryReservationItem
from app.models.order_item import OrderItem
from app.models.packaging_input import PackagingInput
from app.models.packaging_output import PackagingOutput
from app.models.price import Price
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.quality_check import QualityCheck
from app.models.quote_item import QuoteItem
from app.models.stock_movement import StockMovement
from app.models.supplier_product import SupplierProduct
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
from app.services.stock_levels import effective_reserve, stock_level
from app.services.stock_pool import available_packs_by_variant, variant_size

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
            # Subcategories only show while their parent is itself active.
            self._require_active_category(parent_id)
            query = query.filter(Category.parent_id == parent_id)
        else:
            # The storefront's shelf is the top level; subcategories are
            # reached through their parent.
            query = query.filter(Category.parent_id.is_(None))

        total = query.count()
        items = (
            query.order_by(Category.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        child_counts = dict(
            self.db.query(Category.parent_id, func.count(Category.id))
            .filter(
                Category.parent_id.in_([c.id for c in items]),
                Category.status == _ACTIVE,
            )
            .group_by(Category.parent_id)
            .all()
        )
        # Product totals roll up: a shelf counts its subcategories' products.
        shelf = func.coalesce(Category.parent_id, Category.id)
        placements = self._placements().subquery()
        product_counts = dict(
            self.db.query(shelf, func.count(func.distinct(Product.id)))
            .select_from(placements)
            .join(Category, Category.id == placements.c.category_id)
            .join(Product, Product.id == placements.c.product_id)
            .filter(Product.status == _ACTIVE, Category.status == _ACTIVE, shelf.in_([c.id for c in items]))
            .group_by(shelf)
            .all()
        )
        responses = []
        for c in items:
            response = CategoryResponse.model_validate(c)
            response.child_count = child_counts.get(c.id, 0)
            response.product_count = product_counts.get(c.id, 0)
            responses.append(response)
        return CategoryListResponse(
            items=responses,
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
        if category.parent_id is not None:
            self._require_active_category(category.parent_id)

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
            image_url=category.image_url,
            parent_id=category.parent_id,
            status=category.status,
            created_at=category.created_at,
            child_count=len(children),
            children=[CategoryResponse.model_validate(c) for c in children],
        )

    def build_product_summaries(
        self, products: list[Product]
    ) -> list[ProductSummaryResponse]:
        """Summary cards (price + default variant) for already-loaded products.
        Products must have images and variants eagerly loaded."""
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
        stock_by_variant = self._get_available_stock_for_variants(
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
                    in_stock=(
                        stock_by_variant.get(default_variant.id, Decimal("0")) > 0
                        if default_variant
                        else False
                    ),
                )
            )
        return items

    def list_public_products(
        self, category_id: int | None, page: int, page_size: int, *, q: str | None = None
    ) -> ProductListResponse:
        query = self.db.query(Product).filter(Product.status == _ACTIVE)
        if category_id is not None:
            # A parent category shows its own products plus those of its
            # active subcategories.
            ids = [category_id] + [
                cid
                for (cid,) in self.db.query(Category.id).filter(
                    Category.parent_id == category_id, Category.status == _ACTIVE
                )
            ]
            query = query.filter(self._in_categories(ids))
        if q is not None:
            # Phase 20 addition: the smallest possible backend change to
            # support the mobile search screen - no full-text search
            # engine, just a case-insensitive name filter, consistent with
            # the "do not invent a complex search engine" instruction.
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(Product.name.ilike(f"%{escaped}%", escape="\\"))

        total = query.count()
        products = (
            query.order_by(Product.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Product.images), selectinload(Product.variants))
            .all()
        )

        items = self.build_product_summaries(products)
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
        self._validate_parent(data.parent_id)

        category = Category(
            parent_id=data.parent_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            image_url=data.image_url,
            status=data.status,
        )
        self.db.add(category)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A category with this slug already exists."
            ) from exc
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

        if "parent_id" in update_data:
            self._validate_parent(update_data["parent_id"], category_id)

        for field, value in update_data.items():
            setattr(category, field, value)

        try:
            # Flush explicitly, before AdminAuditService.record() (which
            # flushes internally too) - a duplicate-slug UniqueViolation
            # must surface here as the intended 409, not as an unhandled
            # 500 raised from inside the audit call's own flush.
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A category with this slug already exists."
            ) from exc

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

    def _validate_parent(
        self, parent_id: int | None, category_id: int | None = None
    ) -> None:
        """Categories nest exactly one level: Category -> Subcategory."""
        if parent_id is None:
            return
        if parent_id == category_id:
            raise BusinessValidationError("A category cannot be its own parent.")
        parent = self.get_category_or_404(parent_id)
        if parent.parent_id is not None:
            raise BusinessValidationError(
                "Subcategories can't have their own subcategories."
            )
        if category_id is not None and (
            self.db.query(Category.id).filter(Category.parent_id == category_id).first()
        ):
            raise BusinessValidationError(
                "A category with subcategories can't become a subcategory itself."
            )

    def _require_active_category(self, category_id: int) -> None:
        if not (
            self.db.query(Category.id)
            .filter(Category.id == category_id, Category.status == _ACTIVE)
            .first()
        ):
            raise NotFoundError("Category not found.")

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
        placements = self._placements().subquery()
        product_counts = dict(
            self.db.query(placements.c.category_id, func.count(placements.c.product_id))
            .filter(placements.c.category_id.in_(category_ids))
            .group_by(placements.c.category_id)
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
                image_url=c.image_url,
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
        product_count = self._category_product_count(category_id)

        return AdminCategoryDetailResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            image_url=category.image_url,
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
        extra_ids = self._clean_extra_category_ids(data.category_id, data.extra_category_ids)

        product = Product(
            category_id=data.category_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            status=data.status,
        )
        self.db.add(product)
        self.db.flush()
        self._set_extra_categories(product.id, extra_ids)
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

        extra_ids = update_data.pop("extra_category_ids", None)
        for field, value in update_data.items():
            setattr(product, field, value)
        if extra_ids is not None or "category_id" in update_data:
            if extra_ids is None:
                extra_ids = [c.category_id for c in product.extra_category_links]
            self._set_extra_categories(
                product.id, self._clean_extra_category_ids(product.category_id, extra_ids)
            )

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
            query = query.filter(self._in_categories([category_id]))
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

        extra_ids_by_product: dict[int, list[int]] = {}
        for pid, cid in (
            self.db.query(ProductCategory.product_id, ProductCategory.category_id)
            .filter(ProductCategory.product_id.in_([p.id for p in products]))
            .order_by(ProductCategory.category_id)
        ):
            extra_ids_by_product.setdefault(pid, []).append(cid)

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
            # Sizes of one unit family share a pool, so count each family
            # once (via its first size) instead of summing the same stock
            # once per size.
            first_per_family: dict[str, ProductVariant] = {}
            for v in active_variants:
                first_per_family.setdefault(variant_size(v)[0], v)
            total_stock = sum(
                (stock_by_variant.get(v.id, Decimal("0")) for v in first_per_family.values()),
                Decimal("0"),
            )
            items.append(
                AdminProductListItemResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    category_id=p.category_id,
                    category_name=p.category.name,
                    extra_category_ids=extra_ids_by_product.get(p.id, []),
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
                reserve_level=v.reserve_level,
                effective_reserve=effective_reserve(v.reserve_level),
                stock_level=stock_level(stock_by_variant.get(v.id, Decimal("0")), v.reserve_level),
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
            extra_categories=base.extra_categories,
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
            reserve_level=data.reserve_level,
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

    def delete_variant(self, variant_id: int, admin_user_id: int) -> None:
        variant = self.get_variant_or_404(variant_id)

        # Variants that were ever ordered, quoted or stocked are part of the
        # business record - they can only be deactivated, never removed.
        if (
            self.db.query(OrderItem.id)
            .filter(OrderItem.variant_id == variant_id)
            .first()
            or self.db.query(QuoteItem.id)
            .filter(QuoteItem.variant_id == variant_id)
            .first()
            or self.db.query(InventoryLot.id)
            .filter(InventoryLot.variant_id == variant_id)
            .first()
        ):
            raise ConflictError(
                "This variant has orders, quotes or stock history and can't be "
                "deleted. Deactivate it instead."
            )

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.variant.delete",
            resource_type="product_variant",
            resource_id=variant.id,
            previous_state=variant.status,
            reason=f"product_id={variant.product_id}",
        )
        self.db.query(CartItem).filter(CartItem.variant_id == variant_id).delete()
        self.db.query(Price).filter(Price.variant_id == variant_id).delete()
        self.db.delete(variant)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "This variant is still in use and can't be deleted. "
                "Deactivate it instead."
            ) from exc

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
    # Admin: permanent deletes
    # ------------------------------------------------------------------

    def delete_category(self, category_id: int, admin_user_id: int) -> None:
        """Permanently removes a category - only when nothing depends on it.
        Never silently takes products with it."""
        category = self.get_category_or_404(category_id)
        product_count = self._category_product_count(category.id)
        if product_count:
            raise ConflictError(
                f"This category still has {product_count} product(s). Move or delete them first."
            )
        child_count = self.db.query(Category.id).filter(Category.parent_id == category.id).count()
        if child_count:
            noun = "sub-category" if child_count == 1 else "sub-categories"
            raise ConflictError(f"This category has {child_count} {noun}. Delete or move them first.")
        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="category.delete",
            resource_type="category",
            resource_id=category.id,
            reason=f"name={category.name}",
        )
        self.db.delete(category)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("This category is still referenced and cannot be deleted.") from exc

    def delete_product(self, product_id: int, admin_user_id: int) -> None:
        """Permanently removes a product with its variants, prices, photos and
        stock records - but ONLY if it never took part in an order, quote,
        bulk request, supplier listing or packaging run. Anything with that
        history must be archived instead, so past orders keep making sense."""
        product = self.get_product_or_404(product_id)
        variant_ids = [v.id for v in product.variants]
        lot_ids = (
            [r[0] for r in self.db.query(InventoryLot.id).filter(InventoryLot.variant_id.in_(variant_ids)).all()]
            if variant_ids
            else []
        )

        def used(query) -> bool:
            return query.first() is not None

        has_history = bool(
            (variant_ids and used(self.db.query(OrderItem.id).filter(OrderItem.variant_id.in_(variant_ids))))
            or (variant_ids and used(self.db.query(QuoteItem.id).filter(QuoteItem.variant_id.in_(variant_ids))))
            or used(self.db.query(BulkOrderRequestItem.id).filter(BulkOrderRequestItem.product_id == product.id))
            or used(self.db.query(SupplierProduct.id).filter(SupplierProduct.product_id == product.id))
            or (
                lot_ids
                and (
                    used(
                        self.db.query(InventoryReservationItem.id).filter(
                            InventoryReservationItem.inventory_lot_id.in_(lot_ids)
                        )
                    )
                    or used(self.db.query(PackagingInput.id).filter(PackagingInput.inventory_lot_id.in_(lot_ids)))
                    or used(self.db.query(PackagingOutput.id).filter(PackagingOutput.inventory_lot_id.in_(lot_ids)))
                )
            )
        )
        if has_history:
            raise ConflictError(
                "This product has order, quote or supplier history, so it can't be deleted without "
                "breaking those records. Set its status to Archived to hide it from customers instead."
            )

        # Nothing depends on it: clear its stock records, then the product.
        if lot_ids:
            self.db.query(StockMovement).filter(StockMovement.inventory_lot_id.in_(lot_ids)).delete(
                synchronize_session=False
            )
            self.db.query(InventoryLot).filter(InventoryLot.id.in_(lot_ids)).delete(synchronize_session=False)
        batch_ids = [r[0] for r in self.db.query(Batch.id).filter(Batch.product_id == product.id).all()]
        if batch_ids:
            self.db.query(QualityCheck).filter(QualityCheck.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            self.db.query(Batch).filter(Batch.id.in_(batch_ids)).delete(synchronize_session=False)
        if variant_ids:
            self.db.query(CartItem).filter(CartItem.variant_id.in_(variant_ids)).delete(synchronize_session=False)
            self.db.query(Price).filter(Price.variant_id.in_(variant_ids)).delete(synchronize_session=False)
            self.db.query(ProductVariant).filter(ProductVariant.id.in_(variant_ids)).delete(synchronize_session=False)

        AdminAuditService(self.db).record(
            admin_user_id=admin_user_id,
            action="product.delete",
            resource_type="product",
            resource_id=product.id,
            reason=f"name={product.name}",
        )
        self.db.expire(product)
        self.db.query(Product).filter(Product.id == product.id).delete(synchronize_session=False)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "This product is still referenced by other records and cannot be deleted. Archive it instead."
            ) from exc

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
        """Sellable packs per variant from the product's shared stock pool
        (see app.services.stock_pool): stock entered against one size also
        counts for its sibling sizes. Read-only - Products never mutates
        inventory, adjustments happen through the Inventory module.
        """
        return available_packs_by_variant(self.db, variant_ids)

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
        self,
        variant: ProductVariant,
        current_price: Price | None = None,
        in_stock: bool = True,
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
            in_stock=in_stock,
        )

    @staticmethod
    def _placements():
        """Every (product_id, category_id) a product is listed under: its
        main category plus any extra ones."""
        return union(
            select(Product.id.label("product_id"), Product.category_id.label("category_id")),
            select(ProductCategory.product_id, ProductCategory.category_id),
        )

    @staticmethod
    def _in_categories(category_ids: list[int]):
        return or_(
            Product.category_id.in_(category_ids),
            Product.id.in_(
                select(ProductCategory.product_id).where(ProductCategory.category_id.in_(category_ids))
            ),
        )

    def _category_product_count(self, category_id: int) -> int:
        return self.db.query(Product.id).filter(self._in_categories([category_id])).count()

    def _clean_extra_category_ids(self, main_category_id: int, ids: list[int]) -> list[int]:
        wanted = sorted({i for i in ids if i != main_category_id})
        if wanted:
            found = {cid for (cid,) in self.db.query(Category.id).filter(Category.id.in_(wanted))}
            missing = [i for i in wanted if i not in found]
            if missing:
                raise NotFoundError(f"Category not found: {missing[0]}.")
        return wanted

    def _set_extra_categories(self, product_id: int, ids: list[int]) -> None:
        self.db.query(ProductCategory).filter(ProductCategory.product_id == product_id).delete(
            synchronize_session=False
        )
        self.db.add_all(ProductCategory(product_id=product_id, category_id=i) for i in ids)
        self.db.flush()
        self.db.expire_all()

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
        stock_by_variant = self._get_available_stock_for_variants([v.id for v in variants])
        variant_responses = [
            self._to_variant_response(
                v,
                prices_by_variant.get(v.id),
                in_stock=stock_by_variant.get(v.id, Decimal("0")) > 0,
            )
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
            extra_categories=[
                CategoryResponse.model_validate(c)
                for c in self.db.query(Category)
                .join(ProductCategory, ProductCategory.category_id == Category.id)
                .filter(ProductCategory.product_id == product.id)
                .order_by(Category.name)
            ],
            images=[ProductImageResponse.model_validate(i) for i in images],
            variants=variant_responses,
        )
