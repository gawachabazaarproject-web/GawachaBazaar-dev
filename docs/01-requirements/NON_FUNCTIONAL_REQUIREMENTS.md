# Non-Functional Requirements

> **Status:** Partially verified. **Last verified:** 2026-10-14.
> **Important:** the repository states **no** quantified non-functional targets (no SLA, SLO, peak concurrency, RPO/RTO, or accessibility standard). This document therefore records (a) what the implementation **enforces or is configured for**, (b) what has been **measured**, and (c) what is **not defined** and needs an owner decision. Nothing here is a commitment unless marked "enforced".

## 1. Performance and capacity

| Aspect | What is known | Status | Evidence |
|---|---|---|---|
| Target load | **Not defined.** The "10,000 monthly users / 1,000 customers" figure in some conversations is unverified and does not determine concurrency ([BASELINE_AUDIT](../testing/BASELINE_AUDIT.md) §1) | Unknown | – |
| Measured capacity (exploratory, one dev machine, one worker) | ≈ 30–40 requests/s plateau; p95 < 2 s up to 50 virtual users; **100 users → 100 % timeouts and ~6 min recovery** (DB pool 5+10 vs 40 request threads) | Verified (exploratory) | [PERFORMANCE_RESULTS](../testing/PERFORMANCE_RESULTS.md), finding PERF-001 |
| Response compression | JSON responses ≥ 1024 bytes are gzip-compressed | Enforced | [`main.py`](../../backend/app/main.py) `GZipMiddleware` |
| DB connection pool | `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`; default `pool_timeout` | Enforced | [`db/session.py`](../../backend/app/db/session.py) |
| Upload size | Images ≤ 8 MB, types JPEG/PNG/WebP/GIF; Caddy caps request bodies at 10 MB | Enforced | [`image_upload.py`](../../backend/app/services/image_upload.py), [`deploy/Caddyfile`](../../deploy/Caddyfile) |
| Delivery quote latency | Routing call timeout 3 s (`ROUTING_TIMEOUT_SECONDS`), results cached per ~11 m coordinate cell, haversine×1.4 fallback | Enforced | [`delivery.py`](../../backend/app/services/delivery.py) |
| Cold start on Render | The Render service answered `/health` after 44 s when idle (observed 2026-10-14); the mobile client's default timeout is 15 s, with a 60 s warm-up ping | Observed | [`mobile/src/api/client.ts`](../../mobile/src/api/client.ts) |

## 2. Availability and resilience

| Aspect | What is known | Status | Evidence |
|---|---|---|---|
| Uptime target / SLA | **Not defined** | Unknown | – |
| Topology | One backend process (rate limiter, WebSocket hub, reservation sweep are in-process). Kubernetes manifests allow an HPA 1→3, which contradicts that constraint ([MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md)) | Verified | [`Dockerfile`](../../backend/Dockerfile), [`k8s/base/backend-hpa.yaml`](../../k8s/base/backend-hpa.yaml) |
| Health checks | `/health` (no DB) for container/probe liveness; `/health/db` for connectivity; Dockerfile `HEALTHCHECK` every 15 s | Enforced | [`main.py`](../../backend/app/main.py), [`Dockerfile`](../../backend/Dockerfile) |
| Migration gate | Compose: `migrate` must complete before `backend` starts. `start.sh` also runs `alembic upgrade head` at container start (so concurrent replicas race) | Verified | [`docker-compose.prod.yml`](../../docker-compose.prod.yml), [`start.sh`](../../backend/start.sh), OPS-002 |
| Graceful shutdown | `--timeout-graceful-shutdown 20` | Enforced | [`start.sh`](../../backend/start.sh) |
| Gateway failure behaviour | Gateway timeout/connection error → HTTP 502 with a message that does not claim the payment failed; payment stays `PROCESSING`; webhook or `/verify` reconciles | Verified | [`exceptions/handlers.py`](../../backend/app/exceptions/handlers.py), [`payment.py`](../../backend/app/services/payment.py) |
| Push / realtime failure isolation | Push sends run on a background thread with their own DB session; realtime notification never raises into the request | Enforced | [`push.py`](../../backend/app/services/push.py), [`realtime.py`](../../backend/app/core/realtime.py) |
| Backups | Nightly `pg_dump -Fc`, 14-day retention (compose stack only); restore script exists; **no restore drill recorded** | Partially verified | [`backup-db.sh`](../../deploy/scripts/backup-db.sh), [BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md) |

## 3. Data integrity (enforced by database and code)

- Money: `NUMERIC(12,2)` / `Decimal`, quantized `ROUND_HALF_UP`; order lines snapshot price and name ([`order.py`](../../backend/app/services/order.py)).
- Uniqueness and `CHECK` constraints for statuses, positive amounts, one-per-order rows ([DATABASE_SCHEMA](../04-database/DATABASE_SCHEMA.md)).
- Row-level locking with a fixed order (Order → Payment, Order → Fulfillment, lots by id) and idempotent state transitions ([DATA_FLOW](../02-architecture/DATA_FLOW.md)). Concurrency is tested with real threads against PostgreSQL ([`docs/testing/EXISTING_TEST_INVENTORY.md`](../testing/EXISTING_TEST_INVENTORY.md)).
- Known weakness: PAY-001 ([KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md)).

## 4. Security (summary; detail in [SECURITY](../08-security/SECURITY.md))

Enforced: Firebase token verification on every request; live role lookup; static permission map; per-route gates snapshot-tested; HMAC verification for webhooks and checkout signatures; security headers (`nosniff`, `X-Frame-Options: DENY`, restrictive CSP, `Referrer-Policy: no-referrer`, HSTS on https); rate limit only on `/auth/sync` (20/min) and `/auth/legacy-migrate` (5/min); `token=` query values redacted from logs; non-root containers; OpenAPI docs disabled in production. **Not defined:** password policy (delegated to Firebase), session-length policy (Firebase default ID-token lifetime), dependency-scanning cadence, penetration-test cadence.

## 5. Observability

| Aspect | Status | Evidence |
|---|---|---|
| Request correlation (`X-Request-ID`, sanitised or generated) and a start/finish log with method, path, status and duration (no query string) | Enforced | [`request_id.py`](../../backend/app/core/request_id.py) |
| Plain-text log format `time [level] [logger] [request_id]: message` to stdout; DEBUG enables SQL echo outside production | Enforced | [`logging.py`](../../backend/app/core/logging.py) |
| Reconciliation markers to alert on (`PAYMENT_RECONCILIATION`, `PAYMENT_RESERVATION_MISMATCH`, `INVENTORY_RESERVATION_*`, `REFUND_*`) | Present in code; **no alerting or metrics system exists in the repository** | grep of `backend/app` |
| Metrics, tracing, error tracking (Sentry etc.) | **Not present** | no dependency or config found |

See [MONITORING_AND_LOGGING](../09-deployment-operations/MONITORING_AND_LOGGING.md).

## 6. Compatibility, localisation, accessibility

| Aspect | What is known | Status |
|---|---|---|
| Currency / region | INR only; Indian phone numbers normalised to `+91…` (`normalize_phone`, mobile `phone.ts`); timezone `Asia/Kolkata` for the Bazaar+ month | Enforced |
| Languages | English UI; Devanagari font in the theme (product names can show Marathi/Hindi script); no i18n framework found | Observed |
| Mobile platforms | Android build verified by an installed APK; iOS identifiers exist in `app.json` but no iOS folder/build evidence | Partially verified |
| Admin browsers | Not stated | Unknown |
| Accessibility | No standard stated; some `accessibilityRole/Label` use in the app; no audit | Unknown |

## 7. Maintainability

Ruff configured (`E,W,F,I,B,UP`, line length 88 with E501 ignored); last run on 2026-10-14 reported 7 findings ([AI_STATUS](../00-overview/AI_STATUS.md)). Type checking: `tsc --noEmit` available for `mobile/` and `Admin/`. No formatter config, no pre-commit hooks, no coverage tool configured ([CODING_STANDARDS](../06-development/CODING_STANDARDS.md), [QUALITY_GATES](../07-testing/QUALITY_GATES.md)).

## 8. Open decisions (owner input needed)

Peak concurrency and growth expectations · availability target and maintenance windows · RPO/RTO and backup off-site policy · supported Android versions and devices · accessibility baseline · data-retention periods ([DATA_RETENTION](../04-database/DATA_RETENTION.md)).
