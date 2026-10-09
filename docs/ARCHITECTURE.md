# Gawacha Bazaar - System Architecture

How the whole platform fits together. For *what the product does* see
[FEATURES.md](FEATURES.md); for backend internals see [../backend/README.md](../backend/README.md)
and [../backend/docs/](../backend/docs).

## 1. Components

| Component | Responsibility | Talks to |
|---|---|---|
| **Customer app** (`mobile/`) | Shopping UI. Holds no business rules. | Backend REST, Firebase Auth SDK, Razorpay Checkout (WebView) |
| **Admin panel** (`Admin/`) | Staff UI, permission-aware navigation. | Backend REST + WebSocket, Firebase Auth (web SDK) |
| **Promo website** (`website/`) | Static marketing pages. | - |
| **Backend** (`backend/`) | All business logic, pricing, state machines, authorisation. | PostgreSQL, Firebase Admin, Razorpay, Cloudinary, routing APIs |
| **PostgreSQL 16** | The only durable store. | Backend only; never exposed publicly |
| **Firebase Auth** | Identity: passwords, Google, phone OTP, email verification. | Clients and backend |
| **Razorpay** | Online payments (UPI, cards, netbanking, wallets) + webhooks. | Backend, app WebView |
| **Cloudinary** | Image storage for products, categories, ads, home slides. | Backend uploads |
| **Google Distance Matrix / OSRM** | Road distance for delivery fees. | Backend |
| **Caddy** | TLS termination and routing in production. | All web services |

```
internet :80/:443 -> Caddy --+--> website:3000    (SITE_DOMAIN)
                             +--> admin:3001      (ADMIN_DOMAIN)
                             +--> backend:8000    (API_DOMAIN)  REST + /api/v1/ws/events
                                       |
                                       +--> db:5432  PostgreSQL 16
migrate (one-shot: alembic upgrade head)   db-backup (nightly pg_dump, 14-day retention)
```

## 2. Backend structure

A **modular monolith**: one process, organised by domain. Each request flows
`router (api/v1) -> dependency (auth/permission/DB) -> service -> models`.

```
backend/app
├── api/v1/          thin routers - validation, auth dependencies, call a service
├── core/            config, firebase, roles, permissions, rate_limit, realtime, security_headers, request_id
├── dependencies/    get_current_user, require_permission, require_roles, get_db
├── services/        ALL business logic; *_state.py files are the state machines
├── models/          SQLAlchemy 2 declarative models (~50 tables)
├── schemas/         Pydantic v2 request/response contracts
├── exceptions/      AppException hierarchy -> uniform JSON errors {code, message, details}
└── db/              engine, session factory
```

Design rules that keep it maintainable:

- **Routers stay thin; services own rules.** A service never trusts client-computed values.
- **State machines are explicit.** `order_state`, `payment_state`, `fulfillment_state`,
  `refund_state`, `reservation_state`, `quote_state`, `bulk_order_state`, `promotion_state`
  each define the legal transitions; an illegal move raises and is rejected (HTTP 409).
- **Money is `Decimal`/`NUMERIC`.** Prices are stored per variant; order lines snapshot name,
  SKU, unit and price at checkout so history never changes when the catalog does.
- **Uniform errors.** Every failure returns the same JSON shape with a stable `code`
  (e.g. `TOKEN_EXPIRED`, `ACCOUNT_NOT_REGISTERED`, `EMAIL_NOT_VERIFIED`) clients can branch on.
- **Request IDs and security headers** are added by middleware; logs carry the request id.

## 3. Authentication and authorisation

**Authentication (Firebase).** Firebase holds credentials. Clients sign in with Firebase and
send the **ID token** as `Authorization: Bearer <token>`. The backend verifies it with the
Firebase Admin SDK (`core/firebase.py`) and maps `firebase_uid` to a row in `users`.

| Situation | Backend response |
|---|---|
| Token expired | 401 `TOKEN_EXPIRED` - client refreshes the token and retries (never signs out) |
| Valid Firebase user, no app account yet | 401 `ACCOUNT_NOT_REGISTERED` - client calls `POST /auth/sync` |
| Email/password user with unverified email | 403 `EMAIL_NOT_VERIFIED` |
| Firebase unreachable | 503 `AUTH_UNAVAILABLE` |

Legacy (pre-Firebase) accounts migrate once via `POST /auth/legacy-migrate`, keeping their
password. Staff accounts are created through the Staff API using the Firebase Admin SDK.

**Authorisation (RBAC).** Roles live in `roles`/`user_roles` and are read live on each request,
so a role change applies immediately.

| Role | Purpose |
|---|---|
| `CUSTOMER` | Shops in the app (default for sign-ups) |
| `WHOLESALER` | Bulk/wholesale buyer |
| `ADMIN` | Everything |
| `OPERATIONS` | Inventory, order read, delivery, reports |
| `HUB_STAFF` | Inventory, order read, delivery assignment |
| `DELIVERY_PARTNER` | See and complete assigned deliveries |
| `SUPPORT` | Read-only customer lookup |

Permissions (e.g. `orders.read`, `products.update`, `inventory.adjust`, `ads.manage`,
`settings.manage`) are defined in `core/permissions.py` and mapped to roles in code.
Routes use `require_permission("...")` or `require_roles(...)`. The Admin panel keeps a
mirrored copy in `Admin/lib/permissions.ts` **only to hide UI**; the backend always re-checks.

Admin mutations are written to `admin_action_logs` (viewable in the Audit Log page).

## 4. Domain model (high level)

| Domain | Main tables |
|---|---|
| Identity | `users`, `roles`, `user_roles`, `addresses`, `wishlist_items`, `customer_notes` |
| Catalog | `categories`, `products`, `product_variants`, `product_images`, `prices` |
| Supply | `suppliers`, `supplier_products`, `supplier_evaluations`, `farms`, `batches`, `quality_checks` |
| Inventory | `inventory_locations` (warehouses, with map position and the packing-point flag), `inventory_lots`, `stock_movements`, `inventory_reservations` (+ items) |
| Packaging | `packaging_operations`, `packaging_inputs`, `packaging_outputs` |
| Commerce | `carts`, `cart_items`, `checkout_sessions`, `orders`, `order_items`, `order_addresses` |
| Payments | `payments`, `payment_transactions`, `payment_webhook_events`, `refunds` |
| Fulfillment | `fulfillments` (picking -> delivery) |
| Promotions | `promotions`, `promotion_targets`, `promotion_eligible_customers`, `promotion_redemptions` |
| Bulk | `bulk_customer_profiles`, `bulk_order_requests` (+ items), `quotes` (+ items, versions) |
| Content | `ads` (brand cards with title/subtitle), `home_slides` |
| Audit | `admin_action_logs` |

Schema history is in [../backend/docs/database](../backend/docs/database) (V1-V7); the current
truth is the models plus `backend/alembic/versions` (35+ migrations).

## 5. Order lifecycle

Four cooperating state machines, each owned by one service:

```
ORDER        PENDING --> CONFIRMED --> COMPLETED
                 |            \--> CANCELLED
                 +--> EXPIRED / CANCELLED

PAYMENT      PENDING --> PROCESSING --> PAID (terminal)
                              |--> FAILED / EXPIRED --(retry)--> PROCESSING
             (Cash on Delivery stays PENDING until the cash is collected) ; CANCELLED from PENDING/PROCESSING

FULFILLMENT  PENDING -> PICKING -> PACKED -> READY_FOR_DELIVERY -> ASSIGNED
                       -> OUT_FOR_DELIVERY -> DELIVERED          (strictly forward)

REFUND       PENDING_APPROVAL -> APPROVED -> PROCESSING -> REFUNDED
                       \-> REJECTED                        PROCESSING -> FAILED
```

Checkout (`POST /cart/checkout`) in one transaction: validates cart and address, **reserves
stock** (`inventory_reservations`), evaluates the promotion, computes the **delivery fee**,
snapshots lines into `orders`/`order_items`/`order_addresses`, and emits a realtime event.
Unpaid online orders are **expired** (reservations released) by a background sweep every 120 s.

Payments: Cash on Delivery or Razorpay. For online payments the backend creates a Razorpay
order, the app opens Checkout, then the result is **verified server-side** (signature) and
also confirmed by the **Razorpay webhook** (authenticity checked via signature, idempotent via
`payment_webhook_events`). The app never marks anything paid by itself.

## 6. Delivery pricing and the Bazaar offer

Implemented in `services/delivery.py` (pure fee calculation) and `services/bazaar.py`.
The cart quote shown in the app and the fee charged at checkout call the **same function**, so
they cannot disagree.

```
distinct products in basket >= FREE_DELIVERY_MIN_ITEMS (15)  ->  fee = 0  ("a Bazaar")
otherwise  fee = ceil( DELIVERY_BASE_FEE (20) + DELIVERY_PER_KM (10) x road_km )
             road_km capped at DELIVERY_MAX_CHARGED_KM (30)
```

- "Items" means **different products**: the same product in two sizes counts once.
- **Origin = the packing point.** An admin picks one active warehouse as the packing point
  (Admin -> Settings). If none is chosen the `PACKING_POINT_*` env values are the fallback.
- **Road distance**, not straight line: Google Distance Matrix if `GOOGLE_MAPS_API_KEY` is set,
  otherwise OSRM (`OSRM_BASE_URL`; the public demo server is for testing only). Results are
  cached per rounded coordinate pair. If routing fails the fee falls back to straight-line x
  `DELIVERY_ROAD_FACTOR` (1.4) instead of failing checkout.
- No GPS on the address, or no origin configured: only the base fee applies and the quote is
  flagged `distance_estimated`.
- **Gawacha Bazaar+**: a customer with `BAZAAR_PLUS_ORDERS_REQUIRED` (6) Bazaar orders in the
  current calendar month (`BAZAAR_TIMEZONE`, default IST) is eligible; cancelled/expired orders
  do not count. Progress is exposed at `/bazaar`.

## 7. Realtime

`/api/v1/ws/events` is a WebSocket for **staff** (admin roles). The backend pushes a small
invalidation message `{resource, order_id, status, previous_status, occurred_at}` when an
order, fulfillment, payment or refund changes. Clients treat it as "refetch order N"; REST stays
the source of truth. The Admin panel uses it for the new-order alarm, live lists and the pending
order count in the sidebar. A WebSocket cannot send headers, so the token is passed on the
query string.

## 8. Client architecture

**Customer app** (`mobile/`): Expo Router file-based routes in `app/`; `src/api` is the single
HTTP layer (axios, Firebase token attach, refresh-and-retry on `TOKEN_EXPIRED`); `src/features/*`
hold TanStack Query hooks per domain with optimistic updates (cart, wishlist); Zustand stores
the auth session and toasts; `src/theme` holds the design tokens (forest green, mustard accent,
cream background; Bodoni Moda headlines, Plus Jakarta Sans body, Baloo 2, Lora numerals).
An `AppGate` redirects between auth, onboarding (first address) and the main tabs.
`statusPresentation.ts` maps backend statuses to labels/colours - presentation only.

**Admin panel** (`Admin/`): Next.js App Router. `lib/auth-context.tsx` signs in with Firebase,
loads the profile, rejects accounts without an admin role and keeps the ID token fresh (also
re-checked on tab focus, reconnect and every 5 minutes, because browsers throttle timers in
background tabs). `lib/<module>.ts` files are typed API clients; `components/AdminShell.tsx`
renders the permission-filtered sidebar; `lib/realtime-context.tsx` owns the WebSocket.

## 9. Deployment

| Environment | How |
|---|---|
| Local | `docker-compose.yml` (Postgres + backend with reload + website) or run each part natively |
| Production | `docker-compose.prod.yml` on a VPS: Caddy, website, admin, backend, Postgres, `migrate` job, `db-backup`. Runbook: [../deploy/README.md](../deploy/README.md) |
| Kubernetes | Manifests in `k8s/` (namespace, backend and website deployments, services, HPAs, ingress) |
| CI/CD | `.forgejo/workflows/deploy.yml` builds images on push to `main` |

Migrations run as a separate job and must succeed before the backend starts. The backend image
runs as a non-root user. Only ports 80/443 are public. The mobile app ships as an EAS/Android
build (`mobile/eas.json`).

## 10. Scaling limits

Three pieces of state live **inside the backend process**, so the backend must run as **one
worker/replica** today:

1. **Rate limiter** (slowapi, in-memory) - limits would multiply across replicas.
2. **WebSocket registry** (`core/realtime.py`) - events only reach clients on the same process.
3. **Reservation expiry sweep** - runs in each process (harmless but duplicated).

To scale horizontally, move 1 and 2 to Redis (rate-limit storage, pub/sub for events) and make
the sweep a single scheduled job. The delivery distance cache is per-process but harmless to
duplicate.

## 11. Security notes

- No secrets in the repo; everything via environment variables (see `.env.example` files).
- Firebase ID tokens verified on every request; roles read live; admin actions audited.
- Razorpay secrets and webhook secret never leave the server; webhook signature verified.
- Security headers, CORS allow-list, request size/upload limits (images max 8 MB, type-checked).
- Rate limiting on the sensitive auth endpoints (e.g. 5/minute on legacy login/migration);
  Argon2 verification (with a timing-equalising dummy hash) is used for legacy password
  migration only.
- Customer phone numbers are masked for roles without `customers.view_sensitive`.
