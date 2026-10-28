# Test Strategy

## Principles used
Risk first (money, stock, authorization, then everything else) · real PostgreSQL for anything involving locks, constraints or transactions · independent business rules in assertions, not echoes of the implementation · every new guard test is **mutation-checked** (remove the protection, watch the test fail) · nothing weakens an existing assertion · known defects are encoded as `xfail(strict=True)` so they cannot be forgotten or silently fixed.

## Environments
| Env | Use | Status |
|---|---|---|
| Disposable PostgreSQL 16 in Docker (`gb-qa-test-db`, 127.0.0.1:15432, tmpfs, no volume) | all DB tests; `gawachabazaar_test` (suite) and `gb_multiproc_test` (multi-process + load) | available; **recreate if Docker restarts** (data is not persisted) |
| Local multi-process (2 uvicorn replicas) | replica correctness | `backend/tests/multiproc/run_scenarios.py` |
| Local load (1 uvicorn worker, asyncio+httpx driver) | exploratory capacity | `backend/tests/multiproc/perf.py` |
| Razorpay sandbox | payment integration | **blocked** — needs an explicitly opted-in staging environment; a test-mode key is present only in a developer `.env` bound to the AWS demo DB, so it was not used |
| Staging (EKS or AWS) | E2E, performance on real topology | **not available/authorized** |

## Layers and what exists
| Layer | Existing (pre-audit) | Added in audit | Gap |
|---|---|---|---|
| Unit (state machines, pricing, delivery, config) | yes (payment/order/refund state, delivery fee) | DB-safety policy (46) | money/rounding property tests |
| Integration (API+PostgreSQL) | 836 tests, 34 files, all pass | pay-first races, refund races, cross-customer access, fixture integrity | migration-from-previous-revision, schema vs model diff |
| Concurrency (real threads, row locks) | ~40 (last-unit race, webhook duplicates, cancel-vs-deliver …) | pay-first confirm/webhook/last-unit; concurrent refund process/cancel | cross-process payment webhook |
| AuthN/AuthZ | RBAC tests, per-area IDOR tests | **role × operation golden matrix over all 196 operations** | token expiry/revocation against real Firebase |
| Multi-replica | none | 5 scenarios (`MULTI_REPLICA_ANALYSIS.md`) | EKS-level, ALB behaviour |
| Performance | none | 10/25/50/100-VU exploratory | SLO, soak, DB slow-query profile |
| Frontend/mobile | none | — | Playwright for Admin/website checkout & auth; jest-expo + Maestro/Detox for the app |
| Security scanning | none in CI | manual review only | dependency audit (`pip-audit`, `npm audit`), secret scan (gitleaks), container scan (trivy) |

## Release gates recommended (CI job that must pass before deploy)
1. `ruff check` + type check; 2. `pytest` against a PostgreSQL service container with an explicit `TEST_DATABASE_URL` (port ≠ 5432/5433 per policy, marker comment set by the job); 3. `alembic upgrade head` on empty DB and from previous release; 4. frontend `tsc` + `next build` for both Next apps; 5. dependency + secret + image scans; 6. deploy job `needs:` all of the above; 7. post-deploy smoke (`/api/v1/ping`, one authenticated read) with automatic `kubectl rollout undo` on failure.

## Execution
```
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://qa_test:***@127.0.0.1:15432/gawachabazaar_test'   # DB must carry COMMENT 'gb-disposable-test-db'
venv/Scripts/python.exe -m pytest -p no:cacheprovider -v --junitxml=../docs/testing/evidence/<name>_junit.xml
AUTHZ_REGEN=1 pytest tests/test_authz_matrix.py       # only after a human reviews a deliberate access change
```
