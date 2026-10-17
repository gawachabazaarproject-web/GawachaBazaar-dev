# AI Project Context

> **Status:** Verified against source on 2026-10-14 (branch `docs-and-primary-testing`, base commit `8d6229e`, working tree with uncommitted changes — see [AI_STATUS.md](AI_STATUS.md)).
> **Purpose:** the first document an AI coding agent (or new developer) should read. It is a map, not a spec: it says what exists, where to look, and which rules must not be broken. Follow the links for detail.

## 1. What the project is

**Gawacha Bazaar** is a farm-to-home fresh-food marketplace for Nagpur (India). Customers browse and order vegetables, fruit and groceries in a **mobile app**; staff run the business from an **Admin web panel**; a single **FastAPI backend** owns every price, fee, discount, stock movement and state change. A small **promo website** is a separate static-style Next.js app. Source of the one-line description: [`README.md`](../../README.md).

## 2. Applications and technology (versions verified from manifests / installed packages)

| Part | Folder | Stack (verified) | Runs as |
|---|---|---|---|
| Backend API | [`backend/`](../../backend) | Python 3.11 (venv 3.11.6; `python:3.11-slim` image), FastAPI 0.141.1, Starlette 1.7.0, SQLAlchemy 2.1.1 (sync), Pydantic 2.13.5 + pydantic-settings 2.15.0, psycopg 3.3.6, Alembic 1.20.0, slowapi 0.1.10, firebase-admin, cloudinary, httpx 0.28.1, argon2-cffi | one `uvicorn` worker ([`backend/start.sh`](../../backend/start.sh)) |
| Database | – | PostgreSQL 16 (`postgres:16-alpine` in compose; test container 16.x) | `db` service / managed DB |
| Customer app | [`mobile/`](../../mobile) | Expo ~57.0.22, React Native 0.86.3, React 19.2.3, Expo Router ~57, TanStack Query 5, Zustand 5, axios, `@react-native-firebase/*` 26 + Google Sign-In 16, `expo-updates` ~57.0.25, TypeScript ~6.0.3 | Android build via EAS; OTA updates on channels `preview`/`production` |
| Admin panel | [`Admin/`](../../Admin) | Next.js 16.3.5, React 19.1.1, Tailwind 3.4.10, TypeScript 5.5.4, Firebase web SDK 12 | Node 22 standalone image, port 3001 |
| Promo website | [`website/`](../../website) | Next.js 16.3.5, React 19.1.1, Tailwind 3.4.10 | Node 22 standalone image, port 3000 |
| Edge / deploy | [`deploy/`](../../deploy), [`k8s/`](../../k8s), `docker-compose*.yml`, [`.forgejo/workflows/deploy.yml`](../../.forgejo/workflows/deploy.yml) | Caddy 2, Docker Compose, Kubernetes manifests, Forgejo Actions | see [DEPLOYMENT.md](../09-deployment-operations/DEPLOYMENT.md) |

External services: Firebase Authentication, Razorpay, Cloudinary, Google Distance Matrix / OSRM, Expo push service. Details: [THIRD_PARTY_SERVICES.md](../11-integrations/THIRD_PARTY_SERVICES.md).

## 3. Architecture in one paragraph

A **modular monolith**. Each backend request flows `router (app/api/v1) → auth dependency → service (app/services) → SQLAlchemy models (app/models)`; routers are thin, services own the rules, and state machines live in `*_state.py` files. The three clients never compute totals, fees or status transitions — they render what the API returns. **Firebase owns identity** (passwords, Google, phone OTP); the backend verifies the Firebase ID token on every request, maps it to a `users` row by `firebase_uid`, and reads **roles live from the database** on every request. Fine-grained admin **permissions are static code** ([`permissions.py`](../../backend/app/core/permissions.py)), not data. Full picture: [SYSTEM_ARCHITECTURE.md](../02-architecture/SYSTEM_ARCHITECTURE.md), [DATA_FLOW.md](../02-architecture/DATA_FLOW.md). The older, broader overview is [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) (corrected in places, see [AI_STATUS.md](AI_STATUS.md)).

## 4. Repository map and entry points

| Path | Contents / entry point |
|---|---|
| `backend/app/main.py` | App factory, middleware order, CORS, `/health`, `/health/db`, reservation-expiry sweep loop (lifespan) |
| `backend/app/api/v1/router.py` | Mounts every router; **registration order matters** (literal paths before `/{id}` catch-alls) |
| `backend/app/api/v1/*.py` | 22 router modules → [API_REFERENCE.md](../03-api/API_REFERENCE.md) |
| `backend/app/services/` | Business logic. `order.py` (checkout/cancel), `checkout_session.py` (pay-first online checkout), `payment.py` (payments + webhooks), `refund.py`, `inventory_reservation.py`, `fulfillment.py`, `delivery.py`, `promotion.py`, `*_state.py` (state machines) |
| `backend/app/models/` | 50 SQLAlchemy models → [DATABASE_SCHEMA.md](../04-database/DATABASE_SCHEMA.md) |
| `backend/app/core/` | `config.py` (all env settings), `firebase.py` (Admin SDK boundary), `permissions.py`, `roles.py`, `rate_limit.py`, `realtime.py`, `security_headers.py`, `request_id.py`, `logging.py` |
| `backend/alembic/versions/` | 38 migration files, single head `f1a2b3c4d5e6` → [MIGRATIONS.md](../04-database/MIGRATIONS.md) |
| `backend/tests/` | pytest suite (real PostgreSQL) → [TESTING_GUIDE.md](../07-testing/TESTING_GUIDE.md) |
| `mobile/app/` | Expo Router routes; `mobile/src/` = `api/`, `auth/`, `features/`, `store/`, `components/`, `theme/` |
| `Admin/app/(admin)/` | Admin pages; `Admin/lib/<module>.ts` typed API clients; `Admin/lib/permissions.ts` (UI-only mirror of backend permissions) |
| `docs/` | This documentation; `docs/testing/` = the QA audit (evidence, defect log, risk register) |

Full tree: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

## 5. Core entities and workflows

Entities: `users` (+ `roles`, `user_roles`), `addresses`, catalog (`categories` → `products` → `product_variants` → `prices`), inventory (`inventory_locations`, `batches`, `inventory_lots`, `stock_movements`), reservations, `carts`, `orders` (+ items/address snapshots), `payments` (+ transactions, webhook events), `refunds`, `fulfillments`, `promotions`, bulk requests/quotes, `admin_action_logs`.

Workflows: **COD checkout** (cart → order + stock reservation → COD payment confirms order → fulfillment → delivery consumes stock and marks COD paid); **online checkout, pay-first** (price cart → Razorpay order → customer pays → server verifies with Razorpay → order created and confirmed; automatic refund if the order cannot be placed); **cancellation** (release reservation, reverse promotion, create refund request for paid online orders → admin approve/process); **bulk quote** (request → quote versions → accept → convert). See [DATA_FLOW.md](../02-architecture/DATA_FLOW.md) and [`../05-domains/`](../05-domains).

## 6. Invariants an agent must not break

Each is enforced in code and/or by the database; evidence in the linked documents.

1. **The backend is the only authority** for prices, delivery fees, discounts, totals and status transitions. Never trust a client-supplied amount or status.
2. **State machines are explicit**; illegal transitions raise (HTTP 409). Terminal states: order `COMPLETED/EXPIRED/CANCELLED`, payment `PAID`, refund `REFUNDED/REJECTED`, reservation `RELEASED/EXPIRED`.
3. **One-per-order guarantees in the schema:** one `payments` row, one `refunds` row, one `fulfillments` row, one `inventory_reservations` row per order; one order per cart (`uq_orders_cart_id`); one ACTIVE cart per user and one packing point (partial unique indexes).
4. **Lock ordering:** Order before Payment ([`payment.py`](../../backend/app/services/payment.py) docstring), Order before Fulfillment, inventory lots by ascending id. Never hold a row lock across a network call to a gateway.
5. **Webhook idempotency:** `payment_webhook_events` is unique on `(gateway_name, event_id)`; payment transactions are unique on `idempotency_key`.
6. **Money is `Decimal`/`NUMERIC(12,2)`**; order lines snapshot name/SKU/unit/price at checkout so history never changes.
7. **Stock:** `reserved_quantity <= quantity` (CHECK). Reservation lasts 30 minutes; physical stock is consumed only at delivery.
8. **Authorization is re-checked server-side** on every request; roles are read from the database each time; the Admin UI permission mirror grants nothing.
9. **Single backend process.** Rate limiter, WebSocket registry and reservation sweep are in-process; do not run more than one worker/replica without moving them to a shared store ([MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md)).
10. **Tests may only destroy a disposable local database** (`TEST_DATABASE_URL` policy, [`_db_safety.py`](../../backend/tests/_db_safety.py)). Never point the suite at a real database.

## 7. Commands

Backend (from `backend/`, Windows venv shown; Linux/macOS: `venv/bin/python`):

| Task | Command |
|---|---|
| Install | `pip install -r requirements.txt -r requirements-dev.txt` |
| Migrate | `alembic upgrade head` |
| Run | `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| Lint | `python -m ruff check .` |
| Tests (needs a disposable DB) | `TEST_DATABASE_URL=<local *_test db> python -m pytest -p no:cacheprovider` — see [TESTING_GUIDE.md](../07-testing/TESTING_GUIDE.md) |
| Model/migration drift | `alembic check` (against a migrated disposable DB) |

Clients: `cd mobile && npm install && npx expo start -c` · `cd Admin && npm install && npm run dev` (port 3001) · `npx tsc --noEmit` in `mobile/` and `Admin/`. No automated tests exist for any frontend ([QUALITY_GATES.md](../07-testing/QUALITY_GATES.md)). Full setup: [LOCAL_SETUP.md](../06-development/LOCAL_SETUP.md).

## 8. Read these files before changing…

| If you change… | Read first |
|---|---|
| Anything involving money, checkout or payment | `services/order.py`, `services/checkout_session.py`, `services/payment.py`, `services/refund.py`, `services/payment_state.py`, then [PAYMENTS.md](../05-domains/PAYMENTS.md), [REFUNDS.md](../05-domains/REFUNDS.md), [DEFECT_LOG](../testing/DEFECT_LOG.md) (PAY-001) |
| Stock or reservations | `services/inventory_reservation.py`, `services/stock_pool.py`, `services/fulfillment.py`, [INVENTORY.md](../05-domains/INVENTORY.md) |
| Auth, roles, permissions | `core/firebase.py`, `services/auth.py`, `dependencies/auth.py`, `core/permissions.py`, `tests/authz_golden.json`, [AUTHENTICATION.md](../05-domains/AUTHENTICATION.md) |
| A route | `api/v1/router.py` ordering note, [API_CONVENTIONS.md](../03-api/API_CONVENTIONS.md); update `tests/authz_golden.json` (the authorization snapshot test fails otherwise) |
| The schema | the model, a new Alembic revision, [MIGRATIONS.md](../04-database/MIGRATIONS.md); keep `alembic check` clean |
| Deployment | [DEPLOYMENT.md](../09-deployment-operations/DEPLOYMENT.md) — three deployment descriptions exist in the repo and they disagree |
| Delivery fee / Bazaar | `services/delivery.py`, `services/bazaar.py`, [DELIVERY.md](../05-domains/DELIVERY.md) |

## 9. Known architectural limitations (details: [KNOWN_ISSUES.md](../10-project-management/KNOWN_ISSUES.md))

- Single-process assumptions: rate limit, WebSocket events and the reservation sweep do not work across replicas (confirmed by experiment, see [MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md)).
- PAY-001: a captured online payment can be attached to an unrelated, already-existing order without a refund (confirmed, **not fixed**; guarded by a strict `xfail` test).
- CI deploys to production on every push to `main` with no test, lint or migration gate.
- No automated tests for `mobile/`, `Admin/`, `website/`.
- Which deployment is authoritative (Contabo VPS compose, AWS EKS, or the Render service that answers `/health`) is **unresolved** from the repository alone.
- Authentication is Firebase-only; the legacy password migration path still exists in code.

## 10. Link index

[docs/README.md](../README.md) · [AI_STATUS](AI_STATUS.md) · [PROJECT_OVERVIEW](PROJECT_OVERVIEW.md) · [GLOSSARY](GLOSSARY.md) · [ARCHITECTURE_DECISIONS](../02-architecture/ARCHITECTURE_DECISIONS.md) · [ERROR_HANDLING](../02-architecture/ERROR_HANDLING.md) · [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md) · [SECURITY](../08-security/SECURITY.md) · [PRODUCTION_READINESS](../10-project-management/PRODUCTION_READINESS.md)
