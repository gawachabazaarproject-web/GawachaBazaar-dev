# Architecture Decisions

> **Status:** Verified (decisions are those visible in code, schema and configuration). **Last verified:** 2026-10-14.
> **No decision log exists in the repository.** Each entry below records the decision **as implemented** and the rationale **as stated in code comments or docstrings** (cited). Where the rationale is my inference it is marked *(inferred)*. Dates and authors are unknown and not given. Decisions still open are in §3.

## 1. Decisions in force

| # | Decision | Rationale (source) | Consequences / trade-offs |
|---|---|---|---|
| D1 | **Modular monolith** — one FastAPI deployable organised by domain (router → service → model) | Simplicity; comments throughout `services/` describe single-process assumptions *(inferred for the choice itself)* | Fast to change; scaling past one process needs shared state (D6) |
| D2 | **Synchronous SQLAlchemy 2 + psycopg 3**, threadpooled routes; only the WebSocket and webhook routes are `async` | `payments.py` docstring: webhook is `async` only to read the raw body; services use `run_in_threadpool` | Pool (5+10) vs 40-thread default pool can starve under load (PERF-001) |
| D3 | **Firebase Auth owns identity**; backend verifies ID tokens and maps `firebase_uid → users` | [`core/firebase.py`](../../backend/app/core/firebase.py), [`services/auth.py`](../../backend/app/services/auth.py) docstrings: Firebase owns credentials; backend never sees a password. Migration `c5f1a7e3d9b2` dropped `auth_sessions` and made email/phone/password optional | Auth availability depends on Firebase and on correct Render configuration (an invalid service-account setting produced a production-wide 503 on 2026-10-14) |
| D4 | **Roles in the database, permissions in code** (`ROLE_PERMISSIONS`); role checks read live | [`permissions.py`](../../backend/app/core/permissions.py) docstring: "deliberately NOT a database-backed permission system… reviewed and versioned like any other code" | Changing a role's powers is a deploy; role assignment changes apply immediately |
| D5 | **Explicit state machines** as pure modules; illegal moves raise (409) | `*_state.py` docstrings; "single source of truth" for webhook and verify paths | Late/out-of-order gateway events are ignored with a log, not applied |
| D6 | **Single backend worker**; rate limiter, WebSocket hub and reservation sweep in-process | [`Dockerfile`](../../backend/Dockerfile) comment block, [`rate_limit.py`](../../backend/app/core/rate_limit.py), [`realtime.py`](../../backend/app/core/realtime.py) | Horizontal scaling breaks limits and live events (confirmed experimentally — [MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md)); K8s HPA manifests contradict this |
| D7 | **Pay-first online checkout**: order is created only after Razorpay confirms payment; automatic refund if the order cannot be placed | [`checkout_session.py`](../../backend/app/services/checkout_session.py) module docstring (migration `checkout_sessions`) | No unpaid online orders to expire; introduces PAY-001 (attach to an existing order) |
| D8 | **Stock reservation with FIFO lot allocation**, 30-minute window, physical consumption only at delivery | [`inventory_reservation.py`](../../backend/app/services/inventory_reservation.py), [`reservation_state.py`](../../backend/app/services/reservation_state.py) docstrings | Customers' COD choice must happen within the window; a sweep every 120 s reclaims stock |
| D9 | **Shared stock pool across sizes** of a product within a unit family | [`stock_pool.py`](../../backend/app/services/stock_pool.py) docstring | Lots are entered against one size; availability for others is derived (rounded down) |
| D10 | **Delivery fee is one pure function** used by both the cart quote and checkout; road distance via Google or OSRM with straight-line×1.4 fallback; one admin-chosen packing point | [`delivery.py`](../../backend/app/services/delivery.py) docstring: "the quote shown in the app and the fee charged at checkout can never drift" | Public OSRM demo server is flagged "testing only" in config; routing failure silently falls back |
| D11 | **Uniform error envelope** `{code, message, details}` with stable codes | [`handlers.py`](../../backend/app/exceptions/handlers.py) docstring | Clients branch on `code`; unhandled errors collapse to `INTERNAL_SERVER_ERROR` |
| D12 | **Webhook + client confirmation + verify endpoint**, all converging on the same state machine; idempotency via database unique constraints (`payment_webhook_events`, `idempotency_key`, one payment/refund per order) | `payment.py` module docstring ("CLIENT IS NEVER AUTHORITY") | No automatic reconciliation job; unmatched captures are only logged |
| D13 | **Refunds are approval-gated**: cancellation only creates `PENDING_APPROVAL`; an ADMIN approves and processes | [`refund_state.py`](../../backend/app/services/refund_state.py), [`permissions.py`](../../backend/app/core/permissions.py) (`orders.refund` ADMIN-only) | Money never moves automatically except the pay-first failure refund (D7) |
| D14 | **Realtime = invalidation signal only**; REST is the source of truth | [`realtime.py`](../../backend/app/core/realtime.py) docstring | Avoids a second serialisation of every schema; clients refetch |
| D15 | **No queue/Redis/scheduler**; push on a thread; sweep on an asyncio task | `main.py` comment: "No Celery/APScheduler exists in this codebase - this is the smallest safe way" | Simple; jobs are lost on restart and not coordinated across processes |
| D16 | **Order lines snapshot** name/SKU/unit/price; order totals never recalculated; prices are time-ranged rows | `order.py` (`_plan_checkout`), `prices` table | History is stable when the catalogue changes |
| D17 | **Money as `Decimal`/`NUMERIC`**, quantized `ROUND_HALF_UP`; Razorpay amounts converted to paise | `cart.py`, `order.py`, `razorpay_gateway.to_paise` | – |
| D18 | **Auditing**: admin mutations are recorded in `admin_action_logs` via `AdminAuditService.record` (47 distinct action names, 3 of them built dynamically as `promotion.<status>`) | `admin_audit.py`, migration `50946ed1400f` | Written but only read by the product/category activity feeds; no general viewer (Admin "Audit Log" is a placeholder). Rows reference the admin by FK but the target only by `resource_type` + `resource_id` (no FK) |
| D19 | **Tests run against real PostgreSQL** with Firebase and Razorpay faked; a **golden role matrix** snapshot guards every route's authorization; a fail-closed policy limits which database tests may truncate | [`tests/conftest.py`](../../backend/tests/conftest.py), [`_db_safety.py`](../../backend/tests/_db_safety.py), [`authz_golden.json`](../../backend/tests/authz_golden.json), [SEC001_REVIEW](../testing/SEC001_REVIEW.md) | Tests need a disposable database and take ~10 minutes |
| D20 | **Mobile ships JS via EAS Update**; `runtimeVersion` follows the app version; channels `preview`/`production` | [`mobile/app.json`](../../mobile/app.json), [`mobile/eas.json`](../../mobile/eas.json) | Native changes require a new build and a new app version |
| D21 | **Admin UI permission mirror** is a hand-kept copy used only to hide navigation | [`Admin/lib/permissions.ts`](../../Admin/lib/permissions.ts) header comment | Can drift (names identical on 2026-10-14; per-role mapping unverified) |

## 2. Decisions that were reversed or superseded (visible in migrations)

| Earlier design | Evidence | Now |
|---|---|---|
| Custom JWT access/refresh tokens and `auth_sessions` | migrations `4d9160d1bcc6` (create) → `c5f1a7e3d9b2` (drop) | Firebase ID tokens |
| Login OTP, password-reset and contact-change code tables | migrations `a1024b757d60`, `c3f8a91e6b2d`, `b7e2a9f4c1d3` → `efae4c4402ba` (drop) | Firebase flows (email links, phone OTP) |
| Online orders created first, paid later (reservation expiry reclaims unpaid orders) | order/payment design in migrations 6–7, 13; `checkout_sessions` migration | Pay-first for online; COD still reserve-first |

Stale comments describing the superseded designs remain in code (e.g. `api/v1/realtime.py` mentions "type=access, live un-revoked session"; `api/v1/router.py` mentions a "PNB gateway"; `core/permissions.py` still says "no general-purpose audit log exists yet", which is only partly stale: `admin_action_logs` is written by services, but nothing reads it generally).

## 3. Open or conflicting decisions (need an owner)

| Topic | Conflict | Where |
|---|---|---|
| **Deployment target** | Contabo VPS Docker Compose (`deploy/README.md`), AWS EKS (`.forgejo/workflows/deploy.yml`, `k8s/`), and a Render service that answers `/health` with `environment: production` all exist; the repository cannot say which serves customers ([BASELINE_AUDIT](../testing/BASELINE_AUDIT.md) §1) | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| **One worker vs autoscaling** | D6 vs `k8s/base/backend-hpa.yaml` (1→3) | [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md) |
| **Where migrations run** | `start.sh` runs `alembic upgrade head` in every container *and* compose has a one-shot `migrate` service | [MIGRATIONS](../04-database/MIGRATIONS.md) |
| **Bazaar+ benefit** | Eligibility is computed and displayed; no benefit is defined | [DELIVERY](../05-domains/DELIVERY.md) |
| **`WHOLESALER` role** | Seeded, unused | [USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md) |
| **Admin contact edits vs Firebase** | `admin_update_contact` changes PostgreSQL only; the next sync can overwrite the phone from the token ([`_refresh_contact_details`](../../backend/app/services/auth.py)) | [AUTHENTICATION](../05-domains/AUTHENTICATION.md) |
