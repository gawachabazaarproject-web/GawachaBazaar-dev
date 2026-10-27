# Delivery partner system

> **Status (2026-10-27):** backend implemented and tested (`tests/test_delivery_partner.py`, 43 tests); mobile partner screens and Admin pages build (tsc) — runtime status is stated in the release report. Extends the existing fulfillment pipeline ([DELIVERY](DELIVERY.md)); it does not replace it.

## Model

| Table | Purpose |
|---|---|
| `delivery_partner_profiles` | one per partner user: `status` ACTIVE/INACTIVE/SUSPENDED, `availability` OFFLINE/AVAILABLE/ON_DELIVERY, vehicle type/number, phone. Created ACTIVE/OFFLINE on first use for accounts that already held the role. |
| `delivery_assignments` | one row per (order, partner) attempt. **Partial unique index: one active assignment per order.** Reassign/reject/cancel closes the old row; history is kept. Holds COD facts ([COD_OPERATIONS](COD_OPERATIONS.md)). |
| `delivery_partner_locations` | **latest position only**, one row per assignment (upsert). History is deliberately not stored (bounded by construction). Deleted on completion/failure. |
| `delivery_partner_earnings` | append-only earnings ledger (DB trigger), one EARNING per assignment, with a **snapshot** of the rule (version, base, per-km amount, billable km, COD bonus). Separate from the customer's delivery fee. |

Role: the existing `DELIVERY_PARTNER` role (RBAC unchanged). New permissions: `partners.read` (ADMIN, OPERATIONS), `partners.manage`, `partners.cod_reconcile`, `referrals.*` (ADMIN).

## State machine

```
assignment:  ASSIGNED -accept-> ACCEPTED -pickup-> PICKED_UP -out-for-delivery-> OUT_FOR_DELIVERY -deliver-> DELIVERED
             ASSIGNED -reject-> REJECTED            (fulfillment back to READY_FOR_DELIVERY)
             PICKED_UP|OUT_FOR_DELIVERY -fail-> FAILED  (fulfillment back to READY_FOR_DELIVERY; COD_FAILED)
             ASSIGNED|ACCEPTED|PICKED_UP -admin reassign-> CANCELLED (+ new ASSIGNED row);  order cancelled -> CANCELLED
fulfillment: READY_FOR_DELIVERY -> ASSIGNED -> OUT_FOR_DELIVERY -> DELIVERED   (only the two release moves go backward: fulfillment_state.reopen_for_dispatch)
```

No step can be skipped (tested: pickup before accept, deliver before out, repeat accept → 409). Lock order: Order → Fulfillment → Assignment → Payment; no lock is held across a network call (there is none).

## Earnings (REQUIRED BUSINESS DECISION)

`earning = PARTNER_EARNING_BASE + PARTNER_EARNING_PER_KM × billable_km (+ PARTNER_EARNING_COD_BONUS on COD)`; billable km is the order's stored snapshot. Placeholders Rs 20 / Rs 5 / Rs 0. The ledger row stores how it was computed, so later rule changes never rewrite history. Payout/settlement process is not built.

## Live location

Accepted only while the assignment is PICKED_UP or OUT_FOR_DELIVERY, only from the assigned ACTIVE partner. Validation: lat/lng ranges, accuracy ≥ 0, minimum `PARTNER_LOCATION_MIN_INTERVAL_SECONDS` (3 s) between updates per assignment (429 otherwise, enforced under a row lock so bursts cannot slip through), implausible jumps (> `PARTNER_LOCATION_MAX_SPEED_KMH`, 150) rejected, slowapi 120/min/user. The customer sees it via `GET /orders/{id}/delivery-tracking` **only for their own order**, only while PICKED_UP/OUT_FOR_DELIVERY, a position older than `PARTNER_LOCATION_STALE_SECONDS` (300) is hidden, and the response contains first name + vehicle type + coordinates only (no phone, plate or ids). Single backend worker: the table, not memory, holds the state (no Redis needed).

## Endpoints

Partner (`DELIVERY_PARTNER` only; foreign ids → 404):

| Endpoint | Purpose |
|---|---|
| `GET /delivery-partner/me` | profile, active count, delivered/earned today |
| `PATCH /delivery-partner/me/availability` `{OFFLINE\|AVAILABLE}` | online/offline (ON_DELIVERY is derived; cannot go offline with a job) |
| `GET /delivery-partner/assignments?scope=active\|history&status&date_from&date_to&page` | gig list / history (customer name + address only while the job is open) |
| `GET /delivery-partner/assignments/{id}` | detail incl. items, address, Google Maps deep link, COD due |
| `POST .../{id}/accept` · `/reject {reason}` · `/pickup` · `/out-for-delivery` · `/fail {reason}` | transitions |
| `POST .../{id}/otp/send` | at the door: generate + push the COD delivery code to the customer (10/min, 3 per order per 15 min) - [COD_OPERATIONS](COD_OPERATIONS.md#delivery-otp-proof-of-delivery---implemented) |
| `POST .../{id}/deliver {cod_collected_amount, otp}` | atomic completion; exact COD amount **and the customer's 6-digit `otp`** required for unpaid COD |
| `POST .../{id}/location {latitude, longitude, accuracy_m}` | position |
| `GET /delivery-partner/earnings?date_from&date_to` | my ledger |

Customer: `GET /orders/{order_id}/delivery-tracking`, `GET /orders/{order_id}/delivery-otp` (own order only; the code is shown only while ACTIVE).

Staff: `POST /fulfillments/{id}/assign` (existing; now also creates the assignment), `POST /fulfillments/{id}/reassign {delivery_partner_user_id, reason}` (ADMIN/HUB_STAFF/OPERATIONS).

Admin (`/delivery-partners`): `GET /` list, `POST /` create profile, `PATCH /{user_id}` status/vehicle/phone, `GET /assignments`, `GET /active`, `GET /cod`, `POST /assignments/{id}/cod-reconcile`, `GET /earnings`. Suspending/deactivating a partner with an active job is refused (409).

## Authorization matrix

Source of truth: `backend/tests/authz_golden.json` (reviewed 2026-10-27) + the role gates below. ✔ allowed · ✖ 403 · own = only rows that belong to the caller (else 404).

| Operation | Anonymous | CUSTOMER | DELIVERY_PARTNER | HUB_STAFF | OPERATIONS | SUPPORT | ADMIN |
|---|---|---|---|---|---|---|---|
| `/delivery-partner/*` (all) | 401 | ✖ | ✔ own | ✖ | ✖ | ✖ | ✖ (deliberately: admins use the admin API) |
| `GET /orders/{id}/delivery-tracking` | 401 | ✔ own order | ✖ | ✖ | ✖ | ✖ | ✖ |
| `GET /orders/{id}/delivery-otp` | 401 | ✔ own order (404 otherwise) | ✖ | ✖ | ✖ | ✖ | ✖ |
| `POST /fulfillments/{id}/assign`, `/reassign` | 401 | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |
| `GET /delivery-partners`, `/assignments`, `/active`, `/cod`, `/earnings` | 401 | ✖ | ✖ | ✖ | ✔ | ✖ | ✔ |
| `POST/PATCH /delivery-partners…` (manage) | 401 | ✖ | ✖ | ✖ | ✖ | ✖ | ✔ |
| `POST …/cod-reconcile` | 401 | ✖ | ✖ | ✖ | ✖ | ✖ | ✔ |
| `/referrals/me,apply,history,rewards` | 401 | ✔ own | ✖ | ✖ | ✖ | ✖ | ✖ |
| `/referrals/admin*` | 401 | ✖ | ✖ | ✖ | ✖ | ✖ | ✔ |

(Admin permissions are static code in `core/permissions.py`; the Admin UI mirror grants nothing.)

## Known gaps / decisions

Delivery OTP/proof (recommended for COD, not built — see COD_OPERATIONS); partner payouts; partner cash limits; push notification to a partner on assignment (the app polls every 15 s); customer-side tracking map in the mobile app is **not built** (API only); partners cannot self-register (staff creates the account and role).
