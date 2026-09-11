# Gawacha Bazaar — Backend Architecture (Engineering Memory)

> **Purpose of this document**: This is the persistent source of truth for any engineer (human or AI)
> picking up backend work on Gawacha Bazaar. It reflects the **actual state of the repository**
> (code, migrations, tests) as inspected on 2026-09-11, not aspirational design. Where an older
> concept diagram or prior assumption differs from the repository, this document follows the
> repository and calls out the discrepancy explicitly.

---

## 1. Project Overview

Gawacha Bazaar is a production-oriented farm-to-home fresh-food marketplace serving Nagpur city.
Backend is a **Python/FastAPI modular monolith** backed by PostgreSQL 16, with a Next.js frontend
and React Native mobile app (neither inspected in this pass — this document covers `backend/` only).

## 2. Business Workflow

```
Supply Source (currently: Wholesaler)
        ↓
Harvest / Sourcing
        ↓
Collection
        ↓
Sorting & Grading (Quality Check)
        ↓
Gawacha Bazaar Hub (Inventory Lot)
        ↓
Preparation / Packaging / Labeling
        ↓
Delivery
        ↓
Nagpur City
        ↓
Customer Home
```

## 3. Active vs. Future Actors

**CURRENT ACTIVE ACTORS:**
- **CUSTOMER** — browses catalog, places orders, pays.
- **WHOLESALER** — supplies produce batches into the system. Represented as a `User` row (no
  dedicated `wholesalers` table — see §10).
- **ADMIN** — catalog/pricing/system oversight.
- **HUB_STAFF / OPERATIONS** — sorting, grading, quality checks, inventory, packaging.
- **DELIVERY_PARTNER** — last-mile logistics.

**FUTURE (preserved, not deleted, not repurposed):**
- **FARMER**
- **FARM**

> **Farmer/Farm are future capabilities and must not be repurposed as the current Wholesaler
> model.** The `farms` table and `Farm` ORM model remain fully intact. `batches.farm_id` remains a
> valid, structurally live foreign key — it is now **nullable** rather than deleted, so direct
> farm-sourced batches can be introduced later without a schema migration.

> **Before Phase 9, the existing database model must be corrected so that the active supply
> workflow is Wholesaler-based.** As of this inspection, that correction is **already drafted**
> on the current branch — see §9 "Discrepancies Found" for its exact (uncommitted) status.

There is currently **no dual-source design** (a batch cannot conceptually claim both a wholesaler
and a farm as equally-active origins in application logic yet) — `wholesaler_user_id` is mandatory
and authoritative; `farm_id` is optional metadata reserved for the future capability.

## 4. Technology Stack (as found in repo)

- Python 3.11.7, FastAPI, Pydantic v2, pydantic-settings
- SQLAlchemy 2.0 (synchronous ORM, `psycopg` 3 driver), Alembic
- PostgreSQL 16
- Argon2id (`argon2-cffi`) for passwords, PyJWT (HS256) for access tokens
- pytest (via `.venv`), Ruff (present in `pyproject.toml`/lockfile — not independently verified this pass)
- `uv` for dependency management (`uv.lock` present, currently **untracked** — see §9)
- Docker/Docker Compose mentioned in project context but not found/inspected in `backend/` this pass

## 5. Backend Architecture

```
HTTP Client
   ↓
[RequestIDMiddleware]  — X-Request-ID correlation, structured access logging
   ↓
[FastAPI Router /api/v1/...]
   ↓
[Dependencies: get_db, get_current_user, require_roles]
   ↓
[Pydantic v2 Schemas]  — request validation
   ↓
[Domain Services]      — business logic, transaction boundaries
   ↓
[SQLAlchemy 2.0 Models]
   ↓
[PostgreSQL 16]
   ↓
[Pydantic v2 Schemas]  — response serialization
   ↓
HTTP Response (+ X-Request-ID header)
```

**Modular monolith.** No microservices, no message bus, no distributed transactions. Explicitly
rejected until real scale justifies it (see §22).

### 5.1 Layer Responsibilities & Dependency Direction

```
API Routes → Dependencies/Schemas → Domain Services → SQLAlchemy Models → DB
```

- **`app/api/v1/`** — thin HTTP coordinators only. Currently wires only `auth` router
  ([auth.py](../../app/api/v1/auth.py)) plus a `/ping` liveness probe
  ([router.py](../../app/api/v1/router.py)). No catalog/cart/order/payment/inventory routes exist yet.
- **`app/dependencies/`** — `get_db` (request-scoped session), `get_current_user` (JWT → session →
  active-user resolution, fully implemented), `require_roles` (RBAC dependency **stub** — always
  raises `AuthorizationError`; real implementation deferred to Phase 9).
- **`app/schemas/`** — Pydantic v2 contracts. Only `auth.py` + `base.py` exist. No schemas yet for
  catalog, cart, orders, inventory, packaging, payments.
- **`app/services/`** — business logic, session-scoped, own their transaction boundaries. Only
  `AuthService` ([auth.py](../../app/services/auth.py)) exists.
- **`app/models/`** — 26 SQLAlchemy ORM models (see §8) — persistence only, no framework/HTTP awareness.
- **`app/core/`** — `config.py` (pydantic-settings), `security.py` (Argon2id + JWT), `logging.py`,
  `request_id.py`.
- **`app/exceptions/`** — `AppException` hierarchy → uniform `{code, message, details}` JSON contract.
- **`app/db/`** — `Base` (DeclarativeBase), sync engine + `SessionLocal`.

No generic `CRUDBase`/`Repository`/`UnitOfWork` abstractions exist or are planned — this is a
deliberate project decision (see [BACKEND_ARCHITECTURE_V1.md](BACKEND_ARCHITECTURE_V1.md) §8).

## 6. Alembic Migration History (current HEAD)

```
23d1924630c2  create_domain_1_identity_and_access_tables
56f5c455d612  create_phase_2_farm_and_traceability_tables
9fb24ab99384  create_phase_3_catalog_and_products
ff073dad9cfc  create_phase_4_inventory_and_stock
e204d99696f6  create_phase_5_packaging_and_labeling
a493a6752a97  create_phase_6_cart_and_orders
68d13edaa6f2  add_orders_cart_id_and_remove_redundant_order_address_index
a4738979ac7c  create_auth_sessions_table            (Phase 8)
d051168c1d3d  wholesaler_supply_model_batches        (Phase 8.1 — HEAD, see §9)
```

`alembic current` on the local dev database (`gawachabazaar`) reports **`d051168c1d3d (head)`** —
i.e. the Phase 8.1 migration has **already been applied to the local database**, even though the
corresponding model/test source changes are still uncommitted working-tree edits (§9).

## 7. Phase 1–8 Summary

| Phase | Tables | Key Decisions |
|---|---|---|
| 1 — Identity & Access | `roles`, `users`, `user_roles`, `addresses` | Roles are M:N via `user_roles` (`is_primary` flag, one primary role per user via partial unique index). `users` has **no** `role_id` column. |
| 2 — Farm & Traceability | `farms`, `batches`, `quality_checks` | Originally farmer/farm-centric; **corrected in Phase 8.1** (§9) to be wholesaler-centric while preserving farm/farmer structurally. |
| 3 — Catalog & Products | `categories`, `products`, `product_variants`, `product_images`, `prices` | `Product → ProductVariant → Price`; `Batch.product_id` links supply to catalog. |
| 4 — Inventory & Stock | `inventory_locations`, `inventory_lots`, `stock_movements` | `InventoryLot` = Batch + Variant + Location, unique together. `stock_movements.quantity` always > 0; direction encoded by `movement_type` CHECK constraint (`RECEIPT`, `ADJUSTMENT_IN/OUT`, `DAMAGE`, `WASTE`, `TRANSFER_IN/OUT`, `DISPATCH`). No DB triggers, no PG ENUMs — VARCHAR + CHECK throughout. |
| 5 — Packaging & Labeling | `packaging_operations`, `packaging_inputs`, `packaging_outputs` | Packaging/labeling only — not manufacturing/recipes/BOM. One operation: many inputs (source lots), many outputs (new packaged lots using existing `ProductVariant`s). Individual physical package IDs not tracked. |
| 6 — Cart & Orders | `carts`, `cart_items`, `orders`, `order_items`, `order_addresses` | One active cart per user (partial unique index on `status='ACTIVE'`). Cart items do **not** snapshot price. Order items **do** snapshot product/variant/price. Order address is snapshotted. `orders.cart_id` unique + `ON DELETE RESTRICT` — checkout lineage preserved; order creation does not itself touch inventory. |
| 7 — Payments | `payments`, `payment_transactions` | One `payments` row per order (unique `order_id`). Multiple `payment_transactions` per payment (retries/attempts), idempotency key unique. Methods: `UPI`, `COD` only. No gateway integration implemented. No card/CVV/UPI-PIN storage anywhere. |
| 8 — Production Authentication | `auth_sessions` | See §8 below. |

## 8. Current Database Table Inventory (26 tables)

`roles`, `users`, `user_roles`, `addresses`, `auth_sessions`, `farms`, `batches`, `quality_checks`,
`categories`, `products`, `product_variants`, `product_images`, `prices`, `inventory_locations`,
`inventory_lots`, `stock_movements`, `packaging_operations`, `packaging_inputs`,
`packaging_outputs`, `carts`, `cart_items`, `orders`, `order_items`, `order_addresses`, `payments`,
`payment_transactions`.

No `wholesalers` table exists or is planned (§10). No `warehouses`, `suppliers`, `wishlist`,
`promotions`, `coupons`, `fulfillments`, `reviews`, `notifications`, or `audit_logs` tables exist —
any such concept from older diagrams is **not** part of the current schema and must not be assumed.

## 9. Discrepancies Found vs. Provided Project Context

These are factual findings from repository inspection that the project context/prompt did not
fully anticipate — flagged per instructions rather than silently reconciled:

1. **The Wholesaler correction is not a future task — it is already drafted, uncommitted, and
   partially applied to the dev database.** On branch `phase/8.1-wholesaler-supply-model`:
   - [`app/models/batch.py`](../../app/models/batch.py), [`farm.py`](../../app/models/farm.py),
     [`user.py`](../../app/models/user.py) are modified in the working tree (not committed).
   - A new migration [`d051168c1d3d_wholesaler_supply_model_batches.py`](../../alembic/versions/d051168c1d3d_wholesaler_supply_model_batches.py)
     is **untracked** (`git status`) but **has already been run** against the local `gawachabazaar`
     database (`alembic current` = `d051168c1d3d (head)`).
   - A new test suite `tests/test_phase_8_1_wholesaler_supply_model.py` (20 tests) and updates to
     `test_phase_2/3/4/5_models.py` (batch-creation helpers now require `wholesaler_user_id`) are
     untracked/modified but not committed.
   - A doc, [`WHOLESALER_SUPPLY_MODEL.md`](WHOLESALER_SUPPLY_MODEL.md), already exists describing
     this exact correction in full (§3 above is consistent with it).
   - **Net effect**: the "Phase 8.1 correction" the task asked me to plan for already exists as a
     complete, self-consistent draft. Nothing further was implemented or committed in this session
     per instructions — but the next session should **not** re-derive this from scratch; it should
     review and commit/finish what's already on disk, or explicitly discard it if unwanted.
   - The migration includes a **data-safety guard**: it refuses to run if `batches` already has
     rows (`RuntimeError` if `batch_count > 0`), and the `downgrade()` refuses to revert if any
     `farm_id IS NULL` rows exist. This is a sound, non-silent safety pattern worth keeping as
     precedent for future migrations.

2. ~~No role-seeding mechanism exists anywhere in the codebase.~~ **RESOLVED in Phase 9** by
   migration `37bbdf459894_seed_baseline_roles` — see §12a.

3. **`uv.lock` is untracked.** A `uv.lock` file exists at `backend/uv.lock` but is not committed —
   worth resolving (commit it, or confirm dependency management intentionally uses a different
   lockfile such as `requirements.txt`/`pyproject.toml` alone).

4. **Farmer/Farm role does not yet exist as an actor concept anywhere in code.** The `farms` table
   has `owner_user_id → users.id`, implying a farm owner is a `User`, but there is no `FARMER` role
   string referenced anywhere, and no route/service touches `farms` at all yet (no farm CRUD
   exists). This is consistent with "Farmer/Farm is a future capability" — just noting it is
   *entirely* dormant, not partially wired.

5. ~~`require_roles` is a non-functional stub.~~ **RESOLVED in Phase 9** — see §12.

No other contradictions between the provided project context and repository reality were found —
the Phase 1–8 table lists, transaction/security/testing principles, and git branch model all match
what's actually in the repo.

## 9a. Phase 8.1 Verification Review (2026-09-11)

The uncommitted Phase 8.1 draft identified in §9 was formally reviewed and verified against the
running dev database (`gawachabazaar`) and the full relevant test suite. Findings:

- **Schema verified directly against PostgreSQL** (not just migration source): `batches.wholesaler_user_id`
  is `BIGINT NOT NULL`, FK `fk_batches_wholesaler_user_id_users → users.id` with `ON DELETE RESTRICT`,
  backed by `ix_batches_wholesaler_user_id`. `batches.farm_id` is nullable, FK `batches_farm_id_fkey →
  farms.id` with `ON DELETE RESTRICT` retained unchanged. No unrelated table/column was touched. No
  ENUM types, no triggers.
- **Migration `d051168c1d3d`**: correct parent (`4d9160d1bcc6`, auth_sessions), includes an explicit
  safety guard that refuses to run if `batches` has existing rows, and a symmetric guard on
  `downgrade()` refusing to revert if any `farm_id IS NULL` rows exist. Confirmed reversible and safe.
  **Dev database batch-row count at review time: 0** — the migration ran safely with no data at risk.
- **Test verification**: all 20 tests in `test_phase_8_1_wholesaler_supply_model.py` pass. Full
  regression of `test_auth.py` + `test_phase_2_models.py` through `test_phase_5_models.py` (184 tests
  total, including the batch-helper updates in phases 2–5 required by the new mandatory
  `wholesaler_user_id`) passes with zero failures — authentication is unaffected by the schema
  correction.
- **ORM verified correct**: `Batch.wholesaler` (→ `User.batches_supplied`, `passive_deletes=True`)
  and `Batch.farm` (→ `Farm.batches`, now `Farm | None` typed, `passive_deletes=True`) are both
  correctly configured, bidirectional, and consistent with the FK `ON DELETE RESTRICT` semantics
  (ORM does not attempt to cascade-null what the DB restricts).
- **Confirmed via direct query: the `roles` table in the dev database is empty (0 rows).** None of
  `CUSTOMER`, `WHOLESALER`, `ADMIN`, `HUB_STAFF`/`OPERATIONS`, or `DELIVERY_PARTNER` exist. `users`
  is also empty (0 rows). No migration, startup routine, bootstrap script, or seed mechanism exists
  anywhere in the repository to populate `roles` — this was re-confirmed, not merely repeated from
  §9.2. Public registration will fail with a 500 until this is deliberately addressed. **Role seeding
  is an open decision, not yet implemented, and whether `HUB_STAFF`/`OPERATIONS` is one role or two
  separate roles is explicitly unresolved and deferred.**

**Confirmed architectural principles (verbatim, for future sessions):**

> WHOLESALER is currently represented by a User with the WHOLESALER role. A dedicated `wholesalers`
> table is not part of the current architecture unless future wholesaler-specific business
> attributes justify one.

> Farmer/Farm remain future capabilities and are not the current supply-side actor.

No correction to the migration, models, or ORM relationships was found necessary. No new migration
was created.

## 10. Why There Is No `wholesalers` Table

Per [WHOLESALER_SUPPLY_MODEL.md](WHOLESALER_SUPPLY_MODEL.md) §7, all actors are unified under
`users` + `user_roles` (M:N to `roles`). A wholesaler is simply a `User` whose `user_roles` include
a `WHOLESALER` role. `batches.wholesaler_user_id → users.id (ON DELETE RESTRICT)` is the sole FK
representing supply origin at the database level; **role membership is an application-layer
concern**, not a DB constraint (deliberately — no cross-table CHECK/trigger enforcing role
membership, to keep the DB layer portable and fast). Do not create a `wholesalers` profile table
unless/until dedicated B2B attributes (GSTIN, APMC license, bank mandate, etc.) are explicitly
requested.

## 11. Authentication Architecture (Phase 8 — implemented)

Endpoints (`/api/v1/auth/*`): `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`,
`GET /me`.

- **Passwords**: Argon2id via `argon2-cffi` (`app/core/security.py`).
- **Access tokens**: short-lived JWT (default 15 min), HS256, claims `sub`, `sid`, `iat`, `exp`,
  `jti`, `type=access`, `iss`, `aud`.
- **Refresh tokens**: opaque `secrets.token_urlsafe(48)` (~384 bits), stored **only** as SHA-256
  hash in `auth_sessions.refresh_token_hash` (unique). Raw token never persisted.
- **Session lifetime**: 30-day **absolute** expiry from creation; rotation does **not** extend it.
- **Rotation**: `refresh_session` acquires `SELECT ... FOR UPDATE` on the `AuthSession` row,
  validates not-revoked/not-expired/user-active, replaces `refresh_token_hash` in place, updates
  `last_used_at`. A second concurrent request with the stale token fails cleanly once the row is
  updated and committed.
- **Replay protection is bounded, not historical**: because each session stores exactly one current
  `refresh_token_hash` (not a token-family chain), the system detects "this exact token was already
  rotated away" but cannot reconstruct/flag a full historical reuse chain across many rotations.
  **Do not claim stronger replay detection than this, and do not introduce a second refresh-token
  table to simulate it without an explicit design decision** — this is a known, accepted limitation
  per project context, not a bug.
- **Enumeration protection**: unknown email/phone, wrong password, inactive, and suspended accounts
  all raise the identical generic `AuthenticationError("Invalid credentials.")`.
- **Logout**: idempotent — repeated calls with an already-revoked/unknown token succeed silently.
- **`get_current_user`**: validates JWT signature/exp/iss/aud/type, then re-checks the DB-backed
  `AuthSession` (not revoked, not expired) *and* the `User.status == 'ACTIVE'` — a revoked session
  or deactivated user invalidates an otherwise cryptographically valid token immediately.

## 12. Authorization Direction (Phase 9 — implemented as a foundation)

`require_roles(*allowed_roles)` in [`app/dependencies/auth.py`](../../app/dependencies/auth.py) is
implemented: it composes `get_current_user` (authentication) and then checks, against **current
database state** (`user_roles JOIN roles`, not JWT claims), whether the authenticated user holds
**any one** of the given role names. No role hierarchy exists — `ADMIN` does not implicitly satisfy
a requirement for `OPERATIONS`. Unauthenticated → 401 (`AuthenticationError`, unchanged). Authenticated
but missing every required role → 403 (`AuthorizationError`, generic message, no role enumeration).
See [PHASE_9_RBAC.md](PHASE_9_RBAC.md) for full detail. As of Phase 10, `require_roles(ADMIN)` protects
every catalog management route (`POST`/`PATCH`/`DELETE` under `/api/v1/catalog/...`) — the first real
end-to-end proof of this foundation. Public `GET` catalog routes remain unauthenticated by design.

## 12a. Role Initialization (Phase 9)

Baseline roles are seeded by a **reference-data-only Alembic migration**
(`37bbdf459894_seed_baseline_roles`, not a schema change), chosen because Alembic is already the sole
mandatory mechanism every environment must run before the app can function — piggybacking seeding onto
it means there is exactly one initialization mechanism, not a separate bootstrap script that could be
forgotten. Seeding is idempotent (`INSERT ... ON CONFLICT (name) DO NOTHING` keyed on `roles.name`,
never on `roles.id`). The six active roles seeded are `CUSTOMER`, `WHOLESALER`, `ADMIN`, `HUB_STAFF`,
`OPERATIONS`, `DELIVERY_PARTNER` — `HUB_STAFF` and `OPERATIONS` are **two separate roles** (this
resolves the open question flagged after the Phase 8.1 review). `FARMER` is not seeded. Seeding a role
creates no `users` or `user_roles` rows and authorizes nobody by itself — role assignment remains a
separate, explicit operation. `app/core/roles.py` holds the single in-code representation of these six
role-name strings, used by `AuthService` and `require_roles` instead of scattered string literals. Full
detail: [PHASE_9_RBAC.md](PHASE_9_RBAC.md).

## 13. Inventory Principles

- `inventory_lots.quantity` = current operational balance (can be 0, never negative — CHECK
  constraint).
- `stock_movements` = **append-only audit ledger**; `quantity` always strictly positive; direction
  is implied by `movement_type`.
- `InventoryLot` is uniquely keyed on `(batch_id, variant_id, location_id)`.
- **Implemented in Phase 11**: `InventoryService.create_movement` uses `SELECT ... FOR UPDATE`
  (`app/services/inventory.py`) to lock the lot row for the duration of validate→update→insert→commit.
  Quantity can change **only** through `POST /inventory/lots/{id}/movements` — there is no direct
  quantity-mutation endpoint. `batch.product_id == variant.product_id` is enforced in service code
  (the database does not enforce it). Full detail: [PHASE_11_INVENTORY_API.md](../api/PHASE_11_INVENTORY_API.md).
- **Transaction-design gotcha** (see Phase 11 doc for full explanation): any service method reached
  through an authenticated route must **not** call `db.begin()` — `get_current_user` already
  autobegins the session's transaction via its own reads before the route handler runs. Perform
  writes against the already-open transaction and call `db.commit()` once at the end instead.

## 14. Packaging Principles

- `packaging_operations` → many `packaging_inputs` (consumed source lots) → many
  `packaging_outputs` (new/updated packaged lots using existing `ProductVariant`s).
- Strictly packaging/labeling — not manufacturing, recipes, or BOM.
- **Single-batch traceability invariant**: an output inventory lot must trace to exactly one source
  batch — mixing multiple source batches into one output lot is forbidden. **Implemented in Phase 12**:
  `PackagingService.add_output` requires the declared `batch_id` to match a batch actually present
  among the operation's current inputs, and `complete_operation` re-validates this at completion
  time (an input can be removed after an output references its batch). Full detail:
  [PHASE_12_PACKAGING_API.md](../api/PHASE_12_PACKAGING_API.md).
- Individual physical package IDs are not tracked at this granularity.
- **Completion is one atomic transaction** (`PackagingService.complete_operation`): locks the
  operation row (serializes concurrent completion of the same operation), locks every input/output
  lot in one consistently-ordered query, applies `ADJUSTMENT_OUT` to inputs and `RECEIPT` to outputs
  via `InventoryService.apply_movement` (reused, not duplicated), then a single commit. No inventory
  change happens when inputs/outputs are merely added — only at `/complete`.

## 15. Cart / Order Principles

- One **active** cart per user (partial unique index `carts(user_id) WHERE status='ACTIVE'`).
- Cart items do not snapshot price (live-priced until checkout).
- Order items **do** snapshot product name, variant name, SKU, unit, quantity, unit price, total
  price — immune to later catalog/price changes.
- Order address is snapshotted into `order_addresses` (1:1, unique `order_id`).
- `orders.cart_id` is unique and `ON DELETE RESTRICT` — exact checkout lineage, one order per cart
  maximum, cart is never hard-deleted out from under a placed order.
- Order creation does **not** itself mutate inventory — confirmed by test in Phase 13, and remains
  true even though `InventoryService` now exists (Phase 11): checkout deliberately never imports it.
- **Implemented in Phase 13**: `OrderService.checkout` (`app/services/order.py`) is the one atomic
  checkout transaction — locks the cart row (found by `user_id ORDER BY id DESC`, deliberately
  unfiltered by status — see the Phase 13 doc for why a status filter would break retry safety under
  PostgreSQL's `FOR UPDATE` row-exclusion behavior), then purchased variant rows in ascending id
  order, revalidates catalog state, resolves current prices via the shared
  `app/services/pricing.py` rule, snapshots into `order_items`/`order_addresses`, and commits once.
  `orders.cart_id UNIQUE` + the cart-row lock give checkout domain-level retry safety (duplicate/
  concurrent checkout resolves to the same order) with no idempotency-key table. Full detail:
  [PHASE_13_CART_ORDERS_API.md](../api/PHASE_13_CART_ORDERS_API.md).

## 16. Payment Principles

- Exactly one `payments` row per `order` (unique `order_id`).
- One payment can have many `payment_transactions` (gateway attempts/retries), each with a unique
  `idempotency_key`.
- Supported methods today: `UPI`, `COD` only.
- Never store: card numbers, CVV, UPI PIN, OTPs, gateway secrets.
- **Implemented in Phase 14**: `PaymentService` (`app/services/payment.py`) owns initiation, retry,
  client-triggered reconciliation (`/verify`), and webhook processing. An explicit state machine
  (`app/services/payment_state.py`) is the only path `payments.status`/`payment_transactions.status`
  can change through — `PAID` and `CANCELLED` are hard terminal states, a late/duplicate event can
  never downgrade `PAID`. Webhook authenticity (placeholder HMAC-SHA256 — see below) is verified
  before any DB mutation; `UNIQUE(gateway_name, event_id)` on the new `payment_webhook_events` table
  (plus `payments.gateway_name`/`gateway_order_id`, jointly unique) makes duplicate/concurrent webhook
  delivery safe without an in-memory dedup cache. Full detail, including a real concurrency bug found
  and fixed via SQLAlchemy's identity-map/`with_for_update()` interaction:
  [PHASE_14_PAYMENTS_API.md](../api/PHASE_14_PAYMENTS_API.md).
- **No real PNB gateway integration exists.** No PNB merchant specification was found anywhere in
  this repository. `PNBGateway.initiate_payment`/`query_status` deliberately raise
  `NotImplementedError` rather than inventing a contract; only the webhook signature
  verification/parsing use a clearly-labeled placeholder scheme. `FakePNBGateway` (test-only) is
  injected via a `get_payment_gateway` FastAPI dependency override, mirroring the existing `get_db`
  override pattern, so the full domain is tested without real PNB connectivity.

## 17. Security Principles

- Never log or return: passwords, password hashes, JWTs, refresh tokens/hashes, `Authorization`
  headers, payment secrets, gateway credentials, OTPs, CVVs.
- Public error responses (via `app/exceptions/handlers.py`) never leak SQL, stack traces, file
  paths, or internal state — unhandled exceptions collapse to a generic 500
  `INTERNAL_SERVER_ERROR` with full detail only in server-side logs (`exc_info=True`).
- All domain errors funnel through a single `{code, message, details}` JSON contract.
- CORS origins are explicit allow-list (`ALLOWED_ORIGINS`), no wildcard-with-credentials pattern.

## 18. Transaction Principles

- Any multi-row business workflow owns an explicit transaction boundary (`with db.begin():` or the
  project's nested-savepoint-aware `_transaction()` helper in `AuthService`).
- Lower-level helpers/services must never call `db.commit()` independently — only the orchestrating
  service controls commit timing.
- On exception inside the transaction block, SQLAlchemy rolls back automatically.
- Future checkout will require: lock cart → validate → resolve prices → create order → create order
  items → snapshot address → create payment → mark cart checked out → commit (all-or-nothing).

## 19. Testing Principles

- Test DB is hard-isolated: `tests/conftest.py` asserts `"gawachabazaar_test"` appears in the
  resolved `DATABASE_URL` before any engine is created — a real safety rail against accidentally
  truncating the dev database.
- `db_session` fixture truncates all domain tables (`RESTART IDENTITY CASCADE`) in explicit
  dependency order before each test — real PostgreSQL, not mocks, for constraint/FK/lock behavior.
- Phase test files (`test_phase_N_models.py`) validate real DB constraints (uniqueness, CHECKs, FKs)
  — not just ORM-level behavior.
- No test currently exercises concurrency (`SELECT ... FOR UPDATE` refresh rotation has no explicit
  race-condition test yet, despite the service code supporting it) — a gap worth closing before
  Phase 9 if refresh rotation correctness needs to be proven under load.

## 20. Git Workflow

`main` ← `develop` ← `phase/<name>` feature branches, via PR (no separate `test` branch was found in
the actual remote — `origin` has only `main` and `develop`; treat this document's earlier reference to
a `test` branch as aspirational unless one is created). **Promotion discipline**: every feature branch
must PR into `develop` first, never directly into `main` — Phase 8.1 briefly violated this (its PR was
opened against `main`, leaving `develop` behind) and was corrected by re-merging the same branch into
`develop` (PR #16) before Phase 9 started. Never rewrite an applied historical Alembic migration —
always add a new one (Phase 8.1 and Phase 9 both followed this).

## 21. Current Active Development Phase

**Phase 14 — Payments (PNB UPI + COD) — domain implemented, PNB integration deliberately incomplete.**
The Phase 7 payments schema now has a real, `CUSTOMER`-only API (`/api/v1/payments`,
`/api/v1/orders/{id}/payment`) plus one additive migration (`payments.gateway_name`/`gateway_order_id`,
and the new `payment_webhook_events` table for durable webhook deduplication). `PaymentService`
(`app/services/payment.py`) owns initiation, retry, `/verify` reconciliation, and webhook processing,
all driven through an explicit state machine (`app/services/payment_state.py`) — see §16 and
[PHASE_14_PAYMENTS_API.md](../api/PHASE_14_PAYMENTS_API.md) for the full transaction/locking/webhook
algorithm and a second real concurrency bug found and fixed this phase (SQLAlchemy's identity map
silently serving a stale object from a `with_for_update()` re-query after an earlier unlocked read of
the same row — fixed with `.populate_existing()`; this is a general SQLAlchemy gotcha any future
"lock this row, but I need its FK first" pattern should watch for). **No PNB merchant integration
specification exists in this repository** — `PNBGateway.initiate_payment`/`query_status` honestly
raise `NotImplementedError` rather than inventing PNB's real contract; only the webhook signature
scheme is implemented, as a clearly-labeled placeholder. UPI therefore cannot complete against a real
gateway yet — this is a deliberate, documented gap, not an oversight.

Phase 10-13's `db.begin()`-under-authenticated-routes gotcha (§13/§14/§15) applies here too and was
followed correctly — `PaymentService` never calls it, including in its one `async def` route (the
webhook endpoint, which needs the raw request body — the sync DB work is explicitly run via
`starlette.concurrency.run_in_threadpool` so it doesn't block the event loop, a first in this
codebase and the only async route so far).

Still not built: farm, delivery APIs — each should follow the established pattern (thin router →
service returning schema instances directly → `require_roles` for any protected endpoint, reuse
rather than duplicate sibling-domain business logic where safe) rather than introducing a new one.

## 22. Explicitly Rejected / Out-of-Scope Architectural Ideas

Not to be introduced without an explicit, separate request:

- Microservices, service mesh, Kafka/RabbitMQ, event sourcing, CQRS
- Redis / distributed caching (session storage is DB-backed by design)
- Generic `Repository`/`CRUDBase`/`UnitOfWork` abstractions
- PostgreSQL ENUM types, DB triggers, polymorphic generic FK frameworks
- A dedicated `wholesalers` table (until B2B-specific profile attributes are explicitly requested)
- Dual-source (wholesaler + farm simultaneously active) batch model
- A second refresh-token table to fake full historical replay-family detection
- Any table implied only by old conceptual diagrams (`suppliers`, `warehouses`, `wishlist`,
  `promotions`, `coupons`, `fulfillments`, `reviews`, `notifications`, `audit_logs`) — none of these
  exist in the schema today and none should be created spontaneously
- `permissions`, `role_permissions`, `user_permissions`, `acl_rules` tables (no permission/ACL system
  in Phase 9 — role membership alone is the authorization unit)
- Role hierarchy/inheritance (e.g. assuming `ADMIN` implies `OPERATIONS`) — not implemented in Phase 9
- A role-management API (`POST /admin/users/{id}/roles` or similar) — not built in Phase 9; role
  assignment beyond registration's automatic `CUSTOMER` is a deliberate, separate future operation
- Putting role claims into the JWT as an authorization source of truth — `user_roles` in the database
  is authoritative, checked fresh on every request, specifically so a role change doesn't wait for
  access-token expiration

## 23. Rules for Future Sessions (Claude Code or otherwise)

1. **Repository state is the source of truth**, above this document, above old diagrams, above
   verbal project descriptions — if they conflict, re-verify against `git status`, `alembic
   current`, and the actual model files before acting.
2. **Never repurpose Farmer/Farm as Wholesaler.** They are structurally separate, permanently.
3. **Never edit an already-applied Alembic migration.** Add a new one, and mirror the existing
   pattern of adding safety guards (`RuntimeError` on unsafe data state) where a migration could
   silently corrupt or truncate meaningful data.
4. **Before any new phase**, re-run the 13-step inspection this document was built from: repo
   structure, git status/branch/log, `alembic heads`/`current`, models, migrations, tests, docs.
5. **Role names belong in `app/core/roles.py`**, not scattered string literals — import the constants
   (`CUSTOMER`, `WHOLESALER`, `ADMIN`, `HUB_STAFF`, `OPERATIONS`, `DELIVERY_PARTNER`,
   `BASELINE_ROLES`) rather than retyping raw strings. Baseline role seeding is handled by migration
   `37bbdf459894` — do not add a second seeding mechanism (bootstrap script, startup hook, fixture)
   alongside it.
6. **`require_roles` is implemented** (§12) — use `Depends(require_roles("ROLE_A", "ROLE_B"))` on new
   protected routes rather than reinventing an authorization check. Any-of-multiple-roles semantics,
   no hierarchy. Do not add role-level authorization logic anywhere else (routes, services) — this is
   the one place it belongs.
7. **Keep the modular monolith.** Any suggestion to split into services requires an explicit,
   separate request and justification tied to real scale, not speculation.
8. When this document and the live repository disagree, **update this document**, don't silently
   trust stale text here.
