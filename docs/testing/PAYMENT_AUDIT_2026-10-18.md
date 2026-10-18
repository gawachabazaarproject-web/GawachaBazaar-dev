# Payment audit — 2026-10-18

> **Method:** adversarial read of the payment code and the pay-first mobile flow, building on the earlier QA audit ([DEFECT_LOG](DEFECT_LOG.md), [PAYMENTS](../05-domains/PAYMENTS.md), [WEBHOOKS](../03-api/WEBHOOKS.md)). **No test was executed in this audit**: Docker is not running and the only local PostgreSQL is on port 5432, which `AGENTS.md` forbids for tests. Every "OK" below means *verified by reading the code* (or "covered by a prior test that I did not re-run"); every defect is *confirmed by reading, not reproduced*. No live Razorpay sandbox was used. Nothing in the repo was modified except this file and `KNOWN_ISSUES.md`.
>
> **Files read:** `services/checkout_session.py`, `payment.py` (create/retry/verify/confirm/webhook), `razorpay_gateway.py`, `refund.py`, `api/v1/payments.py`, `order.py::checkout`, `models/checkout_session.py`, `mobile/src/features/checkout/useOnlineCheckout.ts`, `mobile/app/checkout/index.tsx`, config/startup checks.
> **Not read in depth:** `payment_state.py`, promotions/redemption locking, the order cancel state machine, inventory reservation internals, the Admin Payments/Refunds pages, deploy config.

## Verdict

**GO-LIVE for real online money: NO** — until PAY-001, PAY-004, PAY-005 are fixed and one end-to-end run against Razorpay *test mode* has been done. COD is unaffected. No P0 (client-controlled amount, signature bypass, authorization bypass, oversell) was found in the code I read; the protections there are good (below). The problems are all in the *unhappy paths*: money taken but no order, no refund, nobody told.

## What is solid (by code reading)

| Area | Evidence |
|---|---|
| Amount is server-computed | `start()` prices via `quote_checkout`; the Razorpay order amount is checked against the quote; `_finalize` re-checks Razorpay's captured amount and passes `expected_total` to checkout, so a price change refunds instead of mis-charging |
| Client is not payment truth | `confirm` verifies the HMAC (`order_id|payment_id`, key secret) and then **asks Razorpay** (`query_status`); `verify` needs no client proof at all |
| Webhook auth | HMAC-SHA256 over the raw body, constant-time compare, missing secret/header → 401, checked before any state change; unknown slug → 404 |
| Replay/duplicates | `UNIQUE(gateway_name, event_id)` dedup row in the same transaction; `uq_payments_order_id`; `uq_checkout_sessions_gateway_order` |
| Ownership | session/payment/order lookups filter by `user_id` and return 404; admin routes need ADMIN |
| Locks | Order → Payment order; reservation commit gates confirmation |
| Secrets | Key secret never leaves the backend; only `key_id` is returned; no `rzp_live_` string in tracked source (checked file list, values not printed) |

## Defects

### PAY-001 (existing, **High**, open) — second paid session is silently absorbed — root cause pinned down
- **Where:** `checkout_session.py` `_finalize`, line ~286: `order_detail, _created = OrderService(...).checkout(...)` — the `created` flag is thrown away. When the cart is already `CHECKED_OUT`, `checkout()` returns the *existing* order (`order.py:455-463`), and `_attach_paid_payment` returns the *existing* payment (`checkout_session.py:321`). The session is marked `COMPLETED` against an order that was paid by a different Razorpay order.
- **Impact:** a customer who paid twice (two sessions, two devices, or COD + online for the same cart) is charged for money that is never attached to anything and never refunded.
- **Fix:** if `created` is false and the order's payment has a different `gateway_order_id`/transaction than this session, call `_refund_and_fail` instead of completing. **Regression test:** two sessions for one cart, both captured → exactly one order, one refund (the existing strict-xfail `…refunded_not_attached` covers the COD variant).

### PAY-004 (new, **P1**) — a transient Razorpay error burns the webhook event, so the order is never created
- **Where:** `payment.py:674` marks the event `PROCESSED` *before* calling `sessions.complete_from_webhook`; `checkout_session.py:268-272` `_finalize` does `self.db.commit(); raise` on `GatewayError`, which commits that dedup row. `GatewayError` is a plain `Exception` (`payment_gateway.py:57`), not an `AppException`, so `complete_from_webhook` does not catch it; the route returns 5xx, Razorpay retries, and the retry is dropped as `PAYMENT_WEBHOOK_DUPLICATE`. `PaymentNotConfirmedError` is caught but the event stays `PROCESSED` too.
- **Scenario:** customer pays in a UPI app and the app dies; Razorpay's `GET /orders/{id}/payments` times out once during the webhook → money taken, no order, event permanently "done". Partial mitigation: Razorpay also sends `order.paid` as a *separate* event id, which gets a second chance — but only if it is subscribed and the outage is shorter than the gap.
- **Fix:** on `GatewayError` roll back (so the dedup row disappears and Razorpay's retry is processed), or only mark `PROCESSED` after `_finalize` succeeds and record `FAILED`/`RETRY` otherwise. **Regression test:** fake gateway whose first `query_status` raises, same event delivered twice → order exists after the second delivery.

### PAY-005 (new, **P1**) — nothing reconciles "paid but no order"
- **Where:** no job, queue or alert exists (confirmed in PAYMENTS "Known gaps", re-confirmed: `PAYMENT_WEBHOOK_UNKNOWN_REFERENCE`, `PAYMENT_RECONCILIATION` are log lines only). The app keeps `session_id` **in memory only** (`useOnlineCheckout.ts` uses `useState`), so after an app kill there is no client-side recovery either. `start()` reuses a still-`PENDING` session but never checks whether Razorpay already captured it, so tapping Pay again opens a sheet for an already-paid order.
- **Fix:** (1) a periodic sweep over `checkout_sessions` `PENDING` older than a few minutes and `payments` stuck `PROCESSING`: ask Razorpay and call `_finalize`/`verify_payment`; (2) in `start()`, when reusing a session, run `_finalize` first and return the order if already paid; (3) persist `session_id` on the device and call `/verify` on app start/resume; (4) alert on `REFUND_FAILED` and unknown-reference events. Note the app must run on **one** worker ([AGENTS.md](../../AGENTS.md)), so a simple in-process loop is consistent with the existing reservation sweep.

### PAY-006 (new, **P1, UX**) — customer is shown an error after a *successful* payment
- **Where:** `useOnlineCheckout.ts:61-77` — after Razorpay's success callback, any confirm failure other than `PAYMENT_NOT_CONFIRMED` (network loss, 502 gateway timeout, expired JWT → 401) is shown as a raw error with the cart "intact" and the Pay button live. `dismiss()` (`:81-96`) swallows every error and returns silently.
- **Impact:** the customer sees "failed" while money is deducted, and may pay again. The order may still appear via the webhook (see PAY-004/005).
- **Fix:** once the success callback has fired, treat any non-business error as "pending": show "Payment received, confirming…", go to Orders, and retry `/verify` in the background; never show a raw network/5xx message on that path.

### PAY-008 (new, **P2**) — concurrent `start` creates two Razorpay orders
- **Where:** `checkout_session.py:90-125`: look-up-then-insert with no cart lock and no unique index on `(user_id, cart_id)` for `PENDING`. A double tap or two devices can create two sessions/orders; only one is normally paid, but if both are, PAY-001 applies. **Fix:** lock the cart row (as `checkout()` does) or add a partial unique index; **test:** 10 concurrent `start` calls → one session.

### PAY-007 (new, **P2**) — row locks held across gateway calls
- `_finalize` holds the session row lock across `query_status` (up to the 10 s timeout) and `_refund_and_fail` holds it across `refund_payment`; this breaks the documented invariant "never hold a row lock across a gateway call" and ties up a DB connection per slow request. **Fix:** release (commit) before the call and re-lock after, as `process_refund` does.

### PAY-009 (new, **P2**) — all failures of the automatic refund look the same
- `_refund_and_fail` catches `Exception`; a *timed-out but successful* refund is recorded `REFUND_FAILED` ("refund manually"), there is no `refunds` row for admins to see, and no retry action. Extends PAY-3. **Fix:** write a `Refund` row (or reuse the admin queue), treat timeouts as "unknown → verify", add an admin retry.

### PAY-010 (new, **P2**) — test keys in production only warn
- `main.py:72-75` logs a warning for `rzp_test_` keys in production. Cheap hardening: fail startup unless an explicit `ALLOW_RAZORPAY_TEST_KEYS` flag is set; and the reverse (live keys in dev) cannot be detected at all.

### Smaller / already known
- **P2** G-REF-1: a refund whose gateway reply was lost has no reference, so *sync* refuses; recovery is the Razorpay dashboard.
- **P2** Refunds are full-amount only and every cancelled paid order needs manual approve + process (`refund.py`); partial refunds are not implemented, so "partial refund" tests are **NOT TESTABLE**.
- **P3** PAY-2 docstring/code mismatch; the unwired `PNBGateway` placeholder.
- **Operational, unverifiable here:** Razorpay must have **automatic capture** on (`payment.authorized` is handled as `PROCESSING` only, and `query_status` treats only `captured`/`refunded` as paid). A wrong setting means authorised-but-uncaptured money that Razorpay later voids while customers believe they paid.

## Test matrix (code-read; **0 executed**)

| ID | Scenario | Result |
|---|---|---|
| T01 | Client sends `status: success` / forged callback | OK (code): signature + Razorpay re-query; no status field is trusted |
| T02 | Tamper amount/price/qty/discount | OK (code): server prices; `expected_total` + gateway amount checks |
| T03 | Another user's order/payment/session id | OK (code): `user_id` filter → 404 |
| T04 | Invalid / missing / modified webhook signature | OK (code) + prior tests, not re-run |
| T05 | Duplicate / replayed webhook | OK (code, prior tests) |
| T06 | Webhook before / after callback | OK (code, prior tests) |
| T07 | Double tap Pay | **FAIL-risk** PAY-008 (two orders); mobile `busy` flag reduces it |
| T08 | Two sheets paid for one cart | **FAIL** PAY-001 |
| T09 | Money deducted, callback lost, app killed | **FAIL-risk** PAY-004/005 (depends on webhook only) |
| T10 | Network loss right after payment | **FAIL** PAY-006 (error shown) |
| T11 | Razorpay 5xx/timeout during webhook finalize | **FAIL** PAY-004 |
| T12 | Razorpay order creation lost response | OK (code): reported as failure, orphan unpaid order is harmless |
| T13 | Refund twice / concurrent refund | OK (code): unique `order_id`, `PROCESSING` guard; Razorpay also rejects over-refund |
| T14 | Refund API timeout | PARTIAL: stays `PROCESSING`; recovery manual (G-REF-1) |
| T15 | Pay-first auto-refund fails | **FAIL** PAY-009 (no row, no alert) |
| T16 | Inventory last-unit race | OK (prior test `…last_unit_one_order_one_refund`, not re-run); reservation not re-read |
| T17 | Coupon concurrency / abuse | NOT EXAMINED |
| T18 | JWT expiry mid-checkout | PARTIAL: `confirm` 401 → PAY-006; webhook path unaffected |
| T19 | Amount mismatch at gateway | OK (code): refused / logged, no state change |
| T20 | Live card/UPI/netbanking, real webhook delivery, Razorpay retry timing | **BLOCKED** (no sandbox) |
| T21 | Partial refund | NOT TESTABLE (not implemented) |
| T22 | Automated suite | **BLOCKED** (no disposable DB); last known: 891 pass / 7 fee-test failures (2026-10-14) |

Totals: 22 scenarios — 0 executed; defects: P0 0, P1 3 (PAY-004, 005, 006) + PAY-001 (High), P2 5, P3 2.

## Support / reconciliation (recommended)
Admin Payments can search by order number, customer name/email and Razorpay **order** id; there is no search by Razorpay **payment** id or phone, and no view of `checkout_sessions` at all — so a "paid but no order" customer is invisible to support. Recommended process: (1) add `checkout_sessions` and payment-id search to Admin; (2) daily job comparing Razorpay `captured` payments of the last 48 h with `payments`/`checkout_sessions.status`; (3) every mismatch → refund or place the order, logged with `internal_order_id`, `razorpay_order_id`, `razorpay_payment_id`, `user_id`. Logs already carry these ids and no card data (not exhaustively grepped).

## The question: 1,000 real payments tomorrow

Based on the code, realistically:
1. **Money taken, no order (most likely):** a handful of customers pay through a UPI app, return to a dead callback, and Razorpay's status API hiccups during the webhook → PAY-004 burns the event, nothing retries (PAY-005), the app shows an error (PAY-006) or nothing. They are out of pocket until someone notices. Expect this in proportion to your Razorpay API error rate and UPI hand-off failures — a few per thousand is plausible, not a guess I can measure.
2. **Charged twice, refunded never:** double taps, two devices or COD-then-online on one cart (PAY-008 → PAY-001). Rare, but the money is silently stranded.
3. **Auto-refund that fails** (stock gone or price changed after paying) leaves the money with you and only a log line (PAY-009).
4. **Refunds:** each cancelled paid order waits for a human to approve *and* process; a lost reply leaves it stuck (G-REF-1). Slow, not lossy.
5. **Not found in the code I read:** client-controlled amounts, signature bypass, cross-customer access, overselling (the last relies on prior tests I did not re-run). **Not examined:** coupon races.

## Recommended order of work
1. PAY-004 (small change), PAY-001 (small change), PAY-008. 2. PAY-005 sweep + `start()` re-check + persisted session id, PAY-006 UX. 3. PAY-009/007/010. 4. One full run in Razorpay test mode (UPI, card, failure, cancel, app-kill, duplicate webhook via the dashboard) on a disposable database, then re-run the suite and fix the 7 fee tests.
