# Webhooks

> **Status:** Verified against source and tests on 2026-10-14 (gateway faked in tests; a live Razorpay sandbox delivery was **not** run). Related: [PAYMENTS](../05-domains/PAYMENTS.md), [REFUNDS](../05-domains/REFUNDS.md), [DATA_FLOW](../02-architecture/DATA_FLOW.md) §4.
> **Evidence:** [`api/v1/payments.py`](../../backend/app/api/v1/payments.py) (`gateway_webhook`), [`services/payment.py`](../../backend/app/services/payment.py) (`process_webhook`), [`services/razorpay_gateway.py`](../../backend/app/services/razorpay_gateway.py), [`models/payment_webhook_event.py`](../../backend/app/models/payment_webhook_event.py), tests [`test_razorpay_payments.py`](../../backend/tests/test_razorpay_payments.py), [`test_phase_14_payments.py`](../../backend/tests/test_phase_14_payments.py), [`test_refund_integrity.py`](../../backend/tests/test_refund_integrity.py), [`test_money_integrity.py`](../../backend/tests/test_money_integrity.py).

## Inbound webhooks (the only ones)

The backend **receives** one webhook and sends none.

| | |
|---|---|
| Endpoint | `POST /api/v1/payments/webhooks/{gateway_slug}` — only `razorpay` is answered; any other slug returns 404 `NOT_FOUND` before the body is read |
| Auth | None (public). Authenticity = **HMAC-SHA256 of the raw body** with `RAZORPAY_WEBHOOK_SECRET`, compared in constant time with the `X-Razorpay-Signature` header. Missing secret, missing header or mismatch → 401 `AUTHENTICATION_ERROR` and no state is touched |
| Response | `200 {"received": true}` for processed, ignored and duplicate events. Errors: 401 (bad signature), 422 `BUSINESS_VALIDATION_ERROR` (malformed payload), 409 on a commit conflict |
| Event id | `X-Razorpay-Event-Id`; if absent, SHA-256 of the body (so re-deliveries still dedupe) |
| Handler | async route reads the raw body, then runs `PaymentService.process_webhook` on the threadpool |

### Events acted on

| Razorpay event | Meaning in the system |
|---|---|
| `payment.captured`, `order.paid` | Transaction `SUCCESS` → payment `PAID` → order confirmed (needs the reservation to commit). For a pay-first checkout with no payment yet, completes the checkout session (creates the order) |
| `payment.authorized` | `PROCESSING` (money on hold; **automatic capture must be on** in Razorpay) |
| `payment.failed` | Deliberately mapped to `PROCESSING`, not failed: the customer can retry in the same Checkout and a later capture must still land |
| `refund.processed` | Refund `PROCESSING → REFUNDED` |
| `refund.failed` | Refund `PROCESSING → FAILED` |
| anything else (e.g. `refund.created`) | Acknowledged and ignored (`PAYMENT_WEBHOOK_IGNORED` logged) |

The operator is told to subscribe to `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`, `refund.failed` ([`deploy/README.md`](../../deploy/README.md) → Payments); `payment.authorized` is handled but not in that list.

### Processing guarantees

1. Signature verified **before** anything else.
2. A `payment_webhook_events` row is inserted with `flush` inside the same transaction; the unique key `(gateway_name, event_id)` makes a duplicate or concurrent re-delivery a no-op that returns 200.
3. The transaction is resolved by gateway transaction id, else gateway order id, else (for pay-first) the checkout session. Unknown references mark the event `FAILED` and log `PAYMENT_WEBHOOK_UNKNOWN_REFERENCE` (still 200).
4. **Amount and currency must equal the stored payment**; a mismatch marks the event `FAILED`, logs `PAYMENT_RECONCILIATION` and changes nothing.
5. State changes go through the pure state machine; an illegal late transition is logged and ignored (no 5xx, so Razorpay does not retry forever).
6. Order locked before payment; one commit; realtime/push events are sent only after the commit.
7. Event status values: `RECEIVED`, `PROCESSED`, `FAILED` (DB `CHECK`).

### Failure and replay behaviour

| Scenario | Behaviour | Evidence |
|---|---|---|
| Forged / unsigned request | 401, no write | `test_razorpay_payments.py`, `test_phase_14_payments.py` |
| Exact replay (same event id) | 200, no second effect | same + `test_money_integrity.py` |
| Webhook racing the app's `confirm`/`verify` | Both converge on the same locked state; second is a no-op | `test_online_checkout.py`, `test_money_integrity.py` |
| Webhook arrives before the app callback (pay-first) | Creates the order from the session | `test_online_checkout.py` |
| Webhook for an order the system cannot match | Logged, event `FAILED`, **money is not refunded and nobody is alerted** | code; no alerting exists |
| Backend down when Razorpay sends | Depends on Razorpay's retry policy (not in the repository); the app's `verify` endpoint is the fallback | – |
| Webhook secret not configured | Every webhook returns 401; production start-up **refuses** a config with `RAZORPAY_KEY_ID` set but secret/webhook secret empty | [`config.py`](../../backend/app/core/config.py) validator |

### Operating notes

- Configure in Razorpay: URL `https://<API_DOMAIN>/api/v1/payments/webhooks/razorpay`, a long random secret copied into `RAZORPAY_WEBHOOK_SECRET`, automatic capture enabled.
- The raw body must reach the app unmodified (Caddy proxies it unchanged; any intermediate that re-serialises JSON would break the signature).
- There is no replay/retry UI. To resolve a stuck payment use the customer `verify` endpoint or inspect the Admin Payments page; refunds stuck in `PROCESSING` use `POST /payments/refunds/{id}/sync` ([REFUNDS](../05-domains/REFUNDS.md)).

## Outbound webhooks

None. The backend calls Razorpay's REST API (`POST /orders`, `GET /orders/{id}/payments`, `POST /payments/{id}/refund`, `GET /refunds/{id}`), Cloudinary, Google/OSRM routing and the Expo push API, but sends no webhooks to anyone.

## Unverified

A real Razorpay test-mode delivery (headers, payload shapes beyond what the tests construct), Razorpay retry timing, and behaviour behind an AWS ALB were not exercised ([QUALITY_GATES](../07-testing/QUALITY_GATES.md), [BASELINE_AUDIT](../testing/BASELINE_AUDIT.md) §4).
