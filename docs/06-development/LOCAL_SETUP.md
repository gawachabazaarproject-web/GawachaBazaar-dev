# Local Setup

> **Status:** Partially verified. **Last verified:** 2026-10-14 on Windows 11 (Git Bash), Docker 29.8.1, Node v26.10.0, npm 11.19.1, backend virtualenv Python **3.11.6** (system `python` on PATH is 3.14.7 — **not** the supported version).
> Each step is tagged **Verified** (I ran the command or its equivalent on 2026-10-14 and observed the result), **Unverified** (taken from the repository's own docs/scripts, not run here), or **Caution**. Existing guides: [`README.md`](../../README.md), [`backend/README.md`](../../backend/README.md), [`mobile/README.md`](../../mobile/README.md), [`Admin/README.md`](../../Admin/README.md), [`deploy/FIREBASE_AUTH.md`](../../deploy/FIREBASE_AUTH.md).

## 1. Prerequisites

| Tool | Version evidence | Needed for |
|---|---|---|
| Python **3.11** | `backend/Dockerfile` (`python:3.11-slim`), `pyproject.toml` (`requires-python >=3.11`); the venv used in this audit is 3.11.6 | backend |
| PostgreSQL 16 | `postgres:16-alpine` in compose and test containers | backend, tests |
| Docker (optional but recommended) | compose files | local PostgreSQL, full stack, disposable test DB |
| Node.js | `node:22-alpine` in the Admin/website Dockerfiles (v26 also type-checked here) | Admin, website, mobile |
| Expo / EAS CLI | `npx expo`, `npx eas-cli` (account `yash145`, project `a751e06b-…` in `app.json`) | mobile builds and OTA updates |
| Android SDK + device/emulator | `mobile/android/` is generated; dev client needs a native build | mobile native (Firebase + Google Sign-In are native — **Expo Go cannot run the app**) |
| A Firebase project | Authentication enabled; see `deploy/FIREBASE_AUTH.md` | sign-in in every client |

## 2. Backend

```bash
cd backend
python -m venv venv                       # use a Python 3.11 interpreter
.\venv\Scripts\Activate.ps1               # Linux/macOS: source venv/bin/activate   (Git Bash: source venv/Scripts/activate)
pip install -r requirements.txt -r requirements-dev.txt     # Unverified here (the existing venv was reused)
cp .env.example .env                      # then edit; .env is git-ignored
```

Minimum `.env` for a local run: `DATABASE_URL` and (for any sign-in) `FIREBASE_PROJECT_ID`. Everything else has a default ([ENVIRONMENT_VARIABLES](ENVIRONMENT_VARIABLES.md)). **Do not put a remote/shared database URL in `.env`** unless you intend the backend to use it — the application, scripts and Alembic all read it (a developer `.env` pointing at a hosted database is a recorded risk, R-14).

### Local PostgreSQL (Docker)

```bash
docker compose up -d db                   # Unverified here; db published on host port 5433 (user/pass postgres/postgres by default)
# then: DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/gawachabazaar
```

### Migrate and run — **Verified** (fresh throw-away database, 2026-10-14)

```bash
alembic upgrade head          # fresh DB → head f1a2b3c4d5e6 in ≈ 4 s; 51 tables; 7 roles; 4 home slides; no users
alembic check                 # "No new upgrade operations detected."
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

With only `DATABASE_URL` and `FIREBASE_PROJECT_ID` set, the app started in about 3 s and answered `GET /health` → 200, `/health/db` → 200, `/api/v1/ping` → `{"ping":"pong"}`, `/api/v1/catalog/products` → empty list, `/api/v1/home-slides` → seeded slides, `/api/v1/cart` → 401 (`AUTHENTICATION_ERROR`), `/docs` → 200 (docs are served because `APP_ENV` is not `production`).

Notes: the migration seeds roles and home slides but **no users**; the four starter promotions are inserted only if an ADMIN already exists ([MIGRATIONS](../04-database/MIGRATIONS.md)). In compose development the backend runs `uvicorn --reload` **without** migrating, so run `alembic upgrade head` yourself.

### First admin — **Unverified**

```bash
python scripts/create_admin.py --name "Owner Name" --email you@example.com --phone 9876543210   # prompts for the password
```

It creates the Firebase user and the database row (needs the service account, [AUTHENTICATION](../05-domains/AUTHENTICATION.md)). Other scripts: `activate_user.py`, `check_admin.py`; `seed_dummy_data.py` is a **dev-only** demo seed (its docstring says so) — never run it against a shared or production database. `seed_sections.py` seeds the "Ready to Cook" and "Juices" storefront sections (categories with photos and a few products, get-or-create on slug); it looks intended for real environments, but it creates catalogue data, so read it before running it anywhere that matters.

## 3. Admin panel — **Unverified (install/run), Verified (type-check)**

```bash
cd Admin
cp .env.example .env.local        # set NEXT_PUBLIC_API_BASE_URL and the six NEXT_PUBLIC_FIREBASE_* values
npm install
npm run dev                       # http://localhost:3001
npx tsc --noEmit                  # Verified 2026-10-14: no diagnostics
```

`NEXT_PUBLIC_*` values are inlined **at build time**; restart `npm run dev` after changing them. `npm run lint` maps to `next lint`; its behaviour on Next 16 was not checked.

## 4. Customer app — **Unverified (run), Verified (type-check)**

```bash
cd mobile
npm install
npx expo start -c                  # needs a dev client / development build (native Firebase + Google Sign-In)
npm run android                    # expo run:android - builds the dev client natively
npx tsc --noEmit                   # Verified 2026-10-14: no diagnostics
```

- `google-services.json` is git-ignored; place it next to `app.config.js` or set `GOOGLE_SERVICES_JSON` (EAS file secret).
- Backend URL: in a dev client the app derives `http://<Metro host>:8000/api/v1` unless `EXPO_PUBLIC_API_URL_OVERRIDE` / `EXPO_PUBLIC_API_BASE_URL` is set. **Caution:** the local `mobile/.env` in this checkout sets the override to the hosted backend, so a dev build talks to that deployment, not to your laptop.
- Google Sign-In on a device requires your build's signing SHA-1 registered in the Firebase Android app (otherwise `DEVELOPER_ERROR` code 10).
- `npm run web` (Expo web) currently crashes at start-up on `ExpoNotifications.getLastNotificationResponse` (unsupported on web) — **observed 2026-10-14** — so the web target is not usable as a preview.
- There are no `lint` or `test` scripts in `mobile/package.json`.

## 5. Promo website — **Unverified**

`cd website && npm install && npm run dev` (port 3000). No environment variables.

## 6. Whole stack in Docker — **Unverified (this audit)**

`docker compose up --build -d` starts `db` (host 5433), `backend` (8000, reload, no migration), `website` (3000), `admin` (3001, build arg `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` and **no Firebase config**, so Admin sign-in will not work in this image — see [ENVIRONMENT_VARIABLES](ENVIRONMENT_VARIABLES.md) §4).

## 7. Tests, lint, type checks

| Task | Command (from the folder shown) | Verified result (2026-10-14) |
|---|---|---|
| Backend lint | `backend$ python -m ruff check .` | 7 findings (3 `E741` in app code, 4 in tests) |
| Backend tests | see [TESTING_GUIDE](../07-testing/TESTING_GUIDE.md) (needs a disposable DB) | 891 passed, 1 xfailed, **7 failed** (all caused by the base-fee change, see [AI_STATUS](../00-overview/AI_STATUS.md)) in 10 min 18 s; 899 tests collected |
| Model/migration drift | `backend$ DATABASE_URL=<migrated disposable db> alembic check` | clean |
| Admin / mobile types | `npx tsc --noEmit` | no diagnostics |
| Frontend tests | none exist | – |

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Every sign-in returns "Sign-in is temporarily unavailable" (503 `AUTH_UNAVAILABLE`) | `FIREBASE_PROJECT_ID` empty, or `FIREBASE_SERVICE_ACCOUNT_JSON` set to something that is not a readable file or valid JSON. Unset it for token-only verification |
| "Could not validate credentials" after a successful Firebase sign-in | Token audience ≠ `FIREBASE_PROJECT_ID`, expired/revoked token, or the user is disabled in Firebase |
| `alembic` cannot connect | `DATABASE_URL` wrong; Alembic ignores the `sqlalchemy.url` in `alembic.ini` |
| App prints `Refusing to start with APP_ENV=production…` | Production validation: set `FIREBASE_PROJECT_ID`, and all three Razorpay values if `RAZORPAY_KEY_ID` is set |
| Test suite: `UnsafeTestDatabaseError` | `TEST_DATABASE_URL` missing/unsafe or the DB lacks the disposable marker ([TESTING_GUIDE](../07-testing/TESTING_GUIDE.md)) |
| Mobile Google sign-in fails with code 10 | Register the build's SHA-1/SHA-256 in Firebase and refresh `google-services.json` |
| Mobile web shows a red error overlay | Known: push-notification module unsupported on web |
| Backend slow on first call (hosted) | Free-tier cold start (~44 s observed); the app retries sync with back-off |
| Port 5432/5433 in use | The dev compose publishes Postgres on **5433**; tests must use a different port (the policy forbids 5432/5433) |
