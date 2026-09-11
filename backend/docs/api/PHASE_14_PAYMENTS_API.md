# Phase 14 — Payments (PNB UPI + COD)

Turns the existing Phase 7 payments schema (`payments`, `payment_transactions`)
into a production-grade payment workflow, plus one additive migration
(`gateway_name`/`gateway_order_id` on `payments`, and a new
`payment_webhook_events` table). **CUSTOMER-only** for all customer-facing
endpoints; the webhook endpoint has no JWT and authenticates via the
gateway's own signature scheme.

## PNB Integration Boundary — Read This First

**No PNB merchant integration specification exists anywhere in this
repository.** A full-repository search was performed before this phase
began and found nothing. Per the explicit instruction for this situation:

- `PNBGateway.initiate_payment` and `PNBGateway.query_status`
  (`app/services/payment_gateway.py`) **raise `NotImplementedError`**. We do
  not know PNB's real request/response shape, authentication scheme, or
  endpoint URLs, and inventing them would misrepresent this as a working
  integration. **UPI payments cannot actually complete against a real PNB
  gateway today** - the domain, state machine, locking, and webhook
  pipeline are fully built and tested, but the last mile (the actual PNB
  API call) is a deliberate, honest gap.
- `PNBGateway.verify_webhook_signature` / `parse_webhook_event` implement a
  **clearly-labeled PLACEHOLDER scheme** (HMAC-SHA256 over the raw body,
  `X-PNB-Signature` header) - a generic, industry-common webhook-signing
  convention, presented honestly as our placeholder, not a claim about
  PNB's real algorithm. This exists so the webhook safety pipeline
  (deduplication, ordering, concurrency - the actual point of this phase)
  is fully exercisable end-to-end in tests.
- `FakePNBGateway` (test-only, lives in `tests/test_phase_14_payments.py`,
  never imported by `app/`) subclasses `PNBGateway` and overrides only
  `initiate_payment`/`query_status` with fully scriptable fake results,
  injected via a FastAPI dependency override
  (`app.dependencies.payments.get_payment_gateway`) - the same pattern
  already used for `get_db` in `conftest.py`.

**Before this can go to production**: obtain the official PNB merchant
integration specification, rewrite `PNBGateway.initiate_payment`/
`query_status` against the real contract, replace the placeholder webhook
signature scheme with PNB's actual algorithm, and run the UAT/contract
tests described in `§36` of the originating spec (none of which exist yet
- they cannot, without real credentials).

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/payments` | CUSTOMER | Initiate payment for an order (UPI or COD). |
| GET | `/payments/{id}` | CUSTOMER, owner-only | Get a payment. |
| GET | `/orders/{order_id}/payment` | CUSTOMER, owner-only | Get the payment for one of the caller's orders. |
| POST | `/payments/{id}/retry` | CUSTOMER, owner-only | New UPI attempt for a FAILED/EXPIRED payment. |
| POST | `/payments/{id}/verify` | CUSTOMER, owner-only | Reconcile status against the gateway - never trusts a client claim. |
| POST | `/payments/webhooks/pnb` | none (gateway signature) | PNB callback. |

Client sends only `order_id` and `payment_method` at creation - amount,
currency, status, gateway references, and order confirmation are always
server- or gateway-authoritative (verified by
`test_client_cannot_control_amount_or_status`).

## Payment State Machine

`app/services/payment_state.py` - pure logic, no DB/HTTP dependency, unit
tested against the complete transition matrix (45 tests, every one of the
30 non-self (current, target) pairs in the 6x6 status grid, both legal and
illegal).

```
PENDING ──┬──> PROCESSING ──┬──> PAID        (terminal)
          ├──> PAID          ├──> FAILED ────> PROCESSING (retry)
          ├──> FAILED         ├──> EXPIRED ───> PROCESSING (retry)
          ├──> EXPIRED        └──> CANCELLED  (terminal)
          └──> CANCELLED (terminal)
```

The spec explicitly gives `PENDING -> PROCESSING`, `PROCESSING -> {PAID,
FAILED, EXPIRED}`, and `{FAILED, EXPIRED} -> PROCESSING`. This
implementation adds two narrow, documented extensions (in the module
docstring, not silently): `PENDING` may also go directly to
`PAID`/`FAILED`/`EXPIRED`/`CANCELLED` (a gateway can confirm/reject
synchronously, faster than our own `PENDING`->`PROCESSING` bookkeeping -
rejecting a legitimate fast confirmation would be strictly worse), and
`PROCESSING -> CANCELLED` (a customer explicitly cancelling mid-flow).

**`PAID` and `CANCELLED` are hard terminal states with zero outgoing
edges** - `transition_payment_status` raises `IllegalTransitionError` for
any attempted transition away from either. Same-state transitions (e.g.
`PAID -> PAID`, a duplicate success event) are always a safe no-op, never
an error. Both properties are directly what make repeated/duplicate events
harmless and a late `FAILED` after `PAID` impossible to apply
(`test_late_failed_after_paid_never_downgrades`).

`PaymentTransaction.status` has a simpler rule, enforced in
`PaymentService._apply_transaction_status`: once a specific attempt reaches
a terminal status (`SUCCESS`/`FAILED`/`CANCELLED`/`EXPIRED`), it is never
changed again - historical attempts are genuinely immutable, not just by
convention.

## Payment Transactions / Attempts

Never overwritten. A retry (`POST /payments/{id}/retry`) always creates a
**new** `payment_transactions` row - the prior attempt's row keeps its
terminal status forever
(`test_retry_creates_new_transaction_without_overwriting_history`).
`gateway_order_id` lives on `payments` (created once per obligation, on
first initiation) and is **reused** across retry attempts against that
same obligation, per the spec's "on the logical payment" instruction;
`gateway_transaction_id` lives on each individual `payment_transactions`
row.

## Client Is Never Authority

No code path ever does `payment.status = <client-or-gateway-claimed
value>` directly - every status change goes through
`transition_payment_status`. The webhook and `/verify` endpoints both
funnel through the exact same internal method,
`PaymentService._apply_transaction_status` (called only after the caller
already holds the payment row lock), so there is one single place gateway
truth is ever allowed to become our truth.

## Amount / Currency Validation

Before a webhook event can mark a payment `PAID`, its `amount`/`currency`
(when present in the event) are compared against `payment.amount`/
`payment.currency` - the values captured from the *order* at payment
creation, never client-supplied. A mismatch marks the
`payment_webhook_events` row `FAILED` and returns the gateway an
acknowledging 200 (nothing to retry - we deliberately chose not to act on
it) **without touching the payment at all**
(`test_webhook_amount_mismatch_does_not_mark_paid`,
`test_webhook_currency_mismatch_does_not_mark_paid`).

## Ownership

Every payment/order lookup is scoped to the authenticated user
(`user_id`). A payment that exists but belongs to another user returns the
**identical 404** as one that doesn't exist at all - ownership violations
are never distinguishable from nonexistence
(`test_user_cannot_read_another_users_payment`,
`test_user_cannot_initiate_payment_for_another_users_order`,
`test_user_cannot_read_another_users_order_payment`).

## COD

`payment_method = COD` never calls the gateway
(`gateway.initiate_calls == []`, asserted directly in
`test_cod_payment_created_pending_and_order_confirmed`). Payment is
created and stays `PENDING`; the order is confirmed immediately (per the
Phase 7 doc's documented COD lifecycle - cash collection and the
corresponding `payment_transactions` row belong to a future Delivery
phase, not built here). COD payments cannot be retried (
`test_cod_payment_cannot_be_retried` - 409, since there is no gateway
attempt to retry).

## Checkout Transaction: UPI Initiation

```
1. lock Order (ownership + existence check)
2. lock Payment for this order (if one already exists)
3. if existing payment already PAID -> 409, stop
4. if existing payment exists with a different method -> 409, stop
5. if existing payment exists (same method, not PAID) -> return it as-is
   (idempotent; re-attempting a non-PAID UPI payment is exclusively done
   via POST /payments/{id}/retry, never implicitly re-triggered here)
6. if no existing payment: verify order.status == PENDING, create Payment
7. UPI: create PaymentTransaction(INITIATED), payment -> PROCESSING,
   COMMIT (short transaction - lock released here)
8. call gateway.initiate_payment() OUTSIDE any held lock
9. re-lock Order+Payment, persist gateway_order_id/gateway_transaction_id,
   apply the gateway's synchronous result via the shared state-transition
   core, commit once
```

Step 7's short-transaction-around-the-external-call is deliberate (§12 of
the originating spec: never hold a DB row lock during a network call).
Step 8's gateway call is wrapped to distinguish three outcomes precisely -
see Crash Safety below.

## Crash Safety: The Central Guarantee

**A gateway call outcome is UNKNOWN unless the gateway definitively said
otherwise.** `app/services/payment_gateway.py` defines three distinct
exception types specifically so `PaymentService` never has to guess:

| Exception | Meaning | Payment ends up |
|---|---|---|
| `GatewayTimeoutError` / `GatewayConnectionError` | We don't know what happened - the payment may have succeeded on PNB's side despite us never getting a response | **`PROCESSING`** (unchanged) - recoverable via `/verify` |
| `GatewayRejectedError` | Gateway synchronously and definitively rejected the request - nothing is unresolved | `FAILED` (safe, retryable) |
| `NotImplementedError` (today's reality - no PNB contract) | This attempt definitively never reached the gateway at all | `FAILED` (safe, retryable) |

Verified directly: `test_gateway_timeout_leaves_payment_processing_not_failed`,
`test_gateway_connection_error_leaves_payment_processing`,
`test_gateway_definitive_rejection_marks_failed`. This is the single most
important behavior in this phase - collapsing all three into "mark
FAILED" is exactly the bug that would let a customer be charged by PNB
while our own records say the payment failed, inviting a blind, duplicate
retry.

### The four crash-safety cases from the originating spec

1. **DB attempt created, gateway call never happens, server crashes**: the
   short transaction in step 7 above either fully committed (transaction
   `INITIATED`, payment `PROCESSING`, safely retryable via `/verify`/`/retry`
   later) or never committed at all (nothing persisted, a fresh `POST
   /payments` call is safe and idempotent). There is no partially-committed
   state possible.
2. **PNB succeeds, our server times out**: `GatewayTimeoutError` ->
   payment stays `PROCESSING`, never `FAILED`. The customer or a later
   webhook can resolve it via `/verify` or the eventual webhook delivery.
3. **PNB succeeds, webhook arrives, we commit, our response to PNB is
   lost**: PNB retries the webhook; `UNIQUE(gateway_name, event_id)` makes
   the redelivery a safe no-op (`test_duplicate_webhook_is_a_safe_noop`).
4. **Two webhooks (or a webhook and a `/verify`) arrive/race
   simultaneously**: both lock the same payment row; Postgres serializes
   them; the loser observes the already-final state and no-ops
   (`test_concurrent_identical_webhook_delivery_processed_exactly_once`,
   `test_webhook_and_verify_race_exactly_one_confirmation`).

## Locking Strategy

Every code path that touches both an `Order` and a `Payment` locks `Order`
**first**, then `Payment` - enforced uniformly via two helpers
(`_lock_owned_order` for the order-first case,
`_lock_payment_and_order` for the payment-first case: webhook/retry/verify
naturally start from a payment reference, but still lock `Order` before
`Payment` internally). A single consistent global lock order across both
directions is what prevents a deadlock between "start from an order"
(payment creation) and "start from a payment" (webhook/retry/verify) under
concurrency.

### A real concurrency bug found and fixed during this phase

`_lock_payment_and_order` needs an initial *unlocked* read of the `Payment`
row purely to discover its `order_id` (so `Order` can be locked first).
That unlocked read populates the session's SQLAlchemy identity map. The
**first version** of this helper then re-queried the same `Payment` row
`with_for_update()` - which correctly acquires the Postgres lock and waits
if necessary, but **SQLAlchemy does not, by default, overwrite an
already-identity-mapped object's attributes with a freshly fetched row**.
The result: the lock was real, but the Python object's `.status` could
still reflect stale pre-lock data. `test_concurrent_retries_do_not_create_two_new_attempts`
caught this directly - two concurrent retries both observed a stale
`FAILED` status (missing the other's already-committed `PROCESSING`) and
both proceeded, instead of the second correctly seeing `PROCESSING` and
being rejected with 409. Fixed with SQLAlchemy's documented
`.populate_existing()` on both locked queries in `_lock_payment_and_order`.
Verified stable across repeated runs after the fix, not just a single
lucky pass.

## Webhook Processing Pipeline

```
1. verify_webhook_signature(raw_body, headers)   -- 401 if invalid, NO DB touch at all
2. parse_webhook_event(raw_body, headers)         -- 422 if malformed
3. INSERT payment_webhook_events (flush, not commit) -- dedup point
   -> IntegrityError (duplicate event_id): rollback, log, return 200 (no-op)
4. resolve the PaymentTransaction this event refers to (by
   gateway_transaction_id, falling back to gateway_order_id -> latest
   transaction for that payment)
   -> not found: mark webhook_event FAILED, commit, return 200 (ack; nothing to act on)
5. lock Order then Payment (via _lock_payment_and_order)
6. validate amount/currency against the payment's authoritative values
   -> mismatch: mark webhook_event FAILED, commit, return 200 (never touch payment)
7. apply state transition via the shared _apply_transaction_status core
8. if payment is now PAID: confirm the order (only from PENDING; already
   CONFIRMED/COMPLETED is a silent no-op; anything else logs a
   reconciliation warning)
9. mark webhook_event PROCESSED
10. COMMIT ONCE -- steps 4-9 are one atomic transaction
```

**Why step 3 uses `flush()` and not `commit()`**: this is what makes the
entire pipeline a single transaction while still giving correct
concurrency-dedup semantics. A concurrent duplicate delivery's own INSERT
attempt on the same `(gateway_name, event_id)` **blocks** at the Postgres
level on our still-uncommitted row until we commit or roll back - only
then does it either succeed (if we rolled back) or fail with a unique
violation (if we committed, meaning our entire processing, including the
final PAID/order-confirmed state, is already durable). This also gives
crash safety for free: if the process crashes anywhere between step 3 and
step 10, **nothing is committed at all** - not even the dedup row - so a
later redelivery of the same `event_id` is processed fresh, correctly,
with no special-case recovery logic needed.

Payment state is **never** touched before signature verification succeeds
(`test_invalid_webhook_signature_rejected_and_no_db_mutation` asserts zero
`payment_webhook_events` rows after a rejected signature).

## Out-of-Order Events

A `FAILED` webhook arriving after an already-`PAID` payment is accepted
(200, ack) but the state transition is illegal per the state machine -
`_apply_transaction_status` catches `IllegalTransitionError`, logs a
`PAYMENT_RECONCILIATION` warning, and leaves the payment untouched
(`test_late_failed_after_paid_does_not_downgrade`). The reconciliation log
line carries enough context (payment_id, source, attempted transition) to
investigate later, without ever risking the live state.

## Reconciliation

`POST /payments/{id}/verify` is the minimal reconciliation capability this
phase provides: it calls `gateway.query_status(...)` for the payment's
current `gateway_order_id`/latest transaction and applies whatever comes
back through the exact same state-transition core the webhook path uses.
There is no separate `PaymentReconciliationService` class - `verify_payment`
on `PaymentService` **is** that capability; introducing a second service
purely to wrap one existing method would be the "generic abstraction"
this project explicitly avoids. A full settlement/reporting reconciliation
sweep (comparing our DB against a PNB settlement report) is out of scope
until PNB's actual reporting format is known.

## Security

- Ownership enforced on every read/write (see Ownership above).
- Amount/currency/status/order_number are never client-settable
  (`test_client_cannot_control_amount_or_status`).
- `PaymentResponse`/`PaymentInitiationResponse` never include
  `gateway_response`, the webhook secret, or the merchant ID
  (`test_secrets_never_in_payment_response`). `PaymentInitiationResponse`'s
  `payment_session_token`/`upi_intent_uri` fields are only ever populated
  from a gateway result explicitly intended for client use - never a raw
  gateway payload.
- Webhook signature comparison uses `hmac.compare_digest` (constant-time).
- Logging never includes secrets, signatures, raw gateway payloads, or
  idempotency keys - only IDs, statuses, and categorized failure reasons
  (see every `logger.*` call in `app/services/payment.py`).

## Explicit Boundaries (Not Built This Phase)

- **No inventory effect.** `PaymentService` never imports
  `InventoryService`; no `InventoryLot`/`StockMovement` row is created or
  modified by any payment operation.
- **No refunds, partial refunds, or disputes.**
  `payment_transactions.transaction_type` remains restricted to
  `'PAYMENT'` by the existing Phase 7 CHECK constraint - untouched.
- **No cards, wallets, net banking, EMI, or multiple simultaneous
  gateways.**
- **No generic idempotency framework.** Payment-specific idempotency comes
  entirely from `payment_transactions.idempotency_key` (existing Phase 7
  column), row locking, and `UNIQUE(gateway_name, event_id)` on webhook
  events - not a reusable idempotency-key table.
- **No cash-collection/delivery machinery for COD.** A COD payment stays
  `PENDING` until a future Delivery phase records its own
  `payment_transactions` attempt.

## Known Limitations

- **UPI cannot actually complete against real PNB** until the official
  merchant integration specification is obtained and `PNBGateway` is
  rewritten against it - see the Integration Boundary section above. This
  is not a bug; it's an honest, structural gap.
- **The webhook signature scheme is a placeholder.** It must be replaced
  with PNB's real algorithm before production use - do not assume
  `X-PNB-Signature` + HMAC-SHA256 is correct.
- **No UAT/contract tests exist** (spec §36) - they require real PNB
  credentials, which do not exist in this environment.
- **No full settlement reconciliation sweep** - only single-payment
  `/verify` reconciliation is implemented.

## Focused Validation Performed

- `tests/test_phase_14_payment_state.py` - 45 unit tests, the complete
  payment status transition matrix (every legal and illegal pair) plus
  terminal-state and idempotency-no-op behavior. No DB, no HTTP.
- `tests/test_phase_14_payments.py` - 34 tests against real PostgreSQL via
  the full HTTP stack (`FakePNBGateway` injected via dependency override):
  COD lifecycle, UPI happy path, retry history preservation, amount/currency
  mismatch rejection, duplicate and out-of-order webhook handling, webhook
  authenticity/malformed-payload/unknown-reference handling, ownership
  isolation, client-authority rejection, secret-leakage checks, order
  payability rules, three-way gateway-failure-mode distinction (including
  a direct assertion against the real un-faked `PNBGateway` proving
  `NotImplementedError` and proving the placeholder signature scheme
  actually verifies/rejects correctly), five genuine-concurrency scenarios
  via `ThreadPoolExecutor` against real Postgres locks (concurrent
  initiation, concurrent identical webhook delivery x4, webhook-vs-verify
  race, concurrent retries), and one fault-injection rollback test
  (monkeypatched mid-transaction failure, DB state re-verified - not
  inferred from the 500 response alone - proving no partial payment/order/
  webhook-event state survives).
- Regression: `tests/test_phase_13_cart_orders.py` (39), `tests/test_phase_10_catalog.py`
  (13), `tests/test_auth.py` (12), and `tests/test_phase_9_rbac.py` (8, run
  in isolation per that suite's own documented requirement) - 109 + 8 = 117
  tests, all passing, confirming the `Payment` model extension and the new
  `Order.status` mutation path introduced no regressions elsewhere.
