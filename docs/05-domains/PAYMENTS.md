# Payments

> **Status:** Verified against source and the fake-gateway test suite on 2026-10-14; **Not verified** against a live Razorpay sandbox (no authorised test environment — [BASELINE_AUDIT](../testing/BASELINE_AUDIT.md) §4). One confirmed open defect: **PAY-001**.
> **Source files:** [`services/payment.py`](../../backend/app/services/payment.py), [`payment_state.py`](../../backend/app/services/payment_state.py), [`payment_gateway.py`](../../backend/app/services/payment_gateway.py) (protocol + errors), [`razorpay_gateway.py`](../../backend/app/services/razorpay_gateway.py), [`checkout_session.py`](../../backend/app/services/checkout_session.py), [`dependencies/payments.py`](../../backend/app/dependencies/payments.py), [`api/v1/payments.py`](../../backend/app/api/v1/payments.py); models `payment`, `payment_transaction`, `payment_webhook_event`, `checkout_session`; mobile `src/api/paymentApi.ts`, `src/features/payment`, `src/features/checkout/useOnlineCheckout.ts`, `src/components/payment/Razorpay*`.
> **Tests:** [`test_phase_14_payment_state.py`](../../backend/tests/test_phase_14_payment_state.py), [`test_phase_14_payments.py`](../../backend/tests/test_phase_14_payments.py), [`test_razorpay_payments.py`](../../backend/tests/test_razorpay_payments.py), [`test_online_checkout.py`](../../backend/tests/test_online_checkout.py), [`test_money_integrity.py`](../../backend/tests/test_money_integrity.py). Webhook details: [WEBHOOKS](../03-api/WEBHOOKS.md). Refunds: [REFUNDS](REFUNDS.md).

## Methods

| Method | Stored `payment_method` | Gateway | When the order becomes `CONFIRMED` |
|---|---|---|---|
| Cash on Delivery | `COD` | none | when COD is chosen (`POST /payments`) and the reservation commits; payment stays `PENDING` until delivery |
| Online (UPI, cards, netbanking, wallets via Razorpay Checkout) | `UPI` (the only online value the DB allows) | Razorpay | when the payment is captured and the reservation commits |

`GET`/`POST` operations and their gates: [API_REFERENCE → payments](../03-api/API_REFERENCE.md#payments). Customer routes require role `CUSTOMER`; admin payment views and the refund queue require role `ADMIN`.

## Two online paths

1. **Pay-first checkout sessions** (`/payments/online/start|confirm|verify`) — used by the app for a normal cart ([CART_AND_CHECKOUT](CART_AND_CHECKOUT.md)). No order exists until payment is confirmed.
2. **Order-first payments** (`POST /payments`, `/payments/{id}/checkout|confirm|retry|verify`) — for an **existing** `PENDING` order: orders converted from bulk quotes, and "pay now / retry" from the order screen. The order's reservation is already running (30 min).

Both converge on `payment_state` and on `RazorpayGateway`; both honour the rules below.

## State machines

Payment: `PENDING → PROCESSING → PAID` (terminal); `PROCESSING → FAILED | EXPIRED` (retryable back to `PROCESSING`); `PENDING → PAID|FAILED|EXPIRED|CANCELLED` (a gateway may answer synchronously); `PROCESSING → CANCELLED`. `CANCELLED` is terminal. The `payment_state.py` docstring says a cancelled attempt "is superseded by a brand-new payment attempt via /retry", but `can_retry_payment` allows retry **only from `FAILED` or `EXPIRED`**, so a `CANCELLED` payment cannot be retried (the code wins; docstring/code mismatch noted in [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md)). Transaction (`payment_transactions`): `INITIATED → PROCESSING → SUCCESS | FAILED | CANCELLED | EXPIRED`. An illegal or late transition (e.g. `PAID → FAILED`) is **logged and ignored**. `payment.failed` from Razorpay is deliberately mapped to `PROCESSING` (the customer may retry in the same Checkout); only a capture finishes a payment.

## Rules (all enforced in `payment.py` unless noted)

- **The client is never authority.** Status moves only from our own gateway call result, an authenticated webhook, or `verify`/`confirm` which re-query Razorpay.
- **Amount comes from the server** (`order.total_amount` or the session amount). Razorpay's reply must match amount and currency or the attempt is refused; webhook and verify amounts must equal the stored amount (mismatch → logged, no state change).
- **One payment per order** (`uq_payments_order_id`); `POST /payments` for an existing payment returns it unchanged; a different method on the same order → 409; a paid order → 409.
- **Idempotency key** per gateway attempt (`payment_transactions.idempotency_key`, unique) — sent to Razorpay **in `notes` only**, not as a Razorpay idempotency header.
- **Retry:** only `UPI`, only from `FAILED` or `EXPIRED` (`can_retry_payment`); a payment still `PROCESSING` must be `verify`-ed first. Retries reuse the same Razorpay order; if it was already paid in the meantime the retry reports success instead of asking the customer to pay twice.
- **Checkout signature** (`razorpay_order_id|razorpay_payment_id` HMAC with the key secret) is verified before `confirm`; then Razorpay is asked for the authoritative order state.
- **Order confirmation requires the reservation to commit.** If the payment is `PAID` but the reservation expired: the order is moved to `EXPIRED` and a refund request is created (`PAYMENT_RECONCILIATION`); if the reservation cannot be committed for another reason the order is left as is and `PAYMENT_RESERVATION_MISMATCH` is logged (no auto-confirm).
- **Payment resolving after the order was cancelled** creates refund eligibility (money was collected for an order that will never ship).
- **Lock order:** Order → Payment everywhere. Gateway calls happen **after** the lock is released (`_initiate_upi`, `process_refund`).

## Duplicate, concurrent and lost-response behaviour

| Scenario | Behaviour | Evidence |
|---|---|---|
| Duplicate `POST /payments` | Existing payment returned, no second gateway call | `test_phase_14_payments.py` |
| Duplicate / replayed webhook | One effect (dedup row), 200 for the replay | `test_duplicate_webhook_is_a_safe_noop`, `test_concurrent_identical_webhook_delivery_processed_exactly_once` |
| Webhook racing `verify` | Exactly one confirmation | `test_webhook_and_verify_race_exactly_one_confirmation`, `test_money_integrity.py` |
| Webhook racing `confirm` (pay-first) | Exactly one order | `test_confirm_and_webhook_racing_place_exactly_one_order`, `test_two_simultaneous_confirms_place_exactly_one_order` |
| Gateway times out creating the Razorpay order | Reported as a definite failure (creating an order moves no money): payment `FAILED`, retryable | `razorpay_gateway.initiate_payment` comment + code |
| Gateway times out on a status/verify call | HTTP 502 `PAYMENT_GATEWAY_UNAVAILABLE`; state unchanged; retry later | `handlers.py`, `verify_payment` |
| Customer paid but the app never called back | Webhook (if delivered) or `/verify` completes it; otherwise **only a log line** exists | `complete_from_webhook`, no reconciliation job |
| Money captured for a payment/session nothing matches | `PAYMENT_WEBHOOK_UNKNOWN_REFERENCE` logged, event `FAILED`, **no refund, no alert** | `process_webhook` |
| Pay-first order cannot be placed | Automatic refund; if the refund call fails the session becomes `REFUND_FAILED` and `PAYMENT_RECONCILIATION` is logged for manual handling | `_refund_and_fail` |
| Latest cart already ordered another way (COD) when a pay-first payment completes | **Defect PAY-001:** payment attached to the existing order, no refund | `test_money_integrity.py::…refunded_not_attached` (strict `xfail`) |
| Two customers pay for the last unit | One order, one automatic refund | `test_two_customers_paying_for_the_last_unit_one_order_one_refund` |

## Cash on Delivery

No gateway, no transaction row at confirmation. At delivery `_collect_cod_payment` moves `PENDING → PAID` and records a `SUCCESS` transaction with `{"method": "CASH_ON_DELIVERY", "collected_by_user_id": …}` in the same transaction as the delivery. A COD payment in an unexpected state at delivery is logged (`PAYMENT_RECONCILIATION`) and **does not block the delivery**.

## Admin views

`GET /payments/admin` (filters: status, payment_method, order_id, date range, `q`) and `/payments/admin/{id}` (transactions, webhook events, refund) — role `ADMIN`, shown on the Admin Payments page. No admin action can mark a payment paid or failed manually.

## Configuration and startup checks

`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_BASE_URL`, `RAZORPAY_TIMEOUT_SECONDS` ([ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md)). Empty `RAZORPAY_KEY_ID` ⇒ online payment refused with 503 `ONLINE_PAYMENTS_NOT_CONFIGURED`, COD continues. In production, a key id without both secrets **prevents start-up**; `rzp_test_…` keys in production only log a warning. The Razorpay account must use **automatic capture**.

## Known gaps

- PAY-001 open; no automatic reconciliation of unmatched captures; no alerting on the reconciliation log markers.
- `payment_method` is `UPI` for cards/netbanking/wallets too (naming debt). **PNB leftovers:** `payment_gateway.py` still contains a deliberately incomplete, **unwired** `PNBGateway` placeholder adapter (every call raises "PNB merchant API contract … not yet available"), several comments mention PNB, and `test_phase_14_payments.py` subclasses it as `FakePNBGateway`. The live gateway is `RazorpayGateway` (`dependencies/payments.py`). The adapter's docstring points to `docs/architecture/PHASE_14_PAYMENTS.md`, which does not exist in `backend/docs/`.
- Razorpay live-mode behaviour, payment-link flows, partial refunds and multi-capture were not examined.
- The order-first and pay-first paths duplicate some logic; changes to one must be mirrored.
