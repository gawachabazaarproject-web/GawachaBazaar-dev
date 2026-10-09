# Gawacha Bazaar

Gawacha Bazaar is a farm-to-home fresh food marketplace for Nagpur: customers order
vegetables, fruit and groceries on a mobile app; staff run the business from an Admin panel;
one FastAPI backend owns every rule, price and state change.

| Part | What it is | Tech | Folder |
|---|---|---|---|
| **Backend API** | The only place business logic lives. REST + one WebSocket. | Python 3.11, FastAPI, SQLAlchemy 2, PostgreSQL 16, Alembic | [`backend/`](backend) |
| **Customer app** | Browse, wishlist, cart, checkout, orders, bulk requests. | React Native 0.86, Expo 57 + Expo Router, TanStack Query, Zustand | [`mobile/`](mobile) |
| **Admin panel** | Orders, products, inventory, delivery, payments, promotions, ads, staff, settings. | Next.js (App Router), Tailwind | [`Admin/`](Admin) |
| **Promo website** | Public marketing site. | Next.js | [`website/`](website) |
| **Deployment** | Docker Compose + Caddy on one VPS; Kubernetes manifests; CI workflow. | Docker, Caddy, k8s | [`deploy/`](deploy), [`k8s/`](k8s), `docker-compose*.yml` |

## Documentation map

| Read this | For |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the whole system fits together: components, auth, data flow, state machines, realtime, pricing, deployment, scaling limits. |
| [docs/FEATURES.md](docs/FEATURES.md) | Everything the product does, by audience (customer, staff/admin, system), with the rules behind each feature. |
| [backend/README.md](backend/README.md) | Backend developer guide: layout, setup, tests, migrations, configuration reference. |
| [backend/docs/](backend/docs) | Deep dives written phase by phase: database schemas V1-V7, per-domain API notes, RBAC, auth. |
| [mobile/README.md](mobile/README.md) | Customer app guide: structure, running, API layer, design system. |
| [Admin/README.md](Admin/README.md) | Admin panel guide: structure, permissions, running. |
| [deploy/README.md](deploy/README.md) | Production runbook (Contabo VPS): first deploy, updates, backups, go-live checklist. |
| [deploy/FIREBASE_AUTH.md](deploy/FIREBASE_AUTH.md) | Firebase Authentication setup. |
| [docs/manual_testing/](docs/manual_testing/USER_MANUAL_TEST_SCENARIOS.md) | Manual test scenarios. |

## System at a glance

```
 Customer app (Expo)        Admin panel (Next.js)        Promo site (Next.js)
        │  Firebase ID token       │  Firebase ID token            │
        └──────────────┬───────────┘                               │ static
                       ▼
              FastAPI backend  ── /api/v1/*  (REST)
                       │        ── /api/v1/ws/events  (live order events, staff)
                       │
   ┌───────────────────┼─────────────────────────────┐
   ▼                   ▼                             ▼
PostgreSQL 16     Firebase Admin SDK         Third parties
(all state)       (verify tokens, staff      Razorpay (payments) · Cloudinary (images)
                   accounts, resets)         Google Distance Matrix / OSRM (road distance)
```

Key ideas:

- **Modular monolith.** One deployable backend, organised by domain (catalog, inventory,
  cart/orders, payments, fulfillment, promotions, ...), each as route -> service -> model.
- **The backend is the authority.** Clients never compute totals, fees, discounts or status
  transitions; they render what the API returns. Every state machine (order, payment,
  fulfillment, refund, reservation, quote, promotion) is enforced server-side.
- **Firebase owns identity, the backend owns authorisation.** Firebase handles passwords,
  Google sign-in and phone OTP. The backend verifies the Firebase ID token and maps it to a
  `users` row; roles and permissions are read live from the database on every request.
- **Everything is auditable.** Admin actions write to an audit log; order/payment/refund
  changes keep history rows.

## Repository structure

```text
GawachaBazaar/
├── backend/                 FastAPI service
│   ├── app/
│   │   ├── api/v1/          Routers: auth, addresses, wishlist, catalog, inventory, packaging,
│   │   │                    cart, orders, payments, fulfillments, suppliers, bulk_orders,
│   │   │                    promotions, customers, staff, dashboard, ads, home_slides, bazaar, realtime
│   │   ├── core/            config, Firebase, permissions/roles, rate limiting, realtime hub, security headers
│   │   ├── db/              declarative base + session
│   │   ├── dependencies/    auth + DB FastAPI dependencies
│   │   ├── exceptions/      uniform error types and handlers
│   │   ├── models/          ~50 SQLAlchemy models
│   │   ├── schemas/         Pydantic request/response models
│   │   ├── services/        business logic + state machines
│   │   └── main.py          application factory
│   ├── alembic/versions/    35+ migrations
│   ├── tests/               pytest suite
│   └── docs/                phase documentation (api / architecture / database)
├── mobile/                  Expo customer app (app/ routes, src/ api · features · components · theme)
├── Admin/                   Next.js admin panel (app/(admin)/* pages, components, lib)
├── website/                 Next.js marketing site
├── deploy/                  Production runbook, Caddyfile, server scripts
├── k8s/                     Kubernetes manifests (backend, website, ingress, HPA)
├── docs/                    This documentation set + manual test scenarios
├── docker-compose.yml       Local stack (Postgres, backend, website)
├── docker-compose.prod.yml  Production stack (adds Caddy, admin, migrate, db-backup)
└── .forgejo/workflows/      CI/CD deploy workflow
```

## Quick start (local)

### Backend

```bash
cd backend
python -m venv venv && .\venv\Scripts\Activate.ps1      # Windows (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                                     # set DATABASE_URL, FIREBASE_PROJECT_ID, ...
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI at http://127.0.0.1:8000/docs, health at `/health` and `/health/db`.
Create the first admin with `python scripts/create_admin.py` (see the deploy runbook).

Or run Postgres + backend in Docker: `docker compose up --build -d` (Postgres is published on
host port **5433** to avoid clashing with a local install).

### Admin panel

```bash
cd Admin && npm install && npm run dev      # http://localhost:3001
```

Set `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000/api/v1`) and the Firebase web
config in `.env.local`.

### Customer app

```bash
cd mobile && npm install && npx expo start -c     # or: npm run android
```

The app derives the backend URL from the Metro host automatically in development;
`EXPO_PUBLIC_API_BASE_URL` overrides it for standalone builds. Native Firebase needs the
dev client (`expo run:android`), not Expo Go.

### Tests and checks

```bash
cd backend && python -m ruff check . && python -m pytest -v
cd mobile  && npx tsc --noEmit
cd Admin   && npx tsc --noEmit
```

DB-backed backend tests need a reachable test database (`DATABASE_URL`).

## Configuration highlights

All backend settings are environment variables ([backend/.env.example](backend/.env.example),
[.env.production.example](.env.production.example)); the full table is in
[backend/README.md](backend/README.md#configuration-reference).

| Area | Variables |
|---|---|
| Database | `DATABASE_URL` |
| Auth | `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON` |
| Payments | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` |
| Images | `CLOUDINARY_*` |
| Delivery pricing | `FREE_DELIVERY_MIN_ITEMS`, `DELIVERY_BASE_FEE`, `DELIVERY_PER_KM`, `DELIVERY_MAX_CHARGED_KM`, `GOOGLE_MAPS_API_KEY`, `OSRM_BASE_URL`, `DELIVERY_ROAD_FACTOR`, `PACKING_POINT_*` (fallback) |
| Bazaar+ | `BAZAAR_PLUS_ORDERS_REQUIRED`, `BAZAAR_TIMEZONE` |

## Production

Production runs as one Docker Compose stack behind Caddy (automatic HTTPS) on a single VPS:
website, admin, backend, Postgres, a migration job (must succeed before the backend starts) and
a nightly `pg_dump` backup. See [deploy/README.md](deploy/README.md). Kubernetes manifests in
[`k8s/`](k8s) and a CI workflow in [`.forgejo/workflows/deploy.yml`](.forgejo/workflows/deploy.yml)
are also provided.

> The backend deliberately runs **one worker process**: the rate limiter, the WebSocket registry
> and the reservation sweep are in-process. Running several replicas needs a shared store
> (e.g. Redis) first - see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#scaling-limits).
