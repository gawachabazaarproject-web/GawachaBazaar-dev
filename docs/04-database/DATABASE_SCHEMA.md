# Database Schema

> **Status:** Verified (generated from the ORM models). **Generated:** 2026-10-14 by [`docs/_tools/gen_schema_reference.py`](../_tools/gen_schema_reference.py).
> **Evidence:** [`backend/app/models/`](../../backend/app/models) (SQLAlchemy 2 declarative models, 50 tables) and the migration history in [`backend/alembic/versions/`](../../backend/alembic/versions). The models were compared with a database migrated to head using `alembic check` (see [MIGRATIONS.md](MIGRATIONS.md)). `alembic_version` is Alembic's own table and is not listed.

Relationships between tables: [ENTITY_RELATIONSHIPS.md](ENTITY_RELATIONSHIPS.md). Retention and lifecycle: [DATA_RETENTION.md](DATA_RETENTION.md). Business meaning of statuses: the domain documents in [`../05-domains/`](../05-domains).

Timestamps show as `DATETIME` here (the ORM type) but are `timestamp with time zone` in PostgreSQL (checked on a migrated database for every `created_at`/`updated_at`/`placed_at`/`expires_at`/`starts_at`/`paid_at` column). Primary keys are `BIGINT` identity columns. Money columns are `NUMERIC(12,2)`, quantities `NUMERIC(12,3)`. `CHECK` constraints are enforced by PostgreSQL, so status vocabularies cannot drift from the database without a migration. Indexes marked *partial* carry a `WHERE` clause that this listing does not print; read the model for the predicate.

## Table index

| Group | Tables |
|---|---|
| Identity and access | [`users`](#users), [`roles`](#roles), [`user_roles`](#user_roles), [`addresses`](#addresses), [`wishlist_items`](#wishlist_items), [`customer_notes`](#customer_notes), [`push_tokens`](#push_tokens) |
| Catalog and content | [`categories`](#categories), [`products`](#products), [`product_variants`](#product_variants), [`product_images`](#product_images), [`prices`](#prices), [`ads`](#ads), [`home_slides`](#home_slides) |
| Supply, farms and packaging | [`suppliers`](#suppliers), [`supplier_products`](#supplier_products), [`supplier_evaluations`](#supplier_evaluations), [`farms`](#farms), [`batches`](#batches), [`quality_checks`](#quality_checks), [`packaging_operations`](#packaging_operations), [`packaging_inputs`](#packaging_inputs), [`packaging_outputs`](#packaging_outputs) |
| Inventory | [`inventory_locations`](#inventory_locations), [`inventory_lots`](#inventory_lots), [`stock_movements`](#stock_movements), [`inventory_reservations`](#inventory_reservations), [`inventory_reservation_items`](#inventory_reservation_items) |
| Cart, checkout and orders | [`carts`](#carts), [`cart_items`](#cart_items), [`checkout_sessions`](#checkout_sessions), [`orders`](#orders), [`order_items`](#order_items), [`order_addresses`](#order_addresses) |
| Payments and refunds | [`payments`](#payments), [`payment_transactions`](#payment_transactions), [`payment_webhook_events`](#payment_webhook_events), [`refunds`](#refunds) |
| Fulfillment | [`fulfillments`](#fulfillments) |
| Promotions | [`promotions`](#promotions), [`promotion_targets`](#promotion_targets), [`promotion_eligible_customers`](#promotion_eligible_customers), [`promotion_redemptions`](#promotion_redemptions) |
| Bulk commerce | [`bulk_customer_profiles`](#bulk_customer_profiles), [`bulk_order_requests`](#bulk_order_requests), [`bulk_order_request_items`](#bulk_order_request_items), [`quotes`](#quotes), [`quote_versions`](#quote_versions), [`quote_items`](#quote_items) |
| Audit | [`admin_action_logs`](#admin_action_logs) |

## Identity and access

### users

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `firebase_uid` | VARCHAR(128) | yes |  |  |
| `name` | VARCHAR(150) | no |  |  |
| `email` | VARCHAR(255) | yes |  |  |
| `phone` | VARCHAR(20) | yes |  |  |
| `password_hash` | TEXT | yes |  |  |
| `status` | VARCHAR(30) | no | ACTIVE |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `(unnamed)`: (email)
- UNIQUE `(unnamed)`: (firebase_uid)
- UNIQUE `(unnamed)`: (phone)
- CHECK `ck_users_email_or_phone`: `email IS NOT NULL OR phone IS NOT NULL`
- CHECK `ck_users_status`: `status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')`

### roles

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `name` | VARCHAR(50) | no |  |  |
| `description` | VARCHAR(255) | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `(unnamed)`: (name)

### user_roles

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `role_id` | BIGINT | no |  | FK -> roles.id (ON DELETE RESTRICT) |
| `is_primary` | BOOLEAN | no | false |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_user_roles_user_role`: (user_id, role_id)
- UNIQUE INDEX `uq_user_roles_user_primary`: (user_id) - partial/filtered (see model)
- INDEX `ix_user_roles_role_id`: (role_id)

### addresses

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `label` | VARCHAR(50) | no |  |  |
| `address_line_1` | VARCHAR(255) | no |  |  |
| `address_line_2` | VARCHAR(255) | yes |  |  |
| `city` | VARCHAR(100) | no |  |  |
| `state` | VARCHAR(100) | no |  |  |
| `postal_code` | VARCHAR(20) | no |  |  |
| `latitude` | NUMERIC(9, 6) | yes |  |  |
| `longitude` | NUMERIC(9, 6) | yes |  |  |
| `is_default` | BOOLEAN | no | false |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE INDEX `uq_addresses_user_default`: (user_id) - partial/filtered (see model)
- INDEX `ix_addresses_user_id`: (user_id)

### wishlist_items

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `product_id` | BIGINT | no |  | FK -> products.id (ON DELETE CASCADE) |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_wishlist_user_product`: (user_id, product_id)
- INDEX `ix_wishlist_items_user_id`: (user_id)

### customer_notes

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `author_admin_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `note` | TEXT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- INDEX `ix_customer_notes_user_id`: (user_id)

### push_tokens

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `token` | VARCHAR(255) | no |  |  |
| `platform` | VARCHAR(16) | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `(unnamed)`: (token)
- INDEX `ix_push_tokens_user_id`: (user_id)

## Catalog and content

### categories

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `parent_id` | BIGINT | yes |  | FK -> categories.id (ON DELETE RESTRICT) |
| `name` | VARCHAR(150) | no |  |  |
| `slug` | VARCHAR(180) | no |  |  |
| `description` | TEXT | yes |  |  |
| `image_url` | TEXT | yes |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_categories_slug`: (slug)
- CHECK `ck_categories_parent_not_self`: `parent_id IS NULL OR parent_id <> id`
- CHECK `ck_categories_status`: `status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')`
- INDEX `ix_categories_parent_id`: (parent_id)
- INDEX `ix_categories_status`: (status)

### products

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `category_id` | BIGINT | no |  | FK -> categories.id (ON DELETE RESTRICT) |
| `name` | VARCHAR(150) | no |  |  |
| `slug` | VARCHAR(180) | no |  |  |
| `description` | TEXT | yes |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_products_slug`: (slug)
- CHECK `ck_products_status`: `status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED')`
- INDEX `ix_products_category_id`: (category_id)
- INDEX `ix_products_status`: (status)

### product_variants

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `product_id` | BIGINT | no |  | FK -> products.id (ON DELETE RESTRICT) |
| `name` | VARCHAR(100) | no |  |  |
| `sku` | VARCHAR(100) | no |  |  |
| `unit` | VARCHAR(20) | no |  |  |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `reserve_level` | NUMERIC(12, 3) | yes |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_product_variants_sku`: (sku)
- CHECK `ck_product_variants_quantity`: `quantity > 0`
- CHECK `ck_product_variants_reserve_level`: `reserve_level IS NULL OR reserve_level >= 0`
- CHECK `ck_product_variants_status`: `status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED')`
- CHECK `ck_product_variants_unit`: `unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'PACK')`
- INDEX `ix_product_variants_product_id`: (product_id)
- INDEX `ix_product_variants_status`: (status)

### product_images

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `product_id` | BIGINT | no |  | FK -> products.id (ON DELETE CASCADE) |
| `image_url` | TEXT | no |  |  |
| `alt_text` | VARCHAR(255) | yes |  |  |
| `is_primary` | BOOLEAN | no | false |  |
| `sort_order` | INTEGER | no | 0 |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_product_images_sort_order`: `sort_order >= 0`
- UNIQUE INDEX `uq_product_images_product_primary`: (product_id) - partial/filtered (see model)
- INDEX `ix_product_images_product_id`: (product_id)

### prices

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `variant_id` | BIGINT | no |  | FK -> product_variants.id (ON DELETE RESTRICT) |
| `price` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `valid_from` | DATETIME | no |  |  |
| `valid_to` | DATETIME | yes |  |  |
| `is_active` | BOOLEAN | no | true |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_prices_price`: `price > 0`
- CHECK `ck_prices_valid_to`: `valid_to IS NULL OR valid_to >= valid_from`
- INDEX `ix_prices_is_active`: (is_active)
- INDEX `ix_prices_valid_from`: (valid_from)
- INDEX `ix_prices_variant_id`: (variant_id)

### ads

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `brand_name` | VARCHAR(150) | no |  |  |
| `image_url` | TEXT | no |  |  |
| `link_url` | TEXT | yes |  |  |
| `title` | VARCHAR(80) | yes |  |  |
| `subtitle` | VARCHAR(140) | yes |  |  |
| `display_order` | INTEGER | no | 0 |  |
| `status` | VARCHAR(20) | no | ACTIVE |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_ads_status`: `status IN ('ACTIVE', 'INACTIVE')`
- INDEX `ix_ads_status_display_order`: (status, display_order)

### home_slides

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `label` | VARCHAR(80) | no |  |  |
| `title` | VARCHAR(150) | no |  |  |
| `script_suffix` | VARCHAR(150) | yes |  |  |
| `body` | TEXT | no |  |  |
| `image_url` | TEXT | no |  |  |
| `cta_label` | VARCHAR(80) | no |  |  |
| `link_url` | TEXT | yes |  |  |
| `display_order` | INTEGER | no | 0 |  |
| `status` | VARCHAR(20) | no | ACTIVE |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_home_slides_status`: `status IN ('ACTIVE', 'INACTIVE')`
- INDEX `ix_home_slides_status_display_order`: (status, display_order)

## Supply, farms and packaging

### suppliers

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `business_name` | VARCHAR(200) | no |  |  |
| `contact_person` | VARCHAR(150) | yes |  |  |
| `phone` | VARCHAR(20) | yes |  |  |
| `email` | VARCHAR(255) | yes |  |  |
| `address_line_1` | VARCHAR(255) | yes |  |  |
| `address_line_2` | VARCHAR(255) | yes |  |  |
| `city` | VARCHAR(100) | yes |  |  |
| `state` | VARCHAR(100) | yes |  |  |
| `postal_code` | VARCHAR(20) | yes |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `notes` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_suppliers_status`: `status IN ('ACTIVE', 'INACTIVE')`
- INDEX `ix_suppliers_business_name`: (business_name)
- INDEX `ix_suppliers_status`: (status)

### supplier_products

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `supplier_id` | BIGINT | no |  | FK -> suppliers.id (ON DELETE RESTRICT) |
| `product_id` | BIGINT | no |  | FK -> products.id (ON DELETE RESTRICT) |
| `active` | BOOLEAN | no | true |  |
| `supplier_reference` | VARCHAR(100) | yes |  |  |
| `notes` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_supplier_products_supplier_product`: (supplier_id, product_id)
- INDEX `ix_supplier_products_product_id`: (product_id)
- INDEX `ix_supplier_products_supplier_id`: (supplier_id)

### supplier_evaluations

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `supplier_id` | BIGINT | no |  | FK -> suppliers.id (ON DELETE RESTRICT) |
| `evaluated_by_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `quality_rating` | NUMERIC(2, 1) | no |  |  |
| `delivery_rating` | NUMERIC(2, 1) | no |  |  |
| `price_rating` | NUMERIC(2, 1) | no |  |  |
| `reliability_rating` | NUMERIC(2, 1) | no |  |  |
| `responsiveness_rating` | NUMERIC(2, 1) | no |  |  |
| `overall_rating` | NUMERIC(2, 1) | no |  |  |
| `notes` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_supplier_evaluations_delivery_rating`: `delivery_rating >= 0 AND delivery_rating <= 5`
- CHECK `ck_supplier_evaluations_overall_rating`: `overall_rating >= 0 AND overall_rating <= 5`
- CHECK `ck_supplier_evaluations_price_rating`: `price_rating >= 0 AND price_rating <= 5`
- CHECK `ck_supplier_evaluations_quality_rating`: `quality_rating >= 0 AND quality_rating <= 5`
- CHECK `ck_supplier_evaluations_reliability_rating`: `reliability_rating >= 0 AND reliability_rating <= 5`
- CHECK `ck_supplier_evaluations_responsiveness_rating`: `responsiveness_rating >= 0 AND responsiveness_rating <= 5`
- INDEX `ix_supplier_evaluations_created_at`: (created_at)
- INDEX `ix_supplier_evaluations_supplier_id`: (supplier_id)

### farms

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `owner_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `name` | VARCHAR(150) | no |  |  |
| `address_line_1` | VARCHAR(255) | no |  |  |
| `address_line_2` | VARCHAR(255) | yes |  |  |
| `village` | VARCHAR(150) | no |  |  |
| `city` | VARCHAR(100) | no |  |  |
| `district` | VARCHAR(100) | yes |  |  |
| `state` | VARCHAR(100) | no |  |  |
| `postal_code` | VARCHAR(20) | no |  |  |
| `latitude` | NUMERIC(9, 6) | yes |  |  |
| `longitude` | NUMERIC(9, 6) | yes |  |  |
| `contact_number` | VARCHAR(20) | yes |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_farms_latitude`: `latitude IS NULL OR (latitude >= -90.0 AND latitude <= 90.0)`
- CHECK `ck_farms_longitude`: `longitude IS NULL OR (longitude >= -180.0 AND longitude <= 180.0)`
- CHECK `ck_farms_status`: `status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')`
- INDEX `ix_farms_owner_user_id`: (owner_user_id)
- INDEX `ix_farms_status`: (status)

### batches

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `wholesaler_user_id` | BIGINT | yes |  | FK -> users.id (ON DELETE RESTRICT) |
| `supplier_id` | BIGINT | yes |  | FK -> suppliers.id (ON DELETE RESTRICT) |
| `farm_id` | BIGINT | yes |  | FK -> farms.id (ON DELETE RESTRICT) |
| `product_id` | BIGINT | no |  | FK -> products.id (ON DELETE RESTRICT) |
| `batch_code` | VARCHAR(100) | no |  |  |
| `harvest_date` | DATE | no |  |  |
| `expiry_date` | DATE | yes |  |  |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `unit` | VARCHAR(20) | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `purchase_price` | NUMERIC(12, 2) | yes |  |  |
| `purchase_currency` | VARCHAR(3) | yes |  |  |
| `received_date` | DATE | yes |  |  |
| `receiving_reference` | VARCHAR(100) | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_batches_batch_code`: (batch_code)
- CHECK `ck_batches_expiry_date`: `expiry_date IS NULL OR expiry_date >= harvest_date`
- CHECK `ck_batches_purchase_price`: `purchase_price IS NULL OR purchase_price > 0`
- CHECK `ck_batches_quantity`: `quantity > 0`
- CHECK `ck_batches_status`: `status IN ('HARVESTED', 'COLLECTED', 'SORTED', 'GRADED', 'APPROVED', 'REJECTED', 'EXPIRED')`
- CHECK `ck_batches_unit`: `unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'CRATE')`
- INDEX `ix_batches_farm_id`: (farm_id)
- INDEX `ix_batches_harvest_date`: (harvest_date)
- INDEX `ix_batches_product_id`: (product_id)
- INDEX `ix_batches_status`: (status)
- INDEX `ix_batches_supplier_id`: (supplier_id)
- INDEX `ix_batches_wholesaler_user_id`: (wholesaler_user_id)

### quality_checks

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `batch_id` | BIGINT | no |  | FK -> batches.id (ON DELETE RESTRICT) |
| `checked_by_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `checked_on` | DATETIME | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `remarks` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_quality_checks_status`: `status IN ('PENDING', 'PASSED', 'FAILED')`
- INDEX `ix_quality_checks_batch_id`: (batch_id)
- INDEX `ix_quality_checks_checked_by_user_id`: (checked_by_user_id)
- INDEX `ix_quality_checks_checked_on`: (checked_on)
- INDEX `ix_quality_checks_status`: (status)

### packaging_operations

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `packaging_code` | VARCHAR(100) | no |  |  |
| `name` | VARCHAR(150) | no |  |  |
| `location_id` | BIGINT | no |  | FK -> inventory_locations.id (ON DELETE RESTRICT) |
| `status` | VARCHAR(30) | no |  |  |
| `started_at` | DATETIME | no |  |  |
| `completed_at` | DATETIME | yes |  |  |
| `performed_by_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `remarks` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_packaging_operations_packaging_code`: (packaging_code)
- CHECK `ck_packaging_operations_completed_at`: `completed_at IS NULL OR completed_at >= started_at`
- CHECK `ck_packaging_operations_status`: `status IN ('DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')`
- INDEX `ix_packaging_operations_location_id`: (location_id)
- INDEX `ix_packaging_operations_started_at`: (started_at)
- INDEX `ix_packaging_operations_status`: (status)

### packaging_inputs

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `packaging_operation_id` | BIGINT | no |  | FK -> packaging_operations.id (ON DELETE RESTRICT) |
| `inventory_lot_id` | BIGINT | no |  | FK -> inventory_lots.id (ON DELETE RESTRICT) |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_packaging_inputs_quantity`: `quantity > 0`
- INDEX `ix_packaging_inputs_inventory_lot_id`: (inventory_lot_id)
- INDEX `ix_packaging_inputs_packaging_operation_id`: (packaging_operation_id)

### packaging_outputs

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `packaging_operation_id` | BIGINT | no |  | FK -> packaging_operations.id (ON DELETE RESTRICT) |
| `inventory_lot_id` | BIGINT | no |  | FK -> inventory_lots.id (ON DELETE RESTRICT) |
| `package_count` | INTEGER | no |  |  |
| `total_quantity` | NUMERIC(12, 3) | no |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_packaging_outputs_package_count`: `package_count > 0`
- CHECK `ck_packaging_outputs_total_quantity`: `total_quantity > 0`
- INDEX `ix_packaging_outputs_inventory_lot_id`: (inventory_lot_id)
- INDEX `ix_packaging_outputs_packaging_operation_id`: (packaging_operation_id)

## Inventory

### inventory_locations

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `name` | VARCHAR(150) | no |  |  |
| `code` | VARCHAR(50) | no |  |  |
| `type` | VARCHAR(30) | no |  |  |
| `address_line_1` | VARCHAR(255) | no |  |  |
| `address_line_2` | VARCHAR(255) | yes |  |  |
| `city` | VARCHAR(100) | no |  |  |
| `state` | VARCHAR(100) | no |  |  |
| `postal_code` | VARCHAR(20) | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `latitude` | NUMERIC(9, 6) | yes |  |  |
| `longitude` | NUMERIC(9, 6) | yes |  |  |
| `is_packing_point` | BOOLEAN | no | false |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_inventory_locations_code`: (code)
- CHECK `ck_inventory_locations_status`: `status IN ('ACTIVE', 'INACTIVE')`
- UNIQUE INDEX `uq_inventory_locations_one_packing_point`: (is_packing_point) - partial/filtered (see model)
- INDEX `ix_inventory_locations_status`: (status)
- INDEX `ix_inventory_locations_type`: (type)

### inventory_lots

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `batch_id` | BIGINT | no |  | FK -> batches.id (ON DELETE RESTRICT) |
| `variant_id` | BIGINT | no |  | FK -> product_variants.id (ON DELETE RESTRICT) |
| `location_id` | BIGINT | no |  | FK -> inventory_locations.id (ON DELETE RESTRICT) |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `reserved_quantity` | NUMERIC(12, 3) | no | 0 |  |
| `status` | VARCHAR(30) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_inventory_lots_batch_variant_location`: (batch_id, variant_id, location_id)
- CHECK `ck_inventory_lots_quantity`: `quantity >= 0`
- CHECK `ck_inventory_lots_reserved_quantity`: `reserved_quantity >= 0 AND reserved_quantity <= quantity`
- CHECK `ck_inventory_lots_status`: `status IN ('ACTIVE', 'INACTIVE', 'DEPLETED')`
- INDEX `ix_inventory_lots_batch_id`: (batch_id)
- INDEX `ix_inventory_lots_location_id`: (location_id)
- INDEX `ix_inventory_lots_status`: (status)
- INDEX `ix_inventory_lots_variant_id`: (variant_id)
- INDEX `ix_inventory_lots_variant_status_fifo`: (variant_id, status, created_at, id)

### stock_movements

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `inventory_lot_id` | BIGINT | no |  | FK -> inventory_lots.id (ON DELETE RESTRICT) |
| `movement_type` | VARCHAR(30) | no |  |  |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `reference_type` | VARCHAR(50) | yes |  |  |
| `reference_id` | BIGINT | yes |  |  |
| `performed_by_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `occurred_at` | DATETIME | no |  |  |
| `remarks` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_stock_movements_movement_type`: `movement_type IN ('RECEIPT', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', 'DAMAGE', 'WASTE', 'TRANSFER_IN', 'TRANSFER_OUT', 'DISPATCH')`
- CHECK `ck_stock_movements_quantity`: `quantity > 0`
- INDEX `ix_stock_movements_inventory_lot_id`: (inventory_lot_id)
- INDEX `ix_stock_movements_movement_type`: (movement_type)
- INDEX `ix_stock_movements_occurred_at`: (occurred_at)
- INDEX `ix_stock_movements_performed_by_user_id`: (performed_by_user_id)

### inventory_reservations

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `status` | VARCHAR(30) | no |  |  |
| `expires_at` | DATETIME | no |  |  |
| `released_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_inventory_reservations_order_id`: (order_id)
- CHECK `ck_inventory_reservations_status`: `status IN ('ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED')`
- INDEX `ix_inventory_reservations_expires_at`: (expires_at)
- INDEX `ix_inventory_reservations_status`: (status)

### inventory_reservation_items

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `reservation_id` | BIGINT | no |  | FK -> inventory_reservations.id (ON DELETE RESTRICT) |
| `order_item_id` | BIGINT | no |  | FK -> order_items.id (ON DELETE RESTRICT) |
| `inventory_lot_id` | BIGINT | no |  | FK -> inventory_lots.id (ON DELETE RESTRICT) |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_inventory_reservation_items_quantity`: `quantity > 0`
- INDEX `ix_inventory_reservation_items_inventory_lot_id`: (inventory_lot_id)
- INDEX `ix_inventory_reservation_items_order_item_id`: (order_item_id)
- INDEX `ix_inventory_reservation_items_reservation_id`: (reservation_id)

## Cart, checkout and orders

### carts

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `status` | VARCHAR(30) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_carts_status`: `status IN ('ACTIVE', 'CHECKED_OUT', 'ABANDONED')`
- UNIQUE INDEX `uq_carts_user_active`: (user_id) - partial/filtered (see model)
- INDEX `ix_carts_status`: (status)
- INDEX `ix_carts_user_id`: (user_id)

### cart_items

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `cart_id` | BIGINT | no |  | FK -> carts.id (ON DELETE CASCADE) |
| `variant_id` | BIGINT | no |  | FK -> product_variants.id (ON DELETE RESTRICT) |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_cart_items_cart_id_variant_id`: (cart_id, variant_id)
- CHECK `ck_cart_items_quantity`: `quantity > 0`
- INDEX `ix_cart_items_cart_id`: (cart_id)
- INDEX `ix_cart_items_variant_id`: (variant_id)

### checkout_sessions

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `cart_id` | BIGINT | no |  | FK -> carts.id (ON DELETE CASCADE) |
| `address_id` | BIGINT | no |  |  |
| `promo_code` | VARCHAR(50) | yes |  |  |
| `amount` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `gateway_name` | VARCHAR(30) | no |  |  |
| `gateway_order_id` | VARCHAR(64) | no |  |  |
| `status` | VARCHAR(20) | no | PENDING |  |
| `order_id` | BIGINT | yes |  | FK -> orders.id (ON DELETE SET NULL) |
| `failure_reason` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |
| `completed_at` | DATETIME | yes |  |  |

Constraints and indexes:

- UNIQUE `uq_checkout_sessions_gateway_order`: (gateway_name, gateway_order_id)
- CHECK `ck_checkout_sessions_amount`: `amount > 0`
- CHECK `ck_checkout_sessions_status`: `status IN ('PENDING', 'COMPLETED', 'REFUNDED', 'REFUND_FAILED')`
- INDEX `ix_checkout_sessions_user_status`: (user_id, status)

### orders

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `cart_id` | BIGINT | yes |  | FK -> carts.id (ON DELETE RESTRICT) |
| `order_number` | VARCHAR(100) | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `total_amount` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `subtotal_amount` | NUMERIC(12, 2) | no |  |  |
| `discount_amount` | NUMERIC(12, 2) | no | 0 |  |
| `delivery_fee` | NUMERIC(12, 2) | no | 0 |  |
| `promotion_id` | BIGINT | yes |  | FK -> promotions.id (ON DELETE RESTRICT) |
| `applied_promo_code` | VARCHAR(50) | yes |  |  |
| `placed_at` | DATETIME | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |
| `cancelled_at` | DATETIME | yes |  |  |
| `cancelled_by_user_id` | BIGINT | yes |  | FK -> users.id (ON DELETE RESTRICT) |
| `cancellation_reason` | VARCHAR(500) | yes |  |  |

Constraints and indexes:

- UNIQUE `uq_orders_cart_id`: (cart_id)
- UNIQUE `uq_orders_order_number`: (order_number)
- CHECK `ck_orders_delivery_fee`: `delivery_fee >= 0`
- CHECK `ck_orders_discount_amount`: `discount_amount >= 0`
- CHECK `ck_orders_discount_not_exceeding_subtotal`: `discount_amount <= subtotal_amount`
- CHECK `ck_orders_status`: `status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'EXPIRED')`
- CHECK `ck_orders_subtotal_amount`: `subtotal_amount >= 0`
- CHECK `ck_orders_total_amount`: `total_amount >= 0`
- INDEX `ix_orders_placed_at`: (placed_at)
- INDEX `ix_orders_status`: (status)
- INDEX `ix_orders_user_id`: (user_id)

### order_items

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `variant_id` | BIGINT | no |  | FK -> product_variants.id (ON DELETE RESTRICT) |
| `product_name` | VARCHAR(150) | no |  |  |
| `variant_name` | VARCHAR(100) | no |  |  |
| `sku` | VARCHAR(100) | no |  |  |
| `unit` | VARCHAR(20) | no |  |  |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `unit_price` | NUMERIC(12, 2) | no |  |  |
| `total_price` | NUMERIC(12, 2) | no |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_order_items_quantity`: `quantity > 0`
- CHECK `ck_order_items_total_price`: `total_price >= 0`
- CHECK `ck_order_items_unit_price`: `unit_price > 0`
- INDEX `ix_order_items_order_id`: (order_id)
- INDEX `ix_order_items_variant_id`: (variant_id)

### order_addresses

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `address_line_1` | VARCHAR(255) | no |  |  |
| `address_line_2` | VARCHAR(255) | yes |  |  |
| `city` | VARCHAR(100) | no |  |  |
| `state` | VARCHAR(100) | no |  |  |
| `postal_code` | VARCHAR(20) | no |  |  |
| `latitude` | NUMERIC(9, 6) | yes |  |  |
| `longitude` | NUMERIC(9, 6) | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_order_addresses_order_id`: (order_id)

## Payments and refunds

### payments

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `payment_method` | VARCHAR(30) | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `amount` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `gateway_name` | VARCHAR(50) | yes |  |  |
| `gateway_order_id` | VARCHAR(150) | yes |  |  |
| `paid_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_payments_gateway_name_order_id`: (gateway_name, gateway_order_id)
- UNIQUE `uq_payments_order_id`: (order_id)
- CHECK `ck_payments_amount`: `amount > 0`
- CHECK `ck_payments_payment_method`: `payment_method IN ('UPI', 'COD')`
- CHECK `ck_payments_status`: `status IN ('PENDING', 'PROCESSING', 'PAID', 'FAILED', 'CANCELLED', 'EXPIRED')`
- INDEX `ix_payments_payment_method`: (payment_method)
- INDEX `ix_payments_status`: (status)

### payment_transactions

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `payment_id` | BIGINT | no |  | FK -> payments.id (ON DELETE RESTRICT) |
| `refund_id` | BIGINT | yes |  | FK -> refunds.id (ON DELETE RESTRICT) |
| `transaction_type` | VARCHAR(30) | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `amount` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `gateway_name` | VARCHAR(50) | yes |  |  |
| `gateway_transaction_id` | VARCHAR(150) | yes |  |  |
| `idempotency_key` | VARCHAR(150) | yes |  |  |
| `gateway_response` | TEXT | yes |  |  |
| `failure_reason` | TEXT | yes |  |  |
| `initiated_at` | DATETIME | no |  |  |
| `completed_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_payment_transactions_idempotency_key`: (idempotency_key)
- CHECK `ck_payment_transactions_amount`: `amount > 0`
- CHECK `ck_payment_transactions_status`: `status IN ('INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')`
- CHECK `ck_payment_transactions_transaction_type`: `transaction_type IN ('PAYMENT', 'REFUND')`
- INDEX `ix_payment_transactions_gateway_transaction_id`: (gateway_transaction_id)
- INDEX `ix_payment_transactions_payment_id`: (payment_id)
- INDEX `ix_payment_transactions_refund_id`: (refund_id)
- INDEX `ix_payment_transactions_status`: (status)

### payment_webhook_events

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `gateway_name` | VARCHAR(50) | no |  |  |
| `event_id` | VARCHAR(150) | no |  |  |
| `event_type` | VARCHAR(50) | no |  |  |
| `payment_transaction_id` | BIGINT | yes |  | FK -> payment_transactions.id (ON DELETE RESTRICT) |
| `received_at` | DATETIME | no | now() |  |
| `processed_at` | DATETIME | yes |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `payload_hash` | VARCHAR(64) | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_payment_webhook_events_gateway_event`: (gateway_name, event_id)
- CHECK `ck_payment_webhook_events_status`: `status IN ('RECEIVED', 'PROCESSED', 'FAILED')`
- INDEX `ix_payment_webhook_events_payment_transaction_id`: (payment_transaction_id)
- INDEX `ix_payment_webhook_events_status`: (status)

### refunds

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `payment_id` | BIGINT | no |  | FK -> payments.id (ON DELETE RESTRICT) |
| `status` | VARCHAR(30) | no |  |  |
| `amount` | NUMERIC(12, 2) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `requested_at` | DATETIME | no |  |  |
| `approved_by_user_id` | BIGINT | yes |  | FK -> users.id (ON DELETE RESTRICT) |
| `approved_at` | DATETIME | yes |  |  |
| `rejection_reason` | TEXT | yes |  |  |
| `processed_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_refunds_order_id`: (order_id)
- CHECK `ck_refunds_amount`: `amount > 0`
- CHECK `ck_refunds_status`: `status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'PROCESSING', 'REFUNDED', 'FAILED')`
- INDEX `ix_refunds_payment_id`: (payment_id)
- INDEX `ix_refunds_status`: (status)

## Fulfillment

### fulfillments

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `status` | VARCHAR(30) | no |  |  |
| `delivery_partner_user_id` | BIGINT | yes |  | FK -> users.id (ON DELETE RESTRICT) |
| `inventory_location_id` | BIGINT | yes |  | FK -> inventory_locations.id (ON DELETE RESTRICT) |
| `assigned_at` | DATETIME | yes |  |  |
| `delivered_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_fulfillments_order_id`: (order_id)
- CHECK `ck_fulfillments_status`: `status IN ('PENDING', 'PICKING', 'PACKED', 'READY_FOR_DELIVERY', 'ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED')`
- INDEX `ix_fulfillments_delivery_partner_user_id`: (delivery_partner_user_id)
- INDEX `ix_fulfillments_inventory_location_id`: (inventory_location_id)
- INDEX `ix_fulfillments_status`: (status)

## Promotions

### promotions

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `name` | VARCHAR(150) | no |  |  |
| `description` | TEXT | yes |  |  |
| `customer_title` | VARCHAR(150) | yes |  |  |
| `customer_description` | TEXT | yes |  |  |
| `code` | VARCHAR(50) | yes |  |  |
| `image_url` | TEXT | yes |  |  |
| `show_in_carousel` | BOOLEAN | no | false |  |
| `discount_type` | VARCHAR(20) | no |  |  |
| `discount_value` | NUMERIC(12, 2) | no |  |  |
| `max_discount_amount` | NUMERIC(12, 2) | yes |  |  |
| `min_order_value` | NUMERIC(12, 2) | yes |  |  |
| `min_quantity` | NUMERIC(12, 3) | yes |  |  |
| `customer_scope` | VARCHAR(20) | no | ALL |  |
| `status` | VARCHAR(20) | no | DRAFT |  |
| `stacking_policy` | VARCHAR(20) | no | SINGLE_BEST |  |
| `priority` | INTEGER | no | 100 |  |
| `usage_limit_total` | INTEGER | yes |  |  |
| `usage_limit_per_customer` | INTEGER | yes |  |  |
| `redemption_count` | INTEGER | no | 0 |  |
| `starts_at` | DATETIME | no |  |  |
| `ends_at` | DATETIME | yes |  |  |
| `created_by_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_promotions_customer_scope`: `customer_scope IN ('ALL', 'NEW_CUSTOMERS', 'EXISTING_CUSTOMERS', 'SPECIFIC')`
- CHECK `ck_promotions_discount_type`: `discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')`
- CHECK `ck_promotions_discount_value`: `discount_value > 0`
- CHECK `ck_promotions_ends_at`: `ends_at IS NULL OR ends_at > starts_at`
- CHECK `ck_promotions_percentage_max`: `discount_type != 'PERCENTAGE' OR discount_value <= 100`
- CHECK `ck_promotions_stacking_policy`: `stacking_policy IN ('SINGLE_BEST')`
- CHECK `ck_promotions_status`: `status IN ('DRAFT', 'ACTIVE', 'PAUSED', 'DISABLED')`
- CHECK `ck_promotions_usage_limit_per_customer`: `usage_limit_per_customer IS NULL OR usage_limit_per_customer > 0`
- CHECK `ck_promotions_usage_limit_total`: `usage_limit_total IS NULL OR usage_limit_total > 0`
- UNIQUE INDEX `uq_promotions_code`: (code) - partial/filtered (see model)
- INDEX `ix_promotions_ends_at`: (ends_at)
- INDEX `ix_promotions_starts_at`: (starts_at)
- INDEX `ix_promotions_status`: (status)

### promotion_targets

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `promotion_id` | BIGINT | no |  | FK -> promotions.id (ON DELETE CASCADE) |
| `target_type` | VARCHAR(20) | no |  |  |
| `target_id` | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_promotion_targets_unique`: (promotion_id, target_type, target_id)
- CHECK `ck_promotion_targets_target_type`: `target_type IN ('PRODUCT', 'CATEGORY')`
- INDEX `ix_promotion_targets_promotion_id`: (promotion_id)
- INDEX `ix_promotion_targets_target`: (target_type, target_id)

### promotion_eligible_customers

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `promotion_id` | BIGINT | no |  | FK -> promotions.id (ON DELETE CASCADE) |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_promotion_eligible_customers_unique`: (promotion_id, user_id)
- INDEX `ix_promotion_eligible_customers_promotion_id`: (promotion_id)

### promotion_redemptions

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `promotion_id` | BIGINT | no |  | FK -> promotions.id (ON DELETE RESTRICT) |
| `order_id` | BIGINT | no |  | FK -> orders.id (ON DELETE RESTRICT) |
| `customer_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `discount_amount` | NUMERIC(12, 2) | no |  |  |
| `status` | VARCHAR(20) | no | APPLIED |  |
| `redeemed_at` | DATETIME | no |  |  |
| `reversed_at` | DATETIME | yes |  |  |

Constraints and indexes:

- UNIQUE `uq_promotion_redemptions_order_id`: (order_id)
- CHECK `ck_promotion_redemptions_discount_amount`: `discount_amount >= 0`
- CHECK `ck_promotion_redemptions_status`: `status IN ('APPLIED', 'REVERSED')`
- INDEX `ix_promotion_redemptions_customer_user_id`: (customer_user_id)
- INDEX `ix_promotion_redemptions_promotion_id`: (promotion_id)

## Bulk commerce

### bulk_customer_profiles

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `user_id` | BIGINT | no |  | FK -> users.id (ON DELETE CASCADE) |
| `business_name` | VARCHAR(200) | no |  |  |
| `business_type` | VARCHAR(30) | no |  |  |
| `contact_person` | VARCHAR(150) | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_bulk_customer_profiles_user_id`: (user_id)
- CHECK `ck_bulk_customer_profiles_business_type`: `business_type IN ('RESTAURANT', 'HOTEL', 'CATERER', 'RETAILER', 'OFFICE', 'INSTITUTION', 'EVENT', 'OTHER')`

### bulk_order_requests

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `customer_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `address_id` | BIGINT | yes |  | FK -> addresses.id (ON DELETE RESTRICT) |
| `order_id` | BIGINT | yes |  | FK -> orders.id (ON DELETE RESTRICT) |
| `status` | VARCHAR(30) | no |  |  |
| `requested_delivery_date` | DATE | yes |  |  |
| `customer_notes` | TEXT | yes |  |  |
| `admin_notes` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_bulk_order_requests_order_id`: (order_id)
- CHECK `ck_bulk_order_requests_status`: `status IN ('REQUESTED', 'UNDER_REVIEW', 'QUOTED', 'CUSTOMER_ACCEPTED', 'CONVERTED_TO_ORDER', 'REJECTED', 'CANCELLED', 'EXPIRED')`
- INDEX `ix_bulk_order_requests_customer_user_id`: (customer_user_id)
- INDEX `ix_bulk_order_requests_status`: (status)

### bulk_order_request_items

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `request_id` | BIGINT | no |  | FK -> bulk_order_requests.id (ON DELETE CASCADE) |
| `product_id` | BIGINT | yes |  | FK -> products.id (ON DELETE RESTRICT) |
| `custom_item_name` | VARCHAR(150) | yes |  |  |
| `requested_quantity` | NUMERIC(12, 3) | no |  |  |
| `unit` | VARCHAR(20) | no |  |  |
| `customer_notes` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_bulk_order_request_items_product_or_custom`: `(product_id IS NOT NULL) OR (custom_item_name IS NOT NULL)`
- CHECK `ck_bulk_order_request_items_quantity`: `requested_quantity > 0`
- CHECK `ck_bulk_order_request_items_unit`: `unit IN ('KG', 'G', 'L', 'ML', 'UNIT', 'DOZEN', 'BOX', 'CRATE')`
- INDEX `ix_bulk_order_request_items_product_id`: (product_id)
- INDEX `ix_bulk_order_request_items_request_id`: (request_id)

### quotes

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `request_id` | BIGINT | no |  | FK -> bulk_order_requests.id (ON DELETE RESTRICT) |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_quotes_request_id`: (request_id)

### quote_versions

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `quote_id` | BIGINT | no |  | FK -> quotes.id (ON DELETE CASCADE) |
| `version_number` | INTEGER | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `currency` | VARCHAR(3) | no |  |  |
| `valid_until` | DATE | yes |  |  |
| `admin_notes` | TEXT | yes |  |  |
| `created_by_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- UNIQUE `uq_quote_versions_quote_version`: (quote_id, version_number)
- CHECK `ck_quote_versions_status`: `status IN ('DRAFT', 'SENT', 'SUPERSEDED', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'CANCELLED')`
- CHECK `ck_quote_versions_version_number`: `version_number > 0`
- INDEX `ix_quote_versions_quote_id`: (quote_id)
- INDEX `ix_quote_versions_status`: (status)

### quote_items

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `quote_version_id` | BIGINT | no |  | FK -> quote_versions.id (ON DELETE CASCADE) |
| `request_item_id` | BIGINT | no |  | FK -> bulk_order_request_items.id (ON DELETE RESTRICT) |
| `variant_id` | BIGINT | no |  | FK -> product_variants.id (ON DELETE RESTRICT) |
| `quantity` | NUMERIC(12, 3) | no |  |  |
| `unit_price` | NUMERIC(12, 2) | no |  |  |
| `total_price` | NUMERIC(12, 2) | no |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- CHECK `ck_quote_items_quantity`: `quantity > 0`
- CHECK `ck_quote_items_total_price`: `total_price >= 0`
- CHECK `ck_quote_items_unit_price`: `unit_price > 0`
- INDEX `ix_quote_items_quote_version_id`: (quote_version_id)
- INDEX `ix_quote_items_request_item_id`: (request_item_id)

## Audit

### admin_action_logs

| Column | Type | Null | Default | Key / reference |
|---|---|---|---|---|
| `id` | BIGINT | no | identity | PK |
| `admin_user_id` | BIGINT | no |  | FK -> users.id (ON DELETE RESTRICT) |
| `action` | VARCHAR(100) | no |  |  |
| `resource_type` | VARCHAR(50) | no |  |  |
| `resource_id` | BIGINT | no |  |  |
| `previous_state` | VARCHAR(50) | yes |  |  |
| `new_state` | VARCHAR(50) | yes |  |  |
| `reason` | TEXT | yes |  |  |
| `created_at` | DATETIME | no | now() |  |

Constraints and indexes:

- INDEX `ix_admin_action_logs_admin_user_id`: (admin_user_id)
- INDEX `ix_admin_action_logs_created_at`: (created_at)
- INDEX `ix_admin_action_logs_resource`: (resource_type, resource_id)

