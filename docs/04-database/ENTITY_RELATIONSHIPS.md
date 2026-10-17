# Entity Relationships

> **Status:** Verified (generated from the SQLAlchemy foreign keys on 2026-10-14; 82 foreign keys, 50 tables). Column-level detail: [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).
> **Reading the diagrams:** `A ||--o{ B` = each B belongs to exactly one A, an A may have many B; `|o` on the left = the reference is nullable; `o|` on the right = at most one B per A (a **full** unique constraint on the foreign key). Partial unique indexes (one default address per user, one ACTIVE cart per user, one primary role per user, one primary image per product) are **not** drawn as one-to-one. Shared tables appear in several diagrams. Labels are the foreign-key column.

## Identity and access

```mermaid
erDiagram
  users ||--o{ addresses : "user_id"
  users ||--o{ admin_action_logs : "admin_user_id"
  users ||--o{ customer_notes : "user_id"
  users ||--o{ customer_notes : "author_admin_user_id"
  users ||--o{ push_tokens : "user_id"
  roles ||--o{ user_roles : "role_id"
  users ||--o{ user_roles : "user_id"
  users ||--o{ wishlist_items : "user_id"
  products ||--o{ wishlist_items : "product_id"
```

## Catalogue

```mermaid
erDiagram
  categories |o--o{ categories : "parent_id"
  categories ||--o{ products : "category_id"
  products ||--o{ product_images : "product_id"
  products ||--o{ product_variants : "product_id"
  product_variants ||--o{ prices : "variant_id"
```

Categories nest exactly one level (enforced in `CatalogService._validate_parent`; the database only forbids `parent_id = id`).

## Supply and packaging

```mermaid
erDiagram
  users ||--o{ farms : "owner_user_id"
  users ||--o{ packaging_operations : "performed_by_user_id"
  inventory_locations ||--o{ packaging_operations : "location_id"
  suppliers ||--o{ supplier_evaluations : "supplier_id"
  users ||--o{ supplier_evaluations : "evaluated_by_user_id"
  suppliers |o--o{ batches : "supplier_id"
  farms |o--o{ batches : "farm_id"
  users |o--o{ batches : "wholesaler_user_id"
  suppliers ||--o{ supplier_products : "supplier_id"
  batches ||--o{ inventory_lots : "batch_id"
  inventory_locations ||--o{ inventory_lots : "location_id"
  product_variants ||--o{ inventory_lots : "variant_id"
  users ||--o{ quality_checks : "checked_by_user_id"
  batches ||--o{ quality_checks : "batch_id"
  packaging_operations ||--o{ packaging_inputs : "packaging_operation_id"
  inventory_lots ||--o{ packaging_inputs : "inventory_lot_id"
  packaging_operations ||--o{ packaging_outputs : "packaging_operation_id"
  inventory_lots ||--o{ packaging_outputs : "inventory_lot_id"
```

`supplier_products` also references `products` (a supplier supplies products, not variants). `farms` and `quality_checks` have no API or service code that creates them (only `catalog.py` deletes `quality_checks` when a product is deleted).

## Inventory and reservations

```mermaid
erDiagram
  batches ||--o{ inventory_lots : "batch_id"
  inventory_locations ||--o{ inventory_lots : "location_id"
  product_variants ||--o{ inventory_lots : "variant_id"
  orders ||--o| inventory_reservations : "order_id"
  orders ||--o{ order_items : "order_id"
  product_variants ||--o{ order_items : "variant_id"
  inventory_reservations ||--o{ inventory_reservation_items : "reservation_id"
  order_items ||--o{ inventory_reservation_items : "order_item_id"
  inventory_lots ||--o{ inventory_reservation_items : "inventory_lot_id"
  inventory_lots ||--o{ stock_movements : "inventory_lot_id"
  users ||--o{ stock_movements : "performed_by_user_id"
```

A reservation (one per order) is split into per-lot allocation rows; `inventory_lots.reserved_quantity` is the sum of ACTIVE/COMMITTED allocations (kept in step by the services, bounded by the `reserved_quantity <= quantity` CHECK).

## Cart, checkout and orders

```mermaid
erDiagram
  users ||--o{ addresses : "user_id"
  users ||--o{ carts : "user_id"
  carts ||--o{ cart_items : "cart_id"
  product_variants ||--o{ cart_items : "variant_id"
  carts |o--o| orders : "cart_id"
  users ||--o{ orders : "user_id"
  users |o--o{ orders : "cancelled_by_user_id"
  promotions |o--o{ orders : "promotion_id"
  orders ||--o| order_addresses : "order_id"
  orders ||--o{ order_items : "order_id"
  product_variants ||--o{ order_items : "variant_id"
  users ||--o{ checkout_sessions : "user_id"
  carts ||--o{ checkout_sessions : "cart_id"
  orders |o--o{ checkout_sessions : "order_id"
```

`order_items` and `order_addresses` are **snapshots** (name, SKU, unit, price, address text and coordinates are copied at checkout). `checkout_sessions.address_id` is a plain column **without a foreign key**, so an address can be deleted between payment and order creation; the checkout then fails and the payment is refunded (`CheckoutSessionService._finalize`).

## Payments, refunds and fulfilment

```mermaid
erDiagram
  orders ||--o| payments : "order_id"
  orders ||--o| refunds : "order_id"
  orders ||--o| fulfillments : "order_id"
  users |o--o{ fulfillments : "delivery_partner_user_id"
  payments ||--o{ refunds : "payment_id"
  users |o--o{ refunds : "approved_by_user_id"
  payments ||--o{ payment_transactions : "payment_id"
  refunds |o--o{ payment_transactions : "refund_id"
  payment_transactions |o--o{ payment_webhook_events : "payment_transaction_id"
```

At most one payment, one refund and one fulfillment per order. `payment_transactions` records each gateway attempt (payment or refund). `payment_webhook_events` holds every received webhook, linked to a transaction only once resolved.

## Promotions

```mermaid
erDiagram
  users ||--o{ promotions : "created_by_user_id"
  promotions ||--o{ promotion_targets : "promotion_id"
  promotions ||--o{ promotion_eligible_customers : "promotion_id"
  users ||--o{ promotion_eligible_customers : "user_id"
  promotions ||--o{ promotion_redemptions : "promotion_id"
  users ||--o{ promotion_redemptions : "customer_user_id"
  orders ||--o| promotion_redemptions : "order_id"
  promotions |o--o{ orders : "promotion_id"
```

`promotion_targets` stores its target generically (`target_type` + `target_id`, **no foreign key** to the target table), so a deleted product or category can leave a dangling target; only `promotion_id` is a real foreign key.

## Bulk commerce

```mermaid
erDiagram
  users ||--o| bulk_customer_profiles : "user_id"
  users ||--o{ bulk_order_requests : "customer_user_id"
  addresses |o--o{ bulk_order_requests : "address_id"
  orders |o--o| bulk_order_requests : "order_id"
  bulk_order_requests ||--o{ bulk_order_request_items : "request_id"
  bulk_order_requests ||--o| quotes : "request_id"
  quotes ||--o{ quote_versions : "quote_id"
  users ||--o{ quote_versions : "created_by_user_id"
  quote_versions ||--o{ quote_items : "quote_version_id"
  bulk_order_request_items ||--o{ quote_items : "request_item_id"
  product_variants ||--o{ quote_items : "variant_id"
```

## Delete behaviour (what a deletion would do)

Of the 82 foreign keys, **64 are `ON DELETE RESTRICT`**, **17 are `CASCADE`** and **1 is `SET NULL`**.

| Parent → child | Rule | Practical effect |
|---|---|---|
| `users` → `orders`, `payments` (via orders), `refunds`, `fulfillments`, `promotion_redemptions`, `stock_movements`, `admin_action_logs`, `quote_versions`, `packaging_operations`, … | RESTRICT | A user who ever ordered or acted as staff cannot be hard-deleted |
| `users` → `addresses`, `customer_notes`, `push_tokens`, `user_roles`, `wishlist_items`, `checkout_sessions`, `bulk_customer_profiles`, `promotion_eligible_customers` | CASCADE | Deleting a user removes these |
| `products` → `product_images`, `wishlist_items` | CASCADE | Product deletion removes photos and wishlist entries (variants/prices/lots are removed explicitly by `CatalogService.delete_product`, which refuses when dependencies exist) |
| `carts` → `cart_items`, `checkout_sessions`; `promotions` → `promotion_targets`, `promotion_eligible_customers`; bulk request/quote children | CASCADE | Child rows follow their parent |
| `orders` → `checkout_sessions.order_id` | SET NULL | Session survives order removal (orders are never deleted by the application) |
| everything else (catalog, inventory, payments, refunds) | RESTRICT | History cannot be orphaned |

There is **no API to delete a user or an order**; `DELETE` routes exist only for addresses, cart items, wishlist items, categories (and their image), product images, products and variants, ads, home slides, inventory locations, packaging inputs/outputs, and staff role revocation ([API_REFERENCE](../03-api/API_REFERENCE.md)). See [DATA_RETENTION](DATA_RETENTION.md).
