# Gawacha Bazaar Database Specification: Version 4 — Inventory & Stock

This document defines the database architecture and technical specifications for **Phase 4: Inventory & Stock** of the Gawacha Bazaar platform.

---

## 1. Business Context & Physical Process Flow

Gawacha Bazaar connects authentic rural farm produce directly with retail consumers. Having established Identity & Access (Phase 1), Farm Traceability (Phase 2), and Catalog & Products (Phase 3), Phase 4 establishes physical stock tracking across warehouses and distribution hubs.

### Core Business Purpose

The inventory domain answers the fundamental operational question:
> **"What stock do we currently have, in what form, where is it, and which farm batch did it come from?"**

### End-to-End Traceability Chain

Farm traceability is preserved without interruption:

```text
FARM (Village Origin, Owner Farmer)
  │
  ▼
BATCH (Harvest Date, Expiry Date, Origin Lot)
  │
  ▼
PRODUCT (Master Catalog Produce)
  │
  ▼
PRODUCT_VARIANT (SKU, Packaging Unit, e.g., 5 KG Mesh Bag)
  │
  ├──────────────────────────────────┐
  ▼                                  ▼
INVENTORY_LOT (Balance at Hub)    LOCATION (Physical Storage, Hub, Cold Storage)
  │
  ▼
STOCK_MOVEMENTS (Immutable Operational Ledger)
  │
  ▼
USER (Warehouse Manager / Operator)
```

---

## 2. Key Domain Decisions & Architectural Models

### 2.1 Operational Balance vs. Audit Ledger
Phase 4 implements a dual-structure inventory model:
1. **Current Operational Balance (`inventory_lots`)**:
   Represents the current physical stock balance for the unique tuple `(batch_id, variant_id, location_id)`.
   Fast queries for stock availability, picking, and checkout validation read directly from this table.
2. **Immutable Audit Ledger (`stock_movements`)**:
   An event-sourced audit ledger recording every quantity adjustment, receipt, dispatch, or damage event.
   Each movement points to the specific `inventory_lot` and the `user` who executed the operation.

```text
+------------------------+
|     STOCK MOVEMENT     |  (Historical event record, occurred_at)
+------------------------+
            │
            ▼ (Atomic transactional update)
+------------------------+
|     INVENTORY LOT      |  (Current balance: quantity, status)
+------------------------+
```

### 2.2 Strict Positive Movement Quantity Rule
In `stock_movements`, `quantity` is **always strictly positive** (`quantity > 0`):
- Direction is explicitly dictated by `movement_type`.
- Signed quantities are prohibited at the database constraint level.
- Zero-quantity movements are rejected at the database level.

| Movement Type | Sign Effect on Lot Balance | Operational Context |
| :--- | :--- | :--- |
| `RECEIPT` | **+ (Increase)** | Initial stock intake from farm harvest batch |
| `ADJUSTMENT_IN` | **+ (Increase)** | Inventory reconciliation (found surplus stock) |
| `ADJUSTMENT_OUT` | **- (Decrease)** | Inventory reconciliation (missing / count shortfall) |
| `DAMAGE` | **- (Decrease)** | Produce spoiled or damaged in transit/storage |
| `WASTE` | **- (Decrease)** | Expired or unmarketable produce written off |
| `TRANSFER_IN` | **+ (Increase)** | Stock received from another internal location |
| `TRANSFER_OUT` | **- (Decrease)** | Stock dispatched to another internal location |
| `DISPATCH` | **- (Decrease)** | Stock removed for retail fulfillment or customer order |

### 2.3 Inventory Lot Depletion & Status
`inventory_lots.quantity >= 0` is enforced by database constraint:
- A lot can legitimately reach `quantity = 0.000` when fully sold or transferred.
- Lots reaching zero balance are marked with status `DEPLETED`.
- Depleted lots are **never physically deleted** to maintain historical traceability.
- Valid lot statuses: `ACTIVE`, `INACTIVE`, `DEPLETED`.

### 2.4 Deletion Protection (`ON DELETE RESTRICT`)
All foreign key relationships in the inventory domain use `ON DELETE RESTRICT`:
- `batches` -> `inventory_lots` (`ON DELETE RESTRICT`)
- `product_variants` -> `inventory_lots` (`ON DELETE RESTRICT`)
- `inventory_locations` -> `inventory_lots` (`ON DELETE RESTRICT`)
- `inventory_lots` -> `stock_movements` (`ON DELETE RESTRICT`)
- `users` -> `stock_movements` (`ON DELETE RESTRICT`)

Traceability data and audit trails must never be lost due to cascading deletions.

### 2.5 Event-Based Audit Model (No `updated_at` on Movements)
- `stock_movements` represents immutable historical operational events.
- It includes `occurred_at` (when the physical activity took place) and `created_at` (audit timestamp).
- It intentionally does **not** include `updated_at`.

### 2.6 Loose Future Reference Fields
- `reference_type VARCHAR(50) NULL`
- `reference_id BIGINT NULL`
- These columns allow future domains (Orders, Preparation, Dispatch, Returns) to link movements to business transactions without introducing early foreign keys or complex polymorphic frameworks.

### 2.7 Intentionally Excluded from Phase 4
- Processing / Packing / Preparation (reserved for future domain)
- Carts / Reservations / Orders / Order Items
- Payments / Delivery / Logistics routes
- Coupons / Promotions / Reviews
- Suppliers / Procurement domain
- Warehouses as a separate complex domain
- Stock snapshots / Stock reservations
- Database triggers (balance updates will be atomic in application service layer)
- PostgreSQL ENUM types (`VARCHAR` + `CheckConstraint` used throughout)

---

## 3. Detailed Table Specifications

### 3.1 `inventory_locations`
Represents physical locations (hubs, cold storage units, packing facilities) capable of holding produce.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `name` | `VARCHAR(150)` | `NO` | — | Friendly location name (e.g., "Gawacha Bazaar Main Hub") |
| `code` | `VARCHAR(50)` | `NO` | — | Unique location identifier code (e.g., "GB-HUB-01") |
| `type` | `VARCHAR(30)` | `NO` | — | Location classification (e.g., "COLD_STORAGE", "WAREHOUSE") |
| `address_line_1` | `VARCHAR(255)` | `NO` | — | Primary street address |
| `address_line_2` | `VARCHAR(255)` | `YES` | `NULL` | Secondary address / unit number |
| `city` | `VARCHAR(100)` | `NO` | — | City / Municipality |
| `state` | `VARCHAR(100)` | `NO` | — | State / Province |
| `postal_code` | `VARCHAR(20)` | `NO` | — | Postal / ZIP code |
| `status` | `VARCHAR(30)` | `NO` | — | Operational status (`ACTIVE`, `INACTIVE`) |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record modification timestamp |

#### Constraints & Indexes
- **Primary Key**: `PRIMARY KEY (id)`
- **Unique Constraint**: `uq_inventory_locations_code` ON `(code)`
- **Check Constraint**: `ck_inventory_locations_status` CHECK `status IN ('ACTIVE', 'INACTIVE')`
- **Indexes**:
  - `ix_inventory_locations_type` ON `(type)`
  - `ix_inventory_locations_status` ON `(status)`
  - Note: An explicit index on `code` is omitted as the `UNIQUE` constraint already creates the backing index.

---

### 3.2 `inventory_lots`
Represents the current physical balance for a specific Batch, Product Variant, and Location combination.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `batch_id` | `BIGINT` | `NO` | — | Origin harvest batch (`batches.id`) |
| `variant_id` | `BIGINT` | `NO` | — | Sellable product packaging variant (`product_variants.id`) |
| `location_id` | `BIGINT` | `NO` | — | Storage facility (`inventory_locations.id`) |
| `quantity` | `NUMERIC(12,3)`| `NO` | — | Current stock balance quantity |
| `status` | `VARCHAR(30)` | `NO` | — | Lot status (`ACTIVE`, `INACTIVE`, `DEPLETED`) |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record modification timestamp |

#### Constraints & Indexes
- **Primary Key**: `PRIMARY KEY (id)`
- **Foreign Keys**:
  - `fk_inventory_lots_batch_id_batches` FOREIGN KEY (`batch_id`) REFERENCES `batches(id)` ON DELETE RESTRICT
  - `fk_inventory_lots_variant_id_product_variants` FOREIGN KEY (`variant_id`) REFERENCES `product_variants(id)` ON DELETE RESTRICT
  - `fk_inventory_lots_location_id_inventory_locations` FOREIGN KEY (`location_id`) REFERENCES `inventory_locations(id)` ON DELETE RESTRICT
- **Unique Constraint**: `uq_inventory_lots_batch_variant_location` ON `(batch_id, variant_id, location_id)`
  *Guarantees a single authoritative inventory balance per Batch + Variant + Location.*
- **Check Constraints**:
  - `ck_inventory_lots_quantity` CHECK `quantity >= 0`
  - `ck_inventory_lots_status` CHECK `status IN ('ACTIVE', 'INACTIVE', 'DEPLETED')`
- **Indexes**:
  - `ix_inventory_lots_batch_id` ON `(batch_id)`
  - `ix_inventory_lots_variant_id` ON `(variant_id)`
  - `ix_inventory_lots_location_id` ON `(location_id)`
  - `ix_inventory_lots_status` ON `(status)`

*Note: `product_id` is intentionally omitted from `inventory_lots` because product identity is fully and unambiguously derivable through `inventory_lot.variant.product`.*

---

### 3.3 `stock_movements`
The immutable ledger documenting every inventory quantity modification event.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `inventory_lot_id` | `BIGINT` | `NO` | — | Affected inventory lot (`inventory_lots.id`) |
| `movement_type` | `VARCHAR(30)` | `NO` | — | Movement category |
| `quantity` | `NUMERIC(12,3)`| `NO` | — | Movement quantity (strictly positive) |
| `reference_type` | `VARCHAR(50)` | `YES` | `NULL` | Business entity type (e.g., "ORDER", "RECEIPT") |
| `reference_id` | `BIGINT` | `YES` | `NULL` | Business entity identifier |
| `performed_by_user_id` | `BIGINT` | `NO` | — | Operator user ID (`users.id`) |
| `occurred_at` | `TIMESTAMPTZ` | `NO` | — | Timestamp when event physically occurred |
| `remarks` | `TEXT` | `YES` | `NULL` | Operational notes or audit explanations |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation audit timestamp |

#### Constraints & Indexes
- **Primary Key**: `PRIMARY KEY (id)`
- **Foreign Keys**:
  - `fk_stock_movements_inventory_lot_id_inventory_lots` FOREIGN KEY (`inventory_lot_id`) REFERENCES `inventory_lots(id)` ON DELETE RESTRICT
  - `fk_stock_movements_performed_by_user_id_users` FOREIGN KEY (`performed_by_user_id`) REFERENCES `users(id)` ON DELETE RESTRICT
- **Check Constraints**:
  - `ck_stock_movements_quantity` CHECK `quantity > 0`
  - `ck_stock_movements_movement_type` CHECK `movement_type IN ('RECEIPT', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', 'DAMAGE', 'WASTE', 'TRANSFER_IN', 'TRANSFER_OUT', 'DISPATCH')`
- **Indexes**:
  - `ix_stock_movements_inventory_lot_id` ON `(inventory_lot_id)`
  - `ix_stock_movements_performed_by_user_id` ON `(performed_by_user_id)`
  - `ix_stock_movements_movement_type` ON `(movement_type)`
  - `ix_stock_movements_occurred_at` ON `(occurred_at)`

---

## 4. SQLAlchemy Model Mappings

The following typed SQLAlchemy 2.x mappings implement this domain:

### `InventoryLocation` ([inventory_location.py](file:///D:/Gawachabazaar/backend/app/models/inventory_location.py))
- `lots: Mapped[list["InventoryLot"]] = relationship("InventoryLot", back_populates="location")`

### `InventoryLot` ([inventory_lot.py](file:///D:/Gawachabazaar/backend/app/models/inventory_lot.py))
- `batch: Mapped["Batch"] = relationship("Batch")`
- `variant: Mapped["ProductVariant"] = relationship("ProductVariant")`
- `location: Mapped["InventoryLocation"] = relationship("InventoryLocation", back_populates="lots")`
- `movements: Mapped[list["StockMovement"]] = relationship("StockMovement", back_populates="inventory_lot")`

### `StockMovement` ([stock_movement.py](file:///D:/Gawachabazaar/backend/app/models/stock_movement.py))
- `inventory_lot: Mapped["InventoryLot"] = relationship("InventoryLot", back_populates="movements")`
- `performed_by_user: Mapped["User"] = relationship("User")`

---

## 5. Migration Lineage

- **Parent Revision**: `9fb24ab99384` (`create_phase_3_catalog_and_products`)
- **Phase 4 Revision**: `ff073dad9cfc` (`create_phase_4_inventory_and_stock`)
- **Downgrade Safety**: Fully reversible in strict reverse-dependency order:
  1. `stock_movements`
  2. `inventory_lots`
  3. `inventory_locations`
