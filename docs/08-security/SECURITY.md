# Security

> **Status:** Partially verified. **Last verified:** 2026-10-14 by source review and the existing automated tests; **no penetration test, dependency scan, live-environment probing beyond three read-only health requests, or destructive test was performed.** Findings from the earlier QA audit are in [`docs/testing/DEFECT_LOG.md`](../testing/DEFECT_LOG.md) and [`RISK_REGISTER.md`](../testing/RISK_REGISTER.md); they are referenced, not repeated.
> Related: [THREAT_MODEL](THREAT_MODEL.md), [SECRETS_MANAGEMENT](SECRETS_MANAGEMENT.md), [PRIVACY](PRIVACY.md), [AUTHENTICATION](../05-domains/AUTHENTICATION.md), [USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md).

Labels: **Verified** (code read *and* exercised by a passing test), **Partially verified** (code read, indirect or no test), **Requires investigation** (cannot be decided from the repository), **Gap** (confirmed weakness).

## 1. Control inventory

| Area | Control (what the code does) | Label | Evidence |
|---|---|---|---|
| Authentication | Firebase ID token verified on every request (signature, expiry, audience); user must be `ACTIVE`; email/password users need a verified email | Verified (with a faked Firebase) | `core/firebase.py`, `dependencies/auth.py`, `test_auth.py`, `test_firebase_gateway.py` |
| Revocation | Per-user revoked/disabled check, cached 60 s; **silently skipped if the lookup fails or no service account is configured** (tokens then stay valid until expiry, ≤ 1 h) | Gap (by design, undocumented until now) | `FirebaseAdminGateway._assert_not_revoked` |
| Authorization | Live role lookup per request; static permission map; every one of the 196 operations' role reachability is snapshot-tested | Verified | `test_authz_matrix.py` + `authz_golden.json`; derived Auth column matched the snapshot for 180/180 gated operations on 2026-10-14 |
| Object-level access (IDOR) | Customer queries filter by `user_id`; other customers' objects return 404; tests for orders, payments, carts, reservations, fulfilments, addresses, cart items, order sub-resources, push tokens | Verified | `test_cross_customer_access.py`, earlier suites |
| Admin-only operations | Refunds, order cancellation, catalogue, promotions, staff, content are ADMIN-only; self-lockout protections | Verified (API); UI Unverified | roles document |
| Input validation | Pydantic v2 request models (types, lengths, ranges); `CHECK` constraints in the database; SQL through the ORM (parameterised) | Verified | schemas, models; no raw SQL string-built from input was found in `app/` |
| Output handling | JSON only; security headers on every response (`nosniff`, `X-Frame-Options: DENY`, `CSP default-src 'none'`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, HSTS on https); React escapes output (no `dangerouslySetInnerHTML`/`innerHTML` found in `Admin/`, `website/`, `mobile/`) | Verified (headers via code); Partially (frontends untested) | `security_headers.py`, grep |
| Admin / website headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Permissions-Policy`, and `Referrer-Policy` (`no-referrer` on Admin, `strict-origin-when-cross-origin` on the website); **no CSP** on either (documented follow-up) | Partially verified | `Admin/next.config.mjs`, `website/next.config.mjs` |
| CORS | Allow-list from `ALLOWED_ORIGINS`, credentials allowed, all methods/headers; applied only if the list is non-empty. The **code default allows `localhost:3000/5173`** | Partially verified | `main.py`, `config.py`; production value on the live service unknown |
| Rate limiting | slowapi, in-memory per process: `/auth/sync` 20/min, `/auth/legacy-migrate` 5/min per client IP; nothing else is limited | Verified (single process) / Gap (multi-replica, XFF) | `rate_limit.py`, SEC-002, OPS-001 |
| Abuse protection | Client-side OTP throttles (60 s, 3 sends/15 min) plus Firebase's own limits; no CAPTCHA/App Check; no limit on checkout, payment or upload routes | Partially verified | `authStore.ts`; recommendation in `deploy/FIREBASE_AUTH.md` (App Check) is not implemented |
| Webhook authenticity | HMAC-SHA256 over the raw body with a constant-time compare; deduplication; amount/currency checks | Verified (fake gateway) | [WEBHOOKS](../03-api/WEBHOOKS.md) |
| Payment integrity | Server-side pricing; Razorpay re-queried before marking paid; signature checks; refunds admin-approved | Verified (fake gateway); PAY-001 open | [PAYMENTS](../05-domains/PAYMENTS.md) |
| File upload | Declared content type in {jpeg, png, webp, gif}, ≤ 8 MB, stored on Cloudinary (not on the server); **no content sniffing**; no dimension check | Partially verified | `image_upload.py` |
| Sensitive data in logs | Token query values redacted in uvicorn and Caddy logs; request log omits query strings; push tokens truncated in warnings; no passwords handled | Verified (redaction unit test); Partially (other log lines not audited exhaustively) | `logging.py`, `test_security.py`, Caddyfile |
| Secrets in the repository | `.env*`, service accounts, keystores, `google-services.json` ignored and none tracked; **but a live-looking API key is committed in `.mcp.json`** | **Gap** | [SECRETS_MANAGEMENT](SECRETS_MANAGEMENT.md) |
| Production start-up validation | Refuses to start without `FIREBASE_PROJECT_ID`, or with half-configured Razorpay; **does not check** `DEBUG`, `ALLOWED_ORIGINS`, or the default database URL | Partially verified | `config.py` (R-17) |
| Container hardening | Backend, Admin and website images run as non-root; only Caddy publishes ports in the compose stack; backend port is never published | Verified (files) | Dockerfiles, compose |
| Transport | Caddy automatic HTTPS + HSTS (VPS stack); ALB HTTPS (EKS overlay); Render terminates TLS (observed `https://`) | Partially verified | Caddyfile, `k8s/overlays/aws/ingress.yaml` |
| API docs exposure | `/docs`, `/redoc`, `/openapi.json` disabled when `APP_ENV=production` (a live probe of the Render service on 2026-10-14 returned 404 for `/docs`) | Verified | `main.py` |
| Test safety | Suite cannot truncate a non-disposable database | Verified | `_db_safety.py`, 46 policy tests |
| Dependency / container scanning | None configured | Gap | [QUALITY_GATES](../07-testing/QUALITY_GATES.md) |
| Audit trail | 47 admin actions recorded with actor, target and states; no general reader | Partially verified | [ADMIN_OPERATIONS](../05-domains/ADMIN_OPERATIONS.md) |

## 2. Open findings (all unfixed unless stated)

| ID | Severity (assessed) | Finding | Where documented |
|---|---|---|---|
| SECR-1 | **High** | A real-looking third-party API key is committed in `.mcp.json` (tracked since commit `bff7053`); it is in every clone and in history, and was echoed to a terminal during this audit. Rotate it and untrack the file | [SECRETS_MANAGEMENT](SECRETS_MANAGEMENT.md) |
| PAY-001 | High | Captured online payment can attach to an unrelated existing order with no refund | [DEFECT_LOG](../testing/DEFECT_LOG.md) |
| CI-001 | High | Production deploys with no test/lint/scan gate | [QUALITY_GATES](../07-testing/QUALITY_GATES.md) |
| SEC-002 / OPS-001 | Medium | `X-Forwarded-For` spoofing and per-replica counters undermine the only two rate limits | DEFECT_LOG |
| REV-1 | Medium | Revocation/disable checks are skipped without the Firebase service account — the situation of any deployment that removed `FIREBASE_SERVICE_ACCOUNT_JSON` (as was done on 2026-10-14 to restore sign-in) | [AUTHENTICATION](../05-domains/AUTHENTICATION.md) |
| PRIV-1 | Medium | Unmasked customer phone and email in staff order detail (`orders.read`), searchable by phone | [ORDERS](../05-domains/ORDERS.md) |
| CFG-1 | Medium | Defaults are development-oriented (`APP_ENV=development`, `DEBUG=True`, localhost CORS); a missing environment variable would expose `/docs`, enable SQL echo and use dev CORS. The Kubernetes top-level manifest even sets `APP_ENV=staging` | `config.py`, `k8s/backend-deployment.yaml` |
| SEC-003 | Low–Medium (suspected) | `legacy-migrate` is an unauthenticated password oracle (rate-limited; enumeration differences untested) | DEFECT_LOG |
| SEC-005 | Low | WebSocket token in the URL query (redacted in app and Caddy logs; an ALB would log it unless disabled) | DEFECT_LOG |
| UPL-1 | Low | Upload type is trusted from the declared content type; no image decoding or size/dimension validation beyond bytes | `image_upload.py` |
| HLTH-1 | Low | `/health/db` is public and reveals database connectivity | `main.py` |
| ADM-1 | Low | No CSP on Admin/website; Admin image built by Docker/CI has no Firebase config ([ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md)) | `Admin/next.config.mjs` |
| HIST-1 | Low | 41 MB APK committed; local untracked `backend/.env` holds a plaintext hosted-database credential (R-14); a stale `JWT_SECRET_KEY` line existed there | RISK_REGISTER |

SEC-001 (test fixtures could truncate a remote database) is **fixed** ([SEC001_REVIEW](../testing/SEC001_REVIEW.md)).

## 3. What was *not* assessed

Real Firebase and Razorpay behaviour; the production Render/EKS/VPS configuration and network exposure; TLS configuration; Cloudinary access settings; Expo/FCM credential handling; mobile app binary hardening (obfuscation, certificate pinning, root detection — none found in the repository); SQL injection beyond reading the ORM usage; business-logic fraud scenarios beyond those covered by the tests; denial of service (only exploratory load tests exist — [PERFORMANCE_RESULTS](../testing/PERFORMANCE_RESULTS.md), including the pool-starvation cliff PERF-001).

## 4. Reporting and response

No security contact, disclosure policy or incident process is defined in the repository. See [INCIDENT_RESPONSE](../09-deployment-operations/INCIDENT_RESPONSE.md).
