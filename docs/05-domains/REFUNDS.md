# Refunds

> **Status:** Verified against source and fake-gateway tests on 2026-10-14; live Razorpay refunds **not verified**. One gap found by code inspection and **not reproduced** (G-REF-1 below).
> **Source files:** [`services/refund.py`](../../backend/app/services/refund.py), [`refund_state.py`](../../backend/app/services/refund_state.py), [`payment.py`](../../backend/app/services/payment.py) (`_confirm_order_if_paid`, webhook), [`order.py`](../../backend/app/services/order.py) (`_cancel_locked_order`), [`checkout_session.py`](../../backend/app/services/checkout_session.py) (`_refund_and_fail`), [`razorpay_gateway.py`](../../backend/app/services/razorpay_gateway.py); models `refund`, `payment_transaction`; Admin `Admin/app/(admin)/payments`, mobile `mobile/app/order/[id]/refund.tsx`.
> **Tests:** [`test_phase_18_cancellation_refunds.py`](../../backend/tests/test_phase_18_cancellation_refunds.py), [`test_refund_integrity.py`](../../backend/tests/test_refund_integrity.py), [`test_razorpay_payments.py`](../../backend/tests/test_razorpay_payments.py) (refund webhooks, reprocessing), [`test_money_integrity.py`](../../backend/tests/test_money_integrity.py).

## Two different kinds of refund

| Kind | Trigger | Records | Who moves the money |
|---|---|---|---|
| **Approval-gated refund** (`refunds` table) | An order is cancelled (or expires/was cancelled while paying) **and** its online payment reached `PAID` | `refunds` row `PENDING_APPROVAL` + `REFUND` rows in `payment_transactions` | An ADMIN: approve → process |
| **Automatic pay-first refund** | A pay-first payment was captured but the order could not be placed (stock, price change, address deleted, …) | Only `checkout_sessions.status = REFUNDED` or `REFUND_FAILED` and `failure_reason` — **no `refunds` row**, so it does not appear in the Admin refund queue | The system, immediately, via `RazorpayGateway.refund_payment` |

COD orders never create a refund (nothing was collected). Refunds are always for the **full payment amount** (`refunds.amount = payments.amount`); partial refunds are not supported.

## Refund state machine (`refund_state.py`)

```
PENDING_APPROVAL ──approve──► APPROVED ──process──► PROCESSING ──► REFUNDED  (terminal)
        │                                               │  └──────► FAILED ──process (retry)──► PROCESSING
        └────reject────► REJECTED (terminal)
```

Same-state transitions are no-ops; illegal ones raise 409. Only admin actions move a refund out of `PENDING_APPROVAL`.

## Where a refund request is created (`create_refund_if_eligible`)

All three call the same idempotent function (unique `refunds.order_id`, existing refund returned):

1. **Cancellation** of an order whose payment is already `PAID` (`OrderService._cancel_locked_order`).
2. **A payment that resolves to `PAID` after the order was already cancelled** (customer cancelled while the UPI attempt was still `PROCESSING`) — `_confirm_order_if_paid`.
3. **A payment that resolves to `PAID` after the reservation expired**, when the order has just been moved `PENDING → EXPIRED` — same function, logged as `PAYMENT_RECONCILIATION`.

## Admin workflow

| Step | Endpoint (role `ADMIN`) | What happens |
|---|---|---|
| List / view | `GET /payments/refunds`, `/payments/refunds/{id}` | Queue, filters |
| Approve | `POST …/approve` | `PENDING_APPROVAL → APPROVED`; records `approved_by_user_id`/`approved_at`; audit `refund.approve` |
| Reject | `POST …/reject` (reason) | `→ REJECTED`; audit `refund.reject` |
| Process | `POST …/process` | `APPROVED` (or `FAILED`) `→ PROCESSING`; creates a `REFUND` transaction with a fresh `refund-{id}-{random}` idempotency key; **commits**; then calls Razorpay (`POST /payments/{pay_id}/refund`, `speed: normal`); audit `refund.process` |
| Sync | `POST …/sync` | For a refund stuck in `PROCESSING`: asks Razorpay for the refund's status (`GET /refunds/{id}`) and applies a terminal verdict; audit `refund.sync` |

Customers can read the refund status of their own order (`GET /orders/{id}/refund`, 404 if none) — shown on the mobile refund screen.

## Gateway outcomes

| Gateway result | Refund becomes |
|---|---|
| `processed` | `REFUNDED` (+ `processed_at`) and a push "Refund processed" |
| `pending`/`created` | stays `PROCESSING` until the webhook or `sync` |
| `failed` / synchronous rejection | `FAILED` with `failure_reason` on the transaction; can be processed again |
| `refund.processed` / `refund.failed` webhook | applied to the matching `PROCESSING` refund through the same function; a refund id the system never issued is acknowledged and logged (`PAYMENT_WEBHOOK_UNKNOWN_REFUND`) |
| Timeout / connection error (outcome unknown) | stays `PROCESSING` (never `FAILED`), HTTP 502 |

## Duplicate, concurrent and lost-response behaviour

| Scenario | Behaviour | Evidence |
|---|---|---|
| Two admins click "process" at once | Row lock + the `PROCESSING` guard ⇒ exactly **one** request reaches Razorpay | `test_simultaneous_process_clicks_send_one_refund_to_razorpay` |
| "Process" on an already `REFUNDED` refund | Rejected (409); no second gateway call | `test_processing_an_already_refunded_refund_never_sends_a_second_one` |
| Customer and admin cancel simultaneously | One cancellation, **one** refund request | `test_concurrent_cancellation_by_customer_and_admin_creates_one_refund` |
| Webhook for a refund failure then re-process | Refund moves to `FAILED` and can be re-processed | `test_refund_webhook_failure_allows_reprocessing` |
| Refund request repeated for the same order | Existing row returned (unique `order_id`) | schema + `create_refund_if_eligible` |

### G-REF-1 — a refund can get stuck in `PROCESSING` with no in-app way out (found by code inspection)

If the Razorpay call times out **before the refund id is stored**, the refund stays `PROCESSING` with a transaction that has no `gateway_transaction_id`. Then: `process` is refused ("still being processed… wait"), `sync` is refused ("never got a reference back from the gateway… look the payment up in the gateway dashboard"), and no webhook can match (no stored refund id). Resolution is out-of-band: check the Razorpay dashboard, and if the refund exists or not, fix the database by hand. The idempotency key is placed only in `notes` on the Razorpay request, so Razorpay does **not** deduplicate a blind retry. This scenario is mentioned as "partly tested" in [RISK_REGISTER](../testing/RISK_REGISTER.md) R-21; I did not reproduce the stuck state. Proposed (not applied): an admin action to mark the unresolved attempt failed (after checking the dashboard) so it can be reprocessed, or reconcile by payment id.

## Other limitations

- No refund-to-original-method confirmation to the customer except the push notification; no email/SMS.
- No automatic reminder for refunds waiting in `PENDING_APPROVAL` or stuck in `PROCESSING`.
- The pay-first automatic refund has no admin-visible record besides the session status and the `PAYMENT_RECONCILIATION` log line when it fails (`REFUND_FAILED`).
- Refund processing is ADMIN-only by design; OPERATIONS/HUB_STAFF cannot approve.
