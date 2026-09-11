# Phase 12 — Packaging & Labeling API

Turns the existing Phase 5 packaging schema (`packaging_operations`,
`packaging_inputs`, `packaging_outputs`) into a real API. No schema
migration was required or created - the tables already had the correct
shape. **Internal staff only** (`ADMIN`, `HUB_STAFF`, `OPERATIONS`) - there
is no public or customer-facing packaging API.

Packaging means final business preparation - packaging and labeling raw
inventory into customer-ready product. It is explicitly **not**
manufacturing, cooking, recipes, BOM, or yield management. No labels
table/schema was created in this phase - exact label requirements are not
finalized.

All endpoints are under `/api/v1/packaging`, registered in
[`app/api/v1/router.py`](../../app/api/v1/router.py). Implementation:
[`app/api/v1/packaging.py`](../../app/api/v1/packaging.py) (routes) →
[`app/services/packaging.py`](../../app/services/packaging.py)
(`PackagingService`) → [`app/schemas/packaging.py`](../../app/schemas/packaging.py)
→ existing SQLAlchemy models. Reuses
[`app/services/inventory.py`](../../app/services/inventory.py)'s
`InventoryService` for the actual stock mutation, rather than duplicating
quantity/movement logic - see "Reused Inventory Behavior" below.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/packaging/operations` | Create an operation (`DRAFT`). |
| GET | `/packaging/operations` | Paginated list. Filters: `status`, `location_id`. |
| GET | `/packaging/operations/{id}` | Full detail, including current inputs and outputs. |
| POST | `/packaging/operations/{id}/start` | `DRAFT` → `IN_PROGRESS`. |
| POST | `/packaging/operations/{id}/cancel` | `DRAFT`/`IN_PROGRESS` → `CANCELLED`. |
| POST | `/packaging/operations/{id}/complete` | **The atomic business transaction.** See below. |
| POST | `/packaging/operations/{id}/inputs` | Record a source inventory lot. Does **not** touch inventory. |
| DELETE | `/packaging/operations/{id}/inputs/{input_id}` | Remove an input (only while `DRAFT`/`IN_PROGRESS`). |
| POST | `/packaging/operations/{id}/outputs` | Declare a packaged output. Resolves/creates its inventory lot; does **not** yet change its quantity. |
| DELETE | `/packaging/operations/{id}/outputs/{output_id}` | Remove an output (only while `DRAFT`/`IN_PROGRESS`). |

**Deliberately absent**: no `PATCH` anywhere (lifecycle changes are explicit
actions, not field edits), no `DELETE` on operations, no way to edit an
input/output's quantity in place (remove and re-add instead).

## Authorization

Every route requires one of `ADMIN`, `HUB_STAFF`, `OPERATIONS`
(`require_roles(ADMIN, HUB_STAFF, OPERATIONS)` at the router level, same
pattern as Phase 11's inventory router). `CUSTOMER`, `WHOLESALER`, and
`DELIVERY_PARTNER` get 403. Unauthenticated requests get 401. Reuses Phase
9's `get_current_user`/`require_roles` unchanged.

## Operation Lifecycle

```
DRAFT ──start──> IN_PROGRESS ──complete──> COMPLETED
  │                    │
  └──cancel──> CANCELLED <──cancel────┘
```

`COMPLETED` and `CANCELLED` are terminal - any further lifecycle action
(`start`, `cancel`, `complete`) or input/output mutation on either returns
409. Invalid transitions never reach the database in a half-applied state;
the status check happens before any other work.

**`started_at` note**: `packaging_operations.started_at` is `NOT NULL` with
no server default on this (frozen, Phase 5) table - meaning it must be set
even for a brand-new `DRAFT` row. `create_operation` sets it to the creation
timestamp; `/start` does not touch it again. This is a necessary
interpretation of the existing frozen schema, not a new design choice -
flagged here because the column name suggests it should only be set at the
`/start` transition, which the `NOT NULL` constraint doesn't actually allow.

## Completion: The Atomic Business Transaction

`PackagingService.complete_operation` (only callable when `IN_PROGRESS`):

```
1.  SELECT packaging_operations WHERE id = :id FOR UPDATE   -- serializes concurrent completion
2.  validate status == IN_PROGRESS                          -- else 409, nothing touched
3.  load inputs, outputs for this operation
4.  validate inputs non-empty, outputs non-empty             -- else 409
5.  validate sum(outputs.total_quantity) <= sum(inputs.quantity) -- else 409
6.  re-validate output batch traceability against CURRENT inputs -- else 409
7.  SELECT inventory_lots WHERE id IN (all input+output lot ids)
    ORDER BY id FOR UPDATE                                   -- single query, consistent lock order
8.  for each input:  apply_movement(lot, ADJUSTMENT_OUT, input.quantity, ...)
9.  for each output: apply_movement(lot, RECEIPT, output.total_quantity, ...)
10. operation.status = COMPLETED; operation.completed_at = now()
11. db.commit()                                               -- single commit, everything or nothing
```

If any step raises, nothing before it is committed - the whole attempt is
discarded when the session closes (see Transaction Design Note below).
Step 8/9's `apply_movement` calls are the same validated core `create_movement`
uses (insufficient stock still raises 409 there, per-lot), so negative
stock is impossible here for exactly the same reason it's impossible via
the inventory movement endpoint directly.

### Transaction Design Note (read before touching this code)

Every route here is protected by `require_roles`, which composes
`get_current_user`, which always issues its own SELECTs against the shared
request-scoped session before the route handler runs - autobegin-ing the
session's transaction. `complete_operation` therefore never calls
`db.begin()`: doing so would either raise (`"A transaction is already begun
on this Session"`) or - as discovered in Phase 10's image primary-swap bug
- silently degrade into a nested savepoint that never gets a real top-level
commit. The fix, consistent with Phase 10/11: perform every step directly
against the already-open transaction, call `db.commit()` exactly once at
the end. Atomicity comes from "no commit until every step succeeds," not
from which API opened the transaction.

## Concurrency

Two protections, both PostgreSQL row locks, no application-level locking:

1. **Operation-level**: `complete_operation` locks the `packaging_operations`
   row first. A second concurrent completion attempt on the *same* operation
   blocks until the first transaction finishes, then sees `status ==
   COMPLETED` and is rejected with 409 - no duplicate movements are ever
   created. Verified by `test_16_duplicate_completion_does_not_duplicate_movements`
   (sequential) and `test_17_concurrent_completion_exactly_one_succeeds`
   (genuine concurrent threads via `ThreadPoolExecutor`, real PostgreSQL
   locking, not mocked).
2. **Lot-level**: all input and output inventory lots are locked together in
   one query, `ORDER BY id`, before any quantity is touched - the same
   `with_for_update()` idiom as Phase 11's `create_movement` and
   `AuthService.refresh_session`. Locking every lot the operation touches in
   one consistently-ordered query (rather than one lock per lot as needed)
   avoids lock-order deadlocks between two operations that happen to share
   an input or output lot.

## Reused Inventory Behavior

Rather than duplicate quantity/status/movement logic, Phase 12 extended
`InventoryService` with two new methods (Phase 11's existing `create_movement`
still passes its full regression suite unchanged after this extraction):

- **`apply_movement(lot, movement_type, quantity, performed_by_user_id, ...)`**
  - the validated core (`INACTIVE` rejection, direction lookup, negative-stock
  check, status transition, `StockMovement` construction) factored out of
  `create_movement`, **without committing** - so a caller with its own
  larger transaction (packaging completion, locking multiple lots) can call
  it repeatedly and commit once at the end. `create_movement` itself now
  just locks the lot, calls this, and commits - identical external behavior.
- **`get_or_create_lot_no_commit(batch_id, variant_id, location_id)`** - the
  same batch/variant product-match validation as `create_lot` (INVARIANT 9),
  but reusing an existing lot instead of rejecting on conflict, and not
  committing. Used by `add_output` to resolve the output's lot.

**A deliberate, documented inconsistency**: `get_or_create_lot_no_commit`
raises `BusinessValidationError` (422) for a batch/variant product mismatch,
matching Phase 11's own established convention for that specific invariant.
Every *other* business conflict introduced in Phase 12 itself (lifecycle
transitions, insufficient stock, traceability, location mismatch, duplicate
resources) uses `ConflictError` (409), per this phase's explicit error
table. This isn't an oversight - Phase 12 reuses Phase 11's already-tested
validation with its already-established error code, while Phase 12's own
new rules follow Phase 12's own given mapping.

## Inputs: No Inventory Effect Until Completion

`add_input` validates the operation is `DRAFT`/`IN_PROGRESS`, the lot exists,
the lot's `location_id` matches `operation.location_id` (else 409), and
rejects a duplicate `(operation, lot)` pair (else 409) - but never touches
`inventory_lots.quantity`. Removing an input is symmetric - just deletes the
row. Quantity only changes at `/complete`.

## Outputs: Lot Resolution vs. Quantity Application

The output's inventory lot is resolved (get-or-create) at `add_output` time,
**not** at completion - because `packaging_outputs.inventory_lot_id` is
`NOT NULL`, the row cannot be inserted without a valid lot id already
existing. A newly-created output lot starts at `quantity=0, status=DEPLETED`
(a valid, ordinary Phase 11 state) and is only incremented by
`total_quantity` when the operation actually completes (via `apply_movement`
RECEIPT). If the resolved lot already existed (e.g. this batch+variant was
already packaged into this location by a prior operation), it is reused
as-is - its existing quantity is left untouched until completion adds to it.

`add_output` requires: variant exists (404), batch exists (404), the
operation already has at least one input (409 if none), and `batch_id`
matches one of the batches actually present among the operation's *current*
inputs (409 otherwise) - see Traceability below. The output's location is
never client-supplied; it is always `operation.location_id` by construction,
so no output location-mismatch case can occur.

## Traceability

Every output inventory lot belongs to exactly one batch (`packaging_outputs`
→ its resolved `inventory_lots.batch_id`), matching the pre-existing
single-batch-traceability invariant already documented for Phase 4/5. There
is no mechanism to merge multiple source batches into one output lot, and
none was added. `add_output`'s `batch_id` must match a batch actually
present among the operation's inputs at the time it's added - **and this is
re-checked at completion time**, because an admin could add an input from
Batch A, add an output declaring Batch A, then remove that input before
completing, leaving the output's traceability claim no longer backed by any
actual consumed batch. Completion re-derives the current input batch set and
rejects (409) if any output's batch is no longer among them - the request
cannot silently invent a mapping or complete with broken provenance.

## Stock Movements

Created only at completion, one per input (`ADJUSTMENT_OUT`) and one per
output (`RECEIPT`), each with `reference_type = "PACKAGING_OPERATION"` and
`reference_id = operation.id`. No new movement types were added - `ADJUSTMENT_OUT`/
`RECEIPT` are existing Phase 4 types, reused exactly as directed. `performed_by_user_id`
on every movement is always the user who called `/complete`, from
`get_current_user`, never from the request body.

## Quantity Rule

`sum(outputs.total_quantity) <= sum(inputs.quantity)` is enforced at
completion (409 otherwise). No automatic waste record is created for the
difference, and none is silently discarded - the gap simply isn't accounted
for yet. Waste semantics (e.g. an explicit `WASTE` movement for trim/loss)
are left for a future phase to formalize, per the given instructions.

## Known Limitations

- **No idempotency mechanism.** Same limitation already documented in Phase
  11 - a duplicate HTTP retry of `/complete` is safely rejected (409, no
  duplicate movements, thanks to the operation-row lock) but a duplicate
  retry of `add_input`/`add_output` would be rejected too (duplicate-row
  check), so this endpoint set is actually more retry-safe than most by
  construction - but there is still no generalized idempotency-key system.
- **No label functionality.** Deliberately out of scope per the phase brief
  - no labels table, templates, or printing.
- **Output quantity shortfall (waste) is not tracked.** See Quantity Rule
  above.
- **No partial completion.** An operation either completes entirely (all
  inputs consumed, all outputs produced, in one transaction) or not at all
  - there is no way to complete "most" of an operation and leave the rest
  pending.

## Focused Validation Performed

`tests/test_phase_12_packaging.py`, 21 tests (20 required scenarios plus one
extra covering both `HUB_STAFF` and `OPERATIONS` role access together),
against real PostgreSQL - covering creation, full lifecycle, input/output
CRUD, the full happy-path completion with database re-verification (not
just HTTP response) of both lot quantities and movement rows, insufficient-stock
409 with unchanged quantity, unauthenticated/unauthorized access, duplicate
and genuinely-concurrent completion (via `ThreadPoolExecutor`, not mocked),
output batch traceability rejection, input location-mismatch rejection, and
a multi-input rollback scenario proving the first (would-have-succeeded)
input's quantity change never persists when a later input fails validation
within the same transaction. Also re-ran the full Phase 11 regression suite
(`test_phase_11_inventory.py`, 22 tests) after extracting `apply_movement`/
`get_or_create_lot_no_commit` from `InventoryService`, confirming the
refactor is behavior-preserving, plus Phase 10 catalog and auth tests.
