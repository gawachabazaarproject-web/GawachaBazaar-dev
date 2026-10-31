# Functional Requirements

> **Status:** Partially verified. **Last verified:** 2026-10-14.
> **How this was built:** these are the requirements the **current implementation satisfies or visibly intends**, reverse-engineered from code, schema, tests and the existing [`FEATURES.md`](../FEATURES.md). They are **not** a signed-off product specification: no requirements document or decision record exists in the repository. Where a requirement is only inferred, it says so.
> **Status column** (see [docs/README](../README.md#status-conventions)): **Verified** = present in source *and* exercised by a backend test that passed in a recorded run; **Partially verified** = present, with only indirect coverage (e.g. role reachability) or UI-only evidence; **Unverified** = present in source, no test; **Not implemented** = absent; **Placeholder** = page exists, feature does not.
> The recorded backend run is in [AI_STATUS](../00-overview/AI_STATUS.md). **No automated tests exist for `mobile/`, `Admin/` or `website/`**, so UI behaviour is never better than *Unverified* here unless the rule itself is enforced by the backend and tested there.

## Accounts and access

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-AUTH-1 | Users sign in with email+password, Google or phone OTP through Firebase; the backend never sees a credential | Partially verified | Firebase fake used in tests ([`firebase_fake.py`](../../backend/tests/firebase_fake.py)); live Firebase flows were not run by the suite. Google sign-in on a device was exercised manually on 2026-10-14 (session log, not a repository artefact) |
| FR-AUTH-2 | `POST /auth/sync` finds, links or creates the application user for a verified identity, idempotently, without creating duplicates | Verified | [`services/auth.py`](../../backend/app/services/auth.py), [`test_auth.py`](../../backend/tests/test_auth.py) |
| FR-AUTH-3 | Email/password users must verify their email before using protected routes | Verified | `requires_email_verification`, `test_auth.py` |
| FR-AUTH-4 | Pre-Firebase accounts migrate once, keeping their password; the hash is then erased | Verified | `migrate_legacy_account`, `test_auth.py` |
| FR-AUTH-5 | Roles are read live; a role change applies on the next request | Verified | [`dependencies/auth.py`](../../backend/app/dependencies/auth.py), [`test_phase_9_rbac.py`](../../backend/tests/test_phase_9_rbac.py) |
| FR-AUTH-6 | Admin staff accounts are created, activated/deactivated and given roles by an ADMIN | Verified | [`services/staff.py`](../../backend/app/services/staff.py), [`test_staff_status.py`](../../backend/tests/test_staff_status.py) |
| FR-AUTH-7 | Each customer can only see and change their own data | Verified | [`test_cross_customer_access.py`](../../backend/tests/test_cross_customer_access.py) |

## Catalogue and content

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-CAT-1 | Public browsing of categories (one nesting level) and products with sizes, prices, images, stock availability | Verified | [`services/catalog.py`](../../backend/app/services/catalog.py), [`test_phase_10_catalog.py`](../../backend/tests/test_phase_10_catalog.py) |
| FR-CAT-2 | Admins create/update/delete categories and products; variants (sizes), time-ranged prices and images are managed per product; every change is audited | Verified | `catalog.py`, `test_phase_10_catalog.py`, audit actions `product.*`, `category.*` |
| FR-CAT-3 | Sizes of one product share one physical stock pool within a unit family | Verified | [`stock_pool.py`](../../backend/app/services/stock_pool.py), [`test_shared_stock_pool.py`](../../backend/tests/test_shared_stock_pool.py) |
| FR-CAT-4 | Admin-managed home slides and brand ads shown in the app | Unverified | [`home_slide.py`](../../backend/app/services/home_slide.py), [`ad.py`](../../backend/app/services/ad.py); only `test_authz_matrix.py` touches these routes |
| FR-CAT-5 | Customers keep a wishlist | Unverified | [`wishlist.py`](../../backend/app/services/wishlist.py); no test references `/wishlist` except the authz matrix |
| FR-CAT-6 | Voice search and recent searches in the app | Unverified | `mobile/` (`expo-speech-recognition`, `useRecentSearches.ts`) — UI only |
| FR-CAT-7 | Offers carousel shows only promotions checkout would also accept | Verified | [`offers.py`](../../backend/app/services/offers.py), [`test_promotion_flow.py`](../../backend/tests/test_promotion_flow.py) (one file references `/offers`) |

## Inventory and supply

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-INV-1 | Warehouses, batches, lots and an append-only stock-movement ledger; receive, adjust, remove, transfer, reconcile | Verified | [`services/inventory.py`](../../backend/app/services/inventory.py), [`test_phase_11_inventory.py`](../../backend/tests/test_phase_11_inventory.py), [`test_stock_reserve_and_deletes.py`](../../backend/tests/test_stock_reserve_and_deletes.py) |
| FR-INV-2 | Stock is allocated FIFO across lots and reserved for 30 minutes at checkout; reservations are released on cancel/expiry and committed on payment/COD | Verified | [`inventory_reservation.py`](../../backend/app/services/inventory_reservation.py), [`test_phase_15_inventory_reservation_fulfillment.py`](../../backend/tests/test_phase_15_inventory_reservation_fulfillment.py) |
| FR-INV-3 | Physical stock is consumed only when delivery is confirmed | Verified | `FulfillmentService.confirm_delivery`, [`test_phase_16_fulfillment_delivery.py`](../../backend/tests/test_phase_16_fulfillment_delivery.py) |
| FR-INV-4 | Reserve levels and low/expiring-stock alerts | Verified | [`stock_alerts.py`](../../backend/app/services/stock_alerts.py), `test_stock_reserve_and_deletes.py` |
| FR-INV-5 | Packaging operations convert input lots into labelled output lots | Verified | [`packaging.py`](../../backend/app/services/packaging.py), [`test_phase_12_packaging.py`](../../backend/tests/test_phase_12_packaging.py) |
| FR-INV-6 | Supplier records, supplied products and performance evaluations | Verified | [`supplier.py`](../../backend/app/services/supplier.py), [`test_phase_17_supplier_bulk_commerce.py`](../../backend/tests/test_phase_17_supplier_bulk_commerce.py) |
| FR-INV-7 | Admin chooses one warehouse as the delivery-distance packing point | Partially verified | `InventoryService.set_packing_point`, unique partial index `uq_inventory_locations_one_packing_point`; no dedicated behavioural test found |

## Cart, checkout, orders

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-ORD-1 | Server-owned cart with add/update/remove/clear; one ACTIVE cart per user | Verified | [`cart.py`](../../backend/app/services/cart.py), [`test_phase_13_cart_orders.py`](../../backend/tests/test_phase_13_cart_orders.py) |
| FR-ORD-2 | Checkout atomically validates items/prices/address, evaluates the promotion, computes the delivery fee, snapshots lines, and reserves stock; retry returns the same order | Verified | `OrderService.checkout`, `test_phase_13_cart_orders.py` |
| FR-ORD-3 | Cash on Delivery: order is confirmed when COD is chosen, within the reservation window | Verified | `PaymentService._confirm_cod`, `test_phase_14_payments.py` |
| FR-ORD-4 | Online payment is pay-first: priced → Razorpay order → paid → verified with Razorpay → order created and confirmed; automatic refund if the order cannot be placed | Verified (defect PAY-001 open) | [`checkout_session.py`](../../backend/app/services/checkout_session.py), [`test_online_checkout.py`](../../backend/tests/test_online_checkout.py), [`test_money_integrity.py`](../../backend/tests/test_money_integrity.py) |
| FR-ORD-5 | Customers cancel their own order (with reason) any time before delivery; admins cancel any order | Verified | `OrderService._cancel_locked_order`, [`test_phase_18_cancellation_refunds.py`](../../backend/tests/test_phase_18_cancellation_refunds.py) |
| FR-ORD-6 | Orders list/detail for customers; filterable list/detail for staff with `orders.read` | Verified | `OrderService.list_orders/admin_list_orders`, `test_phase_13_cart_orders.py` |
| FR-ORD-7 | Delivery fee: free for 10+ different products, else base + per-km by road distance with documented fallbacks | Verified | [`delivery.py`](../../backend/app/services/delivery.py), [`test_delivery_fee.py`](../../backend/tests/test_delivery_fee.py) |
| FR-ORD-8 | Bazaar+ eligibility is exposed per customer (6 Bazaar orders per month) | Unverified | [`bazaar.py`](../../backend/app/services/bazaar.py); no test references `/bazaar`. Only an eligibility flag; **no price benefit exists** |
| FR-ORD-9 | Promotions: discount rules, targeting, limits, promo codes; preview equals checkout result; redemptions reversed on cancel | Verified | [`promotion.py`](../../backend/app/services/promotion.py), [`test_promotion_flow.py`](../../backend/tests/test_promotion_flow.py) |
| FR-ORD-10 | Bulk requests, versioned quotes, accept, convert to order | Verified | [`bulk_order.py`](../../backend/app/services/bulk_order.py), `test_phase_17_supplier_bulk_commerce.py` |
| FR-ORD-11 | Reorder, order tracker, refund status screens in the app | Unverified | `mobile/app/order/[id]/*` — UI only |

## Payments and refunds

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-PAY-1 | One payment per order; the client is never the authority for payment status | Verified | `uq_payments_order_id`, [`payment_state.py`](../../backend/app/services/payment_state.py), [`test_phase_14_payment_state.py`](../../backend/tests/test_phase_14_payment_state.py) |
| FR-PAY-2 | Razorpay webhooks are signature-verified, deduplicated, amount/currency-checked and applied idempotently | Verified | `PaymentService.process_webhook`, [`test_razorpay_payments.py`](../../backend/tests/test_razorpay_payments.py), `test_phase_14_payments.py` |
| FR-PAY-3 | A paid order that is cancelled gets a refund request that an ADMIN approves/rejects and processes; asynchronous gateway outcome applied by webhook or manual sync | Verified | [`refund.py`](../../backend/app/services/refund.py), [`test_refund_integrity.py`](../../backend/tests/test_refund_integrity.py) |
| FR-PAY-4 | COD cash is recorded as collected (payment `PAID`) when delivery is confirmed | Verified | `FulfillmentService._collect_cod_payment` |
| FR-PAY-5 | Admins list/inspect payments and handle the refund queue | Verified | `PaymentService.admin_*`, `test_phase_18_cancellation_refunds.py` |

## Fulfilment and operations

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-FUL-1 | Fulfilment advances strictly forward (picking → … → delivered); delivery partner assigned before out-for-delivery | Verified | [`fulfillment_state.py`](../../backend/app/services/fulfillment_state.py), `test_phase_16_fulfillment_delivery.py` |
| FR-FUL-2 | Delivery partners see and complete only their own deliveries | Verified | `FulfillmentService`, `test_phase_16_fulfillment_delivery.py` |
| FR-OPS-1 | Staff receive live order/fulfilment/payment/refund events over a WebSocket; REST remains authoritative | Partially verified | [`core/realtime.py`](../../backend/app/core/realtime.py), [`api/v1/realtime.py`](../../backend/app/api/v1/realtime.py); no behavioural WebSocket test in `tests/` (the QA audit exercised it in [`multiproc`](../../backend/tests/multiproc) experiments) |
| FR-OPS-2 | Customers receive push notifications for key order events | Partially verified | [`services/push.py`](../../backend/app/services/push.py), [`test_push_send.py`](../../backend/tests/test_push_send.py); delivery to a real device and Expo/FCM credentials not verified in the repository |
| FR-OPS-3 | Admin mutations are **recorded** in `admin_action_logs` (47 distinct action names, e.g. `order.cancel`, `refund.approve`, `customer.phone_changed`, `promotion.paused`). Recorded rows can be read **only** through the per-product and per-category "activity" feeds in `catalog.py`; there is **no general audit-log API**, and the Admin "Audit Log" page is a placeholder (`EmptyState`: "No general-purpose audit log exists yet") | Partially verified (writing: Verified; reading: Placeholder) | [`admin_audit.py`](../../backend/app/services/admin_audit.py), [`catalog.py`](../../backend/app/services/catalog.py) `admin_get_product_activity` / `admin_get_category_activity`, [`Admin/app/(admin)/audit-log/page.tsx`](../../Admin/app/%28admin%29/audit-log/page.tsx) |
| FR-OPS-4 | Admin dashboard: orders, revenue, stock alerts, delivery issues | Verified (API) | [`dashboard.py`](../../backend/app/services/dashboard.py), [`test_admin_dashboard.py`](../../backend/tests/test_admin_dashboard.py) |
| FR-OPS-5 | Customer management: profiles, notes, status, contact change, password reset (Firebase), phone masking | Verified | [`customer.py`](../../backend/app/services/customer.py), [`test_admin_customer_account.py`](../../backend/tests/test_admin_customer_account.py) |
| FR-OPS-6 | Admin **Reports**, **Reviews** and **Audit Log** pages | Placeholder | each page is a 19-line `EmptyState`; `reviews.*` has no backend; `reports.read` only gates the dashboard; `audit.read` is enforced by no route |
| FR-OPS-7 | App can check for and apply over-the-air updates | Unverified | [`useAppUpdates.ts`](../../mobile/src/features/updates/useAppUpdates.ts), `mobile/app.json` |

## Explicitly absent (verified)

Customer reviews; in-app chat support; email/SMS sent by the platform; a Bazaar+ pricing benefit (the app lists five "upcoming benefits" — free delivery on every order, priority slots, members-only prices, early access, a monthly surprise — none of which exists in the backend); a real delivery/harvest slot (the checkout picker is local UI state only); per-step order timestamps (confirmed/preparing/out-for-delivery); Admin reports; a general audit-log viewer; farm and quality-check management (tables exist, no API). Sources: [`FEATURES.md`](../FEATURES.md) §4 and the code searches described in [AI_STATUS](../00-overview/AI_STATUS.md).
