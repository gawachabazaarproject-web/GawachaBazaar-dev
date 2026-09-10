# Gawacha Bazaar Database Specification: Version 6 — Cart & Orders

This document defines the database architecture and technical specifications for **Phase 6: Cart & Orders** of the Gawacha Bazaar platform.

---

## 1. Business Context & Purchasing Flow

Phase 6 introduces the customer purchasing domain to Gawacha Bazaar:

```text
CUSTOMER (User)
    │
    ▼
SHOPPING CART (`carts`)
    │
    ▼
CART ITEMS (`cart_items`)
    │
    ▼
[ CATALOG PRODUCT VARIANTS ] (Live Pricing & Availability)
    │
    ▼
CHECKOUT
    │
    ▼
PURCHASE ORDER (`orders`)
    ├── ORDER ITEMS (`order_items` — Commercial Snapshot)
    └── ORDER ADDRESS (`order_addresses` — Delivery Snapshot)
```

### 1.1 Intent vs. Commercial Record

The domain strictly separates customer intent from permanent commercial records:
- **Cart (`carts`, `cart_items`)**: Represents transient customer shopping intent. Prices are volatile and subject to changes in the product catalog. Deletion cascades cleanly.
- **Order (`orders`, `order_items`, `order_addresses`)**: Represents a legally binding, permanent commercial agreement. Once created, orders preserve the exact transaction snapshot (names, SKU, unit, quantities, prices, address) regardless of subsequent catalog edits, price adjustments, or user profile modifications.

---

## 2. Core Architectural & Domain Invariants

### 2.1 Single Active Cart Per User
- A user may have at most **one active cart** at any given moment.
- Enforced at the database engine level via a PostgreSQL partial unique index:
  ```sql
  CREATE UNIQUE INDEX uq_carts_user_active ON carts (user_id) WHERE status = 'ACTIVE';
  ```
- Historical carts in non-active states (`CHECKED_OUT`, `ABANDONED`) are retained for auditing and abandoned-cart analytics.

### 2.2 Live Pricing in Cart vs. Historical Snapshots in Order
- **`cart_items` has NO price column**: Carts must never freeze stale prices. Product prices fluctuate based on harvest quality, seasonality, and market conditions; prices are resolved dynamically from active `prices` records when the cart is fetched or checked out.
- **`order_items` captures permanent snapshot fields**:
  - `product_name` (`VARCHAR(150)`): Product title at purchase time.
  - `variant_name` (`VARCHAR(100)`): Variant description at purchase time.
  - `sku` (`VARCHAR(100)`): SKU identifier at purchase time.
  - `unit` (`VARCHAR(20)`): Unit of measure (e.g., `KG`, `UNIT`).
  - `quantity` (`NUMERIC(12, 3)`): Quantity purchased.
  - `unit_price` (`NUMERIC(12, 2)`): Selling price per unit at order time.
  - `total_price` (`NUMERIC(12, 2)`): Computed total line price (`quantity * unit_price`).
- **No `updated_at` on `order_items`**: Order line items are immutable commercial ledger entries.
- **No `product_id` on `order_items`**: Order items reference `product_variants.id` (`variant_id`) directly, preserving exact packaging variant provenance.

### 2.3 Immutable 1:1 Delivery Address Snapshot
- **`order_addresses` stores delivery details at purchase time**: `address_line_1`, `address_line_2`, `city`, `state`, `postal_code`, `latitude`, `longitude`.
- **Decoupled from `users.addresses`**: Customers may modify or delete their saved account addresses without invalidating historical order delivery records.
- **1:1 Enforced via `UNIQUE(order_id)`**: Each order references exactly one delivery address snapshot.
- **No `user_id` column**: The address is strictly owned by the order, eliminating ambiguous multi-owner relationships.

### 2.4 Referential Integrity & Deletion Semantics
- `carts -> cart_items`: `ON DELETE CASCADE`. Deleting a transient cart automatically drops its item records.
- `users -> carts`: `ON DELETE RESTRICT`. Users with associated shopping carts cannot be deleted while carts exist.
- `users -> orders`: `ON DELETE RESTRICT`. Users with commercial orders cannot be deleted.
- `product_variants -> cart_items`: `ON DELETE RESTRICT`. Active variants present in carts cannot be abruptly removed.
- `product_variants -> order_items`: `ON DELETE RESTRICT`. Historical variants with orders cannot be deleted.
- `orders -> order_items`: `ON DELETE RESTRICT`. Commercial order items cannot be orphaned.
- `orders -> order_addresses`: `ON DELETE RESTRICT`. Order addresses cannot be orphaned.

### 2.5 Scope Boundaries (Explicitly Deferred)
- **No Inventory Reservation/Movement**: Orders do not deduct or reserve stock in Phase 6. Stock allocation occurs in subsequent operational phases.
- **No Payment Gateways or Transactions**: Payment processing, gateways, and transaction tables are deferred to a dedicated payments phase.
- **No Delivery/Shipment Tracking**: Order logistics, assignment, and dispatch tables are deferred.
- **No Discounts or Promotions**: Coupons, loyalty points, and promo codes are deferred.
- **No REST/GraphQL APIs**: Phase 6 implements strictly the database foundation and domain models.

---

## 3. Detailed Table Specifications

### 3.1 `carts`
Customer shopping cart representing temporary purchasing intent.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `user_id` | `BIGINT` | `NO` | — | FK to `users.id` (`ON DELETE RESTRICT`) |
| `status` | `VARCHAR(30)` | `NO` | — | Cart status (`ACTIVE`, `CHECKED_OUT`, `ABANDONED`) |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record update timestamp |

**Constraints & Indexes**:
- `pk_carts`: PRIMARY KEY (`id`)
- `fk_carts_user_id_users`: FOREIGN KEY (`user_id`) REFERENCES `users(id)` ON DELETE RESTRICT
- `ck_carts_status`: CHECK (`status IN ('ACTIVE', 'CHECKED_OUT', 'ABANDONED')`)
- `ix_carts_user_id`: INDEX (`user_id`)
- `ix_carts_status`: INDEX (`status`)
- `uq_carts_user_active`: UNIQUE INDEX (`user_id`) WHERE `status = 'ACTIVE'`

---

### 3.2 `cart_items`
Individual product variant line items in a customer shopping cart.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `cart_id` | `BIGINT` | `NO` | — | FK to `carts.id` (`ON DELETE CASCADE`) |
| `variant_id` | `BIGINT` | `NO` | — | FK to `product_variants.id` (`ON DELETE RESTRICT`) |
| `quantity` | `NUMERIC(12, 3)` | `NO` | — | Item quantity in cart |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record update timestamp |

**Constraints & Indexes**:
- `pk_cart_items`: PRIMARY KEY (`id`)
- `fk_cart_items_cart_id_carts`: FOREIGN KEY (`cart_id`) REFERENCES `carts(id)` ON DELETE CASCADE
- `fk_cart_items_variant_id_product_variants`: FOREIGN KEY (`variant_id`) REFERENCES `product_variants(id)` ON DELETE RESTRICT
- `uq_cart_items_cart_id_variant_id`: UNIQUE (`cart_id`, `variant_id`)
- `ck_cart_items_quantity`: CHECK (`quantity > 0`)
- `ix_cart_items_cart_id`: INDEX (`cart_id`)
- `ix_cart_items_variant_id`: INDEX (`variant_id`)

---

### 3.3 `orders`
Customer purchase order representing a permanent historical commercial record.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `user_id` | `BIGINT` | `NO` | — | FK to `users.id` (`ON DELETE RESTRICT`) |
| `order_number` | `VARCHAR(100)` | `NO` | — | Unique human-readable business order number |
| `status` | `VARCHAR(30)` | `NO` | — | Order status (`PENDING`, `CONFIRMED`, `CANCELLED`, `COMPLETED`) |
| `total_amount` | `NUMERIC(12, 2)` | `NO` | — | Total monetary order value |
| `currency` | `VARCHAR(3)` | `NO` | — | 3-letter currency code (e.g., `INR`) |
| `placed_at` | `TIMESTAMPTZ` | `NO` | — | Timestamp when customer finalized order |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record update timestamp |

**Constraints & Indexes**:
- `pk_orders`: PRIMARY KEY (`id`)
- `uq_orders_order_number`: UNIQUE (`order_number`)
- `fk_orders_user_id_users`: FOREIGN KEY (`user_id`) REFERENCES `users(id)` ON DELETE RESTRICT
- `ck_orders_status`: CHECK (`status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED')`)
- `ck_orders_total_amount`: CHECK (`total_amount >= 0`)
- `ix_orders_user_id`: INDEX (`user_id`)
- `ix_orders_status`: INDEX (`status`)
- `ix_orders_placed_at`: INDEX (`placed_at`)

---

### 3.4 `order_items`
Permanent snapshot line item within an order.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `order_id` | `BIGINT` | `NO` | — | FK to `orders.id` (`ON DELETE RESTRICT`) |
| `variant_id` | `BIGINT` | `NO` | — | FK to `product_variants.id` (`ON DELETE RESTRICT`) |
| `product_name` | `VARCHAR(150)` | `NO` | — | Snapshot: Product name at time of order |
| `variant_name` | `VARCHAR(100)` | `NO` | — | Snapshot: Variant name at time of order |
| `sku` | `VARCHAR(100)` | `NO` | — | Snapshot: SKU at time of order |
| `unit` | `VARCHAR(20)` | `NO` | — | Snapshot: Unit of measure at time of order |
| `quantity` | `NUMERIC(12, 3)` | `NO` | — | Quantity ordered |
| `unit_price` | `NUMERIC(12, 2)` | `NO` | — | Price per unit at time of order |
| `total_price` | `NUMERIC(12, 2)` | `NO` | — | Total line price (`quantity * unit_price`) |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |

**Constraints & Indexes**:
- `pk_order_items`: PRIMARY KEY (`id`)
- `fk_order_items_order_id_orders`: FOREIGN KEY (`order_id`) REFERENCES `orders(id)` ON DELETE RESTRICT
- `fk_order_items_variant_id_product_variants`: FOREIGN KEY (`variant_id`) REFERENCES `product_variants(id)` ON DELETE RESTRICT
- `ck_order_items_quantity`: CHECK (`quantity > 0`)
- `ck_order_items_unit_price`: CHECK (`unit_price > 0`)
- `ck_order_items_total_price`: CHECK (`total_price >= 0`)
- `ix_order_items_order_id`: INDEX (`order_id`)
- `ix_order_items_variant_id`: INDEX (`variant_id`)

---

### 3.5 `order_addresses`
Permanent snapshot of delivery address captured at order placement.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `order_id` | `BIGINT` | `NO` | — | FK to `orders.id` (`ON DELETE RESTRICT`), UNIQUE |
| `address_line_1` | `VARCHAR(255)` | `NO` | — | Delivery address line 1 |
| `address_line_2` | `VARCHAR(255)` | `YES` | `NULL` | Delivery address line 2 |
| `city` | `VARCHAR(100)` | `NO` | — | Delivery city |
| `state` | `VARCHAR(100)` | `NO` | — | Delivery state |
| `postal_code` | `VARCHAR(20)` | `NO` | — | Delivery postal / PIN code |
| `latitude` | `NUMERIC(9, 6)` | `YES` | `NULL` | Geolocation latitude |
| `longitude` | `NUMERIC(9, 6)` | `YES` | `NULL` | Geolocation longitude |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |

**Constraints & Indexes**:
- `pk_order_addresses`: PRIMARY KEY (`id`)
- `fk_order_addresses_order_id_orders`: FOREIGN KEY (`order_id`) REFERENCES `orders(id)` ON DELETE RESTRICT
- `uq_order_addresses_order_id`: UNIQUE (`order_id`)
- `ix_order_addresses_order_id`: INDEX (`order_id`)

---

## 4. SQLAlchemy Model Mapping & Relationships

```text
User
  ├── 1:N ──> Cart (back_populates="user")
  └── 1:N ──> Order (back_populates="user")

Cart
  └── 1:N (cascade="all, delete-orphan") ──> CartItem (back_populates="cart")

ProductVariant
  ├── 1:N ──> CartItem (back_populates="variant")
  └── 1:N ──> OrderItem (back_populates="variant")

Order
  ├── 1:N ──> OrderItem (back_populates="order")
  └── 1:1 (uselist=False) ──> OrderAddress (back_populates="order")
```
