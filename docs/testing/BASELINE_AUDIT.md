# Gawacha Bazaar — Baseline Audit (revision 2, corrected)

Branch `docs-and-primary-testing`, base `07b8450`. Revision 1 contained errors (listed in §8). **Confirmed** = observed in code or by running something. **Suspected** = pattern seen, not reproduced. **Unresolved** = cannot be determined from this machine.

## 1. System as it actually is
- **Payments:** Razorpay (UPI/cards/netbanking via Standard Checkout, server-side order creation, HMAC-verified checkout callback and webhooks, refunds API) **and Cash on Delivery**. **No PhonePe code exists.**
- **No Redis, no queue, no scheduler.** In-process state: slowapi rate-limit counters (`core/rate_limit.py`), WebSocket connection hub (`core/realtime.py`), reservation-expiry sweep as an `asyncio` task per process (`main.py`, every 120 s).
- **Backend:** FastAPI 0.141, SQLAlchemy 2 (sync), psycopg 3, Alembic (single head `f1a2b3c4d5e6`, 40 revisions), Pydantic v2, Firebase Admin token verification; uvicorn 1 worker/process with `--proxy-headers --forwarded-allow-ips "*"`; DB pool `5 + 10 overflow`; 196 HTTP operations (12 public) + 1 WebSocket.
- **Data:** PostgreSQL 16, 51 tables at head; row locks (`FOR UPDATE`) in cart, checkout session, order, inventory, reservation, fulfillment, bulk order; unique constraints on webhook events, payment idempotency keys, `payments.order_id`, `orders.cart_id`, reservation per order.
- **Clients:** `website/` and `Admin/` (Next.js), `mobile/` (Expo, EAS OTA updates). **None of the three has a test framework or test files.**
- **Deployment configuration in the repo:** Forgejo Actions → Docker Hub → **AWS EKS** (`k8s/`, ALB ingress; backend pod limit 1 CPU / 768 Mi; HPA 1→3 at 70 % of a 250 m request; `DEBUG=False`, `APP_ENV=production`). 
- **What is actually serving (probed read-only, one GET each):** `https://api.gawachabazaar.in/health` → 200 `{"environment":"production"}` (uvicorn). `https://api.gawachabazaar.in/api/v1/ping` → 200 from AWS-hosted address; `/health` on that host returns the Next.js 404 page (the ALB routes only `/api/v1` to the backend). **Both look live. Which one the shipped app uses, how traffic is split, and which database each uses are Unresolved. Neither environment is treated as authoritative.** No kubeconfig, AWS credentials or staging access exist here.
- **Workload:** no peak-concurrency requirement is recorded anywhere. The "10,000 monthly users / 1,000 customers" planning figure is unverified and does not determine concurrency. No requirement is invented in this audit.

## 2. Test baseline (actually executed)
| Item | Value |
|---|---|
| Command | `TEST_DATABASE_URL=<127.0.0.1:15432/gawachabazaar_test> venv/Scripts/python.exe -u -m pytest -p no:cacheprovider -v --durations=15 --junitxml=docs/testing/evidence/baseline_junit.xml` |
| Environment | disposable PostgreSQL 16.15 container, tmpfs, loopback only; Firebase and Razorpay faked |
| Result | **883 passed, 0 failed, 0 errors, 0 skipped**, exit code 0 |
| Duration | 535.6 s (pytest) / 543 s wall; started 2026-10-13T21:36:21Z |
| Composition | the **836 pre-existing tests** + 47 added for SEC-001 (46 policy tests, 1 fixture-integrity test). All 836 pass with the SEC-001 changes in place. |
| Evidence | `evidence/baseline_pytest.txt` (full output), `baseline_junit.xml`, `baseline_meta.txt` |
| An earlier run | aborted by me after it hung (cause: my own fixture bug TEST-REG-001); **not** counted. |
Failure classification: none to classify (0 failures). Pre-existing defects, environment issues, test defects and SEC-001-induced failures: 0 / 0 / 0 / 1 (the hang above, fixed and regression-tested before the baseline).
Later additions (money, refund, authorization, cross-customer): see `FINAL`-level totals in `EXISTING_TEST_INVENTORY.md`.

## 3. Confirmed findings (full detail in `DEFECT_LOG.md`)
PAY-001 (High, payment attached to wrong order, xfail test) · SEC-001 (fixed) · CI-001 (High, no gates) · TEST gap on all frontends (High) · SEC-002 XFF spoof (Medium) · OPS-001 per-replica rate limit (Medium) · OPS-003 WebSocket across replicas (Medium) · OPS-002 migration start race (Low–Med) · OPS-004 redundant sweep (Low, safe) · plus config/hygiene items R-14…R-18 in `RISK_REGISTER.md`.
**Not found (after targeted testing):** oversell, duplicate order/payment, webhook forgery/replay acceptance, cross-customer access, over-broad role access (see `RISK_REGISTER.md` R-09…R-12). That is "not reproduced in the tested scope", not a proof of absence.

## 4. Not verified / blocked
Razorpay sandbox end-to-end (no authorized staging; the only test-mode key is in a developer `.env` bound to the AWS demo DB — not used) · EKS behaviour and ALB header handling · VPS-vs-AWS topology · backup/restore · frontend/mobile behaviour · live Firebase tokens (expiry/revocation/project mismatch) · migration from a previous revision with data · soak/long-run behaviour.

## 5. Safe environments now available
Disposable Postgres container `gb-qa-test-db` (recreate after any Docker restart; data is in tmpfs). The pre-existing `gawachabazaar-db` container (port 5433) and the unidentified listener on :5432 were never touched.

## 6. Incidents during the audit (disclosed)
1. A `pytest -x` run before SEC-001 was understood tried to connect to the remote AWS host and failed at fixture setup; no SQL ran.
2. My first multi-process harness leaked `DATABASE_URL`; the new safety guard blocked it as designed.
3. Two invalid load-test runs (SQL echo left on; synchronized start) are kept, labelled `INVALID`, and excluded from conclusions.

## 7. Next highest-priority actions
1. Approve and apply PAY-001 fix (small, no schema change). 2. Add a CI test gate (CI-001). 3. Confirm the production topology (VPS vs AWS) and rotate the DB credential that sat in `backend/.env`. 4. Decide XFF trust and migration-job approach. 5. Provide an opted-in staging environment + Razorpay test keys for sandbox flows. 6. Add frontend smoke tests.

## 8. Corrections to revision 1
- "No concurrency tests found" (TEST-002) was **wrong**: the suite has ~40 real-thread PostgreSQL concurrency tests; retracted.
- Revision 1 said AWS was only a stale config; a live AWS backend reporting `production` exists.
- Revision 1 listed a local Postgres on :5432 as a possible test target; it was never used.
