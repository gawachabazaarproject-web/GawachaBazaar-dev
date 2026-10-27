# Cash on Delivery operations

> **Status (2026-10-27):** implemented with the delivery partner system (see [DELIVERY_PARTNER](DELIVERY_PARTNER.md)). Evidence: `services/delivery_assignment.py`, `models/delivery_partner.py`, `tests/test_delivery_partner.py`.

## What the server owns

* **Expected amount.** When a partner is assigned, `delivery_assignments.cod_expected_amount` is copied from the order's COD `payments.amount` (never typed by anyone). Prepaid orders get `NOT_APPLICABLE` and amount 0.
* **States:** `NOT_APPLICABLE` → (`COD_PENDING` → `COD_COLLECTED` | `COD_FAILED`). Cancelling/rejecting before pickup returns `COD_PENDING` to `NOT_APPLICABLE` (nothing was ever at stake); a failed hand-over sets `COD_FAILED`.
* **Confirmation.** Only the assigned partner, only from `OUT_FOR_DELIVERY`, only with `cod_collected_amount` **exactly equal** to the expected amount. Lower, higher, zero, negative or missing → 422 and **nothing changes** (order stays CONFIRMED, payment unpaid, stock reserved, no earning). **Partial collection is deliberately not supported** (decision: the customer either pays the whole bill or the delivery is marked failed); change it only with an explicit design.
* **Atomic completion.** One transaction (`FulfillmentService.confirm_delivery`): lock Order → Fulfillment → Assignment → reservation → lots → Payment; consume stock; payment PAID + transaction row; assignment DELIVERED with COD facts; partner earning row; order COMPLETED; referral qualification. Any failure rolls back the lot. Double/concurrent completion is idempotent (one earning, one stock movement).
* **DB guards:** `CHECK(cod_status <> 'COD_COLLECTED' OR collected = expected)` and `CHECK(status <> 'DELIVERED' OR cod_status IN ('NOT_APPLICABLE','COD_COLLECTED'))`.
* **Legacy path:** `POST /fulfillments/{id}/deliver` still works for ADMIN/the assigned partner and records the full expected amount as collected; for an unpaid COD order a non-admin partner must now also send the delivery `otp` (see below). The partner app uses the strict `/delivery-partner/assignments/{id}/deliver`.

## Reconciliation

`GET /delivery-partners/cod` (`partners.read`) lists COD rows and the **outstanding** total (collected, not yet reconciled). `POST /delivery-partners/assignments/{id}/cod-reconcile` (`partners.cod_reconcile`, ADMIN only) stamps `cod_reconciled_at/by`, audited, once. It records that the shop received the cash; it does not move money in any gateway. Settlement frequency and partner cash limits are **business decisions not yet made** (no limit is enforced).

## Delivery OTP (proof of delivery) - implemented

> Evidence: `services/delivery_otp.py`, `models/delivery_otp.py`, migration `d3e4f5a60712`, `tests/test_delivery_otp.py`. Runtime verification on a real device/FCM has **not** been done (see Limitations).

**Rule.** **Every** delivery (prepaid and COD) cannot be completed without the 6-digit code the customer holds - by the partner or by an ADMIN (no bypass). The check lives inside `FulfillmentService.confirm_delivery`, i.e. inside the same transaction that consumes stock, marks payment PAID, writes the partner earning and completes the order - so a wrong code changes nothing but its own attempt counter, and a right code can only ever be spent once.

**Flow.**
1. The code is issued **automatically** when the order goes `OUT_FOR_DELIVERY` (partner app or `/fulfillments/{id}/out-for-delivery`); `POST /delivery-partner/assignments/{id}/otp/send` resends (replaces) it.
2. Server generates `secrets.randbelow(10**6)` formatted to 6 digits, stores an **HMAC-SHA256** (key `DELIVERY_OTP_SECRET`, over `order_id:assignment_id:code`) plus a Fernet-encrypted copy that exists only so the *owning customer* can read it in the app; the copy is set to NULL on verify/invalidate/lock. Any older active code for the order is invalidated (`REPLACED`). One active code per order is a partial unique index.
3. Customer gets a push (type `DELIVERY_OTP`, tap opens the order) and sees the code on the order screen (`GET /orders/{id}/delivery-otp`, owner only, 404 for anyone else; code returned only while ACTIVE).
4. Partner submits it with the existing `POST /delivery-partner/assignments/{id}/deliver` (`otp` field) - this is the verification endpoint; legacy `POST /fulfillments/{id}/deliver` accepts an optional `{ "otp": "..." }` body.

**Limits.** Expiry `DELIVERY_OTP_EXPIRY_MINUTES` (240, so a code issued at departure outlives the trip); `DELIVERY_OTP_MAX_ATTEMPTS` (5) wrong tries lock the code (even the right code then fails until a new one is sent); at most `DELIVERY_OTP_RESEND_LIMIT` (3) codes per order per `DELIVERY_OTP_RESEND_WINDOW_MINUTES` (15); per-user slowapi limit on send (10/min). Failed attempts are committed before the error is returned, so concurrent guessing cannot exceed the limit.

**Error codes** (`code` in the error body): `OTP_INVALID` (422), `OTP_NOT_FOUND` (409), `OTP_EXPIRED` (409), `OTP_ATTEMPTS_EXCEEDED` (429), `ORDER_NOT_ELIGIBLE` (409), `INVALID_PAYMENT_METHOD` (409), `DELIVERY_ASSIGNMENT_NOT_FOUND` (409), `RATE_LIMIT_EXCEEDED` (429).

**Admin.** The Admin order page asks for the customer's code before "Confirm delivered"; `/fulfillments/{id}/deliver` requires `{"otp"}` for ADMIN too. `DELIVERY_OTP_ENFORCED=false` disables the requirement entirely (rollout switch / emergency only). Push is best-effort: if it fails the customer still sees the code in the app, and delivery never depends on the push.

**Never logged / never stored:** plaintext codes (logs carry order id and otp row id only). The push *payload* does carry the code (it must reach the lock screen); Expo/FCM transit it.

**Admin visibility.** Partner and admin assignment responses carry `delivery_otp` status (`NOT_GENERATED/ACTIVE/EXPIRED/LOCKED/INVALIDATED/VERIFIED`, attempts left) and never the code.

**Limitations.** A customer without the app or push cannot receive a code (no SMS fallback); support can only complete the order once the customer reads the code out (or an operator switches `DELIVERY_OTP_ENFORCED=false`). The code is shown on a customer's screen, so a shoulder-surfer could read it - the same as any app OTP. Reassigning a delivery invalidates the code (a new assignment needs a new code).
