# Admin Operations (Admin panel, staff and customer management)

> **Status:** Backend behaviour Verified (code + tests); the **Admin web UI is Unverified** (no frontend tests; pages were not run in this documentation task). **Last verified:** 2026-10-14.
> **Source files:** Admin [`app/(admin)/*`](../../Admin/app), [`components/AdminShell.tsx`](../../Admin/components/AdminShell.tsx), [`lib/*.ts`](../../Admin/lib), [`lib/auth-context.tsx`](../../Admin/lib/auth-context.tsx), [`lib/permissions.ts`](../../Admin/lib/permissions.ts); backend [`services/staff.py`](../../backend/app/services/staff.py), [`customer.py`](../../backend/app/services/customer.py), [`dashboard.py`](../../backend/app/services/dashboard.py), [`admin_audit.py`](../../backend/app/services/admin_audit.py).
> **Tests (backend):** [`test_staff_status.py`](../../backend/tests/test_staff_status.py), [`test_admin_customer_account.py`](../../backend/tests/test_admin_customer_account.py), [`test_admin_dashboard.py`](../../backend/tests/test_admin_dashboard.py), [`test_phase_9_rbac.py`](../../backend/tests/test_phase_9_rbac.py).

## Access

Admin sign-in is Firebase email/password only. `auth-context.tsx` fetches `/auth/me` (calling `/auth/sync` if needed), **rejects accounts with no staff role** (`canOpenAdminPanel`), and requires a verified email for password sign-ins (sending a verification email and signing the user out until verified). The ID token is refreshed on tab focus, network return and every 5 minutes. The sidebar shows only the pages whose permission the roles hold (UI only — the backend decides).

## Pages (navigation order) and what backs them

| Page | Permission shown in nav | Backend operations | State |
|---|---|---|---|
| Overview `/dashboard` | none (any staff) | `GET /dashboard` requires `reports.read` (ADMIN, OPERATIONS) — other roles get 403; UI handling **not verified** | Live |
| Orders `/orders`, `/orders/{id}` | `orders.read` | list/detail/cancel ([ORDERS](ORDERS.md)); sidebar count of `PENDING` orders; delivery actions on detail | Live |
| Products, Categories | `products.read`, `categories.read` | catalogue admin ([CATALOG](CATALOG.md)) | Live |
| Inventory `/inventory` | `inventory.read` | lots, receive/remove/transfer/reconcile, alerts, warehouses, reserve levels ([INVENTORY](INVENTORY.md)) | Live |
| Promotions | `promotions.read` | [PROMOTIONS](PROMOTIONS.md) | Live |
| Customers | `customers.view` | profile, orders, notes, status, contact change, password reset, timeline (below) | Live |
| Reviews | `reviews.read` | none | **Placeholder** |
| Delivery `/delivery` | `delivery.read` | `GET /fulfillments`, `GET /fulfillments/{id}/order` and the step actions; stage tabs, expandable rows (items, address, COD amount, next action); a delivery partner sees only their own assignments | Live (added 2026-10-17; **not exercised against a live backend** — build/typecheck only) |
| Payments `/payments` | `orders.refund` (ADMIN) | payment list/detail, refund queue ([REFUNDS](REFUNDS.md)) | Live |
| Reports | `reports.read` | none | **Placeholder** |
| Home slides `/content` | `ads.read` | `/home-slides/admin` | Live |
| Settings | `settings.manage` | packing-point choice, warehouse coordinates | Live (UI); backend gates are role-based |
| Audit Log | `audit.read` | none — "No general-purpose audit log exists yet" | **Placeholder** |
| Staff | `staff.read` | staff CRUD | Live |
| Ads | `ads.read` | `/ads/admin` | Live |

## Staff management (`/staff`, ADMIN)

- **Create** (`staff.manage`): a Firebase user (verified email) + `users` row + role + audit, atomically; the Firebase user is deleted again if the database step fails. Needs the Firebase **service account** (without it → 503 `AUTH_UNAVAILABLE`, [AUTHENTICATION](AUTHENTICATION.md)).
- **Roles:** assign (idempotent; first role becomes primary) and revoke; only the five staff roles can be assigned (`_require_staff_role`). **Status:** activate/deactivate (an admin cannot deactivate themself; the last active admin is protected).
- First admin: [`backend/scripts/create_admin.py`](../../backend/scripts/create_admin.py) (also `activate_user.py`, `check_admin.py`, `seed_dummy_data.py` — a **dev-only** demo seed — and `seed_sections.py`, which creates the "Ready to Cook"/"Juices" storefront sections and sample products; read both before running them against anything shared).

## Customer management (`/customers`)

| Capability | Permission (role) | Notes |
|---|---|---|
| List/search, dashboard, detail, orders, addresses, promotions used, timeline | `customers.view` (ADMIN, SUPPORT) | Phone masked unless `customers.view_sensitive` (ADMIN) — but see PRIV-1 in [ORDERS](ORDERS.md): order detail leaks the phone to `orders.read` roles |
| Notes (create/edit) | `customers.notes` (ADMIN) | Stored in `customer_notes` with the author |
| Activate/suspend | `customers.manage_status` (ADMIN) | Also disables the Firebase user and revokes its sessions where a Firebase UID exists (best effort — the database status stays the authority if Firebase is unreachable); audited `customer.status_change` |
| Change email/phone | `customers.manage_contact` (ADMIN) | Updates PostgreSQL only; audited; may be overwritten by the next sync ([AUTHENTICATION](AUTHENTICATION.md)) |
| Reset password | `customers.reset_password` (ADMIN) | Sets the Firebase password and revokes all sessions; cannot be used on yourself; audited `customer.password_reset` |

## Navigation and usability (2026-10-17)

The sidebar is grouped (Sell, Catalogue, Marketing, Administration, Coming soon), sticky, and becomes a slide-in drawer below the `lg` breakpoint. The top-bar search (`/` or Ctrl/Cmd+K) offers "search orders/products/customers/… for X" shortcuts that open the list page with `?q=X` (list pages read it and debounce typing by 350 ms) plus page jumps; it calls no API itself. The tab title follows the page. Pages crashing show `app/(admin)/error.tsx` instead of a blank screen; unknown URLs show `app/not-found.tsx`. These changes are **typechecked and built (`next build --webpack`) but were not exercised signed-in or on a phone** (no staff credentials were available to the author).

## Realtime and alarm

Admin opens one WebSocket (`realtime-context.tsx`); a new/pending order triggers the alarm and toast; the sidebar pending-order count refreshes on events. Events do not cross replicas ([NOTIFICATIONS](NOTIFICATIONS.md)).

## Audit trail

Every admin mutation records `{admin_user_id, action, resource_type, resource_id, previous_state, new_state, reason}` in `admin_action_logs` (47 distinct action names, [FUNCTIONAL_REQUIREMENTS](../01-requirements/FUNCTIONAL_REQUIREMENTS.md) FR-OPS-3). It is **write-only except** the per-product and per-category activity feeds; there is no audit-log API or page. States are truncated to 50 characters.

## Known gaps

- Three placeholder pages (Reviews, Reports, Audit Log), now labelled "Soon" in the sidebar.
- The Overview page is visible to roles whose API call would be forbidden (**unverified** behaviour).
- No bulk operations, exports or reports; no admin UI for delivery-fee parameters, Razorpay settings or promotions' stacking.
- Admin has no password-reset UI for staff (use Firebase's reset flow) and no sign-in with Google.
- `NEXT_PUBLIC_API_BASE_URL` and the six `NEXT_PUBLIC_FIREBASE_*` values are fixed at **build time** (the Dockerfile and compose files now take them as build args and fail the build when Firebase values are missing); pointing an existing Admin image at another API requires a rebuild ([DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md)).
