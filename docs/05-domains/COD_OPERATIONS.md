# Cash on Delivery operations

> **Status (2026-10-27):** implemented with the delivery partner system (see [DELIVERY_PARTNER](DELIVERY_PARTNER.md)). Evidence: `services/delivery_assignment.py`, `models/delivery_partner.py`, `tests/test_delivery_partner.py`.

## What the server owns

* **Expected amount.** When a partner is assigned, `delivery_assignments.cod_expected_amount` is copied from the order's COD `payments.amount` (never typed by anyone). Prepaid orders get `NOT_APPLICABLE` and amount 0.
* **States:** `NOT_APPLICABLE` → (`COD_PENDING` → `COD_COLLECTED` | `COD_FAILED`). Cancelling/rejecting before pickup returns `COD_PENDING` to `NOT_APPLICABLE` (nothing was ever at stake); a failed hand-over sets `COD_FAILED`.
* **Confirmation.** Only the assigned partner, only from `OUT_FOR_DELIVERY`, only with `cod_collected_amount` **exactly equal** to the expected amount. Lower, higher, zero, negative or missing → 422 and **nothing changes** (order stays CONFIRMED, payment unpaid, stock reserved, no earning). **Partial collection is deliberately not supported** (decision: the customer either pays the whole bill or the delivery is marked failed); change it only with an explicit design.
* **Atomic completion.** One transaction (`FulfillmentService.confirm_delivery`): lock Order → Fulfillment → Assignment → reservation → lots → Payment; consume stock; payment PAID + transaction row; assignment DELIVERED with COD facts; partner earning row; order COMPLETED; referral qualification. Any failure rolls back the lot. Double/concurrent completion is idempotent (one earning, one stock movement).
* **DB guards:** `CHECK(cod_status <> 'COD_COLLECTED' OR collected = expected)` and `CHECK(status <> 'DELIVERED' OR cod_status IN ('NOT_APPLICABLE','COD_COLLECTED'))`.
* **Legacy path:** `POST /fulfillments/{id}/deliver` (no body) still works for ADMIN/the assigned partner and records the full expected amount as collected. The partner app uses the strict `/delivery-partner/assignments/{id}/deliver`.

## Reconciliation

`GET /delivery-partners/cod` (`partners.read`) lists COD rows and the **outstanding** total (collected, not yet reconciled). `POST /delivery-partners/assignments/{id}/cod-reconcile` (`partners.cod_reconcile`, ADMIN only) stamps `cod_reconciled_at/by`, audited, once. It records that the shop received the cash; it does not move money in any gateway. Settlement frequency and partner cash limits are **business decisions not yet made** (no limit is enforced).

## Do we need a delivery OTP or proof of delivery? (evaluation)

Risks: a partner marks "delivered" without delivering and pockets the goods; or reports less cash. Today's controls: server-owned amount, exact-match confirmation, assignment-scoped authorization, cancellation/fail paths, audit rows, reconciliation, location trail (latest only).

**Recommendation: yes for COD, before scaling beyond a handful of trusted partners.** A 4-digit **delivery OTP** shown to the customer in the app (on `GET /orders/{id}`) and typed by the partner at the door would prove the customer was present and close the "false delivered" attack at low cost. It is **not implemented** (it needs a customer-app change, an SMS/push fallback for customers without the app, and an owner decision on failure handling). Photo proof is heavier (storage, privacy) and is recommended only if OTP is rejected. Until then the residual risk is partner fraud on COD deliveries; mitigate operationally (trusted partners, daily reconciliation).
