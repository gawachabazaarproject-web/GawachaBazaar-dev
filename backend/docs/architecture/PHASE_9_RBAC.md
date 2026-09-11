# Phase 9 — Role Initialization & RBAC

## 1. Problem

`roles` was empty on any freshly-migrated database. Public registration
(`AuthService.register_user`) requires a `CUSTOMER` `Role` row to exist and
raises a 500 if it doesn't. No migration, startup routine, bootstrap script,
or documented process seeded it — this was a genuine initialization gap, not
a design choice.

Separately, `require_roles` (`app/dependencies/auth.py`) existed only as a
stub that unconditionally raised `AuthorizationError` for every caller. No
route depended on it.

## 2. Role Initialization

**Mechanism chosen: a reference-data-only Alembic migration**
(`37bbdf459894_seed_baseline_roles.py`), not a new schema change and not a
separate bootstrap script.

**Why this mechanism:**
- Alembic is already the sole, mandatory mechanism for bringing any
  environment's database to a runnable state — no code path creates tables
  via `Base.metadata.create_all()`, so `alembic upgrade head` must already
  run before the app can function at all. Piggybacking baseline reference
  data onto that same, already-required step means seeding cannot be
  forgotten as a separate manual/deploy step, and there is exactly one
  mechanism, not two competing ones.
- It is a **data** migration, not a schema migration — `roles` already has
  the correct shape from Phase 1. No `roles.id`, `roles.name`, or table
  structure changed.
- It follows the safety-guard precedent established in the Phase 8.1
  migration (`d051168c1d3d`): the `downgrade()` refuses to remove a role
  that is still referenced by `user_roles`, raising a clear `RuntimeError`
  rather than relying solely on the FK's `ON DELETE RESTRICT` to fail
  opaquely.

**Idempotency**: `upgrade()` uses `INSERT ... ON CONFLICT (name) DO NOTHING`
keyed on `roles.name` — safe to re-run against a database where some or all
baseline roles already exist, with no duplicate-key error and no duplicate
rows. Role `id` values are never hardcoded or depended upon; `roles.name` is
the stable identifier, consistent with the rest of the codebase (e.g.
`AuthService` already looked up roles by name, not id).

**Roles seeded** (six, all currently-active actors):

| Role | Description |
|---|---|
| `CUSTOMER` | Retail customer browsing catalog and placing orders. |
| `WHOLESALER` | Supply partner providing produce batches into the supply chain. |
| `ADMIN` | Platform superuser overseeing catalog, pricing, and configuration. |
| `HUB_STAFF` | Hub facility staff handling sorting, grading, and quality checks. |
| `OPERATIONS` | Operations staff handling inventory and packaging workflows. |
| `DELIVERY_PARTNER` | Logistics personnel handling last-mile delivery dispatch. |

`HUB_STAFF` and `OPERATIONS` are seeded as **two separate roles** — this
resolves the "one role or two?" question left open after the Phase 8.1
review, per the explicit six-name role list given for Phase 9.

`FARMER` is deliberately **not** seeded. Farmer/Farm remain future
capabilities and are not an active actor (see ARCHITECTURE.md §3).

**What this migration does NOT do**: it creates no `users` rows, no
`user_roles` rows, no admin account, and no default password. Seeding a role
into `roles` does not authorize anyone — a user only ever gains a role
through an explicit `user_roles` insert, which this migration never performs.

## 3. RBAC Implementation

**Location**: `app/dependencies/auth.py` — the existing `require_roles`
factory was implemented in place; no second authorization framework, no new
file, no new dependency-injection pattern.

```python
get_current_user()   # authentication: "who is this user?"
        ↓
require_roles(...)   # authorization: "does this user hold a required role?"
        ↓
endpoint
```

**Authentication vs. authorization stay separate**: `require_roles` composes
`get_current_user` as its own first dependency (via `Depends`) rather than
duplicating JWT decoding, session lookup, or user-status checks. All of that
logic still lives exclusively in `AuthService.resolve_current_user`.

**Role membership is checked against current database state on every
request** — `require_roles` runs `UserRole JOIN Role WHERE user_id = ? AND
Role.name IN (...)` against the live `db` session, not against JWT claims.
The JWT carries no role information. This means a role granted or revoked in
`user_roles` takes effect on the very next request, without waiting for the
15-minute access token to expire — exactly the property required by the
project's security principles.

**401 vs. 403**:
- No/invalid/expired credentials → `get_current_user` raises
  `AuthenticationError` → HTTP 401, `AUTHENTICATION_ERROR`. Unchanged.
- Valid, authenticated user lacking every required role →
  `require_roles`'s `role_checker` raises `AuthorizationError` → HTTP 403,
  `AUTHORIZATION_ERROR`.

Both use the pre-existing centralized exception hierarchy and the
`{code, message, details}` contract — no new error shape was introduced. The
403 message is generic ("You do not have permission to perform this
action.") and does not enumerate which role(s) were required or missing.

**Multiple-role semantics**: `require_roles(*allowed_roles)` grants access if
the user holds **any one** of the given roles (`Role.name.in_(allowed_roles)`
in the query). There is no role hierarchy or inheritance in Phase 9 —
`ADMIN` does not implicitly satisfy `require_roles(OPERATIONS)`.

**Role name constants**: `app/core/roles.py` is the single in-code
representation of the six active role name strings
(`CUSTOMER`, `WHOLESALER`, `ADMIN`, `HUB_STAFF`, `OPERATIONS`,
`DELIVERY_PARTNER`) plus a `BASELINE_ROLES` tuple. `AuthService` was updated
to import `CUSTOMER` from here instead of the raw string literal it
previously hardcoded. This is intentionally a flat module of constants —
not a class hierarchy, not a database-backed permission registry.

## 4. Public Registration — Unchanged Semantics, Verified

Registration continues to unconditionally assign `CUSTOMER`
(`AuthService.register_user` looks up the `CUSTOMER` role by name and never
reads a role from the request body). `RegisterRequest` has no `role` field,
and `BaseSchema` does not set `extra="forbid"`, so Pydantic v2's default
behavior is to silently ignore any unexpected `role` key a client sends —
this was already structurally enforced before Phase 9 and required no code
change, only a test proving it (`test_8_public_registration_ignores_client_
supplied_role`).

## 5. What Was Deliberately Not Built

Per Phase 9 scope: no role-management API, no role-assignment endpoint, no
`permissions`/`role_permissions`/`acl_rules` tables, no role hierarchy, no
resource-level/attribute-based authorization, no `wholesalers` table, no new
authentication or JWT system, no business-domain routes (catalog, farm,
inventory, packaging, cart, order, payment, delivery). `require_roles` is
not yet wired to any route — there are no protected business endpoints to
protect yet. It is proven correct via direct dependency-level tests
(`tests/test_phase_9_rbac.py`) rather than through a new endpoint added
solely to exercise it.

## 6. Focused Validation Performed

`tests/test_phase_9_rbac.py` (8 tests, run in isolation — not part of a full
regression run per current fast-development policy):

1. All six baseline roles exist after migration (`test_engine`, unaffected
   by the per-test truncating `db_session` fixture).
2. Re-running the seed INSERT is idempotent (no duplicate rows).
3. Authenticated user with the required role → authorized.
4. Authenticated user without the required role → `AuthorizationError` (403,
   `AUTHORIZATION_ERROR`).
5. `require_roles(A, B)` succeeds when the user holds only `B`.
6. A user with multiple roles satisfies any endpoint requiring one of them,
   and is still rejected for role sets it holds none of.
7. Unauthenticated `GET /api/v1/auth/me` → 401 (existing endpoint, exercised
   through the real HTTP `TestClient`, no new route added).
8. `POST /api/v1/auth/register` with `"role": "ADMIN"` in the body still
   results in exactly one `CUSTOMER` assignment.

Also re-ran `tests/test_auth.py` (12 tests) as a focused regression check
since `app/dependencies/auth.py` and `app/services/auth.py` were touched —
all pass. Full-suite regression, migration validation, and security review
are explicitly deferred to pre-deployment per current project policy.
