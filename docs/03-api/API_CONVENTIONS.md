# API Conventions

> **Status:** Verified against source on 2026-10-14. Operation inventory: [API_REFERENCE.md](API_REFERENCE.md). Error contract: [ERROR_HANDLING](../02-architecture/ERROR_HANDLING.md).
> **Evidence:** [`main.py`](../../backend/app/main.py), [`api/v1/router.py`](../../backend/app/api/v1/router.py), [`schemas/base.py`](../../backend/app/schemas/base.py), [`dependencies/auth.py`](../../backend/app/dependencies/auth.py), [`core/request_id.py`](../../backend/app/core/request_id.py), [`core/rate_limit.py`](../../backend/app/core/rate_limit.py).

## Base URL and versioning

- All business routes are under **`/api/v1`**. Health routes are at the root: `GET /health` (no database), `GET /health/db` (503 when the database is unreachable). There is one WebSocket: `/api/v1/ws/events`.
- Only `v1` exists; no deprecation policy is stated. Interactive docs (`/docs`, `/redoc`, `/openapi.json`) exist only when `APP_ENV != production`.
- The mobile app takes its base URL from `EXPO_PUBLIC_API_BASE_URL` / `EXPO_PUBLIC_API_URL_OVERRIDE`; Admin from `NEXT_PUBLIC_API_BASE_URL` (a **build-time** value in the Docker image).

## Authentication

- `Authorization: Bearer <Firebase ID token>` on every protected route. Missing/invalid/expired tokens give 401 with codes `AUTHENTICATION_ERROR` or `TOKEN_EXPIRED`.
- The WebSocket takes the token as `?token=` (browsers cannot set handshake headers); the value is redacted from backend and Caddy logs.
- Public routes (12): catalogue reads (`GET /catalog/categories[/{id}]`, `/catalog/products[/{id}]`), `GET /ads`, `/home-slides`, `/offers`, `/ping`, `/health`, `/health/db`, `POST /auth/legacy-migrate`, `POST /payments/webhooks/{gateway_slug}`. `POST /auth/sync` needs a Bearer token but not an existing application account.
- Authorization is per route (roles/permissions); see the Auth column in the reference. **Cross-check:** on 2026-10-14 the roles derivable from that column for all 180 role- or permission-gated operations matched the reviewed role matrix [`authz_golden.json`](../../backend/tests/authz_golden.json) exactly (0 mismatches).

## Request and response format

| Aspect | Convention | Evidence |
|---|---|---|
| Format | JSON (`application/json`); uploads use `multipart/form-data` (ads, home slides, categories, product images) | [`API_REFERENCE`](API_REFERENCE.md) request column |
| Field names | `snake_case` | Pydantic models in `backend/app/schemas/` |
| Unknown/extra fields | Pydantic default for `BaseSchema`; strings are whitespace-stripped (`str_strip_whitespace=True`) | `schemas/base.py` |
| IDs | Integers (`BIGINT`) | [`DATABASE_SCHEMA`](../04-database/DATABASE_SCHEMA.md) |
| Money | `Decimal` serialised as a **string** with two decimals (e.g. `"90.00"`); currency `INR`. Razorpay amounts are converted to integer paise only inside the gateway adapter | tests assert `'90.00'`; `razorpay_gateway.to_paise` |
| Quantities | `NUMERIC(12,3)` (three decimals) | schema |
| Timestamps | Timezone-aware (`timestamptz`), ISO-8601 in responses | schema |
| Enumerations | Upper-case strings validated by database `CHECK` constraints | schema |
| Success codes | 200 read/update, 201 create, 204 delete/no body | [`API_REFERENCE`](API_REFERENCE.md) response column |
| Empty bodies | `POST /auth/sync` accepts no body; `POST /push-tokens*` return 204 | auth, push routers |

## Pagination and filtering

List endpoints take `page` (≥ 1, default 1) and `page_size` (default 20 on customer order lists, hard maximum `MAX_PAGE_SIZE = 100` in every schema module that defines it) and return `{ "items": [...], "page": n, "page_size": n, "total": n }`. Not every list is paginated (e.g. addresses, cart, ads, home slides, offers return everything). Filters are query parameters named per endpoint (see the request column).

## Idempotency and retries

- There is **no `Idempotency-Key` request header** convention. Idempotency is built from natural keys and constraints: one payment/refund/fulfillment/reservation per order; `POST /payments` on an order that already has a payment returns it; `POST /cart/checkout` on an already checked-out cart returns the existing order; checkout sessions are reused for an unchanged basket; webhook events are deduplicated on `(gateway_name, event_id)`; `POST /auth/sync` is idempotent by `firebase_uid`.
- Gateway calls carry a locally generated `idempotency_key` stored on `payment_transactions` (unique). It is sent to Razorpay **only inside `notes`**, not as a Razorpay idempotency header ([`razorpay_gateway.py`](../../backend/app/services/razorpay_gateway.py)); see [REFUNDS](../05-domains/REFUNDS.md) for what that means for lost responses.
- Clients retry `TOKEN_EXPIRED` once after refreshing the token; the mobile auth store retries `/auth/sync` with back-off on transient failures.

## Rate limiting

Only two routes are limited, per client IP, in memory per process: `POST /auth/sync` 20/min, `POST /auth/legacy-migrate` 5/min. Exceeding returns 429 `RATE_LIMIT_EXCEEDED`. The key is the peer address as reported by uvicorn with `--proxy-headers --forwarded-allow-ips "*"`, so it follows `X-Forwarded-For`; whether that can be spoofed depends on the proxy (Caddy overwrites it; behaviour behind an AWS ALB was **not observed** — finding SEC-002 in [DEFECT_LOG](../testing/DEFECT_LOG.md)).

## Cross-cutting headers and middleware

| Header / behaviour | Source |
|---|---|
| `X-Request-ID` accepted (if `[A-Za-z0-9_-]{1,64}`) or generated; echoed on every response; appears in every log line | `request_id.py` |
| Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (relaxed only for `/docs`, `/redoc`), `Referrer-Policy: no-referrer`, `Permissions-Policy: geolocation=(), camera=(), microphone=()`, `Strict-Transport-Security` on https | `security_headers.py` |
| Gzip for responses ≥ 1024 bytes | `main.py` |
| CORS: origins from `ALLOWED_ORIGINS`, credentials allowed, all methods and headers | `main.py` |

## Route design gotchas

- **Registration order is behaviour.** Literal paths must be mounted before `/{id}` catch-alls in the same prefix (`/orders/admin`, `/payments/refunds`, `/payments/admin`, `/payments/online/*`); `router.py` documents the 422 `int_parsing` bug this prevents.
- Customer-facing and admin-facing handlers for the same domain are separate routers with different gates (`/orders/{id}/cancel` vs `/orders/admin/{id}/cancel`).
- A customer asking for another customer's object receives **404**, never 403 ([USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md)).
- Adding or re-gating a route changes `app.openapi()` and fails `test_authz_matrix.py` until [`authz_golden.json`](../../backend/tests/authz_golden.json) is updated deliberately.
