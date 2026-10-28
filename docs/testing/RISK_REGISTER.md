# Risk Register

Likelihood (L) and impact (I): H/M/L. Severity follows the mission scale and is independent of likelihood. **Evidence** points to what was actually run; "Suspected" means not reproduced.
Environment facts: Razorpay + COD (no PhonePe); no Redis/queue/scheduler; in-process rate limiter, WebSocket hub and reservation sweep; AWS EKS manifests in repo **and** a AWS backend reporting `environment: production` — authoritative environment, traffic split and database topology are **unresolved**; no confirmed peak-concurrency requirement.

| ID | Risk | Sev | L | I | Status | Evidence / where | Test / next step |
|---|---|---|---|---|---|---|---|
| R-01 | Captured online payment attached to an unrelated existing order, no refund (PAY-001) | High | L | H | **Confirmed** | `checkout_session._finalize`; xfail test | fix needs approval |
| R-02 | CI deploys production with no gates (CI-001) | High | H | H | **Confirmed** | `.forgejo/workflows/deploy.yml` | add test/lint/typecheck/migration/scan job, `needs:` for deploy |
| R-03 | No automated tests for website, Admin, mobile (checkout totals, session handling) | High | H | M | **Confirmed** | no test framework in 3 `package.json` | add Playwright (web/admin) + jest-expo (mobile) smoke |
| R-04 | Rate limit per replica (OPS-001) | Medium | H (HPA 1→3) | M | **Confirmed** | multireplica S2 | shared counter in PostgreSQL or accept + tighten |
| R-05 | XFF spoofing bypasses rate limit (SEC-002) | Medium | H* | M | **Confirmed (simulated)** | multireplica S3; *ALB append behaviour per AWS docs, not observed | trust ALB range only |
| R-06 | WebSocket events lost across replicas (OPS-003) | Medium | H (>1 pod) | L–M | **Confirmed** | multireplica S4 | `LISTEN/NOTIFY` or client refetch |
| R-07 | Concurrent migration start crashes one pod (OPS-002) | Low–Med | M | L | **Confirmed** | multireplica S1, 6/6 | migration Job / advisory lock |
| R-08 | Single uvicorn worker is CPU-bound at ≈1 core (≈25–40 req/s on dev hardware); DB pool 5+10 saturates | Medium | M | M | **Measured, exploratory** | `PERFORMANCE_RESULTS.md` | define SLO, profile catalog-list, tune pool/workers |
| R-09 | Double-spend / duplicate order / oversell via concurrency | Critical if present | L | C | **Not reproduced** — extensively tested, mutation-checked | 40+ existing real-thread tests + new pay-first/refund tests | keep in CI |
| R-10 | Webhook forgery/replay | Critical if present | L | C | **Not reproduced** — tested (bad/missing signature, amount/currency mismatch, duplicate, replay, race with verify) | existing + `test_razorpay_payments` | add live-sandbox check when keys/env approved |
| R-11 | Cross-customer data access (IDOR) | High if present | L | H | **Not reproduced** — orders, payments, carts, reservations, fulfillments (existing); addresses, cart items, order sub-resources, push tokens (new) | `test_cross_customer_access.py` | keep |
| R-12 | Missing/wrong role checks on any of 196 operations | High if present | L | H | **Not reproduced** — golden role×operation matrix over every endpoint | `test_authz_matrix.py` | keep; review on every new endpoint |
| R-13 | Test suite destroys a real DB (SEC-001) | High | M | H | **Fixed** | `SEC001_REVIEW.md` | residual items there |
| R-14 | `backend/.env` holds a plaintext remote DB credential; scripts default to it | Medium | M | H | **Confirmed (local file)** | `SEC001_REVIEW.md` §residual | rotate; separate dev DB |
| R-15 | Multiple production-labelled backends — risk of split data, wrong app→API pointing | High | M | H | **Unresolved** | health probe: AWS `environment: production`; AWS ALB routes `/api/v1` | owner to confirm topology; compare app API base in shipped APK |
| R-16 | 41 MB APK tracked in git; stale `JWT_SECRET_KEY` in `.env` | Low | H | L | Confirmed | `git ls-files` | remove from history/repo |
| R-17 | Production-config validator misses DEBUG/ALLOWED_ORIGINS/DB URL defaults | Medium | L | M | Confirmed (code) | `core/config.py` | extend `check_production_secrets` (k8s sets `DEBUG=False`) |
| R-18 | WebSocket token in query string | Low | M | L | Confirmed (code) | `api/v1/realtime.py` | short-lived ticket or first-message auth |
| R-19 | Backup/restore never exercised | High if untested | ? | C | **Not tested** (no environment) | — | restore drill into disposable DB |
| R-20 | Razorpay live sandbox flow unverified end-to-end | Medium | ? | H | **Blocked** — a *test-mode* key exists only in a developer `.env` that also points at the AWS demo DB; no authorized staging | needs opt-in env |
| R-21 | Payments: timeouts after provider success | Medium | L | H | Partly tested (gateway outage keeps PROCESSING; `verify` reconciles; refund-failed leaves `REFUND_FAILED` with log) | extend with reconciliation job test |
| R-22 | AI-generated-code defect classes (Phase 2 research document `AI_ASSISTED_ENGINEERING_RISKS.md` **not yet produced**) | — | — | — | Not started | — | pending |
