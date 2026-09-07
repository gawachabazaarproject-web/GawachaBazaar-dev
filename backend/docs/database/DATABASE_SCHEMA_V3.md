# Gawacha Bazaar Database Specification: Version 3 — Catalog & Products

This document defines the database architecture and technical specifications for **Phase 3: Catalog & Products** of the Gawacha Bazaar platform.

---

## 1. Business Context & Physical Process Flow

Gawacha Bazaar connects genuine village farms directly with consumers. With identity (Phase 1) and farm traceability (Phase 2) established, Phase 3 introduces the master catalog and sellable product entities, linking farm batches to retail products.

```text
CATEGORY (e.g., Vegetables / Root Vegetables)
   │
   ▼
PRODUCT (e.g., Desi Tomato)
   ├───────────────────────┬───────────────────────┐
   ▼                       ▼                       ▼
PRODUCT_VARIANT       PRODUCT_IMAGE              BATCH (Harvest Lot)
(e.g., 500g / 1kg)    (Media Asset)                │
   │                                               ▼
   ▼                                             FARM (Village Origin)
 PRICE
(e.g., ₹40 / ₹75)
```

### Traceability Chain

Produce flows physically from the farm to the customer, while the database models provenance through batches linked to catalog products:

```text
  FARM (Village Source, Farmer Owner)
   │
   ▼
 BATCH (Harvest Date, Expiry Date, Quantity, Physical Inspection)
   │
   ▼
PRODUCT (Master Catalog Produce Definition)
   │
   ▼
PRODUCT_VARIANT (Packaging Unit & Sellable SKU)
   │
   ▼
 PRICE (Active & Historical Pricing)
```

### Key Business Rules & Structural Cardinalities
1. **One Product to Many Batches (`1 : N`)**: A single master product (e.g., "Alphonso Mango") can be sourced from multiple harvest batches across different farms and harvest dates.
2. **One Batch belongs to Exactly One Product (`N : 1`)**: Each harvest batch is assigned directly to a specific catalog product (`batches.product_id` is `NOT NULL`).
3. **Product to Variants (`1 : N`)**: A master product defines common attributes; variants define pack sizes, packaging units, and unique SKUs (e.g., "500 G", "1 KG", "1 BOX").
4. **Single Primary Image Constraint**: A product may have multiple media assets, but strictly at most one primary image (`UNIQUE(product_id) WHERE is_primary = true`).
5. **Variant to Prices (`1 : N`)**: Pricing is versioned over time (`valid_from` to `valid_to`) with status tracking (`is_active`).

---

## 2. Key Domain Boundary Decisions

- **Batches Identify Produce, Variants Define Packaging**:
  `batches` references `products`, **not** `product_variants`. The harvest batch tracks agricultural lot origin (farm, harvest date, grading), whereas variants represent packaging units and catalog SKUs.
- **Inventory Decoupling (No `inventory` or `stock_movements`)**:
  Inventory tracking, stock allocations, and warehouse movements belong to subsequent operational phases. Phase 3 focuses solely on the product catalog, packaging variants, pricing, and origin linkage.
- **No E-Commerce Transactional Tables**:
  Tables for carts, orders, order items, payments, coupons, promotions, reviews, and delivery are intentionally excluded from Phase 3.
- **Farmers as Users, Direct Sourcing**:
  Middlemen, vendor marketplaces, and third-party supplier entities are omitted. Farmers exist as Phase 1 users with roles; farms and batches originate directly from Phase 2.
- **No PostgreSQL ENUM Types**:
  All lifecycle statuses and units use `VARCHAR` columns with explicit database `CHECK` constraints for portability, flexibility, and non-blocking alterations.
- **Self-Parenting Prevention**:
  A database check constraint (`parent_id IS NULL OR parent_id <> id`) prevents circular self-parenting on categories. Arbitrary multi-level cycle detection is handled in application domain validation.

---

## 3. Entity-Relationship Model

```text
       ┌──────────────┐
       │  categories  │◀──────────────────┐
       └──────┬───────┘                   │
              │ 1                         │ parent_id (N:1, RESTRICT)
              │                           │
              │ N                         │
       ┌──────┴───────┐                   │
       │   products   │───────────────────┘
       └──┬───┬───┬───┘
          │ 1 │ 1 │ 1
          │   │   │
        N │   │ N │ N
   ┌──────┘   │   └───────────────────────┐
   ▼          ▼                           ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│product_images│ │product_varian│ │   batches    │
└──────────────┘ └──────┬───────┘ └──────┬───────┘
                        │ 1              │ N
                        │                │
                        │ N              │ 1
                 ┌──────┴───────┐ ┌──────┴───────┐
                 │    prices    │ │    farms     │
                 └──────────────┘ └──────────────┘
```

---

## 4. Table Specifications

### Table 1: `categories`

#### Purpose
Organizes products into a hierarchical taxonomy (e.g., "Vegetables" → "Leafy Greens").

#### Columns
| Column Name | PostgreSQL Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `BIGINT GENERATED BY DEFAULT AS IDENTITY` | No | Auto-increment | Primary key |
| `parent_id` | `BIGINT` | Yes | `NULL` | Foreign key referencing `categories.id` (ON DELETE RESTRICT) |
| `name` | `VARCHAR(150)` | No | None | Human-readable category name |
| `slug` | `VARCHAR(180)` | No | None | URL-safe slug (Unique) |
| `description` | `TEXT` | Yes | `NULL` | Detailed category description |
| `status` | `VARCHAR(30)` | No | None | Lifecycle status: `ACTIVE`, `INACTIVE`, `ARCHIVED` |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | `now()` | Row modification timestamp |

#### Constraints & Indexes
- Primary Key: `categories_pkey (id)`
- Unique: `uq_categories_slug (slug)`
- Foreign Key: `fk_categories_parent_id_categories (parent_id) -> categories(id) ON DELETE RESTRICT`
- Check: `ck_categories_status: status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')`
- Check: `ck_categories_parent_not_self: parent_id IS NULL OR parent_id <> id`
- Indexes: `ix_categories_parent_id`, `ix_categories_status`

---

### Table 2: `products`

#### Purpose
Represents master catalog produce entities (e.g., "Desi Tomato", "Nagpur Orange").

#### Columns
| Column Name | PostgreSQL Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `BIGINT GENERATED BY DEFAULT AS IDENTITY` | No | Auto-increment | Primary key |
| `category_id` | `BIGINT` | No | None | Foreign key referencing `categories.id` (ON DELETE RESTRICT) |
| `name` | `VARCHAR(150)` | No | None | Product commercial name |
| `slug` | `VARCHAR(180)` | No | None | URL-safe slug (Unique) |
| `description` | `TEXT` | Yes | `NULL` | Product narrative & details |
| `status` | `VARCHAR(30)` | No | None | Catalog status: `DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED` |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | `now()` | Row modification timestamp |

#### Constraints & Indexes
- Primary Key: `products_pkey (id)`
- Unique: `uq_products_slug (slug)`
- Foreign Key: `fk_products_category_id_categories (category_id) -> categories(id) ON DELETE RESTRICT`
- Check: `ck_products_status: status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED')`
- Indexes: `ix_products_category_id`, `ix_products_status`

---

### Table 3: `product_variants`

#### Purpose
Represents sellable packaging and stock-keeping units (SKUs) associated with a master product.

#### Columns
| Column Name | PostgreSQL Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `BIGINT GENERATED BY DEFAULT AS IDENTITY` | No | Auto-increment | Primary key |
| `product_id` | `BIGINT` | No | None | Foreign key referencing `products.id` (ON DELETE RESTRICT) |
| `name` | `VARCHAR(100)` | No | None | Variant name (e.g., "500g Pack", "1 Dozen") |
| `sku` | `VARCHAR(100)` | No | None | Globally unique SKU code |
| `unit` | `VARCHAR(20)` | No | None | Unit of measure: `KG`, `G`, `L`, `ML`, `UNIT`, `DOZEN`, `BOX`, `PACK` |
| `quantity` | `NUMERIC(12,3)` | No | None | Quantity per variant package (> 0) |
| `status` | `VARCHAR(30)` | No | None | Status: `ACTIVE`, `INACTIVE`, `ARCHIVED` |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | `now()` | Row modification timestamp |

#### Constraints & Indexes
- Primary Key: `product_variants_pkey (id)`
- Unique: `uq_product_variants_sku (sku)`
- Foreign Key: `fk_product_variants_product_id_products (product_id) -> products(id) ON DELETE RESTRICT`
- Check: `ck_product_variants_unit: unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'PACK')`
- Check: `ck_product_variants_quantity: quantity > 0`
- Check: `ck_product_variants_status: status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')`
- Indexes: `ix_product_variants_product_id`, `ix_product_variants_status`

---

### Table 4: `product_images`

#### Purpose
Stores media assets, URLs, and display order for products, enforcing at most one primary image per product.

#### Columns
| Column Name | PostgreSQL Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `BIGINT GENERATED BY DEFAULT AS IDENTITY` | No | Auto-increment | Primary key |
| `product_id` | `BIGINT` | No | None | Foreign key referencing `products.id` (ON DELETE CASCADE) |
| `image_url` | `TEXT` | No | None | Resolvable URL of the image |
| `alt_text` | `VARCHAR(255)` | Yes | `NULL` | Accessibility and SEO alt text |
| `is_primary` | `BOOLEAN` | No | `false` | True if this image is the primary hero image |
| `sort_order` | `INTEGER` | No | `0` | Display order sequence (>= 0) |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | Row creation timestamp |

#### Constraints & Indexes
- Primary Key: `product_images_pkey (id)`
- Foreign Key: `fk_product_images_product_id_products (product_id) -> products(id) ON DELETE CASCADE`
- Check: `ck_product_images_sort_order: sort_order >= 0`
- Index: `ix_product_images_product_id (product_id)`
- Partial Unique Index: `uq_product_images_product_primary: UNIQUE(product_id) WHERE (is_primary = true)`

---

### Table 5: `prices`

#### Purpose
Maintains historical and current pricing records for product variants.

#### Columns
| Column Name | PostgreSQL Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `BIGINT GENERATED BY DEFAULT AS IDENTITY` | No | Auto-increment | Primary key |
| `variant_id` | `BIGINT` | No | None | Foreign key referencing `product_variants.id` (ON DELETE RESTRICT) |
| `price` | `NUMERIC(12,2)` | No | None | Monetary price (> 0) |
| `currency` | `VARCHAR(3)` | No | None | ISO 4217 currency code (e.g., `INR`) |
| `valid_from` | `TIMESTAMPTZ` | No | None | Effective start timestamp |
| `valid_to` | `TIMESTAMPTZ` | Yes | `NULL` | Effective end timestamp (`NULL` = currently open-ended) |
| `is_active` | `BOOLEAN` | No | `true` | Pricing active flag |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | Row creation timestamp |

#### Constraints & Indexes
- Primary Key: `prices_pkey (id)`
- Foreign Key: `fk_prices_variant_id_product_variants (variant_id) -> product_variants(id) ON DELETE RESTRICT`
- Check: `ck_prices_price: price > 0`
- Check: `ck_prices_valid_to: valid_to IS NULL OR valid_to >= valid_from`
- Indexes: `ix_prices_variant_id`, `ix_prices_valid_from`, `ix_prices_is_active`

---

### Table 6: `batches` (Modified from Phase 2)

#### Purpose
Represents physical harvest lots from farms. Modified in Phase 3 to establish mandatory traceability to catalog products.

#### Added Columns
| Column Name | PostgreSQL Type | Nullable | Default | Description |
|---|---|---|---|---|
| `product_id` | `BIGINT` | No | None | Foreign key referencing `products.id` (ON DELETE RESTRICT) |

#### Updated Constraints & Indexes
- Foreign Key Added: `fk_batches_product_id_products (product_id) -> products(id) ON DELETE RESTRICT`
- Index Added: `ix_batches_product_id (product_id)`

---

## 5. Referential Integrity & Delete Action Matrix

| Relationship | Parent Table | Child Table | Foreign Key | On Delete Action | Rationale |
|---|---|---|---|---|---|
| Category Taxonomy | `categories` | `categories` | `parent_id` | `RESTRICT` | Cannot delete parent category with active children |
| Product Category | `categories` | `products` | `category_id` | `RESTRICT` | Cannot delete category that contains catalog products |
| Product Variant | `products` | `product_variants`| `product_id` | `RESTRICT` | Cannot delete product with sellable variants |
| Product Image | `products` | `product_images` | `product_id` | `CASCADE` | Deleting a product automatically cleans up its media assets |
| Product Batch Trace | `products` | `batches` | `product_id` | `RESTRICT` | Cannot delete product linked to physical harvest history |
| Variant Price | `product_variants`| `prices` | `variant_id` | `RESTRICT` | Cannot delete variant with financial pricing records |

---

## 6. Allowed Status & Unit Values

### Category Status (`categories.status`)
- `ACTIVE`: Available in active taxonomy
- `INACTIVE`: Temporarily hidden from customer browsing
- `ARCHIVED`: Obsolete category retained for historical records

### Product Status (`products.status`)
- `DRAFT`: Initial draft product, not published
- `ACTIVE`: Active catalog product visible to customers
- `INACTIVE`: Temporarily deactivated
- `ARCHIVED`: Archived product retained for historical and audit purposes

### Variant Status (`product_variants.status`)
- `ACTIVE`: Active SKU available for purchase
- `INACTIVE`: SKU temporarily inactive
- `ARCHIVED`: Discontinued SKU

### Variant Unit (`product_variants.unit`)
- Weight: `KG`, `G`
- Volume: `L`, `ML`
- Count / Packaging: `UNIT`, `DOZEN`, `BOX`, `PACK`

---

## 7. Out of Scope for Phase 3 (Explicitly Excluded)

The following areas are intentionally NOT implemented in Phase 3:
- Inventory tables (`inventory`, `stock_movements`, `warehouses`)
- Shopping cart & ordering (`carts`, `orders`, `order_items`)
- Payments & billing (`payments`, `transactions`, `invoices`)
- Marketing (`coupons`, `promotions`, `discounts`)
- Customer engagement (`reviews`, `ratings`)
- Logistics & fulfillment (`delivery`, `shipments`)
- Intermediaries & suppliers (`suppliers`, `procurement`, `marketplace_vendors`)
