# Monitoring and Logging

> **Status:** Verified from source on 2026-10-14. **There is no monitoring, metrics, tracing, error-tracking or alerting system in the repository.** What exists is structured-ish logging to stdout, health endpoints and Docker/Kubernetes health checks. Where logs go on EKS/the VPS beyond stdout is outside the repository.
> **Evidence:** [`backend/app/core/logging.py`](../../backend/app/core/logging.py), [`request_id.py`](../../backend/app/core/request_id.py), [`main.py`](../../backend/app/main.py), [`start.sh`](../../backend/start.sh), [`Dockerfile`](../../backend/Dockerfile), [`docker-compose.prod.yml`](../../docker-compose.prod.yml), [`deploy/Caddyfile`](../../deploy/Caddyfile), `grep` of log markers in `backend/app`.

## What is logged

| Item | Behaviour |
|---|---|
| Destination | stdout/stderr only (no files, no log shipper) |
| Format | `YYYY-MM-DD HH:MM:SS [LEVEL] [logger] [request_id]: message` (plain text, not JSON) |
| Level | `DEBUG` when `DEBUG=True`, otherwise `INFO`; SQLAlchemy engine logs at INFO only in debug; SQL echo when `DEBUG` and not production. **The code default is `DEBUG=True`** — compose/K8s set `False`; a missing variable would make production log every SQL statement (parameters included) |
| Request log | One line at request start/finish with method, path (no query string), status and duration; request id from `X-Request-ID` (sanitised) or a generated UUID; echoed in the response header |
| Uvicorn | `--no-access-log` (the request middleware replaces it); handshake lines for WebSockets are logged by `uvicorn.error` with `token=` redacted by a filter |
| Caddy (VPS stack) | No access log by design; the default error log redacts the `token` query value |
| Docker logs (compose) | `json-file`, 5 files × 10 MB per service |
| Frontends | Browser/device consoles only; no remote error reporting (mobile logs, e.g. `GOOGLE_SIGNIN_FAILED`, are visible with `adb logcat`) |

## Log markers worth searching or alerting on (all exist in code; nothing alerts on them)

| Marker | Level | Meaning |
|---|---|---|
| `PAYMENT_RECONCILIATION` | warning/error | Amount/currency mismatch; COD in an unexpected state at delivery; paid but reservation expired (refund request created); pay-first order failed **and** the automatic refund failed (needs a human) |
| `PAYMENT_RESERVATION_MISMATCH` | error | Payment `PAID` but the reservation could not be committed; order left unconfirmed |
| `PAYMENT_WEBHOOK_INVALID_SIGNATURE`, `…_UNKNOWN_REFERENCE`, `…_UNKNOWN_REFUND`, `…_DUPLICATE`, `…_IGNORED`, `…_MALFORMED` | warning/info | Webhook outcomes; unknown references are captured money nobody matched |
| `PAYMENT_UPI_INITIATE_OUTCOME_UNKNOWN`, `REFUND_PROCESSING_OUTCOME_UNKNOWN` | warning | Gateway timeout: money state unknown; resolve with verify/sync |
| `CHECKOUT_SESSION_*` (`BAD_SIGNATURE`, `WEBHOOK_NOT_COMPLETED`) | warning | Pay-first checkout anomalies |
| `INVENTORY_RESERVATION_*` (`CREATED`, `COMMITTED`, `RELEASED`, `LATE_PAYMENT`, `INSUFFICIENT_STOCK`, `SWEEP_FAILED`, `SWEEP_LOOP_ERROR`), `INVENTORY_RESERVATION_SWEEP` | info/warning/error | Stock holds and expiry |
| `ORDER_CANCELLED`, `ORDER_EXPIRED`, `FULFILLMENT_DELIVERED`, `PAYMENT_COD_CONFIRMED`, `PAYMENT_COD_COLLECTED`, `PAYMENT_ORDER_CONFIRMED` | info | Business events |
| `AUTH_INVALID_TOKEN` (with reason `invalid`/`revoked`), `AUTH_UNKNOWN_FIREBASE_UID`, `AUTH_USER_NOT_ACTIVE`, `AUTH_USER_CREATED`, `AUTH_ACCOUNT_LINKED`, `AUTH_SYNC_CONFLICT`, `AUTH_LEGACY_*`, `FIREBASE_CERT_FETCH_FAILED`, `FIREBASE_CREDENTIAL_FILE_LOAD_FAILED`, `FIREBASE_CERTIFICATE_INIT_FAILED`, `FIREBASE_VERIFY_CREDENTIALS_FAILED`, `FIREBASE_REVOCATION_CHECK_FAILED` | info/warning/error | Sign-in health; a burst of `FIREBASE_*` errors means every user is locked out |
| `routing cache=miss ... status=failed` | warning | Router failed; the quote/checkout returned 503 (also `routing cache=hit/miss`, `latency_ms`, `delivery_priced`, `route_cache redis_*_failed`) |
| `PUSH_NO_TOKENS`, `PUSH_TICKET_ERROR`, `PUSH_SEND_FAILED`, `PUSH_NOTIFY_FAILED` | info/warning/error | Push delivery problems (credentials, dead tokens) |
| `RATE_LIMIT_EXCEEDED`, `Unhandled server exception …` | warning/error | Abuse; unexpected 500s |

Start-up lines also warn when Razorpay is off or in test mode, or Cloudinary is unconfigured (in production only).

## Health and liveness

`/health` (no DB) and `/health/db`; container `HEALTHCHECK` every 15 s; Kubernetes readiness/liveness on `/health`; `smoke-test.sh` after a deploy. There is **no readiness probe that checks the database**, no synthetic monitoring, no uptime service configured in the repository. During pool starvation `/health` can time out (PERF-001).

## Metrics, alerts, dashboards

None: no Prometheus/StatsD/OpenTelemetry, no Sentry-style error tracker, no uptime monitor, no on-call tooling in the code or manifests. The Admin dashboard shows *business* tiles (orders, revenue, unpicked orders, low stock, delivery issues — `GET /dashboard`), not system health.

## Practical monitoring today

- **VPS:** `docker compose … logs -f backend`; `ps` for container health; `ls backups/` for backup recency.
- **EKS:** `kubectl logs`, `kubectl get hpa,pods`; the HPA scales on CPU only (does not see pool starvation).
- **Mobile:** `adb logcat | grep ReactNativeJS`.

## Recommended (not implemented)

Ship logs to a searchable store with retention; JSON logging; alerts on `PAYMENT_RECONCILIATION`, `PAYMENT_RESERVATION_MISMATCH`, `REFUND_FAILED`/`PAYMENT_WEBHOOK_UNKNOWN_REFERENCE`, a spike of `AUTH_UNAVAILABLE`/`FIREBASE_*`, and 5xx rate; an external uptime check on `/health` (this also keeps a free-tier AWS backend warm); a DB-aware readiness probe; frontend error reporting; request-id propagation to clients' bug reports.
