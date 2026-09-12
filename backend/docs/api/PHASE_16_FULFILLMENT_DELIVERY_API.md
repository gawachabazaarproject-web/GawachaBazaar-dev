# Phase 16 — Fulfillment & Delivery Operations

Extends Phase 15's order-level `Fulfillment` with a mandatory delivery-partner assignment step and
RBAC-scoped delivery-in-transit actions. See
[ARCHITECTURE.md §21b](../architecture/ARCHITECTURE.md) for the full design narrative and the
architectural conflict this phase resolved (a reservation can span multiple inventory locations);
this document covers only the actually-implemented API surface and the exact business rules behind
it.

**No GPS, live tracking, maps, route optimization, ETA prediction, geofencing/delivery zones, or
proof-of-delivery/signature/OTP capture** - all explicitly out of scope, same as Phase 15's
equivalent exclusions for reservation/expiry.

---

## 1. Extended State Machine

```
PENDING → PICKING → PACKED → READY_FOR_DELIVERY → ASSIGNED → OUT_FOR_DELIVERY → DELIVERED
```

Linear, no skipping, no reverse transitions. Same-state is an idempotent no-op for the plain
warehouse progression endpoint (`PICKING → PICKING` succeeds harmlessly) - but **not** for
assignment (see §3). Only DELIVERED consumes physical inventory; every other transition, including
the new ASSIGNED step, is pure status bookkeeping - no inventory quantity or reservation change
happens at picking, packing, staging, assignment, or dispatch.

## 2. Fulfillment Creation (unchanged from Phase 15)

A `Fulfillment` is created automatically, atomically with reservation commit, the moment an order
becomes CONFIRMED (COD acceptance, or UPI payment success) - never earlier. An order that is
PENDING, EXPIRED, or CANCELLED never has a fulfillment. Nothing in Phase 16 changed this timing;
Phase 16 only extends what happens to a fulfillment that already exists.

## 3. Delivery Partner Assignment

- A delivery partner is a `User` holding the `DELIVERY_PARTNER` role - not a dedicated
  `delivery_partners` table, consistent with the existing Wholesaler model (Phase 8.1).
- `POST /fulfillments/{id}/assign` requires the fulfillment to be exactly READY_FOR_DELIVERY.
  Unlike the plain `/status` progression, assignment does **not** treat "already ASSIGNED" as a
  harmless same-state no-op: a second assignment call could name a *different*
  `delivery_partner_user_id`, and silently allowing that would overwrite the original assignment.
  Assignment is therefore an unconditional one-time transition out of READY_FOR_DELIVERY - any
  other current status (including already ASSIGNED) is rejected with `409`.
- The target user must exist (`404` if not) and hold the `DELIVERY_PARTNER` role (`409` if not) -
  validated server-side against current database role membership, never trusted from the client
  beyond the numeric id.
- `assigned_at` is set from server time at the moment of assignment, never client-supplied.

## 4. Delivery-Partner Ownership

`POST /fulfillments/{id}/out-for-delivery` and `POST /fulfillments/{id}/deliver` both require the
authenticated caller to **be** the fulfillment's assigned `delivery_partner_user_id`, with `ADMIN`
as the sole administrative override. `HUB_STAFF`/`OPERATIONS` cannot perform either action, even
though they can perform every earlier warehouse step (`/status`, `/assign`) - warehouse and
delivery-in-transit are treated as distinct operational roles in this phase.

A `DELIVERY_PARTNER` who is not the assigned partner gets the same "don't disclose existence" `404`
on `GET /fulfillments/{id}` that `PaymentService._get_owned_payment` already established for
cross-user resource access in Phase 14; the mutation endpoints return `403` (existence is already
implied by the id the caller supplied).

## 5. Delivery Confirmation (unchanged core algorithm, extended with two checks)

`POST /fulfillments/{id}/deliver` is the sole physical-consumption transaction, inherited from
Phase 15 with two additions:

1. Lock order, then fulfillment (Order-before-Fulfillment, per the established lock order).
2. **New**: verify the caller is the assigned delivery partner (or ADMIN).
3. If already DELIVERED: idempotent no-op, returns current state.
4. Verify fulfillment is OUT_FOR_DELIVERY.
5. **New**: verify order is CONFIRMED (defense in depth against EXPIRED/CANCELLED orders reaching
   this transaction - should be unreachable given upstream invariants, but not trusted blindly per
   this phase's own instruction not to silently assume consistency).
6. Lock reservation; verify COMMITTED.
7. Read reservation items - **the exact FIFO allocation from checkout time, never recomputed**.
8. Lock every allocated lot in ascending-id order.
9. For each: apply a `DISPATCH` stock movement (reusing `InventoryService.apply_movement`, not
   duplicating it) and decrement `reserved_quantity` by the same amount.
10. Mark fulfillment DELIVERED, order COMPLETED.
11. Commit once.

No partial fulfillment: if any lot can no longer support its allocated quantity, the whole
transaction aborts and nothing is written - proven by `test_24_mid_delivery_failure_on_second_lot_rolls_back_the_first_too`.

## 6. COD vs UPI Eligibility (already guaranteed by Phase 15, not new logic)

- **COD**: a fulfillment exists and can be delivered while `payment.status` remains `PENDING` -
  COD payment is collected later and delivery never requires it to be PAID.
- **UPI**: a fulfillment cannot exist at all until the reservation is COMMITTED, which for UPI only
  happens after payment succeeds. This is a structural consequence of Phase 15's design (fulfillment
  creation is gated on reservation commit), not a new check Phase 16 had to add.

## 7. Inventory Location

`fulfillments.inventory_location_id` (nullable) records the single location the reservation
actually allocated from, populated automatically at fulfillment-creation time - **only** when every
allocated lot shares one location. Reservations pool lots across ALL locations for a variant (Phase
15 design), so a genuinely multi-location allocation leaves this `NULL` rather than recording a
misleading single location. No location is ever chosen or re-chosen at delivery time.

## 8. Endpoints

Only endpoints actually needed by this phase were implemented.

### Operations (`ADMIN`, `HUB_STAFF`, `OPERATIONS`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/fulfillments/{id}/status` | Advance one warehouse step (`PICKING`/`PACKED`/`READY_FOR_DELIVERY`). `ASSIGNED`/`OUT_FOR_DELIVERY`/`DELIVERED` are rejected here - each has its own endpoint. |
| POST | `/api/v1/fulfillments/{id}/assign` | Assign a delivery partner (`READY_FOR_DELIVERY → ASSIGNED`). Body: `{"delivery_partner_user_id": <id>}`. |

### Delivery-in-transit (`ADMIN`, `DELIVERY_PARTNER` - ownership enforced for the latter)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/fulfillments/{id}/out-for-delivery` | `ASSIGNED → OUT_FOR_DELIVERY`. Only the assigned partner (or ADMIN). |
| POST | `/api/v1/fulfillments/{id}/deliver` | Confirm delivery - the only endpoint that consumes physical inventory. Idempotent. Only the assigned partner (or ADMIN). Takes no body: consumption is derived entirely from the reservation, never from client input. |

### Reads (`ADMIN`, `HUB_STAFF`, `OPERATIONS`, `DELIVERY_PARTNER` - scoped in the service)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/fulfillments` | Paginated list. Staff see everything (optional `status`/`delivery_partner_user_id` filters); a `DELIVERY_PARTNER`-only caller is always scoped to their own assignments - any client-supplied `delivery_partner_user_id` filter is ignored for them. |
| GET | `/api/v1/fulfillments/{id}` | Detail. A `DELIVERY_PARTNER`-only caller gets `404` for a fulfillment not assigned to them. |

### Customer-facing (`CUSTOMER`, scoped to the authenticated user's own order)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/orders/{order_id}/fulfillment` | Safe fulfillment status only - `status`, `delivered_at`, `created_at`, `updated_at`. No `delivery_partner_user_id`, no `inventory_location_id`, no reservation/lot detail. `404` if the order has no fulfillment yet (not CONFIRMED) or belongs to another user. |

Existing Phase 13/14/15 order, payment, and reservation endpoints are unchanged in contract.

## 9. Response Safety

`FulfillmentResponse` (staff/delivery-partner facing) includes `delivery_partner_user_id`,
`inventory_location_id`, and `assigned_at` - internal operational detail appropriate for those
roles. `CustomerFulfillmentResponse` deliberately excludes all three, along with any reservation or
inventory-lot reference, per the existing "never leak internal warehouse/lot/reservation detail to
customers" convention established in Phase 15.

## 10. Security

- Client never supplies fulfillment status, `delivery_partner_user_id` outcome, `assigned_at`,
  `delivered_at`, inventory lot, or consumed quantity as authoritative input anywhere in this
  phase's request bodies. `AssignDeliveryPartnerRequest` accepts only the target user id (validated
  server-side against real role membership); `/out-for-delivery` and `/deliver` take no body at
  all - the authenticated identity is the only input that matters, and ownership is derived from
  the database, never from a client-supplied field.
- A `DELIVERY_PARTNER` can never enumerate or act on another partner's assignments (`GET
  /fulfillments` scoping, `404`/`403` on direct access by id).
- A non-`DELIVERY_PARTNER` user can never be assigned (`409` if the target lacks the role).

## 11. Testing

`tests/test_phase_16_fulfillment_delivery.py` (43 tests) - fulfillment creation gating (confirmed
vs. pending/expired/UPI-unpaid), the full extended state machine (every valid step, every invalid
forward/skip/reverse transition, same-state idempotency), assignment rules (wrong state, nonexistent
user, wrong role, cannot reassign, RBAC), inventory invariants at every warehouse step (unchanged
through ASSIGNED and OUT_FOR_DELIVERY, only changing at DELIVERED), exact multi-lot FIFO reuse at
delivery (never recomputed, a newly-added older-dated lot is never touched), a forced mid-delivery
failure proving no partial consumption, ownership/RBAC security (customer, wrong delivery partner,
wrong role, ADMIN override), COD-while-PENDING and UPI-requires-PAID eligibility, list scoping, and
five real-PostgreSQL concurrency scenarios (assignment race, duplicate concurrent delivery, a legal
transition racing an always-illegal one, delivery racing a concurrent reassignment attempt, and
delivery racing an attempt to expire the now-un-expirable COMMITTED reservation).

A genuine product bug was caught during this phase's own test-writing: the first `assign_delivery_partner`
implementation relied on the generic transition-matrix's same-state-is-a-no-op rule, which let a
*second* assignment call silently overwrite the first with a different partner instead of being
rejected. Fixed by making READY_FOR_DELIVERY an unconditional precondition for assignment, checked
before any transition-matrix logic runs.

Pre-existing Phase 15 fulfillment tests were updated to route through the new mandatory ASSIGNED
step and the correctly-assigned delivery partner's identity (the old direct
READY_FOR_DELIVERY → OUT_FOR_DELIVERY single step, and delivery by any DELIVERY_PARTNER-having
user regardless of assignment, no longer exist) - this is a genuine, spec-intended behavior change,
not a regression; the underlying invariants those tests proved (exact physical consumption,
idempotency, stock movement creation, order completion) are all still asserted, just via the new
required flow.

## 12. Known Limitations

- No GPS, live tracking, maps, route optimization, ETA prediction, geofencing, or delivery zones -
  explicitly out of scope.
- No proof-of-delivery photo, signature capture, or OTP delivery verification - explicitly out of
  scope.
- No customer cancellation/refund workflow - not built in Phase 15 and not added here; fulfillment
  transitions respect the existing `CANCELLED` order status (which no code path currently sets) but
  no cancellation trigger exists.
- No partial fulfillment or substitutions - a delivery either fully succeeds against its exact
  reservation allocation or the whole transaction rolls back.
- Assignment is a single-step dispatcher action (`POST /fulfillments/{id}/assign` with a target
  partner id) - there is no separate partner-facing "browse and accept" self-service flow, since
  the spec's own assignment algorithm (verify target user, verify their role) implies an operator
  choosing a specific partner rather than a partner self-selecting.
- No real PNB gateway integration (unchanged from Phase 14) - irrelevant to this phase's scope but
  noted for completeness, since UPI eligibility for fulfillment still depends on it.
