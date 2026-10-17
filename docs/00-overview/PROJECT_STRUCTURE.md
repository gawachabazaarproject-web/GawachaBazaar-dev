# Project Structure

> **Status:** Verified from the working tree on 2026-10-14. Generated/vendored directories (`node_modules/`, `.next/`, `venv/`, `__pycache__/`, `mobile/android/`, `.expo/`) are omitted; they are git-ignored (see [`.gitignore`](../../.gitignore)).

```text
GawachaBazaar/
├── backend/                     FastAPI service (the only place business logic lives)
│   ├── app/
│   │   ├── main.py              app factory, middleware, CORS, health, reservation-sweep loop
│   │   ├── api/v1/              22 router modules + router.py (mounting order matters)
│   │   ├── core/                config, firebase, permissions, roles, rate_limit, realtime,
│   │   │                        request_id, security_headers, logging, security (Argon2/normalisers)
│   │   ├── db/                  base.py (declarative Base), session.py (engine, pool 5+10)
│   │   ├── dependencies/        auth.py (get_current_user, require_roles, require_permission), database.py
│   │   ├── exceptions/          base.py (AppException family), handlers.py (uniform JSON errors)
│   │   ├── models/              50 SQLAlchemy models (one file per table)
│   │   ├── schemas/             Pydantic request/response models
│   │   └── services/            business logic; *_state.py = pure state machines
│   ├── alembic/ + alembic.ini   migrations (38 files, single head f1a2b3c4d5e6)
│   ├── scripts/                 create_admin.py, activate_user.py, check_admin.py, seed_*.py (operator CLIs)
│   ├── tests/                   pytest suite; _db_safety.py, conftest.py, firebase_fake.py,
│   │                            authz_golden.json, multiproc/ (replica + load harness)
│   ├── docs/                    older per-phase docs (api/, architecture/, database/ V1–V7)
│   ├── Dockerfile, start.sh     image + entrypoint (alembic upgrade head, then 1 uvicorn worker)
│   ├── requirements*.txt, pyproject.toml
│   └── .env.example             (a local .env is git-ignored)
├── mobile/                      Expo customer app
│   ├── app/                     Expo Router routes: (auth)/, (onboarding)/, (tabs)/, account/,
│   │                            address/, bazaar/, bulk/, cart/, category/, checkout/, order/[id]/,
│   │                            product/[id], wishlist
│   ├── src/                     api/ (axios client + one file per backend area), auth/ (Firebase),
│   │                            features/ (TanStack Query hooks per domain), store/ (Zustand),
│   │                            components/, navigation/AppGate.tsx, theme/, utils/, types/
│   ├── assets/                  images (incl. assets/login/ for the login artwork)
│   ├── plugins/withAndroidRelease.js   prebuild customisations (signing, UPI <queries>, gradle)
│   ├── app.json, app.config.js, eas.json
│   └── google-services.json     (git-ignored; supplied via EAS file secret)
├── Admin/                       Next.js admin panel (port 3001)
│   ├── app/login, app/(admin)/  pages: dashboard, orders, products, categories, inventory,
│   │                            promotions, customers, delivery, payments, content (home slides),
│   │                            ads, settings, staff, audit-log, reports*, reviews*   (*placeholders)
│   ├── components/, lib/        shared UI; lib/<module>.ts API clients; auth-context, realtime-context,
│   │                            permissions.ts (UI-only mirror of backend permissions)
│   └── Dockerfile               Node 22 standalone build; NEXT_PUBLIC_API_BASE_URL is a build arg
├── website/                     Next.js promo site (port 3000); no API calls
├── deploy/                      Caddyfile, README (VPS runbook), FIREBASE_AUTH.md, scripts/
│                                (bootstrap-server, deploy, smoke-test, backup-db, restore-db)
├── k8s/                         Kubernetes manifests: top-level *.yaml, base/, overlays/{aws,azure,gcp}
├── docker-compose.yml           local stack (db on host port 5433, backend, website, admin)
├── docker-compose.prod.yml      production stack (adds caddy, migrate job, db-backup)
├── .forgejo/workflows/deploy.yml   CI/CD: build images, push to Docker Hub, roll out to EKS
├── .env.production.example      variables for docker-compose.prod.yml
├── docs/                        documentation (this set) + testing/ audit + manual_testing/
├── package.json                 root: only a `playwright` devDependency (no tests use it)
├── .mcp.json                    editor/agent MCP configuration (contains a secret — see SECRETS_MANAGEMENT)
├── .agents/, skills-lock.json   AI-agent skill definitions (not application code)
└── .claude/launch.json          dev-server launch configurations
```

## Where to find things

| You are looking for… | Look in |
|---|---|
| A URL / route | [`API_REFERENCE.md`](../03-api/API_REFERENCE.md), then `backend/app/api/v1/<module>.py` |
| The rule behind a behaviour | `backend/app/services/<domain>.py` and its `*_state.py` |
| A table or constraint | [`DATABASE_SCHEMA.md`](../04-database/DATABASE_SCHEMA.md), `backend/app/models/<table>.py` |
| An environment variable | [`ENVIRONMENT_VARIABLES.md`](../06-development/ENVIRONMENT_VARIABLES.md), `backend/app/core/config.py` |
| What a role can do | [`USER_ROLES_AND_PERMISSIONS.md`](../01-requirements/USER_ROLES_AND_PERMISSIONS.md), `backend/app/core/permissions.py` |
| A mobile screen | `mobile/app/<route>.tsx`; its data hook in `mobile/src/features/` |
| An Admin page | `Admin/app/(admin)/<page>/page.tsx`; API client `Admin/lib/<module>.ts` |
| Deployment definition | [`DEPLOYMENT.md`](../09-deployment-operations/DEPLOYMENT.md) |

## Notes on layout

- `k8s/` contains **two** descriptions of the backend deployment (top-level `backend-deployment.yaml` and `base/backend-deployment.yaml`) that differ (replicas, `APP_ENV`, image, allowed origins). See [DEPLOYMENT.md](../09-deployment-operations/DEPLOYMENT.md).
- `backend/docs/` is historical, phase-by-phase documentation. Treat the models, migrations and code as authoritative where it disagrees ([README](../README.md#authoritative-sources)).
- `backend/pyproject.toml` lists only a subset of the dependencies in `backend/requirements.txt` ([DEPENDENCY_MANAGEMENT](../06-development/DEPENDENCY_MANAGEMENT.md)).
