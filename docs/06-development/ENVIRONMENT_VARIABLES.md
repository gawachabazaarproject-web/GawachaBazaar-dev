# Environment Variables

> **Status:** Verified from source on 2026-10-14 (every name below was found in code, compose files, manifests or CI). Values are **never** recorded here; "Default" shows only the code default or a placeholder. **Do not copy `.env` files into `docs/`.**
> **Evidence:** [`backend/app/core/config.py`](../../backend/app/core/config.py), [`core/firebase.py`](../../backend/app/core/firebase.py), [`backend/start.sh`](../../backend/start.sh), [`docker-compose.yml`](../../docker-compose.yml), [`docker-compose.prod.yml`](../../docker-compose.prod.yml), [`.env.production.example`](../../.env.production.example), [`backend/.env.example`](../../backend/.env.example), [`Admin/.env.example`](../../Admin/.env.example), [`mobile/.env.example`](../../mobile/.env.example), [`mobile/eas.json`](../../mobile/eas.json), [`mobile/app.config.js`](../../mobile/app.config.js), [`k8s/base/backend-deployment.yaml`](../../k8s/base/backend-deployment.yaml), [`.forgejo/workflows/deploy.yml`](../../.forgejo/workflows/deploy.yml), [`backend/tests/conftest.py`](../../backend/tests/conftest.py).
> Related: [SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md), [LOCAL_SETUP](LOCAL_SETUP.md).

Legend — **When:** *runtime* = read when the process starts/handles requests; *build* = inlined into a bundle/image at build time (changing it requires a rebuild). **Secret:** must never be committed or shipped to a client.

## 1. Backend (`backend/`, class `Settings`, case-sensitive, `.env` supported, extra keys ignored)

| Name | Purpose | Required? | When | Secret | Default / placeholder |
|---|---|---|---|---|---|
| `APP_NAME` | App title, Razorpay merchant name, `/health` payload | No | runtime | No | `GawachaBazaar` |
| `APP_ENV` | `development`/`testing`/`staging`/`production`. `production` disables `/docs`,`/redoc`,`/openapi.json` and enables start-up validation | No | runtime | No | `development` |
| `DEBUG` | Log level DEBUG and SQL echo (when not production) | No | runtime | No | `True` (**the code default is True**; compose/k8s set `False`) |
| `HOST`, `PORT` | Bind settings (the container uses `$PORT` in `start.sh`, default 8000) | No | runtime | No | `0.0.0.0`, `8000` |
| `DATABASE_URL` | PostgreSQL connection; `postgres://`/`postgresql://` are rewritten to `postgresql+psycopg://` | **Yes** | runtime (also Alembic) | **Yes** | local default `postgresql+psycopg://postgres:postgres@localhost:5432/gawachabazaar` |
| `FIREBASE_PROJECT_ID` | Audience for ID-token verification | **Yes in production** (start-up refuses without it) | runtime | No | empty |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Service-account key as inline JSON **or** a path to a file; needed for staff creation, password reset, disable/revoke, legacy migration, and the revocation check | Optional (token verification works without it) | runtime | **Yes** | empty. **A non-file value that is not valid JSON makes every sign-in return 503** (observed 2026-10-14) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google ADC path; read directly with `os.environ` (not a `Settings` field) | No | runtime | path only | unset |
| `RAZORPAY_KEY_ID` | Public key id; empty ⇒ online payments off (COD only) | No | runtime | No | empty |
| `RAZORPAY_KEY_SECRET` | API secret; also verifies checkout signatures | Required if key id set | runtime | **Yes** | empty |
| `RAZORPAY_WEBHOOK_SECRET` | HMAC secret for webhooks | Required if key id set | runtime | **Yes** | empty |
| `RAZORPAY_BASE_URL`, `RAZORPAY_TIMEOUT_SECONDS` | API base and timeout | No | runtime | No | `https://api.razorpay.com/v1`, `10.0` |
| `FREE_DELIVERY_MIN_ITEMS` | Distinct products for free delivery | No | runtime | No | `15` |
| `DELIVERY_BASE_FEE` | Base delivery fee (Rs) | No | runtime | No | `40` (was 20 until 2026-10-14) |
| `DELIVERY_PER_KM` | Fee per road km (Rs) | No | runtime | No | `10` |
| `DELIVERY_MAX_CHARGED_KM` | Distance cap for pricing | No | runtime | No | `30.0` |
| `PACKING_POINT_LATITUDE`, `PACKING_POINT_LONGITUDE` | Fallback origin when no packing-point warehouse is chosen | No | runtime | No | unset |
| `GOOGLE_MAPS_API_KEY` | Distance Matrix key; else OSRM is used | No | runtime | **Yes** | empty |
| `OSRM_BASE_URL` | OSRM router (public demo server by default; "testing only") | No | runtime | No | `https://router.project-osrm.org` |
| `ROUTING_TIMEOUT_SECONDS`, `DELIVERY_ROAD_FACTOR` | Routing timeout; fallback multiplier | No | runtime | No | `3.0`, `1.4` |
| `BAZAAR_PLUS_ORDERS_REQUIRED`, `BAZAAR_TIMEZONE` | Bazaar+ threshold and month boundary zone | No | runtime | No | `6`, `Asia/Kolkata` |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Image uploads; empty ⇒ uploads return 503 | No | runtime | key + secret **Yes** | empty |
| `ALLOWED_ORIGINS` | CORS allow-list; JSON list or comma-separated | No (but needed for browser clients) | runtime | No | `["http://localhost:3000","http://localhost:5173"]` |
| `PORT` (Render) | Injected by the host; `start.sh` honours it | – | runtime | No | – |

Start-up validation in production (`check_production_secrets`): empty `FIREBASE_PROJECT_ID`, or `RAZORPAY_KEY_ID` without both Razorpay secrets, aborts start-up. It does **not** check `DEBUG`, `ALLOWED_ORIGINS`, or the default `DATABASE_URL` (RISK_REGISTER R-17).

Legacy/unused: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` are **not read by any code** (the Firebase migration removed them; `deploy/FIREBASE_AUTH.md` says they can be deleted from Render; a stale `JWT_SECRET_KEY` was found in a developer `.env`).

## 2. Production Docker Compose (`docker-compose.prod.yml` + `.env.production`)

| Name | Purpose | Required? | Notes |
|---|---|---|---|
| `SITE_DOMAIN`, `ADMIN_DOMAIN`, `API_DOMAIN` | Hostnames Caddy serves; also derive `ALLOWED_ORIGINS` and the Admin build arg | **Yes** (`:?` guards) | DNS must resolve first |
| `ACME_EMAIL` | Let's Encrypt contact | **Yes** | – |
| `POSTGRES_USER`, `POSTGRES_DB` | DB role/name | No (defaults `gawacha`, `gawachabazaar`) | – |
| `POSTGRES_PASSWORD` | DB password | **Yes** | secret; `deploy.sh` refuses any `CHANGE_ME` |
| `FIREBASE_PROJECT_ID` | passed to backend | **Yes** | – |
| `FIREBASE_SERVICE_ACCOUNT_JSON`, `RAZORPAY_*`, `CLOUDINARY_*` | passed to backend | optional | secrets |
| `BACKUP_RETENTION_DAYS`, `BACKUP_INTERVAL_SECONDS` | db-backup loop | No | `14`, `86400` |

> **Discrepancy:** `.env.production.example` also lists `FREE_DELIVERY_MIN_ITEMS`, `DELIVERY_BASE_FEE`, `DELIVERY_PER_KM`, `DELIVERY_MAX_CHARGED_KM`, `PACKING_POINT_*`, `GOOGLE_MAPS_API_KEY`, `OSRM_BASE_URL`, `ROUTING_TIMEOUT_SECONDS`, `DELIVERY_ROAD_FACTOR`, `BAZAAR_PLUS_ORDERS_REQUIRED`, `BAZAAR_TIMEZONE`, but the compose file's `x-backend-env` block **does not pass any of them** to the backend container. In the compose deployment these variables have **no effect**; the code defaults apply. `docker-compose.yml` (dev) likewise passes only a subset.

Development compose (`docker-compose.yml`): `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (defaults `postgres`/`postgres`/`gawachabazaar`, host port 5433), `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `CLOUDINARY_*`, `RAZORPAY_*`.

## 3. Kubernetes / CI

| Where | Names | Source |
|---|---|---|
| `k8s/base/backend-deployment.yaml` (plain values) | `APP_NAME`, `APP_ENV=production`, `DEBUG=False`, `HOST`, `PORT`, `ALLOWED_ORIGINS` | manifest |
| same, `envFrom: secretRef gawachabazaar-backend-secret` | everything else the backend needs (database, Firebase, Razorpay, Cloudinary…) | The secret's **contents are not in the repository** — which keys exist is unknown |
| top-level `k8s/backend-deployment.yaml` | `APP_ENV=staging`, localhost origins, 2 replicas, ECR image | **differs from `base/`** — see [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| `.forgejo/workflows/deploy.yml` | CI secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`; AWS credentials (provided by the runner, not named); workflow env `ADMIN_API_BASE_URL`, `EKS_CLUSTER`, `AWS_REGION`, `K8S_NAMESPACE`, image names | workflow |

## 4. Admin panel (`Admin/`, Next.js)

| Name | Purpose | Required? | When |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL including `/api/v1` | Yes (falls back to `http://localhost:8000/api/v1`) | **build** (Docker `ARG`; Vercel project env) |
| `NEXT_PUBLIC_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_STORAGE_BUCKET`, `_MESSAGING_SENDER_ID`, `_APP_ID` | Firebase **web** config (public identifiers, not secrets) | Yes — without them the login page reports a missing configuration | **build** |

> **Discrepancy (deployment blocker for Docker/CI builds):** [`Admin/Dockerfile`](../../Admin/Dockerfile) declares only `NEXT_PUBLIC_API_BASE_URL` as a build argument, [`Admin/.dockerignore`](../../Admin/.dockerignore) excludes `.env.*`, and neither `docker-compose.prod.yml` nor the CI workflow passes the six `NEXT_PUBLIC_FIREBASE_*` values. An Admin image built that way has **no Firebase config** and cannot sign anyone in. `Admin/.env.example` says to set the variables in **Vercel**, which suggests the Admin panel is meant to be hosted there (the login page the user showed on 2026-10-14 was served from a `*.vercel.app` host). Not verified which build path is used in production.

## 5. Customer app (`mobile/`, Expo — `EXPO_PUBLIC_*` are inlined into the JS bundle; never put secrets here)

| Name | Purpose | Required? | When |
|---|---|---|---|
| `EXPO_PUBLIC_API_BASE_URL` | Backend base URL with `/api/v1` (standalone builds) | Yes for builds (set per profile in `eas.json`) | build |
| `EXPO_PUBLIC_API_URL_OVERRIDE` | Forces dev builds onto another backend (currently set in the local `mobile/.env`) | No | build/dev |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Google Sign-In web client id | Yes for Google sign-in | build |
| `EXPO_PUBLIC_FIREBASE_*` (six) | Firebase web config used only by the **web** build (native uses `google-services.json`) | web only | build |
| `GOOGLE_SERVICES_JSON`, `GOOGLE_SERVICE_INFO_PLIST` | Paths to the native Firebase files (EAS **file secrets**; the files are git-ignored) | Yes for native builds | build |
| `GAWACHA_UPLOAD_*` (Gradle properties, not env) | Android upload keystore for signed release builds | For store/shared releases | build machine |

Dev client URL resolution order: `EXPO_PUBLIC_API_URL_OVERRIDE` → Metro host `:8000` → `EXPO_PUBLIC_API_BASE_URL` ([`client.ts`](../../mobile/src/api/client.ts)).

## 6. Tests

| Name | Purpose |
|---|---|
| `TEST_DATABASE_URL` | **Required** for DB tests: an explicit, validated local disposable database ([TESTING_GUIDE](../07-testing/TESTING_GUIDE.md)). It is never derived from `DATABASE_URL`. |
| `APP_ENV=testing`, `DATABASE_URL` | Set by `conftest.py` itself; Razorpay/Cloudinary/Maps/Firebase-account variables are blanked for every test |
| `PGHOST`, `PGHOSTADDR`, `PGPORT`, `PGDATABASE`, `PGSERVICE`, `PGSERVICEFILE`, `PGPASSFILE`, `PGOPTIONS` | **Must be unset** — their presence aborts the suite (fail-closed policy) |

## 7. Website (`website/`)

No environment variables are read (`process.env` is not used in `website/app` or `website/components`).

## Checks to run when you add a variable

1. Add the field to `Settings` (with a safe default) and to `backend/.env.example` and `.env.production.example`.
2. **Pass it through `docker-compose.prod.yml` `x-backend-env`** (and the Kubernetes secret/config) — listing it in an example file alone does nothing.
3. If it must reach a browser/app bundle, it is `NEXT_PUBLIC_*`/`EXPO_PUBLIC_*` and a *build-time* value; add the Docker build argument or EAS profile entry.
4. Document it here.
