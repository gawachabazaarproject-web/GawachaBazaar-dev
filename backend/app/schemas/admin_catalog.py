"""Admin-facing catalog schemas.

Separate module from `schemas/catalog.py` for the same reason
`schemas/admin_order.py` is separate from `schemas/order.py`: these types
extend `ProductResponse`/`ProductSummaryResponse` with admin-only fields
(timestamps, aggregated stock) without risking a future circular import as
the admin surface grows. Every field is either copied verbatim from an
existing schema or computed the same way `CatalogService`'s public methods
already compute it (see `get_current_prices_for_variants` /
`InventoryLot.reserved_quantity`) - nothing here recomputes a business
value independently.
"""

from datetime import datetime
from decimal import Decimal

from app.schemas.base import BaseSchema
from app.schemas.catalog import CategoryResponse, ProductImageResponse, ProductVariantResponse

MAX_PAGE_SIZE = 100


class AdminProductListItemResponse(BaseSchema):
    """One row of the admin product table. `total_available_stock` sums
    `quantity - reserved_quantity` across ACTIVE inventory lots for every
    ACTIVE variant of this product - the same arithmetic the Inventory
    module uses, not a separate stock concept invented for this table.
    """

    id: int
    name: str
    slug: str
    category_id: int
    category_name: str
    status: str
    primary_image_url: str | None
    price: Decimal | None
    currency: str | None
    variant_count: int
    total_available_stock: Decimal
    created_at: datetime
    updated_at: datetime


class AdminProductListResponse(BaseSchema):
    items: list[AdminProductListItemResponse]
    page: int
    page_size: int
    total: int


class VariantStockResponse(BaseSchema):
    variant_id: int
    variant_name: str
    sku: str
    status: str
    available_quantity: Decimal


class ProductActivityEntryResponse(BaseSchema):
    """One row of a product's real activity feed - read directly from
    `admin_action_logs` (see app/models/admin_action_log.py), never
    synthesized. Covers changes to the product itself and to its variants/
    prices, since those are the sub-resources a Product Activity view
    needs (see the admin-panel Products spec's "Product Activity" section)
    - image changes are intentionally excluded here (too frequent/low-value
    to be worth surfacing on this feed) but remain in the audit table.
    """

    id: int
    action: str
    resource_type: str
    resource_id: int
    previous_state: str | None
    new_state: str | None
    reason: str | None
    admin_name: str
    created_at: datetime


class ProductActivityResponse(BaseSchema):
    items: list[ProductActivityEntryResponse]


class AdminCategoryListItemResponse(BaseSchema):
    """One row of the admin category table. `product_count` is a real
    `COUNT(*) ... GROUP BY category_id` over the Product table, never
    derived from whatever page of products happens to be loaded client-side
    (see the admin-panel Categories spec's explicit "must come from
    authoritative backend data" rule). `is_featured`/`sort_order` still
    have no backing column on Category and stay absent here rather than a
    fabricated default - `image_url` was added once a real column (and
    the Cloudinary-backed upload/delete routes that populate it) existed.
    """

    id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    parent_id: int | None
    parent_name: str | None
    status: str
    product_count: int
    child_count: int
    created_at: datetime
    updated_at: datetime


class AdminCategoryListResponse(BaseSchema):
    items: list[AdminCategoryListItemResponse]
    page: int
    page_size: int
    total: int


class AdminCategoryDetailResponse(BaseSchema):
    id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    parent_id: int | None
    parent_name: str | None
    status: str
    product_count: int
    created_at: datetime
    updated_at: datetime
    children: list[CategoryResponse]


class AdminProductDetailResponse(BaseSchema):
    """Everything `ProductResponse` has (category, images, every variant
    regardless of status, each with its current price) plus what an admin
    additionally needs: timestamps and a real per-variant stock summary.
    """

    id: int
    name: str
    slug: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    category: CategoryResponse
    images: list[ProductImageResponse]
    variants: list[ProductVariantResponse]
    variant_stock: list[VariantStockResponse]
