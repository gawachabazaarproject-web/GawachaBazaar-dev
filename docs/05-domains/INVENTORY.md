# Inventory, Reservations, Packaging and Suppliers

> **Status:** Verified (code + backend tests; concurrency covered by real-thread PostgreSQL tests). **Last verified:** 2026-10-14.
> **Source files:** [`services/inventory.py`](../../backend/app/services/inventory.py), [`inventory_reservation.py`](../../backend/app/services/inventory_reservation.py), [`reservation_state.py`](../../backend/app/services/reservation_state.py), [`stock_pool.py`](../../backend/app/services/stock_pool.py), [`stock_levels.py`](../../backend/app/services/stock_levels.py), [`stock_alerts.py`](../../backend/app/services/stock_alerts.py), [`packaging.py`](../../backend/app/services/packaging.py), [`supplier.py`](../../backend/app/services/supplier.py); routers `inventory.py`, `packaging.py`, `suppliers.py`; models `inventory_location`, `batch`, `inventory_lot`, `stock_movement`, `inventory_reservation(_item)`, `packaging_*`, `supplier*`.
> **Tests:** [`test_phase_11_inventory.py`](../../backend/tests/test_phase_11_inventory.py), [`test_phase_12_packaging.py`](../../backend/tests/test_phase_12_packaging.py), [`test_phase_15_inventory_reservation_fulfillment.py`](../../backend/tests/test_phase_15_inventory_reservation_fulfillment.py), [`test_phase_16_fulfillment_delivery.py`](../../backend/tests/test_phase_16_fulfillment_delivery.py), [`test_shared_stock_pool.py`](../../backend/tests/test_shared_stock_pool.py), [`test_stock_reserve_and_deletes.py`](../../backend/tests/test_stock_reserve_and_deletes.py), [`test_phase_17_supplier_bulk_commerce.py`](../../backend/tests/test_phase_17_supplier_bulk_commerce.py). Existing concurrency inventory: [`docs/testing/EXISTING_TEST_INVENTORY.md`](../testing/EXISTING_TEST_INVENTORY.md).

## Model

| Entity | Meaning | Important constraints |
|---|---|---|
| `inventory_locations` | Warehouse/hub (`code` unique, address, optional GPS, `ACTIVE/INACTIVE`, `is_packing_point`) | One packing point (partial unique index); delete and packing-point choice are ADMIN-only; a location holding stock cannot be deleted (admin UI message) |
| `batches` | A received supply of one product (supplier, farm or wholesaler optional; expiry date; status) | Batch and lot variant must belong to the same product (`get_or_create_lot_no_commit`) |
| `inventory_lots` | `quantity` and `reserved_quantity` of one variant from one batch at one location | `quantity >= 0`; `0 <= reserved_quantity <= quantity`; unique `(batch, variant, location)`; status `ACTIVE/INACTIVE/DEPLETED`; FIFO index `(variant_id, status, created_at, id)` |
| `stock_movements` | Append-only ledger | `quantity > 0`; types `RECEIPT, ADJUSTMENT_IN, TRANSFER_IN` (+) and `ADJUSTMENT_OUT, DAMAGE, WASTE, TRANSFER_OUT, DISPATCH` (−) |
| `inventory_reservations` (+ `_items`) | Stock promised to one order, split per lot | One reservation per order; `ACTIVE/COMMITTED/RELEASED/EXPIRED` |
| `packaging_operations` (+ inputs/outputs) | Convert input lots into labelled output lots atomically | – |
| `suppliers` (+ `supplier_products`, `supplier_evaluations`) | Supplier records, supplied products, ratings | Evaluations ADMIN-only |

## Core rules

1. **Quantity changes only through movements** (`apply_movement`, caller holds the lot row lock, no commit inside). A movement that would make quantity negative → 409; a `0` quantity marks the lot `DEPLETED`; a positive movement reactivates a `DEPLETED` lot; `INACTIVE` lots reject movements.
2. **Receive** (`POST /inventory/admin/receive`) is one atomic action: get-or-create the lot, lock it, apply a `RECEIPT`; with no `batch_id` a minimal batch (`ADMIN-<hex>`, harvest date today, status `APPROVED`) is created. Receive and `POST /inventory/lots/{id}/movements` accept either `quantity` (packs) or `amount` + `amount_unit` (KG/G/L/ML/UNIT/DOZEN); the server converts the amount into packs of the lot's variant (`stock_pool.weight_to_packs`: 1 kg into a 250 g variant = 4 packs, 1.1 kg = 4.4 packs). Customer-facing availability from the shared pool is floored to whole packs. Tests: `test_weight_to_packs.py` (pure); DB-backed inventory suites not re-run for this change.
3. **Reconcile** sets quantity to a physical count (difference recorded as an adjustment with the reason); **remove** takes out stock but never below the reserved amount (`available = quantity - reserved`); **transfer** is an atomic `TRANSFER_OUT` + `TRANSFER_IN` between locations. Raw `POST /inventory/lots/{id}/movements` and reconcile rely on the `reserved_quantity <= quantity` CHECK as the last defence (an `IntegrityError` becomes 409 "conflicting update").
4. **Shared stock pool:** sizes of one product in the same unit family (KG/G, L/ML, UNIT/DOZEN; BOX and PACK pool only with identical units) draw on one physical stock. A lot's quantity is in packs of *its own variant's* size; availability and allocation convert through each variant's size, rounding down.
5. **Reserve level / alerts** ([`stock_levels.py`](../../backend/app/services/stock_levels.py)): each variant has an optional `reserve_level` (default **10** when unset); `available <= 0` → OUT, `<= reserve` → BELOW, `<= reserve × 1.25` → NEAR. This only drives alerts and the dashboard — **it does not stop customers from buying below the reserve**. Lots expiring within 7 days (`EXPIRING_SOON_DAYS`) are flagged; expired lots are flagged as expired.
6. **Physical stock leaves only at delivery** (`DISPATCH`, see [ORDERS](ORDERS.md)); cancellation releases the *reservation* only.

## Reservations (the checkout side)

- **Create** (`create_reservation_for_order`, inside the checkout transaction): collect needed packs per variant; lock **every candidate lot** (own variant plus same-family siblings) in one `ORDER BY id ASC ... FOR UPDATE` query — the fixed order is what keeps concurrent checkouts deadlock-free; allocate **FIFO** (`created_at`, `id`; own-variant lots first, then siblings) in memory; if any variant cannot be fully covered raise 409 "doesn't have enough stock right now" with nothing written; otherwise increment `reserved_quantity` and write allocation rows; `expires_at = now + 30 minutes` (`RESERVATION_WINDOW_MINUTES`).
- **Commit** (`ACTIVE → COMMITTED`): on COD confirmation or payment success; fails if the reservation expired or was released — a late payment never resurrects it. Also creates the order's `fulfillments` row.
- **Release** (`ACTIVE|COMMITTED → RELEASED`): order cancelled (COMMITTED → RELEASED is the one allowed exception to COMMITTED being terminal).
- **Expire** (`ACTIVE → EXPIRED`): lazily when anything reads/acts on an overdue reservation, explicitly via `POST /inventory/reservations/{id}/expire` (staff), and by the **sweep** every 120 s (≤ 500 per tick; one transaction per reservation). Expiry also marks a still-`PENDING` order `EXPIRED`.
- Staff can list/inspect reservations (`GET /inventory/reservations`); customers can read their own order's reservation (`GET /orders/{id}/reservation`).

## Concurrency, idempotency, failures

| Scenario | Behaviour | Evidence |
|---|---|---|
| Two customers buy the last unit | Row locks serialise; exactly one reservation succeeds (the other 409) | existing real-thread tests; `test_money_integrity.py::test_two_customers_paying_for_the_last_unit_one_order_one_refund` |
| Expiry sweep vs payment commit vs cancel | One winner under the reservation/order locks; expiry is idempotent | `test_phase_15…` concurrency tests (`test_concurrency_c/d`, `test_concurrency_39`), [MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md) |
| Two replicas sweeping | Redundant work (each reports the same 12), correct end state (OPS-004) | experiment S5 |
| Delivery with a lot that can no longer cover its allocation | Whole transaction aborts, nothing written | `FulfillmentService.confirm_delivery` |
| Admin removes/transfers reserved stock | `remove_stock` refuses below reserved; raw movement relies on the CHECK | `inventory.py`, schema |

## Packaging and suppliers (summary)

Packaging operations (`DRAFT → IN_PROGRESS → COMPLETED`, or `CANCELLED`) hold input lots and output lots; **completion locks all input and output lots in one id-ordered pass and applies the movements in one transaction** ([`packaging.py`](../../backend/app/services/packaging.py)). Supplier records, supplied products, ADMIN-only evaluations and a performance summary are plain CRUD with row locks on read-modify-write ([`supplier.py`](../../backend/app/services/supplier.py)).

## Quantity model: exact base units (2026-10-27)

**Canonical unit.** Stock is accounted as an exact **integer** in the product family's base unit:
MASS = grams, VOLUME = millilitres, COUNT = pieces; BOX / PACK are their own unit (1 base unit each,
no invented conversion). One conversion layer: `backend/app/services/units.py`; clients carry an
identical copy (`Admin/lib/units.ts` = `mobile/src/utils/units.ts`), and `tests/test_units_parity.py`
fails if either drifts from the backend table. Mass is never converted to volume or count.

| Thing | Authoritative | Display / legacy |
|---|---|---|
| Size of a variant | `product_variants.size_base` (integer base units in ONE pack; follows quantity x unit) | `quantity`, `unit` |
| Lot stock | `inventory_lots.quantity_base`, `reserved_base` (BIGINT) | `quantity`, `reserved_quantity` (packs, 3 dp) - **derived by a DB trigger**, never the truth |
| Movement | `stock_movements.quantity_base` | `quantity` (packs, display) |
| Reservation allocation | `inventory_reservation_items.quantity_base` | `quantity` (packs, display) |
| Reserve level | `product_stock_reserves.reserve_base` (one physical amount per product & family) | `product_variants.reserve_level` (legacy per-size packs, used only when the product has no reserve row) |

**Invariants (asserted by `tests/test_inventory_base_units.py`):** `0 <= reserved_base <= quantity_base` per lot
(DB check); `sum(available) == shared pool + size-specific shares` (nothing counted twice, nothing lost); the
movement ledger sums to physical stock; **unit conversion alone never creates or destroys stock**.

**Sellable packs.** `floor((shared pool + that size's own share) / size_base)` - 68,999 g sells 275 x 250 g or 68 x 1 kg
(not 343). Shared = ordinary lots; "kept for this size" = share lots (`is_share`), sellable by that size only.

**Exact reservation.** An order for 250 g reserves exactly 250 g from any lot (a 3 kg lot goes 3000 -> 2750); delivery
consumes exactly the reserved base units; release restores exactly (100 reserve/release cycles are tested for 250 g, 1 pc,
5 pc, 1 dozen, 250 ml, 1 L). Receiving 5 pieces against a 1-dozen size stores 5, not 0.416 dozen.

**Never rounded.** An amount that is not a whole number of base units (half a gram) is refused (422), not rounded. The
batch row is a traceability record in the variant's own unit and is not used for accounting.

**Products selling only a dozen** still cannot sell single pieces (unchanged); internally their stock is pieces.

### Migration `e5f6a7b80923` (phase 1, additive) and what it did NOT touch

Adds the base columns, backfills them **only where exact**, creates `product_stock_reserves` and
`inventory_base_migration_report`, and installs trigger `trg_gb_sync_lot_base`. It **fails with a clear message** (changing
nothing) if any size is not a whole number of base units. A lot whose pack quantity is not an exact number of base units
(e.g. 0.416 dozen = 4.992 pieces), or that carries a live reservation that cannot be converted exactly, is **quarantined**
(`quantity_base` NULL): never sold, never moved, listed in `inventory_base_migration_report` (lot, product, size, old
quantity, calculated base, nearest representable base, difference, warehouse, batch/expiry) - nothing is rounded. An
admin confirms the true amount with `POST /inventory/admin/lots/{id}/resolve-base`. Reserve levels: a product whose sizes
all have an explicit level that agrees physically becomes one product reserve; every other case is reported as
`RESERVE_LEVEL_AMBIGUOUS` and keeps the legacy per-size rule. **Historical drift already caused by the old rounding
(2 g per order, fractional dozens) is not recoverable by the migration** - it can only be reported.
Downgrade drops the base columns (the pack columns stay consistent but lose exactness).

Phase 3 (retire the pack columns) is intentionally NOT done: the trigger still lets legacy writers (tests, scripts) write
packs; remove it only after confirming no code or consumer writes `quantity` / `reserved_quantity`.

## Known gaps

- `farms` and `quality_checks` have **no create/read API** or service; only `catalog.py` deletes quality checks with a product. Treat farm traceability as **not implemented** despite the tables ([KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md)).
- The reservation sweep is per process and not coordinated across replicas.
- Customer-facing availability for a product with no lots is 0 (no "unlimited" mode).
- No automated test covers the Admin inventory pages.

## Product-level stock actions (added 2026-10-26, uncommitted)

Staff talk about a *product and an amount*; the server picks the lots. Implemented in [`services/product_stock.py`](../../backend/app/services/product_stock.py), routes under `/inventory/admin/products/{id}/…` (see [API_REFERENCE](../03-api/API_REFERENCE.md)). Every action is **one transaction**: lots are locked in ascending id (the system-wide order), quantity changes only through `InventoryService.apply_movement`, stock reserved for orders is never taken, and one audit row (`inventory.correct_product` / `remove_product` / `move_product`) is created whose id is stamped on every movement (`reference_type` `product_correct|remove|move`).

| Action | Route (permission) | Rule |
|---|---|---|
| Correct stock | `POST …/products/{id}/correct` (`inventory.reconcile`) | Client sends the **count** in kg/g/L/ml/pcs/dozen; the server computes the difference against **on hand** (reserved stock is still physically there). A count below the reserved amount is refused. A warehouse (`location_id`) is required when stock is in more than one. |
| Remove stock | `POST …/products/{id}/remove` (`inventory.adjust`) | Amount + reason; movement type `DAMAGE` (reason contains "damag"), `WASTE` ("spoil", "waste", "expire") or `ADJUSTMENT_OUT`. Only available (unreserved) stock can go. |
| Move stock | `POST …/products/{id}/move` (`inventory.transfer`) | Source and destination lots locked in one ascending pass; destination lot is get-or-created for the same batch/size (expiry follows the stock); `TRANSFER_OUT`+`TRANSFER_IN` pairs. Destination must be an ACTIVE warehouse. |
| Undo | `POST …/stock-actions/{operation_id}/undo` | Compensating movements only (nothing is edited or deleted), same user (or ADMIN), within 30 minutes, once. Refused with 409 "can no longer be undone" if reversing would take stock that has since been reserved, sold or moved. |

**Allocation rule (business decision to confirm with the client):** a shortage is taken **oldest lot first** (the FIFO order checkout uses), stock shared by all sizes before stock assigned to one size; a surplus is added to the **newest** shared lot of the warehouse. No lot is created for a surplus: with no stock record the action asks to use Add stock first.

**Receive with expiry:** `POST /inventory/admin/receive` accepts `expiry_date` (not in the past, not together with `batch_id`) and stores it on the automatically created delivery (batch). Before this change normal receipts never had an expiry, so expiry alerts could not fire for them.

**Inventory page data:** `GET /inventory/admin/products` now also returns `stock_status` (OK/LOW/OUT), per-warehouse amounts (available and on hand), soonest expiry, and per-family `on_hand_amount` / `reserved_amount`; `?status=low|out|expiring` filters (judges every product, so it is the slower path) and `GET …/products/summary` gives the chip counts.

## One definition of "low" and "out" (2026-10-26)

`stock_levels.product_status` is the only rule: **OUT** = no live size can be sold (or there is none), **LOW** = some live size is out, at/below its low-stock level or close to it, **OK** otherwise. The Inventory chips and cards, the header alert (`products_out` / `products_low` in `GET /inventory/admin/stock-alerts`) and the Products list (`stock_status`) all use it, and only **ACTIVE** products can be low/out (a draft cannot be bought). The per-size list (`items`, "Restock list") is the detail behind it. "Expiring" = the soonest lot with stock expires within 7 days (or already has); dates follow `BAZAAR_TIMEZONE`.

## Who may operate on which warehouse

Nobody is limited: `inventory.*` permissions apply to every warehouse. There is no user-to-warehouse association in the data model and the PRD describes single-warehouse operation, so per-warehouse authorization is **not implemented and is an open decision** (KNOWN_ISSUES VAL-7). The Admin only shows a warehouse picker / Move when more than one active warehouse exists; that is convenience, not access control.

## Two different "oldest first" rules (do not confuse them)

| | Customer fulfilment | Staff stock actions |
|---|---|---|
| Where | `InventoryReservationService.create_reservation_for_order` | `ProductStockService._fifo` |
| Rule | Reserve FIFO by lot age at checkout (own size first, then sibling sizes) - approved, tested, concurrency-safe | Correct / remove / move take the **oldest** lot first, shared stock before a size's own share - **an assumption, not approved** |
| Effect | Decides which lot an order is promised from | Decides which lot loses (or gains) quantity when staff count, discard or move stock |

They share nothing: changing the staff rule cannot change checkout. Open question for the client: should discards/corrections take the lot that **expires first** instead (it may differ from the oldest)? Surplus found in a count goes to the newest shared lot of the warehouse.

