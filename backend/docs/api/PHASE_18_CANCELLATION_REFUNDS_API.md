# Phase 18 — Order Cancellation & Refund Approval

See [ARCHITECTURE.md §21d](../architecture/ARCHITECTURE.md) for the full design narrative
(the delivery-vs-cancellation race, the reservation-state-machine gap this phase fixed, why
refund is a separate entity from Payment). This document covers only the actually-implemented
API surface.

## 1. Central Rule

A customer may cancel an order any time **before delivery is completed**:

```
PENDING / CONFIRMED  →  CANCELLED   (any time up to delivery)
CONFIRMED             →  COMPLETED   (delivery confirmed - no longer cancellable)
```

`CONFIRMED` covers every Fulfillment sub-status (`PICKING`/`PACKED`/`READY_FOR_DELIVERY`/
`ASSIGNED`/`OUT_FOR_DELIVERY`) - the Order itself only becomes `COMPLETED` at the moment delivery
is actually confirmed. `CANCELLED` is terminal: it can never become `CONFIRMED`/`COMPLETED`, and a
`COMPLETED` order can never become `CANCELLED`. See `app/services/order_state.py`.

## 2. Endpoints

### Customer (`CUSTOMER`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/orders/{order_id}/cancel` | Cancel one of the current user's own orders. Body: `{"reason": "..."}` (optional, max 500 chars). |
| GET | `/api/v1/orders/{order_id}/refund` | Get the refund status for one of the current user's orders, `404` if none exists. |

### Admin (`ADMIN`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/orders/admin/{order_id}/cancel` | Administrative cancellation of any order - no ownership constraint. Same body shape as the customer endpoint. |
| GET | `/api/v1/payments/refunds` | List refund requests, optional `?status=`. |
| GET | `/api/v1/payments/refunds/{refund_id}` | Get one refund request. |
| POST | `/api/v1/payments/refunds/{refund_id}/approve` | `PENDING_APPROVAL → APPROVED`. |
| POST | `/api/v1/payments/refunds/{refund_id}/reject` | `PENDING_APPROVAL → REJECTED`. Body: `{"reason": "..."}` (optional). |
| POST | `/api/v1/payments/refunds/{refund_id}/process` | `APPROVED`/`FAILED → PROCESSING`, then calls the payment gateway. |

`OPERATIONS` and `HUB_STAFF` have no access to any refund endpoint and cannot administratively
cancel an order - no existing business rule in this codebase grants either role financial
authority, and this phase does not introduce one. `DELIVERY_PARTNER` has no access to any Phase 18
endpoint.

## 3. Cancellation Transaction

`OrderService.cancel_own_order` / `admin_cancel_order` (one shared `_cancel_locked_order` core):

1. Lock the `Order` row (`with_for_update()`, unconditionally on id) - **first**, matching
   `FulfillmentService.confirm_delivery`'s own lock order. This single fact is what resolves the
   cancellation-vs-delivery race (§6 below).
2. Customer path only: verify ownership (404, not 403, on another customer's order).
3. Attempt `order_state.transition_order_status(current, CANCELLED)` - `ConflictError` (409) if the
   current status is `COMPLETED`/`EXPIRED`, or a no-op if already `CANCELLED`.
4. Set `cancelled_at`, `cancelled_by_user_id`, `cancellation_reason`.
5. Release the reservation via the existing `InventoryReservationService.release_reservation_for_order`
   (now accepts `ACTIVE` **or** `COMMITTED` as source - see §5) - decrements `reserved_quantity` on
   every allocated lot. Physical `quantity` is **never** touched; it is only ever decremented by
   `FulfillmentService.confirm_delivery`'s `DISPATCH` movement.
6. If the order's payment is an online (UPI) payment that has actually reached `PAID`, create a
   `PENDING_APPROVAL` refund via `RefundService.create_refund_if_eligible` - this **never** issues
   the refund itself, only makes it visible for admin review. COD creates no refund (nothing was
   collected); an online payment that never reached `PAID` has nothing to refund.
7. Commit once - Order status, reservation release, and refund-eligibility creation succeed or fail
   together.

## 4. Delivery vs. Cancellation Race

Both `OrderService._lock_order_for_cancel` and `FulfillmentService.confirm_delivery` lock the
`Order` row first, unconditionally. Whichever transaction acquires that lock first proceeds to
completion (`CANCELLED` or `COMPLETED`) and commits; the other blocks, then re-reads the
now-committed status and is rejected by its own existing guard:

- Cancellation loses → `order_state.transition_order_status` raises (current is already
  `COMPLETED`).
- Delivery loses → `confirm_delivery`'s pre-existing `order.status != "CONFIRMED"` check rejects it
  (current is now `CANCELLED`) - **no code change was needed here**, since `CANCELLED != CONFIRMED`
  already made this case correct.

The same Order-first lock was added to the three fulfillment-progression methods that previously
touched only their own `Fulfillment` row - `update_status`, `assign_delivery_partner`,
`mark_out_for_delivery` (via `FulfillmentService._lock_order_and_fulfillment` +
`_assert_order_still_active`) - so a cancelled order's fulfillment can never be assigned or
dispatched either, not just never delivered.

## 5. Reservation Release

`InventoryReservationService.release_reservation_for_order` (built in Phase 15 "for a future
cancellation feature", first actually called here) now accepts a reservation in `ACTIVE` **or**
`COMMITTED` status as a valid release source - `reservation_state.py` gained exactly one new
transition, `COMMITTED → RELEASED`, since a confirmed order's reservation is `COMMITTED`, which was
previously terminal. `RELEASED`/`EXPIRED` remain terminal and this call is a safe no-op on either.

```
Before cancellation:  quantity = 10, reserved_quantity = 4  (available = 6)
After cancellation:   quantity = 10, reserved_quantity = 0  (available = 10)
```

No `DISPATCH` (or any) stock movement is created by cancellation - only `confirm_delivery` ever
creates one.

## 6. Refund Model

`Refund` (one per order, `UNIQUE(order_id)`): `order_id`, `payment_id`, `amount`/`currency`
(copied from `Payment` at creation, never recomputed), `status`, `requested_at`,
`approved_by_user_id`, `approved_at`, `rejection_reason`, `processed_at`.

```
PENDING_APPROVAL → APPROVED → PROCESSING → REFUNDED
                 → REJECTED (terminal)              PROCESSING → FAILED → PROCESSING (retry)
```

`PaymentStatus.PAID` is **never** changed by any of this - it remains terminal exactly as Phase 14
defined it. A refund's own approval lifecycle is a separate concern from the payment it refunds; an
old `PAYMENT`-type `payment_transactions` row is never edited into a refund. Refund **processing**
attempts are recorded as new `payment_transactions` rows with `transaction_type = 'REFUND'` and a
`refund_id` FK, using the exact same `INITIATED`/`PROCESSING`/`SUCCESS`/`FAILED` vocabulary a
payment attempt already uses.

Refund eligibility is created from two places (both idempotent on `refunds.order_id UNIQUE`):
`OrderService.cancel_order` (payment already `PAID` at cancellation time) and
`PaymentService._confirm_order_if_paid` (a UPI payment still `PROCESSING` at cancellation time that
later resolves `PAID` - money genuinely collected for an order that will never be fulfilled).

## 7. Refund Processing / Gateway

`RefundService.process_refund` mirrors `PaymentService._initiate_upi`'s exact shape: a short
transaction (`APPROVED`/`FAILED → PROCESSING`, create the `REFUND` transaction row, commit - lock
released) followed by an outbound `PaymentGateway.refund_payment` call outside any held lock, with
the same three-way outcome handling payments already use (definitive rejection → `FAILED`;
timeout/connection error → left `PROCESSING`, outcome unknown, never `FAILED`; success →
`REFUNDED`).

`PNBGateway.refund_payment` raises `NotImplementedError`, following `initiate_payment`/
`query_status`'s own precedent exactly - no PNB refund API specification exists in this repository,
and none is invented. The internal abstraction (Protocol method + `GatewayRefundResult`) is ready
for a real implementation once one exists.

## 8. Security

- A customer can only cancel/view their own orders/refunds (404 on another customer's).
- No endpoint accepts a client-supplied order status, refund status, refund amount, timestamp, or
  approving-admin id - all server-derived. The only client input anywhere in this domain is a
  free-text cancellation/rejection reason.
- Refund approval, rejection, and processing are `ADMIN`-only; a customer can only ever read a
  refund's status, never approve/reject/trigger it.
- `OPERATIONS`/`HUB_STAFF` have no financial authority in this phase (no refund access, no
  administrative cancellation) - consistent with there being no prior business rule granting either
  role payment authority.

## 9. Bulk/Custom Orders (Phase 17 integration)

A bulk/custom quote converted into a real `Order` (Phase 17) is cancelled through this exact same
system - there is no separate bulk cancellation/refund/reservation/fulfillment path. Once
`BulkOrderService.convert_to_order` has run, the resulting order is indistinguishable from a retail
one for every purpose Phase 18 touches.

## 10. Known Limitations

- No partial/item-level refunds - one refund per order, for the order's full paid amount.
- No automatic refund approval - every refund requires an explicit `ADMIN` approve action.
- No real PNB refund integration - `PNBGateway.refund_payment` is a structural placeholder, exactly
  like `initiate_payment`/`query_status` have been since Phase 14.
- No returns-after-delivery, exchanges, or replacement orders - cancellation is only possible before
  delivery is completed, by design.
