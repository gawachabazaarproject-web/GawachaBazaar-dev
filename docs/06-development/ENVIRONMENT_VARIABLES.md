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
| `FREE_DELIVERY_MIN_ITEMS` | Distinct products for free delivery | No | runtime | No | `10` |
| `DELIVERY_BASE_FEE` | Base delivery fee (Rs) | No | runtime | No | `20` (was 40 from 2026-10-14 to 2026-10-27) |
| `DELIVERY_PER_KM` | Fee per road km (Rs) | No | runtime | No | `10` |
| `DELIVERY_MAX_CHARGED_KM` | Distance cap for pricing | No | runtime | No | `30.0` |
| `PACKING_POINT_LATITUDE`, `PACKING_POINT_LONGITUDE` | Fallback origin when no packing-point warehouse is chosen | No | runtime | No | unset |
| `ROUTING_PROVIDER`, `OSRM_BASE_URL`, `ROUTING_TIMEOUT_SECONDS` | Road-distance provider (only `osrm`), its URL (public demo server by default: development only), request timeout | No | runtime | No | `osrm`, `https://router.project-osrm.org`, `3.0` |
| `DELIVERY_MAX_DISTANCE_KM`, `DELIVERY_MIN_ORDER_VALUE` | Maximum road distance deliverable (0 = none); minimum order value after discount (0 = off) | No | runtime | No | `0`, `0` |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `MAX_INFLIGHT_REQUESTS`, `INFLIGHT_QUEUE_TIMEOUT_SECONDS` | SQLAlchemy pool per worker; in-flight HTTP cap (must be <= pool total); queue wait before 503 `SERVER_BUSY` | No | runtime | No | `12`, `12`, `24`, `15` |
| `DB_STATEMENT_TIMEOUT_MS`, `DB_IDLE_IN_TRANSACTION_TIMEOUT_MS`, `DB_POOL_TIMEOUT_SECONDS`, `DB_POOL_RECYCLE_SECONDS` | Server-side query / idle-transaction guards (0 = off); pool wait; connection recycle | No | runtime | No | `20000`, `60000`, `10`, `1800` |
| `REDIS_URL`, `ROUTE_CACHE_TTL_SECONDS` | Route-distance cache (empty = in-process); TTL | No | runtime | URL may hold a password: **Yes** | empty, `604800` |
| `GEOCODING_PROVIDER`, `NOMINATIM_BASE_URL`, `NOMINATIM_USER_AGENT`, `GEOCODING_TIMEOUT_SECONDS` | Address search (`POST /delivery/geocode`); Nominatim policy needs an identifying User-Agent | No | runtime | No | `nominatim`, public URL, project UA, `5.0` |
| `BAZAAR_PLUS_ORDERS_REQUIRED`, `BAZAAR_TIMEZONE` | Bazaar+ threshold and month boundary zone | No | runtime | No | `6`, `Asia/Kolkata` |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Image uploads; empty ⇒ uploads return 503 | No | runtime | key + secret **Yes** | empty |
| `ALLOWED_ORIGINS` | CORS allow-list; JSON list or comma-separated | No (but needed for browser clients) | runtime | No | `["http://localhost:3000","http://localhost:5173"]` |
| `PORT` | Injected by the host; `start.sh` honours it | – | runtime | No | – |

Start-up validation in production (`check_production_secrets`): empty `FIREBASE_PROJECT_ID`, or `RAZORPAY_KEY_ID` without both Razorpay secrets, aborts start-up. It does **not** check `DEBUG`, `ALLOWED_ORIGINS`, or the default `DATABASE_URL` (RISK_REGISTER R-17).

Legacy/unused: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` are **not read by any code** (the Firebase migration removed them; `deploy/FIREBASE_AUTH.md` says they can be deleted from the backend environment; a stale `JWT_SECRET_KEY` was found in a developer `.env`).

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

> **Delivery variables in compose (changed 2026-10-26):** `docker-compose.prod.yml` now forwards the delivery, routing, Redis and Nominatim variables (defaults equal the code defaults) and runs a `redis` service. `BAZAAR_PLUS_ORDERS_REQUIRED` and `BAZAAR_TIMEZONE` are still **not** forwarded; `docker-compose.yml` (dev) passes only a subset.

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

## 8. Refer & Earn and delivery partners (added 2026-10-27, backend `Settings`)

All are **placeholders pending business decisions**; they are passed through `docker-compose.prod.yml` and `docker-compose.aws.yml`.

| Name | Default | Purpose |
|---|---|---|
| `REFERRAL_ENABLED` | `false` | master switch for Refer & Earn |
| `REFERRAL_REFERRER_REWARD` / `REFERRAL_REFERRED_REWARD` | 50 / 50 | Rs credited |
| `REFERRAL_MIN_ORDER_VALUE` | 199 | minimum items value (after discount) of the qualifying order |
| `REFERRAL_APPLY_WINDOW_DAYS` / `REFERRAL_QUALIFY_WINDOW_DAYS` | 14 / 30 | windows |
| `REFERRAL_MAX_REWARDS_PER_REFERRER` | 20 | cap (0 = unlimited) |
| `PARTNER_EARNING_BASE` / `PARTNER_EARNING_PER_KM` / `PARTNER_EARNING_COD_BONUS` | 20 / 5 / 0 | partner earning per delivery (Rs) |
| `PARTNER_EARNING_RULE_VERSION` | `partner-v1` | stored on each ledger row; bump when you change the formula |
| `PARTNER_LOCATION_MIN_INTERVAL_SECONDS` | 3 | min gap between accepted location updates |
| `PARTNER_LOCATION_MAX_SPEED_KMH` | 150 | larger jumps are rejected |
| `PARTNER_LOCATION_STALE_SECONDS` | 300 | customers stop seeing older positions |

`DELIVERY_BASE_FEE` is Rs 20 (owner decision 2026-10-27); do not override it on the host.
