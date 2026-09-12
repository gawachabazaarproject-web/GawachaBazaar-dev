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
68d13edaa6f2  create_phase_7_payments
a4738979ac7c  add_orders_cart_id_and_remove_redundant_order_address_index
4d9160d1bcc6  create_auth_sessions_table                            (Phase 8)
d051168c1d3d  wholesaler_supply_model_batches                       (Phase 8.1)
37bbdf459894  seed_baseline_roles                                   (Phase 9)
7b8bd4525a83  add_payment_gateway_reference_and_webhook_events      (Phase 14)
2603b7a0587e  inventory_reservation_and_fulfillment                 (Phase 15 — HEAD)
```

> Corrected 2026-09-12: the ID/message pairing above had drifted from `alembic history` in this
> document's earlier revision (IDs were paired with the wrong phase labels after Phase 9-14 were
> merged) — re-verified directly against `alembic history` while adding the Phase 15 row. Trust
> `alembic history`/`alembic heads` over this table if they ever disagree again.

`alembic current` on the local dev database (`gawachabazaar`) now reports **`2603b7a0587e (head)`**
(the Phase 15 migration) — confirmed applied to both `gawachabazaar` and `gawachabazaar_test` with
zero autogenerate drift (`alembic check`) as of this phase.

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

## 8. Current Database Table Inventory (40 tables, as of Phase 17)

`roles`, `users`, `user_roles`, `addresses`, `auth_sessions`, `farms`, `batches`, `quality_checks`,
`categories`, `products`, `product_variants`, `product_images`, `prices`, `inventory_locations`,
`inventory_lots`, `stock_movements`, `packaging_operations`, `packaging_inputs`,
`packaging_outputs`, `carts`, `cart_items`, `orders`, `order_items`, `order_addresses`, `payments`,
`payment_transactions`, `payment_webhook_events`, `inventory_reservations`,
`inventory_reservation_items`, `fulfillments`, `suppliers`, `supplier_products`,
`supplier_evaluations`, `bulk_customer_profiles`, `bulk_order_requests`,
`bulk_order_request_items`, `quotes`, `quote_versions`, `quote_items`.

No `wholesalers` table exists or is planned (§10). `suppliers` **is** now part of the schema
(Phase 17, §21c) - it is a deliberately distinct concept from the old "wholesaler" idea; see §10
and §21c for why both `batches.wholesaler_user_id` and `batches.supplier_id` now coexist. No
`warehouses`, `wishlist`, `promotions`, `coupons`, `reviews`, `notifications`, or `audit_logs`
tables exist — any such concept from older diagrams is **not** part of the current schema and must
not be assumed.
`fulfillments` **is** now part of the schema (Phase 15, §21a; delivery-partner assignment added in
Phase 16, §21b) — the "not built" list in §22 has been updated to reflect this; it is intentionally
coarse (order-level status + basic assignment only), not a full logistics system (no routing, live
tracking, or proof-of-delivery).

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

## 10. Why There Is No `wholesalers` Table (and Why `suppliers` Is Different)

Per [WHOLESALER_SUPPLY_MODEL.md](WHOLESALER_SUPPLY_MODEL.md) §7, all actors are unified under
`users` + `user_roles` (M:N to `roles`). A wholesaler is simply a `User` whose `user_roles` include
a `WHOLESALER` role. `batches.wholesaler_user_id → users.id (ON DELETE RESTRICT)` is the sole FK
representing supply origin at the database level; **role membership is an application-layer
concern**, not a DB constraint (deliberately — no cross-table CHECK/trigger enforcing role
membership, to keep the DB layer portable and fast). This section's original guidance ("do not
create a `wholesalers` profile table") still holds - no such table exists.

**Phase 17 correction**: "wholesaler" turned out to conflate two different business concepts. A
**Supplier** (Phase 17) is a business GawachaBazaar buys FROM - it does **not** need a login and is
therefore deliberately **not** a `User` (unlike a wholesaler, which always was one). `suppliers` is
an independent business-record table, not a `wholesalers` profile table wrapping a `User` - the
distinction this section originally warned against (inventing user-wrapper tables) does not apply,
because a `Supplier` has no associated `User` to wrap. `batches.supplier_id` and
`batches.wholesaler_user_id` now coexist on the same row (additive migration, Phase 17) - see §21c
for the full reasoning and the CHECK constraint that guarantees every batch still has at least one
traceable origin. Fully retiring `wholesaler_user_id` is an explicit, undone future stage.

An entirely separate Phase 17 concept, **Bulk Customer**, is the opposite direction (buys FROM
GawachaBazaar in large quantities) and stays a `User` with the existing `CUSTOMER` role plus an
optional `BulkCustomerProfile` - no new role, no new auth flow. Supplier ≠ Bulk Customer ≠ Customer;
see §21c.

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

- `inventory_lots.quantity` = current **physical** balance (can be 0, never negative — CHECK
  constraint). Only a `stock_movements` row changes it.
- **Added in Phase 15**: `inventory_lots.reserved_quantity` = inventory promised to
  ACTIVE/COMMITTED reservations, CHECK `0 <= reserved_quantity <= quantity`.
  `available = quantity - reserved_quantity` is **computed, never persisted**. Reservation
  changes `reserved_quantity` only — physical `quantity` is untouched until delivery
  confirmation (§21a). This is the AVAILABLE → RESERVED → COMMITTED → DELIVERED/CONSUMED
  lifecycle: reservation ≠ consumption, payment ≠ consumption, picking/packing ≠ consumption.
- `stock_movements` = **append-only audit ledger**; `quantity` always strictly positive; direction
  is implied by `movement_type`. **Phase 15 reuses `DISPATCH`** (already meaning "goods leaving
  the facility") for delivery-confirmation physical consumption — no new movement type was added;
  see §21a.
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
- **Superseded in Phase 15**: order creation used to leave inventory completely untouched (true for
  Phase 13). As of Phase 15, checkout **reserves** inventory (`inventory_lots.reserved_quantity`)
  atomically as part of the same transaction — physical `quantity` still never moves at checkout;
  only reservation bookkeeping changes. See §21a.
- **Implemented in Phase 13, extended in Phase 15**: `OrderService.checkout` (`app/services/order.py`)
  is the one atomic checkout transaction — locks the cart row (found by `user_id ORDER BY id DESC`,
  deliberately unfiltered by status — see the Phase 13 doc for why a status filter would break retry
  safety under PostgreSQL's `FOR UPDATE` row-exclusion behavior), then purchased variant rows in
  ascending id order, revalidates catalog state, resolves current prices via the shared
  `app/services/pricing.py` rule, snapshots into `order_items`/`order_addresses`, **creates the
  order's inventory reservation via `InventoryReservationService.create_reservation_for_order`
  (Phase 15, §21a) before the single commit** — insufficient stock rolls back the entire checkout,
  not just the reservation — and commits once. `orders.cart_id UNIQUE` + the cart-row lock give
  checkout domain-level retry safety (duplicate/concurrent checkout resolves to the same order,
  and thus the same reservation) with no idempotency-key table. Full detail:
  [PHASE_13_CART_ORDERS_API.md](../api/PHASE_13_CART_ORDERS_API.md) (checkout mechanics) and
  [PHASE_15_INVENTORY_RESERVATION_FULFILLMENT_API.md](../api/PHASE_15_INVENTORY_RESERVATION_FULFILLMENT_API.md)
  (reservation mechanics).
- Checkout still never decides COD vs UPI or creates a `Payment` row — that remains
  `POST /payments`'s job (§16), unchanged in request shape since Phase 14.

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
- **Extended in Phase 15**: order confirmation (`PENDING → CONFIRMED`) is now gated by committing
  the order's inventory reservation, not payment status alone. `PaymentService._confirm_cod` and
  `PaymentService._confirm_order_if_paid` both call
  `InventoryReservationService.commit_reservation_for_order` before touching `order.status` — if
  the reservation already expired (or was otherwise released), the order is **not** confirmed, even
  though the payment itself may be legitimately `PAID` (a late-payment-after-expiry reconciliation
  case, logged as `PAYMENT_RESERVATION_MISMATCH`, never silently resolved). See §21a.
- **Deliberate Phase 15 deviation, documented in `app/services/inventory_reservation.py`**: a
  definitively FAILED UPI payment attempt does **not** release its reservation (the spec's literal
  text called for ACTIVE→RELEASED on failure). Because `inventory_reservations` has
  `UNIQUE(order_id)` and RELEASED is terminal, releasing on failure would strand a later successful
  `POST /payments/{id}/retry` with no reservation left to commit, and re-reserving inside
  `retry_payment` would duplicate FIFO allocation logic in a second place. Instead the reservation
  stays ACTIVE through a failed attempt (bounded by its own 30-minute expiry) so the existing,
  unmodified retry flow keeps working.

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

Phase 14/15 background above is now historical — see §21b for the current phase.

Still not built: farm APIs, advanced delivery logistics (routing, live tracking, ETA prediction,
geofencing/delivery zones, proof-of-delivery/signature/OTP capture). Basic delivery-partner
assignment IS built (Phase 16, §21b). Each new domain should follow the established pattern (thin
router → service returning schema instances directly → `require_roles` for any protected endpoint,
reuse rather than duplicate sibling-domain business logic where safe) rather than introducing a new
one.

## 21a. Inventory Reservation & Order Expiry & Fulfillment Foundation (Phase 15)

Adds inventory reservation (hold at checkout, before payment),
a 30-minute order-level payment window, and a minimal order-level fulfillment state machine ending
in physical inventory consumption at delivery confirmation. New migration
`2603b7a0587e_inventory_reservation_and_fulfillment` (additive: `inventory_lots.reserved_quantity`
+ CHECK, `orders.ck_orders_status` widened to add `EXPIRED`, three new tables). Full detail:
[PHASE_15_INVENTORY_RESERVATION_FULFILLMENT_API.md](../api/PHASE_15_INVENTORY_RESERVATION_FULFILLMENT_API.md).

**Core lifecycle**: `AVAILABLE → RESERVED → COMMITTED → DELIVERED/CONSUMED`. Reservation changes
`inventory_lots.reserved_quantity` only; physical `quantity` is untouched until delivery
confirmation. Payment commits a reservation; it never itself consumes inventory.

**New tables**:
- `inventory_reservations` — one per order (`UNIQUE(order_id)`), status
  `ACTIVE → {COMMITTED, RELEASED, EXPIRED}` (all three terminal), `expires_at` fixed at creation
  (`checkout time + 30 minutes`, independent of payment method — see below).
- `inventory_reservation_items` — the FIFO allocation join (`order_item_id` × `inventory_lot_id` ×
  `quantity`); one order item may span multiple lots. Append-only; delivery confirmation replays
  this exact allocation rather than recomputing it.
- `fulfillments` — one per order (`UNIQUE(order_id)`), linear chain
  `PENDING → PICKING → PACKED → READY_FOR_DELIVERY → OUT_FOR_DELIVERY → DELIVERED`. Created the
  moment a reservation is first COMMITTED (COD acceptance or UPI payment success).

**FIFO allocation** (`app/services/inventory_reservation.py`,
`InventoryReservationService.create_reservation_for_order`, called from inside
`OrderService.checkout` before its single commit): locks every ACTIVE lot for each needed variant
via `SELECT ... FOR UPDATE ORDER BY created_at ASC, id ASC` — **across all locations**, not scoped
to one (there is no location-selection concept anywhere else in this codebase, and the spec only
requires FIFO-by-time ordering, so pooling across locations is the smallest correct design, not a
gap that needed a new convention). Allocates in memory against freshly-locked quantities; any
variant left short fails the *entire* reservation (and therefore the entire checkout) with nothing
partially applied.

**Expiry** is lazy, not worker-dependent: any operation that touches an ACTIVE reservation
(`commit_reservation_for_order`, a customer `GET .../reservation`, an ops detail read) checks
`expires_at` against the current server time and atomically expires it inline if overdue, under the
same row lock used for every other transition — this is what makes the payment-success-vs-expiry
race resolve to exactly one winner. `expires_at` is set once, at reservation creation, from
`checkout time + 30 minutes` — **not** UPI-specific: the reservation exists before a payment method
is ever chosen, so COD is not exempt from the window either (a COD confirmation attempt on an
already-expired reservation is rejected, not silently allowed). When a reservation actually expires,
its order moves `PENDING → EXPIRED` (a new explicit terminal status; `orders.ck_orders_status` was
widened additively to allow it) in the same locked transaction — Order is always locked *before*
Reservation everywhere this can happen, matching the global lock order below, specifically so this
doesn't deadlock against the payment-confirmation path racing the same pair of rows.

**Payment integration** (`app/services/payment.py`, unchanged request/response contracts): COD
confirmation and the payment-success confirmation path (`_confirm_cod`,
`_confirm_order_if_paid` — the latter shared by initiate/webhook/verify, as in Phase 14) both now
call `InventoryReservationService.commit_reservation_for_order` before setting `order.status =
"CONFIRMED"`. If the reservation cannot be committed (already EXPIRED/RELEASED), the order is left
exactly as it was — this is the enforcement point for "a late payment success must never resurrect
an expired reservation." See §16 for the one documented deviation from the spec's literal text
(UPI failure does not release the reservation).

**Delivery confirmation** (`app/services/fulfillment.py`, `FulfillmentService.confirm_delivery`) is
the sole physical-consumption transaction: lock order → lock fulfillment (idempotent no-op if
already DELIVERED) → verify `OUT_FOR_DELIVERY` → lock reservation → verify COMMITTED → read its
allocation items → lock every allocated lot in ascending-id order → for each, apply a `DISPATCH`
stock movement (reusing `InventoryService.apply_movement`, not duplicating it — `DISPATCH` already
meant "goods leaving the facility," a direct semantic fit, so no new movement type was added) and
decrement `reserved_quantity` by the same amount → mark fulfillment DELIVERED, order COMPLETED →
commit once. No partial fulfillment: any inconsistency aborts the whole transaction.

**Lock ordering**, extending Phase 13/14's Order-before-Payment convention: **Cart → Order →
Payment → Fulfillment → Reservation → InventoryLots** (lots always last, in `created_at ASC, id ASC`
FIFO order for allocation or plain `id ASC` for a known set during release/delivery). Every new
locking helper that does an unlocked pre-read (to discover a foreign key) followed by a locked
re-read of the *same* row uses `.populate_existing()` on the locked query — the Phase 14
stale-identity-map gotcha (§21, "lock this row, but I need its FK first") recurred at least twice
while building this phase (`InventoryReservationService._lock_reservation_by_order_id`,
`FulfillmentService.confirm_delivery`) and was fixed the same way each time.

**Concurrency-tested** (real threads against real PostgreSQL row locks, `tests/test_phase_15_inventory_reservation_fulfillment.py`):
two customers racing the last unit of stock, concurrent multi-lot FIFO allocation, concurrent
manual expiry (double-release-safe), payment-success-vs-expiry (exactly one of
COMMITTED/EXPIRED wins), concurrent delivery confirmation (no double physical consumption), and
concurrent checkout across customers for shared limited inventory (no oversell).

## 21b. Fulfillment & Delivery Operations (Phase 16)

Extends Phase 15's order-level `Fulfillment` with a delivery-partner
assignment step and full RBAC-scoped delivery-in-transit actions. New migration
`2c63b696c267_fulfillment_delivery_assignment` (additive: `fulfillments.delivery_partner_user_id`,
`fulfillments.inventory_location_id`, `fulfillments.assigned_at`, `ck_fulfillments_status` widened
to add `ASSIGNED`). Full detail:
[PHASE_16_FULFILLMENT_DELIVERY_API.md](../api/PHASE_16_FULFILLMENT_DELIVERY_API.md).

**Extended state machine**:

```
PENDING → PICKING → PACKED → READY_FOR_DELIVERY → ASSIGNED → OUT_FOR_DELIVERY → DELIVERED
```

Only DELIVERED consumes physical inventory - picking, packing, staging, assignment, and dispatch
are all pure status bookkeeping. `app/services/fulfillment_state.py`'s generic linear-chain
transition logic (unchanged since Phase 15) picked up the new `ASSIGNED` step automatically by
inserting one entry into its ordered status list - no transition-matrix rewrite was needed.

**Delivery partner = User + role, not a new table**: identical precedent to Wholesaler
(Phase 8.1). `fulfillments.delivery_partner_user_id` is a nullable FK to `users.id`; assignment
validates the target holds the `DELIVERY_PARTNER` role via the same `user_roles JOIN roles` pattern
`require_roles` itself uses - there is no `delivery_partners` profile table and none is planned
unless dedicated attributes are ever requested.

**A real architectural conflict, resolved**: the spec's mental model was "one fulfillment ↔ one
inventory location," but Phase 15 deliberately pools FIFO allocation across ALL locations for a
variant (no location-selection concept exists anywhere in this codebase). A single reservation can
therefore legitimately span multiple locations. Smallest compatible fix:
`fulfillments.inventory_location_id` is nullable and populated by
`InventoryReservationService._ensure_fulfillment` only when every lot the reservation actually
allocated from shares one location; a genuinely multi-location allocation leaves it `NULL` rather
than recording a misleading single location. No location-selection convention was invented.

**Assignment is not a same-state no-op**: `FulfillmentService.assign_delivery_partner` deliberately
does NOT reuse `transition_fulfillment_status`'s generic "current == target is a harmless no-op"
rule the way the plain `/status` progression endpoint does. A second assignment call can name a
*different* `delivery_partner_user_id` than the first - treating ASSIGNED→ASSIGNED as an idempotent
no-op would silently let it overwrite the original assignment. Assignment instead requires the
fulfillment to be in READY_FOR_DELIVERY, unconditionally, checked explicitly before touching
anything else - a real bug caught by `test_16_cannot_reassign_already_assigned_fulfillment` during
this phase's own test run (the first implementation let a second assignment silently win).

**Delivery-partner ownership** (§29 of the phase spec) is a data check, not a role check, so it
lives in the service, not in `require_roles`: `FulfillmentService._assert_can_act_as_delivery_partner`
requires the acting user to BE `fulfillment.delivery_partner_user_id`, with `ADMIN` as the sole
override. `HUB_STAFF`/`OPERATIONS` are deliberately excluded from `/out-for-delivery` and `/deliver`
even though they can perform every earlier warehouse step (`/status`, `/assign`) - warehouse
staff and delivery-in-transit are treated as distinct operational roles. A `DELIVERY_PARTNER` who
is not the assigned partner gets the same "don't disclose existence" 404 on `GET /fulfillments/{id}`
that `PaymentService._get_owned_payment` already established for cross-user resource access,
consistent with 403 only where existence is already implied (mutating a fulfillment id the caller
just tried to act on).

**Lock ordering** (extends §21a's convention): `Order → Fulfillment → Reservation →
InventoryLots` for delivery confirmation - unchanged from Phase 15, since `confirm_delivery`'s
logic is otherwise the same transaction. The new `assign_delivery_partner`, `mark_out_for_delivery`,
and the plain `/status` progression touch only the single `Fulfillment` row, so they carry no
cross-row lock-ordering concern. The Phase 14 stale-identity-map gotcha (§21) did not recur in this
phase's new code - `assign_delivery_partner`/`mark_out_for_delivery` each lock their row as the
first read in the request, matching the safe pattern.

**Concurrency-tested** (real threads against real PostgreSQL row locks,
`tests/test_phase_16_fulfillment_delivery.py`): two dispatchers racing assignment of two different
partners to the same fulfillment (exactly one wins), duplicate concurrent delivery confirmation
from the same partner (idempotent, no double consumption), a legal transition racing an
always-illegal one (deterministic final state), delivery racing a concurrent reassignment attempt
on the same row (safe cross-endpoint serialization), and delivery racing an ops attempt to expire
the (already-COMMITTED, therefore un-expirable) reservation.

## 21c. Supplier Management + Bulk & Custom Commerce (Phase 17)

**Current active phase.** Introduces two independent business concepts that Phase 8.1's
"wholesaler" had conflated, and a request→quote→order pipeline for large/custom purchases that
deliberately reuses every existing Order/Payment/Reservation/Fulfillment mechanism rather than
building a parallel one. New migration `c683dfa20681_supplier_management_and_bulk_commerce`
(additive only). Full detail:
[PHASE_17_SUPPLIER_BULK_COMMERCE_API.md](../api/PHASE_17_SUPPLIER_BULK_COMMERCE_API.md).

**SUPPLIER ≠ BULK CUSTOMER ≠ CUSTOMER** (spec's own framing, preserved exactly):
- **Supplier**: a business GawachaBazaar buys FROM. New `suppliers` table - deliberately **not** a
  `User` (no login, no `user_id` anywhere on it), unlike every prior actor in this codebase. Staff
  (ADMIN/HUB_STAFF/OPERATIONS) maintain supplier records and `supplier_products` links; only ADMIN
  records `supplier_evaluations` (append-only, six 0-5 dimensions - never a single mutable "current
  score" column, mirroring `stock_movements`/`payment_transactions`). Ratings are never exposed to
  customers.
- **Bulk Customer**: a `User` with the existing `CUSTOMER` role plus an optional
  `BulkCustomerProfile` - no new role, no new auth flow, identical precedent to how the retail
  customer already works.

**The Batch/Wholesaler migration conflict, resolved additively (stage 1 of a documented multi-stage
plan)**: `batches.wholesaler_user_id` (Phase 8.1, `NOT NULL`) is referenced by 8+ test files across
Phases 2-16 and has zero live route touching it beyond the FK itself (there is, and never was, a
batch-creation API - batches are only ever created directly via the ORM in tests and, going
forward, would need one). Rather than rename or drop it, Phase 17 adds nullable
`batches.supplier_id` alongside it, relaxes `wholesaler_user_id` to nullable (safe - every existing
row already has a value, so nothing changes for any of those 8+ fixtures), and adds
`ck_batches_supplier_or_wholesaler` (at least one of the two must be set) so no batch ever loses a
traceable origin. Fully deprecating `wholesaler_user_id` remains an explicit, undone future stage.
Batch also gained `purchase_price`/`purchase_currency`/`received_date`/`receiving_reference`
(all nullable) - the smallest fix for "what did we pay, when did we receive it," extending Batch
directly rather than a parallel `supplier_purchases` table that could drift from the same physical
receiving event Batch already represents.

**Supplier purchase price ≠ customer selling price ≠ bulk quote price**: three genuinely different
numbers, stored in three different places on purpose - `batches.purchase_price` (what GawachaBazaar
paid a supplier for one physical batch), `prices` (existing Phase 3 customer-facing catalog price,
untouched), and `quote_items.unit_price` (a negotiated price for one bulk request, scoped to one
quote version). None of the three tables was reused to store another's concept.

**Core rule for bulk/custom commerce**: a `BulkOrderRequest` is never an `Order`. The pipeline is
```
REQUESTED → UNDER_REVIEW → QUOTED → CUSTOMER_ACCEPTED → CONVERTED_TO_ORDER
```
(terminal alternatives `REJECTED`/`CANCELLED`/`EXPIRED` reachable from any non-terminal state).
Nothing touches `orders`/`payments`/`inventory_reservations` before `CONVERTED_TO_ORDER` - this is
what keeps abandoned or rejected requests from polluting the order system. Quoting is allowed
directly from `REQUESTED` as a convenience (a straightforward request doesn't need a separate
"start reviewing" click); `BulkOrderService.create_quote_version` silently advances the request
through `UNDER_REVIEW` first so the state machine's strict single-step adjacency is never violated
by a `REQUESTED → QUOTED` jump.

**Quotes are never overwritten**: `Quote` (one per request) → `QuoteVersion` (one row per
revision, `version_number` strictly increasing, old versions marked `SUPERSEDED` not deleted) →
`QuoteItem` (per-version line pricing, referencing a concrete `product_variants.id` - unlike the
looser `BulkOrderRequestItem` it prices, which may be a bare catalog `product_id` or free-form
`custom_item_name` for Mode B). A customer's `POST .../accept` and admin's eventual convert both
resolve "the current version" server-side (the one `SENT`, or the one `ACCEPTED`) - the client
never names a `quote_version_id` for either action.

**Quote version lifecycle is DRAFT → SENT, not immediately-active**: `QuoteVersion.status` is one
of `DRAFT, SENT, SUPERSEDED, ACCEPTED, REJECTED, EXPIRED, CANCELLED`.
`BulkOrderService.create_quote_version` always creates a `DRAFT` - private admin work-in-progress,
invisible to the customer's operative quote and not yet superseding anything; the request's own
status does **not** move to `QUOTED` at this point. Only the explicit
`POST .../quote/{version_id}/send` (`send_quote_version`, ADMIN/OPERATIONS) transitions
`DRAFT → SENT`, supersedes whichever version was previously `SENT` (if any), and moves the request
to `QUOTED`. `send_quote_version` rejects (409) any `version_id` that is not currently `DRAFT` -
without that guard, resending an already-`SENT` version would match itself as "the previous SENT
version" and immediately supersede itself, a genuine bug caught by this phase's own concurrency
testing and fixed before merge. A separate `POST .../quote/{version_id}/reject`
(`reject_quote_version`) lets ops withdraw a live `SENT` version (`SENT → REJECTED`) without
rejecting the whole request - a new version can still be drafted and sent afterward. Quote
creation and quote sending are deliberately two separate actions/endpoints, matching the spec's
own framing: drafting is cheap and revisable, sending is the one moment a price becomes a real
offer to the customer.

**Quote expiry is lazy and server-time-authoritative**: `QuoteVersion.valid_until` (a plain date,
optional, never client-computed) is checked only at the moment of `accept_quote`, against
`date.today()` (database/application server time, never a client-supplied timestamp). If the
`SENT` version being accepted has already passed `valid_until`, `accept_quote` transitions it to
`EXPIRED` right there (under the same row lock used for acceptance) and rejects the accept with
409 - this is what makes "accept races expiry" resolve to exactly one deterministic outcome rather
than a window where an expired quote could still be accepted. No background job or scheduler marks
quotes expired proactively; per the spec's own "keep it simple, no unnecessary automation"
instruction, an unaccepted expired quote simply sits `SENT` until someone next tries to accept it.

**Inventory availability for quoting is read-only and never reserves**: `GET
/bulk-orders/admin/variants/{variant_id}/availability` (`get_variant_availability`) reports
`total_quantity`/`reserved_quantity`/`available_quantity` (the same `quantity - reserved_quantity`
computation `InventoryReservationService` uses internally) summed across a variant's `ACTIVE` lots,
purely so ops can price a quote without promising stock that doesn't exist. It never mutates
`inventory_lots` and never creates an `InventoryReservation` - the real reservation, with its own
row-locked re-check, only happens at `convert_to_order`, regardless of what this endpoint reported
moments earlier.

**Quote→Order conversion idempotency has a database-level backstop, not just a Python check**:
`bulk_order_requests.order_id` (nullable FK → `orders.id`) is set at the end of `convert_to_order`
immediately before the status transition to `CONVERTED_TO_ORDER`, and
`uq_bulk_order_requests_order_id` (`UNIQUE(order_id)`) guarantees no two request rows can ever
point at the same order. This is defense-in-depth, never relied on alone - the primary protection
is `_lock_request`'s row lock plus the `CUSTOMER_ACCEPTED`-only status check, which already
serializes concurrent conversion attempts on the *same* request to exactly one winner (the loser
re-reads `CONVERTED_TO_ORDER` post-lock and gets a clean 409). `order_id` doubles as the
retail/bulk traceability signal (join `bulk_order_requests` on `orders.id`) - a separate
`order_source` column was deliberately **not** added, since it would duplicate the same
information this column already provides.

**Conversion reuses the existing machinery verbatim** - the single most important design decision
in this phase: `BulkOrderService.convert_to_order` builds `Order`/`OrderItem`/`OrderAddress` with
the exact same snapshot fields `OrderService.checkout` already uses (including its
`_generate_order_number` helper, called directly rather than duplicated), then calls the
**unmodified** `InventoryReservationService.create_reservation_for_order`. A converted bulk order
gets the same FIFO allocation, oversell protection, and 30-minute unpaid-window expiry as a retail
order for free, and pays/fulfills/delivers through the exact same Phase 14/15/16 endpoints
afterward - nothing bulk-specific was added to any of those flows. If reservation fails
(insufficient stock), the whole conversion rolls back and the request stays `CUSTOMER_ACCEPTED` for
a retry, identical to checkout's own insufficient-stock handling.

**Why accept and convert are two separate steps** (not one, even though nothing technically
prevents folding them together): the state machine's own explicit `CUSTOMER_ACCEPTED` →
`CONVERTED_TO_ORDER` split gives ops a deliberate checkpoint - re-verify stock/delivery feasibility
- before the order (and its 30-minute reservation clock) actually starts. `POST .../accept` is
CUSTOMER-only; `POST .../convert` is ADMIN/OPERATIONS-only.

**HUB_STAFF is deliberately excluded from bulk/custom review, quoting, and conversion** (unlike
suppliers.py, where it has full access) - pricing and order-conversion decisions are commercial,
not warehouse-floor operations, mirroring how Phase 16 excluded `HUB_STAFF`/`OPERATIONS` from
delivery-in-transit actions for the same reason (distinct operational roles, not a hierarchy).

**Lock ordering**: `BulkOrderRequest → Quote → QuoteVersion(s)` is this domain's own chain,
locked unconditionally on id (the same retry-safe pattern used throughout this codebase) so a
concurrent accept-vs-requote race resolves to one winner instead of a lost update. It only
intersects the existing `Cart → Order → Payment → Fulfillment → Reservation → InventoryLots` chain
at the single moment of conversion, creating a brand-new `Order` (nothing else could be
concurrently holding a lock on a row that doesn't exist yet) before delegating to
`InventoryReservationService`'s own established lock order unchanged.

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
  `promotions`, `coupons`, `reviews`, `notifications`, `audit_logs`) — none of these exist in the
  schema today and none should be created spontaneously. `fulfillments` is the one exception: it
  **was** built in Phase 15, but intentionally minimal (order-level status only) — do not expand it
  into per-item picking, delivery partner assignment, routing, live tracking, or
  proof-of-delivery without an explicit separate request; those remain out of scope.
- `fulfillment_items` (a second lot-allocation table mirroring `inventory_reservation_items`) — not
  built in Phase 15; `inventory_reservation_items` already records the order_item→lot→quantity
  allocation delivery confirmation needs, and a second copy would only risk drifting out of sync
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
