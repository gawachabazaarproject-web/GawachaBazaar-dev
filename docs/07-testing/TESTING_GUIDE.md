# Testing Guide

> **Status:** Verified by running the suite on 2026-10-14. Strategy, risk analysis and the QA audit evidence are in the existing [`docs/testing/`](../testing) folder (kept in place; see [docs/README](../README.md#omitted-or-merged-documents)). This guide is the practical "how to run and extend the tests" document.
> **Evidence:** [`backend/tests/`](../../backend/tests) (`conftest.py`, `_db_safety.py`, `firebase_fake.py`, `authz_golden.json`, 42 `test_*.py` modules plus helpers → 899 collected cases on 2026-10-14), [`backend/pyproject.toml`](../../backend/pyproject.toml) (`[tool.pytest.ini_options]`), [`docs/testing/evidence/`](../testing/evidence).

## Frameworks and what exists

| Layer | Tooling | Where | Notes |
|---|---|---|---|
| Backend unit + integration + API + concurrency | pytest 8.4.2, `pytest-asyncio` (`asyncio_mode=auto`), `starlette.testclient.TestClient`, real PostgreSQL | `backend/tests/` | The only automated tests in the repository |
| Security-relevant suites | role × operation golden matrix, cross-customer access, webhook forgery/replay, DB-safety policy | `test_authz_matrix.py`, `test_cross_customer_access.py`, `test_phase_14_payments.py`, `test_razorpay_payments.py`, `test_db_safety.py` | – |
| Multi-replica / load experiments | custom harness, **not collected by pytest** | `backend/tests/multiproc/` | Run by hand against a disposable DB |
| Frontend (`mobile/`, `Admin/`, `website/`) | **none** (root `package.json` lists `playwright`, but no test or config uses it) | – | [QUALITY_GATES](QUALITY_GATES.md) |
| End-to-end, live Razorpay/Firebase | **none** | – | Blocked: no authorised staging ([BASELINE_AUDIT](../testing/BASELINE_AUDIT.md) §4) |

## The disposable-database rule (read before running anything)

The suite **TRUNCATEs about 50 tables between tests**. It therefore refuses to run unless `TEST_DATABASE_URL` points at a database that passes every rule in [`_db_safety.py`](../../backend/tests/_db_safety.py): driver `postgresql[+psycopg]`; one host which is `127.0.0.1`, `localhost` (resolving only to loopback) or `::1`; an explicit port **other than 5432/5433**; database name matching `^[a-z][a-z0-9_]*_test$`; only the query keys `connect_timeout`, `application_name`, `sslmode`; no `PGHOST/PGHOSTADDR/PGPORT/PGDATABASE/PGSERVICE/PGSERVICEFILE/PGPASSFILE/PGOPTIONS` in the environment; not identical to `DATABASE_URL`; and (checked after connecting) the database carries the comment `gb-disposable-test-db`. `conftest.py` also pins `DATABASE_URL` to the validated test database (or an unroutable sentinel) so application code that bypasses the fixtures cannot reach a real database, and blanks the Razorpay/Cloudinary/Google-Maps/Firebase-account variables. **Never weaken this policy.** (Background: incident SEC-001 in [DEFECT_LOG](../testing/DEFECT_LOG.md) — the old suite could have truncated a remote database.)

### Create a disposable database (Docker) — pattern verified on 2026-10-14

```bash
docker run -d --name gb-qa-test-db --tmpfs /var/lib/postgresql/data \
  -p 127.0.0.1:15432:5432 \
  -e POSTGRES_USER=qa_test -e POSTGRES_PASSWORD=<choose-a-local-password> -e POSTGRES_DB=gawachabazaar_test \
  postgres:16-alpine
docker exec gb-qa-test-db psql -U qa_test -d gawachabazaar_test \
  -c "COMMENT ON DATABASE gawachabazaar_test IS 'gb-disposable-test-db'"
```

`tmpfs` means the data vanishes when the container restarts — recreate and re-migrate. The schema is **not** created by the test fixtures; migrate it first:

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://qa_test:<password>@127.0.0.1:15432/gawachabazaar_test'
python -m alembic upgrade head        # schema to head (verified: head f1a2b3c4d5e6)
unset DATABASE_URL
```

## Running

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://qa_test:<password>@127.0.0.1:15432/gawachabazaar_test'
python -m pytest -p no:cacheprovider -q                       # whole suite (≈ 10 minutes)
python -m pytest -p no:cacheprovider -q tests/test_delivery_fee.py    # one file (pure logic, ~0.1 s)
python -m pytest -p no:cacheprovider -q -k "webhook"          # by keyword
python -m pytest -p no:cacheprovider -q --junitxml=<path>     # keep a report (write it outside the repo unless you intend to commit evidence)
python -m ruff check .                                        # lint
```

(Windows: use `venv\Scripts\python.exe -m pytest …`.) `-p no:cacheprovider` avoids a `.pytest_cache` in the repository.

### Last recorded run (2026-10-14, branch `docs-and-primary-testing`, working tree with uncommitted changes)

| Item | Value |
|---|---|
| Command | `python -u -m pytest -p no:cacheprovider -q --junitxml=<scratch>` with `TEST_DATABASE_URL` pointing at the disposable container above (PostgreSQL 16, tmpfs, loopback) |
| Started | 2026-10-14 06:32 UTC; duration 618 s |
| Result | **899 collected: 891 passed, 7 failed, 1 xfailed** (0 errors) |
| Failures | `test_online_checkout.py` ×4, `test_phase_13_cart_orders.py::test_22_successful_checkout` and `::test_26_correct_order_total`, `test_promotion_flow.py::test_percentage_code_previews_and_is_charged_at_checkout` — each fails by exactly Rs 20 because the **default `DELIVERY_BASE_FEE` was changed from 20 to 40 on 2026-10-14**; the same 7 tests pass (7 passed in 12.6 s) when `DELIVERY_BASE_FEE=20` is set in the environment |
| xfail | `test_money_integrity.py::test_online_payment_for_a_basket_already_ordered_by_cod_is_refunded_not_attached` — strict `xfail` encoding open defect PAY-001 |
| Previous recorded run | 894 passed, 1 xfailed, 0 failed ([`docs/testing/evidence/final_pytest.txt`](../testing/evidence/final_pytest.txt)) — before the fee change and before `test_push_send.py` and others were added |
| Not run | `backend/tests/multiproc/*` (manual harness), any frontend check beyond `tsc`, anything against a real Razorpay/Firebase |

Fixing the 7 failures is mechanical (either pin `DELIVERY_BASE_FEE` to 20 in the tests' environment/fixture, or update the expected amounts by +20) and was **not done** because this task is documentation-only.

## Fixtures and conventions ([`conftest.py`](../../backend/tests/conftest.py))

| Fixture | Behaviour |
|---|---|
| `test_engine` (session) | Engine on the validated URL; verifies the live database name and marker |
| `firebase_fake` (autouse) | Installs the in-memory Firebase fake for every test; mint tokens with `fake_firebase.issue(...)` / `auth_headers_for(db, user, **claims)` |
| `reset_rate_limiter` (autouse) | Clears the in-memory slowapi counters between tests |
| `db_session` | Re-verifies the target, `TRUNCATE … RESTART IDENTITY CASCADE` on the listed tables (roles are truncated too — tests create the roles they need), yields a session |
| `client` | `TestClient(app, raise_server_exceptions=False)` with `get_db` overridden to sessions on the test engine; payment tests additionally override `get_payment_gateway` with a fake |

Conventions: tests create their own data (no shared factory module; many files define `_staff(...)`-style helpers); concurrency tests use real threads with separate connections; a **known defect is encoded as `xfail(strict=True)`** so the suite fails when it is fixed; new guard tests were mutation-checked (the protection was removed to prove the test fails — [TEST_STRATEGY](../testing/TEST_STRATEGY.md)).

### Changing routes or access rules

[`test_authz_matrix.py`](../../backend/tests/test_authz_matrix.py) compares the app's reachability for each of the 196 operations and each role (`NONE`, `CUSTOMER`, `WHOLESALER`, `SUPPORT`, `HUB_STAFF`, `OPERATIONS`, `DELIVERY_PARTNER`; `ADMIN` is implied) with `authz_golden.json`. After a **deliberate, reviewed** change, regenerate with `AUTHZ_REGEN=1 python -m pytest tests/test_authz_matrix.py` and commit the diff for review.

### Notes on the test files

- `test_phase_N_*` names follow the historical build phases; `test_phase_14_payments.py` still uses a `FakePNBGateway` (a planned gateway that Razorpay replaced).
- `test_architecture.py` actually tests the app factory, health endpoints, router registration and request-id handling — not code layering.
- The `TRUNCATE` list in `conftest.py` does not name `ads`, `home_slides`, `wishlist_items`, `push_tokens`, `checkout_sessions`; the last three are emptied through `users … CASCADE`, but `ads` and `home_slides` have no foreign keys, so rows seeded by the migration survive between tests. No current test depends on this (none touches those tables beyond the authz matrix).

## Known testing gaps (see [QUALITY_GATES](QUALITY_GATES.md), [RISK_REGISTER](../testing/RISK_REGISTER.md))

No frontend/mobile tests; no live-gateway or live-Firebase test; no migration-from-previous-revision test; no WebSocket behaviour test inside pytest; no automated check that `Admin/lib/permissions.ts` matches the backend map; no coverage measurement configured; performance numbers are exploratory only.
