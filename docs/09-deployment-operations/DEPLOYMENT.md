# Deployment

> **Status:** Partially verified. **Last verified:** 2026-10-14. The repository describes **three different production deployments of the backend** (and evidence of a fourth, for the Admin panel). I could not determine from the repository which one serves customers. Nothing was deployed, changed or run against production by this task; the only live checks were read-only `GET`s (below).
> **Evidence:** [`deploy/README.md`](../../deploy/README.md) + [`docker-compose.prod.yml`](../../docker-compose.prod.yml) + [`deploy/Caddyfile`](../../deploy/Caddyfile) + [`deploy/scripts/`](../../deploy/scripts); [`.forgejo/workflows/deploy.yml`](../../.forgejo/workflows/deploy.yml) + [`k8s/`](../../k8s); [`backend/start.sh`](../../backend/start.sh) (honours Render's `$PORT`); [`Admin/.env.example`](../../Admin/.env.example) (mentions Vercel); [`mobile/eas.json`](../../mobile/eas.json), [`mobile/app.json`](../../mobile/app.json); the QA audit's probes in [`docs/testing/BASELINE_AUDIT.md`](../testing/BASELINE_AUDIT.md) §1.

## 1. The four deployment descriptions

| # | Target | Described in | What it deploys | Evidence it is live |
|---|---|---|---|---|
| A | **Single VPS (Contabo), Docker Compose + Caddy** | `deploy/README.md`, `docker-compose.prod.yml`, `deploy/` scripts | website, Admin, backend, PostgreSQL 16, one-shot `migrate`, nightly `db-backup`, Caddy (HTTPS) | None found (it is a runbook) |
| B | **AWS EKS (ap-south-1) behind an ALB** | `.forgejo/workflows/deploy.yml`, `k8s/` (`base/`, `overlays/aws`) | backend, website, Admin deployments + HPAs; Docker Hub images tagged by commit SHA | Earlier audit (2026-10-13): `https://api.gawachabazaar.in/api/v1/ping` answered 200 from an AWS-hosted address; the ALB routes only `/api/v1` of that host to the backend |
| C | **Render web service** (+ Render PostgreSQL) | `backend/start.sh` (reads `$PORT`), `mobile/.env`/`eas.json` (API URL), config comments mentioning Render | backend only | Probed on 2026-10-14: `GET https://gawachabazaar-backend.onrender.com/health` → 200 `{"status":"ok","app":"GawachaBazaar","environment":"production"}`; `/docs` → 404 (docs disabled ⇒ `APP_ENV=production`); cold start ≈ 44 s after idle |
| D | **Vercel (Admin panel)** | `Admin/.env.example` ("set the same names in Vercel → Project → Settings → Environment Variables") | Admin only | The Admin login the project owner showed on 2026-10-14 was served from a `*.vercel.app` host (a screenshot in the conversation, not a repository artefact) |

**What the installed customer app uses:** the APK inspected on 2026-10-14 listens on update channel `preview`, update URL `https://u.expo.dev/a751e06b-…`, and the mobile `.env`/`eas.json` point to the Render backend (`…onrender.com/api/v1`). Commit `88d6090` (2026-10-14, "point builds at live API") changed `eas.json` from `https://api.gawachabazaar.in/api/v1` to the Render URL and states that `api.gawachabazaar.in` "serves the website, not the API" — direct evidence that the AWS hostname was not serving the API the app needs. So **the Render backend (C) is what the app talks to** in the builds examined; the EKS (B) and VPS (A) descriptions may be unused, stale, or serving other clients — **unresolved**. Which database each backend uses, and whether any traffic is split, is also unresolved. Treat none as authoritative until the owner confirms.

### Inconsistencies inside the repository

| # | Inconsistency | Impact |
|---|---|---|
| 1 | `k8s/backend-deployment.yaml` (top-level) ≠ `k8s/base/backend-deployment.yaml`: 2 vs 1 replicas, `APP_ENV=staging` vs `production`, ECR image vs a bare image name, localhost vs real CORS origins; CI applies only `base/admin-*` and edits existing deployments by name | Unclear which manifest set is the source of truth; a fresh apply of the top-level file would run `staging` with dev CORS |
| 2 | Backend HPA 1→3 (and website HPA 2→4) vs the **single-worker** design | Confirmed breakage with >1 replica (rate limit, realtime, migrations race) — [MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md) |
| 3 | The ALB ingress routes only `api.gawachabazaar.in/api/v1` and `gawachabazaar.in`; the Admin service/deployment exist but **no ingress rule exposes Admin** | Admin is not reachable on EKS as defined |
| 4 | Admin Dockerfile/compose/CI pass only `NEXT_PUBLIC_API_BASE_URL`; the six `NEXT_PUBLIC_FIREBASE_*` values are not provided, and `.dockerignore` excludes `.env.*` | A Docker-built Admin image cannot sign in ([ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md) §4) |
| 5 | `docker-compose.prod.yml` does not pass delivery/routing/Bazaar variables to the backend although `.env.production.example` lists them | Those settings are ignored in compose; code defaults apply |
| 6 | `start.sh` migrates at every container start **and** compose has a separate `migrate` service; K8s has no migration job | Redundant in compose; racy on K8s (OPS-002) |
| 7 | CI builds the Admin image with `ADMIN_API_BASE_URL=https://api.gawachabazaar.in/api/v1`, but the mobile app and (observed) Admin use the Render URL | Admin on EKS would talk to a different backend than the app |

## 2. Build and release procedures (as written)

### A. VPS with Docker Compose (`deploy/README.md`, **Unverified in this audit**)
1. DNS A records for site/admin/api/www; `bootstrap-server.sh deploy` once (ufw SSH/80/443, fail2ban, unattended upgrades, swap, Docker, non-root `deploy` user); harden SSH.
2. `git clone` to `/opt/gawachabazaar`; `cp .env.production.example .env.production` (`chmod 600`, replace every `CHANGE_ME`).
3. `deploy/scripts/deploy.sh` (add `--pull` to `git pull --ff-only`): validates compose config, `build --pull`, `up -d --remove-orphans`; `migrate` must succeed before `backend` starts; prunes dangling images.
4. First admin: `docker compose … exec backend python scripts/create_admin.py …`. Verify with `deploy/scripts/smoke-test.sh` (health, health/db, public catalogue, `/docs` 404, auth 401, HSTS, nosniff, http→https 308, Admin login 200, X-Frame-Options, website 200, www→apex 301).
5. Update: `deploy/scripts/deploy.sh --pull`. Failed migration ⇒ the old backend keeps running.

### B. EKS via Forgejo Actions (`.forgejo/workflows/deploy.yml`)
On every push to `main`: checkout → Docker Hub login → build backend, website and Admin images tagged `$GITHUB_SHA` → push → `aws eks update-kubeconfig` (cluster `gawachabazaar-prod`, region `ap-south-1`) → create/refresh the `dockerhub-regcred` pull secret → `kubectl set image` for backend, website, Admin (Admin Deployment/Service/HPA are applied from `k8s/base/admin-*` only if the Deployment does not yet exist) → `rollout status` (5 min each) → list pods/HPAs. **No tests, scans or approvals; no migration step; no post-deploy smoke test.** Backend secrets come from the `gawachabazaar-backend-secret` Kubernetes Secret (not in the repository).

### C. Render (backend)
Not described in the repository beyond `start.sh` (migrate, then one uvicorn worker on `$PORT`) and the use of the `/health` endpoint. Build/start commands, auto-deploy branch, instance size, disk, backups and environment variables live in the Render dashboard (**not inspected**). Free-tier behaviour observed: sleeps when idle, ≈ 44 s cold start. A bad `FIREBASE_SERVICE_ACCOUNT_JSON` value on this service took sign-in down on 2026-10-14 (resolved by removing the variable).

### D. Admin on Vercel
Environment variables are set in the Vercel project (`NEXT_PUBLIC_API_BASE_URL` and the six `NEXT_PUBLIC_FIREBASE_*`); they are inlined at build, so any change requires a redeploy. Branch/auto-deploy settings are not in the repository.

### Mobile app (EAS)
- **Build:** `eas build --profile preview|production` (`eas.json`: `preview` = internal APK, `production` = auto-incremented version code; channels `development`/`preview`/`production`; env per profile). Needs EAS file secret `GOOGLE_SERVICES_JSON` and the Android signing key; the project is owned by account **`yash145`** (project `a751e06b-…`), so the signing key and its SHA-1 are new relative to earlier builds.
- **OTA update (JS + assets only):** `cd mobile && npx eas-cli update --channel preview --message "…"` (use the channel baked into the installed build; the build examined on 2026-10-14 uses `preview`, runtime version `1.0.0`). The app checks on launch (`checkAutomatically: ON_LOAD`, `fallbackToCacheTimeout: 3000`), so a new update usually applies on the second launch. Native changes, new native dependencies, and `app.json` changes need a new build; changing `version` changes the runtime version and strands installed apps.
- A 41 MB APK is tracked in git (`mobile/GawachaBazaar-1.0.0.apk`) — not a deployment mechanism.

## 3. Required configuration

All variables with their purpose, requiredness and build/runtime timing: [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md). Production minimums for the backend: `APP_ENV=production`, `DEBUG=False`, `DATABASE_URL`, `FIREBASE_PROJECT_ID`, `ALLOWED_ORIGINS` (real origins), plus Razorpay trio and Cloudinary trio if those features are on. Razorpay dashboard: automatic capture, webhook URL `https://<API_DOMAIN>/api/v1/payments/webhooks/razorpay` with the five events listed in [WEBHOOKS](../03-api/WEBHOOKS.md).

## 4. Health checks

| Check | What it proves |
|---|---|
| `GET /health` | The process serves HTTP (no DB). Used by the container `HEALTHCHECK` (15 s), K8s liveness/readiness, compose `depends_on` for dev |
| `GET /readiness` | **Public on purpose** (orchestrator/uptime probe, same class as `/health/db`). Returns 200/503 with `{status, checks}` where `checks` holds only short strings for `database`, `redis` (ok / degraded / not configured) and `origin` (configured / unset). No product, stock, user, order, URL or credential data, and it never calls external providers (test: `test_the_public_readiness_probe_shares_no_business_data`). Added by the delivery work, not by the Admin UX work |
| `GET /health/db` | Database connectivity (503 otherwise); used by `smoke-test.sh` |
| Admin `/login`, website `/` | Frontend containers up (their `HEALTHCHECK`s) |
| Note | Under pool starvation `/health` queues behind the same thread pool (PERF-001), so probes can fail during overload |

Logs, monitoring and incident handling: [MONITORING_AND_LOGGING](MONITORING_AND_LOGGING.md), [INCIDENT_RESPONSE](INCIDENT_RESPONSE.md). Backups and restore: [BACKUP_AND_RECOVERY](BACKUP_AND_RECOVERY.md). Rolling back: [ROLLBACK](ROLLBACK.md).

## 5. Decisions needed from the owner

Which of A/B/C is production (and decommission the others or label them); where Admin is hosted and how its Firebase config is injected; whether migrations run as a separate step; whether to scale beyond one process (requires shared state first); a CI gate before the `main` deploy ([QUALITY_GATES](../07-testing/QUALITY_GATES.md)).
