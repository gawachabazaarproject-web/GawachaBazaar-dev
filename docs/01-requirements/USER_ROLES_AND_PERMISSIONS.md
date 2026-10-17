# User Roles and Permissions

> **Status:** Verified (roles/permissions read from code; reach counts from the reviewed role matrix). **Last verified:** 2026-10-14.
> **Evidence:** [`backend/app/core/roles.py`](../../backend/app/core/roles.py), [`permissions.py`](../../backend/app/core/permissions.py), [`dependencies/auth.py`](../../backend/app/dependencies/auth.py), [`tests/authz_golden.json`](../../backend/tests/authz_golden.json) + [`test_authz_matrix.py`](../../backend/tests/test_authz_matrix.py), [`Admin/lib/permissions.ts`](../../Admin/lib/permissions.ts).

## 1. How access control works

1. **Authentication** — Firebase ID token → `users` row by `firebase_uid`; user must be `ACTIVE`; email/password sign-ins must have a verified email ([AUTHENTICATION](../05-domains/AUTHENTICATION.md)).
2. **Roles** — rows in `roles` linked by `user_roles`, **read from the database on every request** (`require_roles`), so a role change applies immediately. A role is never taken from the token.
3. **Permissions** — a **static in-code map** `ROLE_PERMISSIONS` (no `permissions` table). `require_permission("x.y")` loads the caller's roles from the database and checks the map. Changing what a role can do is a code deployment.
4. Routes use `require_roles(...)` (often as a router-level gate), `require_permission(...)`, or only `get_current_user`. Public routes: 12 operations (catalog browsing, ads, home slides, offers, `/ping`, health, `legacy-migrate`, payment webhook). See [API_REFERENCE](../03-api/API_REFERENCE.md) for the gate on each operation.
5. The Admin panel keeps a hand-synchronised copy of the map in `Admin/lib/permissions.ts` **only to hide navigation**; it grants nothing and can drift (no shared package). The backend always re-checks.

## 2. Roles (the seven baseline roles)

| Role | Kind | What it can do (verified) | Notes |
|---|---|---|---|
| `CUSTOMER` | Self-registered | Everything customer-facing: addresses, wishlist, cart, checkout, own orders/payments/refund status, bulk requests, bazaar status, push tokens | Default for new sign-ups. Wholesale buyers also use this role |
| `WHOLESALER` | Self-registered type | Only the endpoints open to any signed-in user (`/auth/me`, `/auth/sync`, `/push-tokens`) | **Partially implemented:** the role is seeded (migration `37bbdf459894`) and appears in code comments, but no route is gated on it; bulk-order routes require `CUSTOMER` |
| `ADMIN` | Staff | All 41 permissions; the only role for refunds, order cancellation, catalog/promotion/content/staff/settings/audit management | No `SUPER_ADMIN` exists (deliberately deferred in code comments) |
| `OPERATIONS` | Staff | Inventory (all), read orders, delivery (read/assign/fulfil), reports | 10 permissions |
| `HUB_STAFF` | Staff | Inventory (all), read orders, delivery read/assign | 8 permissions; cannot mark deliveries out/delivered |
| `DELIVERY_PARTNER` | Staff | See and complete **their own** assigned deliveries | 2 permissions; ownership enforced in the service layer (`FulfillmentService`), not just by route |
| `SUPPORT` | Staff | Read-only customer lookup (`customers.view`), phone masked | 1 permission |
| *(no role)* | Signed-in user with no roles | `/auth/me`, `/auth/sync`, `/push-tokens` only | Observed in the matrix as role `NONE` |

Staff roles (`STAFF_ROLES`) = `ADMIN, HUB_STAFF, OPERATIONS, DELIVERY_PARTNER, SUPPORT`. They receive realtime order events, except that `DELIVERY_PARTNER` is deliberately excluded from the staff broadcast ([`realtime.py`](../../backend/app/api/v1/realtime.py)).

## 3. Permission matrix (generated from `ROLE_PERMISSIONS`)

| Permission | ADMIN | OPERATIONS | HUB_STAFF | DELIVERY_PARTNER | SUPPORT |
|---|---|---|---|---|---|
| `ads.manage` | yes |  |  |  |  |
| `ads.read` | yes |  |  |  |  |
| `audit.read` | yes |  |  |  |  |
| `categories.create` | yes |  |  |  |  |
| `categories.delete` | yes |  |  |  |  |
| `categories.read` | yes |  |  |  |  |
| `categories.update` | yes |  |  |  |  |
| `customers.manage_contact` | yes |  |  |  |  |
| `customers.manage_status` | yes |  |  |  |  |
| `customers.notes` | yes |  |  |  |  |
| `customers.reset_password` | yes |  |  |  |  |
| `customers.view` | yes |  |  |  | yes |
| `customers.view_sensitive` | yes |  |  |  |  |
| `delivery.assign` | yes | yes | yes |  |  |
| `delivery.fulfill` | yes | yes |  | yes |  |
| `delivery.read` | yes | yes | yes | yes |  |
| `inventory.adjust` | yes | yes | yes |  |  |
| `inventory.read` | yes | yes | yes |  |  |
| `inventory.receive` | yes | yes | yes |  |  |
| `inventory.reconcile` | yes | yes | yes |  |  |
| `inventory.transfer` | yes | yes | yes |  |  |
| `orders.cancel` | yes |  |  |  |  |
| `orders.read` | yes | yes | yes |  |  |
| `orders.refund` | yes |  |  |  |  |
| `orders.update` | yes |  |  |  |  |
| `products.create` | yes |  |  |  |  |
| `products.delete` | yes |  |  |  |  |
| `products.manage_media` | yes |  |  |  |  |
| `products.manage_pricing` | yes |  |  |  |  |
| `products.read` | yes |  |  |  |  |
| `products.update` | yes |  |  |  |  |
| `promotions.create` | yes |  |  |  |  |
| `promotions.manage_status` | yes |  |  |  |  |
| `promotions.read` | yes |  |  |  |  |
| `promotions.update` | yes |  |  |  |  |
| `reports.read` | yes | yes |  |  |  |
| `reviews.moderate` | yes |  |  |  |  |
| `reviews.read` | yes |  |  |  |  |
| `settings.manage` | yes |  |  |  |  |
| `staff.manage` | yes |  |  |  |  |
| `staff.read` | yes |  |  |  |  |

**Enforcement reality** (checked 2026-10-14 by comparing this map with the `perm …` gates in [API_REFERENCE](../03-api/API_REFERENCE.md)): 41 permissions are defined; **31 are enforced by a route** through `require_permission`. The other 10 are enforced differently or not at all:

| Permission(s) | How it is actually enforced |
|---|---|
| `customers.view_sensitive` | Read in the customers router to decide whether the phone number is masked ([`customers.py`](../../backend/app/api/v1/customers.py)) — not a route gate |
| `orders.cancel`, `orders.refund` | The routes use `require_roles(ADMIN)` instead (orders admin router, payments admin router); the permission strings only drive the Admin UI |
| `delivery.read`, `delivery.assign`, `delivery.fulfill` | The fulfilment routes use role tuples (`ADMIN/HUB_STAFF/OPERATIONS[/DELIVERY_PARTNER]`); the permission strings only drive the Admin UI |
| `settings.manage` | Admin navigation only; the packing-point route is gated by role `ADMIN` |
| `audit.read`, `reviews.read`, `reviews.moderate`, `orders.update` | No backend route requires them (no general audit-log API, no review domain; `orders.update` is unused) |

Consequence: the permission map cannot be used as the sole source of truth for what a role may do. Use the **Auth** column of [API_REFERENCE](../03-api/API_REFERENCE.md) and the reviewed matrix (§4).

## 4. Reach per role (from the reviewed matrix)

`tests/authz_golden.json` records, for every one of the 196 operations, which roles may reach it (`ADMIN` is excluded from the matrix because it reaches all). Snapshot at 2026-10-14:

| Role | Non-public operations reachable |
|---|---|
| `OPERATIONS` | 63 |
| `HUB_STAFF` | 52 |
| `CUSTOMER` | 46 |
| `SUPPORT` | 11 |
| `DELIVERY_PARTNER` | 9 |
| `WHOLESALER` / no role | 4 each (`/auth/me`, `/auth/sync`, two `/push-tokens` calls) |
| `ADMIN` only (no other role) | 184 non-public − 114 reachable by some non-admin role = **70** |

The test [`test_authz_matrix.py`](../../backend/tests/test_authz_matrix.py) fails whenever any operation's reachability changes, so adding or re-gating a route requires updating the snapshot deliberately.

## 5. Protections built into the rules

| Rule | Where |
|---|---|
| A customer receives **404, not 403**, for another customer's order/payment/address (existence is not disclosed) | e.g. `OrderService.cancel_own_order`; cross-customer tests in [`test_cross_customer_access.py`](../../backend/tests/test_cross_customer_access.py) |
| A delivery partner can act only on their own assignment (admin override) | [`fulfillment.py`](../../backend/app/services/fulfillment.py) `_assert_can_act_as_delivery_partner` |
| Customer phone is masked (`+91******7890`) unless the caller has `customers.view_sensitive` | [`customer.py`](../../backend/app/services/customer.py) |
| An admin cannot deactivate their own account; the last active admin cannot be removed (`_active_admin_count`) | [`staff.py`](../../backend/app/services/staff.py) |
| An admin cannot reset their own password through the customer-reset endpoint | [`customer.py`](../../backend/app/services/customer.py) `admin_reset_password` |
| Refund approval/processing is ADMIN-only by design | [`payments.py`](../../backend/app/api/v1/payments.py) admin router, [`permissions.py`](../../backend/app/core/permissions.py) |
| Admin sign-in is refused for accounts without a staff role | [`Admin/lib/auth-context.tsx`](../../Admin/lib/auth-context.tsx) (`canOpenAdminPanel`) — UI-level gate only; the backend re-checks every call |

## 6. Gaps and open questions

- `WHOLESALER` has no dedicated capability (see §2). Whether a distinct wholesale experience is planned is **unknown**.
- Permission names are partly "anticipatory" (see the comments in `permissions.py`); do not infer that a permission implies a working feature without checking the route table.
- `Admin/lib/permissions.ts` is a manual copy and no test compares it with the backend. On 2026-10-14 a regex comparison showed the **set of permission names is identical** in both files; the **per-role assignments were not compared** (unverified). Compare both when changing either.
