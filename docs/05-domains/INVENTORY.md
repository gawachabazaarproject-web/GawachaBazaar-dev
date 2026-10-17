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

## Known gaps

- `farms` and `quality_checks` have **no create/read API** or service; only `catalog.py` deletes quality checks with a product. Treat farm traceability as **not implemented** despite the tables ([KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md)).
- The reservation sweep is per process and not coordinated across replicas.
- Customer-facing availability for a product with no lots is 0 (no "unlimited" mode).
- No automated test covers the Admin inventory pages.
