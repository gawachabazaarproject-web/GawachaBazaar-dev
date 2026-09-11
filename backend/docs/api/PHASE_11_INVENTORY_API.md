# Phase 11 — Inventory & Stock API

Turns the existing Phase 4 inventory schema (`inventory_locations`,
`inventory_lots`, `stock_movements`) into a real API. No schema migration
was required or created - the tables already had the correct shape.
**Internal staff only** - there is no public inventory API.

All endpoints are under `/api/v1/inventory`, registered in
[`app/api/v1/router.py`](../../app/api/v1/router.py). Implementation:
[`app/api/v1/inventory.py`](../../app/api/v1/inventory.py) (routes, HTTP
only) → [`app/services/inventory.py`](../../app/services/inventory.py)
(`InventoryService`, all business logic, locking, and queries) →
[`app/schemas/inventory.py`](../../app/schemas/inventory.py) (Pydantic v2
contracts) → existing SQLAlchemy models.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/inventory/locations` | Create a location. 409 on duplicate `code`. |
| GET | `/inventory/locations` | Paginated list, optional `status` filter. |
| GET | `/inventory/locations/{id}` | Get one location. |
| PATCH | `/inventory/locations/{id}` | Partial update, including ACTIVE/INACTIVE lifecycle. |
| POST | `/inventory/lots` | Create a lot. See Lot Validation below. |
| GET | `/inventory/lots` | Paginated list, filters: `batch_id`, `variant_id`, `location_id`, `status`. |
| GET | `/inventory/lots/{id}` | Get one lot. |
| POST | `/inventory/lots/{lot_id}/movements` | **The only way `quantity` changes.** |
| GET | `/inventory/lots/{lot_id}/movements` | Paginated, read-only history. Filters: `movement_type`, `performed_by_user_id`, `occurred_from`, `occurred_to`. |

**Deliberately absent**: `PATCH /inventory/lots/{id}` (no direct quantity
mutation - INVARIANT 5), `DELETE` on locations (`ON DELETE RESTRICT` makes
this unsafe - use `status`), `DELETE` on lots, and any `PATCH`/`DELETE` on
movements (append-only audit history - INVARIANT 11).

## Authorization

Every route in this domain requires one of `ADMIN`, `HUB_STAFF`,
`OPERATIONS` (`require_roles(ADMIN, HUB_STAFF, OPERATIONS)` applied at the
router level - read and mutation roles are identical in Phase 11, so there
is no separate read-only dependency set). `CUSTOMER`, `WHOLESALER`, and
`DELIVERY_PARTNER` get 403 on every route. Unauthenticated requests get 401.
Reuses Phase 9's `get_current_user`/`require_roles` unchanged - no new
authorization mechanism.

## Stock Movement: Atomicity, Locking, and a Transaction-Design Note

`InventoryService.create_movement` is the one place `inventory_lots.quantity`
can change:

```
SELECT inventory_lots WHERE id = :lot_id FOR UPDATE   -- row lock acquired
  → validate lot.status != INACTIVE
  → delta = direction(movement_type) * quantity
  → new_quantity = lot.quantity + delta
  → validate new_quantity >= 0                         -- else 409, no writes
  → lot.quantity = new_quantity; lot.status = ...
  → INSERT stock_movements row
  → COMMIT (single commit call)
```

If any validation fails, an exception is raised before any write - nothing
is mutated, and the session's uncommitted work (including the held lock) is
discarded when the request's session closes. If everything succeeds, the
lot update and the movement insert commit together in the same transaction
- INVARIANT 4 (no successful quantity change without a movement record, and
vice versa) holds structurally, not by convention.

**Transaction-design note (important for future services in this codebase):**
`create_movement` does **not** call `db.begin()`. Every route here is
protected by `require_roles`, which composes `get_current_user`, which
always issues its own SELECTs against the shared request-scoped session
before the route handler runs. SQLAlchemy 2.0 autobegins a transaction on
that first read, so by the time `create_movement` runs, the session is
already inside a transaction. Calling `db.begin()` at that point either
raises (`"A transaction is already begun on this Session"`) or - as
discovered and fixed in Phase 10's image primary-swap logic - silently
degrades into a nested savepoint that never gets a real top-level commit,
so a write can report success while being rolled back on session close.
The fix, used consistently here: perform the locking SELECT, validation,
and writes directly against the already-open transaction, then call
`db.commit()` exactly once. Atomicity comes from "no commit until every
step succeeds," not from which API opened the transaction.

## Row Locking & Concurrency

`with_for_update()` on the lot SELECT (same idiom already used by
`AuthService.refresh_session` for refresh-token rotation) takes a
PostgreSQL row lock held until commit/rollback. A second concurrent request
against the same lot blocks at the database level until the first
transaction finishes, then reads the now-current (committed) quantity -
never a stale read. Verified by
`test_22_concurrent_dispatch_cannot_oversell` in
[`tests/test_phase_11_inventory.py`](../../tests/test_phase_11_inventory.py):
starting quantity 10, concurrent `DISPATCH 8` and `DISPATCH 7` (sum 15 > 10)
- exactly one succeeds (409 for the other), final quantity is 2 or 3, never
negative, and exactly one movement row exists.

## Negative Stock Protection

`new_quantity < 0` is rejected with `ConflictError` (409) **before** any
write happens - not clamped to zero, not partially applied. Verified by
re-reading the database after a rejected request: quantity unchanged, zero
movement rows created.

## Movement Semantics (centralized, one place)

```python
_MOVEMENT_DIRECTION = {
    "RECEIPT": 1, "ADJUSTMENT_IN": 1, "TRANSFER_IN": 1,
    "ADJUSTMENT_OUT": -1, "DAMAGE": -1, "WASTE": -1,
    "TRANSFER_OUT": -1, "DISPATCH": -1,
}
```

The client always supplies `quantity > 0` (Pydantic `Field(gt=0)`); the sign
is derived here, once, in `InventoryService`, and never duplicated in the
router.

## Lot Status Transitions

| Current status | Event | New status |
|---|---|---|
| `ACTIVE` | outgoing movement, result `> 0` | `ACTIVE` (unchanged) |
| `ACTIVE` | movement (either direction), result `== 0` | `DEPLETED` |
| `DEPLETED` | positive movement | `ACTIVE` |
| `INACTIVE` | any movement | **rejected**, 422 `BUSINESS_VALIDATION_ERROR` |

`INACTIVE` never auto-activates from a movement - the lot must be
explicitly reactivated first (no such endpoint exists yet in Phase 11;
lots don't have a status-change endpoint, only creation and movements).
This is a deliberate, conservative choice given the spec's instruction to
"reject cleanly rather than silently changing the state" for ambiguous
cases.

## Lot Creation Validation

`POST /inventory/lots` validates, in order: batch exists (404), variant
exists (404), location exists (404), **`batch.product_id == variant.product_id`**
(422 `BUSINESS_VALIDATION_ERROR` - INVARIANT 9; the database does not
enforce this, so it must be checked here), then attempts the insert,
translating the `uq_inventory_lots_batch_variant_location` unique
constraint violation into 409 (INVARIANT 10). Initial `status` is derived
from `quantity` (`ACTIVE` if `> 0`, else `DEPLETED`) and is never
client-supplied.

## Unresolved Business Decision: Batch Eligibility for Inventory

Per the task's explicit instruction not to invent an irreversible business
rule, **lot creation does not currently restrict which `batches.status`
values are eligible for inventory** (e.g. it does not require
`status = 'APPROVED'`). No existing documentation, migration, or prior
phase establishes such a rule - `docs/database/DATABASE_SCHEMA_V2.md`
documents the `batches.status` CHECK constraint values but no eligibility
policy. **This is an open decision for a future phase**, not an oversight:
introducing it now would be inventing business logic without a source of
truth. If/when this is decided, the natural place to enforce it is
`InventoryService.create_lot`, immediately after the batch-existence check.

## No Transfer Entity

`TRANSFER_IN`/`TRANSFER_OUT` are recorded as ordinary movements against a
single lot, exactly like every other movement type. There is no
`inventory_transfers` table and no cross-location atomic transfer workflow
in Phase 11 - the database has no such entity, and inventing one wasn't in
scope. A real transfer (moving stock from lot A at location X to lot B at
location Y as one atomic operation, sharing a transfer identity) would need
a dedicated design - two-lot locking order, a transfer record, etc. - and is
explicitly deferred, not faked.

## No Idempotency Mechanism

There is no idempotency-key mechanism anywhere in this codebase yet (this
was confirmed by inspection, not assumed). A duplicate HTTP retry of
`POST /inventory/lots/{id}/movements` (e.g. a client retrying after a
timeout that the server actually processed) **will create a second,
distinct movement and apply its effect twice** - there is nothing in this
phase preventing that. This is a known limitation, not a bug: introducing a
generalized idempotency-key system was explicitly out of scope for Phase
11. **A future idempotency mechanism should be introduced before this
endpoint is used in production**, particularly once it's driven by
automated systems (packaging, delivery) rather than only manual staff
entry.

## Domain Boundaries (unchanged)

- **No catalog changes.** Product/variant status is untouched by inventory
  state; there is no "in stock" catalog behavior.
- **No cart/order/checkout integration.** No stock reservation, no
  deduction on order creation.
- **No packaging integration.** Packaging will eventually call
  `InventoryService`'s movement logic transactionally, but does not yet.
- **No public access.** `inventory_lots`, `stock_movements`, and location
  operational data are never exposed to `CUSTOMER`.

## Performance

Lot and movement listings query only the columns/rows needed for their
response shape - no eager-loading of `movements`, `performed_by_user`, or
full product/batch objects into a list response. Existing Phase 4 indexes
(`ix_inventory_lots_batch_id`, `ix_inventory_lots_variant_id`,
`ix_inventory_lots_location_id`, `ix_inventory_lots_status`,
`ix_stock_movements_inventory_lot_id`, `ix_stock_movements_movement_type`,
`ix_stock_movements_occurred_at`) cover every filter this API exposes - no
new indexes were added or needed.

## A Bug Found and Fixed Outside This Domain

Writing `test_12_non_positive_quantity_rejected` (a required Phase 11 test:
"quantity <= 0 rejected") surfaced a pre-existing bug in the shared
[`app/exceptions/handlers.py`](../../app/exceptions/handlers.py)
`validation_exception_handler`: Pydantic v2's `RequestValidationError.errors()`
can include a raw `Decimal` in an error's `ctx` (from a `Field(gt=0)`
constraint on a `Decimal` field - `Field(quantity, gt=0)` here, and
also present in Phase 10's `price`/`quantity` fields). The handler passed
`exc.errors()` straight into `JSONResponse`, whose `json.dumps` cannot
serialize `Decimal` - so instead of the required 422, the request crashed
with an unhandled 500. This was latent since Phase 10 but never actually
triggered by a failing request in any prior test. Fixed with a one-line
change: wrap `exc.errors()` in FastAPI's `jsonable_encoder()`. This is a
correctness fix to already-shared, already-used code (every domain's 422
responses go through this handler), not a Phase 11-specific change -
verified with a full regression of `test_phase_10_catalog.py`,
`test_phase_9_rbac.py`, and `test_auth.py` afterward, all passing.
