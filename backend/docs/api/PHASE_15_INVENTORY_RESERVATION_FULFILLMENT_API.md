# Phase 15 — Inventory Reservation, Order Expiry & Fulfillment Foundation

Implements: inventory reservation at checkout (before payment), a 30-minute order-level payment
window with lazy expiry, integration with the existing Phase 14 payment lifecycle, and a minimal
order-level fulfillment state machine whose only DELIVERED transition physically consumes
inventory. See [ARCHITECTURE.md §21a](../architecture/ARCHITECTURE.md) for the full design
narrative; this document covers only the actually-implemented API surface and the exact business
rules behind it.

**No PNB production gateway integration exists** (unchanged from Phase 14) — UPI payments still run
against `FakePNBGateway` in tests; `PNBGateway.initiate_payment`/`query_status` still honestly raise
`NotImplementedError` against the real merchant contract.

---

## 1. Core Concept: AVAILABLE → RESERVED → COMMITTED → DELIVERED/CONSUMED

- **AVAILABLE**: `inventory_lots.quantity - inventory_lots.reserved_quantity` (computed, never
  persisted).
- **RESERVED**: checkout creates an `ACTIVE` `inventory_reservations` row and increases
  `reserved_quantity` on the lots it allocates from. Physical `quantity` is untouched.
- **COMMITTED**: payment success (UPI) or COD acceptance moves the reservation ACTIVE → COMMITTED
  and the order PENDING → CONFIRMED, atomically. Physical `quantity` still untouched.
- **DELIVERED/CONSUMED**: delivery confirmation is the *only* operation that decreases physical
  `quantity` (via a `DISPATCH` stock movement) and `reserved_quantity` together, and moves the
  order to COMPLETED.

Reservation ≠ consumption. Payment ≠ consumption. Picking/packing ≠ consumption.

## 2. The 30-Minute Payment Window

- `inventory_reservations.expires_at` is set once, at reservation creation (checkout time),
  to `now + 30 minutes`. It is **not** recomputed at payment-initiation time.
- It applies uniformly regardless of eventual payment method. The reservation is created before a
  payment method is ever chosen, so COD is not exempt: a COD confirmation attempt against an
  already-expired reservation is rejected (`409`), not silently accepted.
- Expiry is **lazy**, checked and applied atomically (under the reservation's row lock, Order locked
  first) by whichever operation next touches an ACTIVE reservation past its `expires_at` — payment
  confirmation, a customer's `GET .../reservation`, an ops detail read, or the explicit ops expire
  endpoint. There is no background worker in this phase, and none is required for correctness.
- Whenever a reservation actually expires (not just when found already expired), the order it
  belongs to moves `PENDING → EXPIRED` in the same transaction — a new explicit terminal order
  status, distinct from `CANCELLED`/`COMPLETED` (`orders.ck_orders_status` was widened, additively,
  to allow it). One exception: if the expiry is discovered *while attempting to confirm via COD*
  (`_confirm_cod`), that whole attempt rolls back (to also discard the doomed COD payment row) and
  the order-EXPIRED write rolls back with it — the order is left PENDING in that specific case, to
  be moved to EXPIRED by whatever next touches the reservation without needing to roll back.

## 3. Reservation Lifecycle

```
ACTIVE ──┬──> COMMITTED   (payment success / COD acceptance, before expiry)
         ├──> RELEASED    (generic manual release - kept reusable for a future
         │                 cancellation feature; nothing in this phase calls it
         │                 automatically)
         └──> EXPIRED     (30-minute window elapsed, detected lazily)
```

COMMITTED, RELEASED, and EXPIRED are all terminal. A reservation that reaches EXPIRED can never be
resurrected — a payment that resolves PAID afterward does **not** move it back to ACTIVE/COMMITTED
and does **not** confirm the order. The payment itself is still marked PAID (the money genuinely
arrived); only order confirmation is withheld, and a `PAYMENT_RESERVATION_MISMATCH` reconciliation
event is logged. This is a deliberate, safe, observable exception case — not silently resolved and
not treated as a system error.

### Deliberate deviation from a literal reading of the spec

A definitively FAILED UPI payment attempt does **not** release the reservation (ACTIVE stays
ACTIVE). `inventory_reservations` has `UNIQUE(order_id)` and RELEASED is terminal with no
re-activation path; releasing on failure would strand a later successful
`POST /payments/{id}/retry` with nothing to commit, and re-reserving inside `retry_payment` would
duplicate the FIFO allocation logic in a second place. The reservation instead stays ACTIVE through
a failed attempt — still bounded by its own 30-minute expiry — so the existing, unmodified retry
flow keeps working exactly as it did in Phase 14.

## 4. FIFO Allocation

- Oldest eligible lot first: `ORDER BY created_at ASC, id ASC` (the `id` tie-break is mandatory for
  determinism when two lots share a `created_at`).
- Explicitly FIFO, not FEFO — no expiration-date/shelf-life logic exists or is used.
- Allocation pools across **all locations** for a variant, not one location. There is no
  location-selection concept anywhere else in this codebase (`InventoryLocation` has only
  ACTIVE/INACTIVE, no "default"/"operational" flag), and the spec only requires
  `created_at ASC, id ASC` ordering — pooling across locations is the smallest design consistent
  with the existing schema.
- One order item may span multiple lots. `inventory_lots.id` is **not** added to `order_items` —
  the join lives in `inventory_reservation_items` (`order_item_id` × `inventory_lot_id` ×
  `quantity`).
- All-or-nothing: candidate lots are locked (`SELECT ... FOR UPDATE`) before allocation begins;
  availability is recalculated from the freshly-locked rows, not from any earlier unlocked read. If
  any order item's demand cannot be fully covered, the *entire* reservation attempt fails and the
  entire checkout transaction rolls back — no partial reservation is ever created.

## 5. Integration with Checkout (Phase 13)

`POST /cart/checkout` is unchanged in request/response shape. Internally,
`InventoryReservationService.create_reservation_for_order` now runs inside the same atomic
transaction, before `OrderService.checkout`'s single commit. Insufficient stock raises a
`ConflictError` (`409`) that rolls back the order, its items, its address snapshot, and the cart's
status change together — the order is never left in a state where it exists without its required
reservation.

Checkout still never creates a `Payment` or decides COD vs UPI — that remains `POST /payments`'s
job, unchanged from Phase 14.

## 6. Integration with Payments (Phase 14)

- `PaymentService._confirm_cod` now calls `commit_reservation_for_order` before setting
  `order.status = "CONFIRMED"`. If the reservation cannot be committed (expired), the whole
  operation rolls back and `409` is returned — no payment row is left behind for a dead
  reservation.
- `PaymentService._confirm_order_if_paid` (shared by synchronous-initiate confirmation, webhook
  processing, and `/verify`) does the same. If commit fails, the payment's PAID status is still
  persisted by the caller's existing commit — only order confirmation is withheld.
- No new payment endpoints. No change to `CreatePaymentRequest`/`PaymentResponse`/
  `PaymentInitiationResponse` shapes.

## 7. Fulfillment State Machine

```
PENDING → PICKING → PACKED → READY_FOR_DELIVERY → OUT_FOR_DELIVERY → DELIVERED
```

Linear, no skipping, no reverse transitions in this phase. A `Fulfillment` row is created
automatically the moment a reservation first becomes COMMITTED (inside
`commit_reservation_for_order`) — there is no separate "create fulfillment" endpoint. Only the
DELIVERED transition (via `POST /fulfillments/{id}/deliver`) consumes physical inventory; every
other transition is pure status bookkeeping via `POST /fulfillments/{id}/status`.

Out of scope in this phase: per-item picking detail, delivery partner assignment, routing, live
tracking, proof-of-delivery, substitutions, partial fulfillment.

### Delivery confirmation transaction

`POST /fulfillments/{id}/deliver`:

1. Lock the order, then the fulfillment (unconditional lock, retry-safe pattern — a status filter
   in the locking query would silently exclude the row once a concurrent transaction changes its
   status).
2. If already DELIVERED: idempotent no-op, returns current state, no further writes.
3. Verify the fulfillment is currently OUT_FOR_DELIVERY, else `409`.
4. Lock the reservation; verify COMMITTED, else `409` (should be unreachable given the invariants
   above, but is not trusted blindly).
5. Read the reservation's allocation items (`inventory_reservation_items`) — the exact FIFO
   allocation from checkout time is replayed, never recomputed.
6. Lock every allocated lot in ascending-`id` order (a fixed, deterministic order, distinct from
   the FIFO `created_at` order used at allocation time — this is the release-time lock order).
7. For each: apply a `DISPATCH` stock movement (reusing `InventoryService.apply_movement`, not
   duplicating it — `DISPATCH` already means "goods leaving the facility," a direct semantic fit
   for delivery-time consumption, so no new movement type was added) and decrement
   `reserved_quantity` by the same amount.
8. Mark the fulfillment DELIVERED, the order COMPLETED.
9. Commit once.

No partial fulfillment: any lot that can no longer support its allocated quantity aborts the whole
transaction (a controlled `ConflictError`, not a silent short-fill).

## 8. Lock Ordering

Extending Phase 13/14's established Order-before-Payment convention:

```
Cart → Order → Payment → Fulfillment → Reservation → InventoryLots
```

Lots are always locked last, in `created_at ASC, id ASC` order for FIFO allocation or plain
`id ASC` for a known set during release/delivery. This consistent, documented order is what
prevents a deadlock between, e.g., the payment-confirmation path (Order → Payment → ... →
Reservation) and the delivery-confirmation path (Order → Fulfillment → Reservation → Lots) racing
on the same order.

Every locking helper introduced in this phase that does an unlocked pre-read (to discover a foreign
key, e.g. `fulfillment.order_id`) followed by a locked re-read of the *same* row applies
`.populate_existing()` on the locked query — the Phase 14 stale-identity-map bug (a `with_for_update()`
re-query silently returning the same already-mapped, pre-lock Python object) recurred at least
twice while building this phase and was fixed with the same established pattern each time:
`InventoryReservationService._lock_reservation_by_order_id` and
`FulfillmentService.confirm_delivery`.

## 9. Endpoints

Only endpoints actually needed by this phase were implemented — not every endpoint a full spec
could imagine.

### Customer-facing (`CUSTOMER` only, scoped to the authenticated user)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/orders/{order_id}/reservation` | The reservation for one of the current user's orders. Lazily expires it first if overdue. Never exposes lot IDs or item-level allocation. |

Existing `POST /payments`, `GET /payments/{id}`, `POST /payments/{id}/retry`,
`POST /payments/{id}/verify`, `GET /orders/{id}/payment` are unchanged in contract.

### Operations/Admin (`ADMIN`, `HUB_STAFF`, `OPERATIONS`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/inventory/reservations` | Paginated list, optional `?status=` filter. |
| GET | `/api/v1/inventory/reservations/{id}` | Detail, including the FIFO lot allocation (`inventory_lot_id`, `order_item_id`, `quantity` per row). Lazily expires it first if overdue. |
| POST | `/api/v1/inventory/reservations/{id}/expire` | Manually expire an ACTIVE reservation (idempotent — a no-op returning the current state if already terminal). |

### Fulfillment (`ADMIN`, `HUB_STAFF`, `OPERATIONS`, `DELIVERY_PARTNER`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/fulfillments/{id}` | Fulfillment detail. |
| POST | `/api/v1/fulfillments/{id}/status` | Advance one step (`PICKING`/`PACKED`/`READY_FOR_DELIVERY`/`OUT_FOR_DELIVERY`). `DELIVERED` is rejected here (`409`) — use `/deliver`. |
| POST | `/api/v1/fulfillments/{id}/deliver` | Confirm delivery. Idempotent. The only endpoint that consumes physical inventory. |

`CUSTOMER` receives `403` on every ops/fulfillment endpoint above. No new roles were introduced —
all authorization uses the existing six roles via `require_roles`.

## 10. Security

- Client never supplies price, quantity, reservation status, order status, payment status, expiry
  time, inventory lot reference, or `user_id` anywhere in this phase's request bodies.
  `UpdateFulfillmentStatusRequest` accepts only a status literal excluding `DELIVERED`; `/deliver`
  takes no body at all — physical consumption is derived entirely from the order's committed
  reservation, never from client input.
- Customer-facing reservation responses never include `inventory_lot_id` or per-item allocation —
  that detail is only ever returned from the ops/admin detail endpoint.
- Customers cannot read another user's reservation (`404`, indistinguishable from "doesn't exist").

## 11. Testing

`tests/test_phase_15_inventory_reservation_fulfillment.py` — reservation creation, FIFO allocation
(including ties and multi-lot spanning), insufficient-stock rollback, COD, UPI success/failure/retry,
late-payment-after-expiry, lazy and manual expiry, the full fulfillment lifecycle, idempotent
duplicate delivery, authorization boundaries, and six real-PostgreSQL concurrency scenarios (two
customers racing the last unit, concurrent multi-lot FIFO, concurrent expiry, payment-vs-expiry
race, concurrent delivery confirmation, concurrent checkout oversell prevention).

Pre-existing Phase 13 checkout tests were updated to stock a variant's inventory before checking
out (checkout now requires available inventory to succeed, where Phase 13 never touched inventory
at all) — this is a genuine, spec-intended behavior change, not a regression; `test_29` was renamed
and rewritten to assert the new, correct invariant (physical `quantity` unchanged, `reserved_quantity`
increased, zero stock movements at checkout) instead of its Phase-13-only "inventory untouched"
premise. Pre-existing Phase 14 payment tests' `_create_order` helper was updated to also create a
matching ACTIVE reservation, since "every order has a reservation" is now a structural invariant
`PaymentService` depends on.

## 12. Known Limitations

- No real PNB gateway integration (unchanged from Phase 14) — this phase does not and cannot claim
  production readiness for UPI against a real merchant account.
- No background expiry worker — correctness does not depend on one (see §2), but a large number of
  abandoned ACTIVE reservations will not be proactively cleaned up until something touches them.
  Acceptable for this phase; an operational sweep job would be a natural, separate future addition.
- No customer-facing cancellation flow. `release_reservation_for_order` exists and is
  concurrency-safe/idempotent for a future cancellation feature to call, but nothing in this phase
  invokes it.
- No partial fulfillment, no substitutions, no per-item picking detail, no delivery partner
  assignment/routing/tracking/proof-of-delivery — all explicitly out of scope.
