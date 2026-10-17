# Existing Test Inventory

Counts come from `pytest --collect-only` (836 collected, 0 collection errors). Results below were obtained in this audit (see the update section at the end).

## Backend (pytest 8, FastAPI TestClient, real PostgreSQL required, in-memory Firebase fake)

| File | Tests | Apparent scope (from names; deeper review pending) |
|---|---|---|
| test_phase_6_models | 82 | model constraints |
| test_phase_7_models | 63 | model constraints |
| test_phase_4_models / 5_models | 56 / 56 | model constraints |
| test_phase_3_models / 2_models / domain_1_models / 8_1 | 42 / 18 / 17 / 20 | model constraints |
| test_phase_14_payment_state | 45 | payment state machine (pure logic) |
| test_phase_17_supplier_bulk_commerce | 45 | suppliers, bulk orders |
| test_phase_16_fulfillment_delivery | 43 | fulfillment transitions |
| test_phase_13_cart_orders | 39 | cart + orders API |
| test_phase_14_payments | 36 | payments API |
| test_auth | 33 | Firebase-based auth |
| test_phase_15_inventory_reservation_fulfillment | 31 | reservation logic |
| test_razorpay_payments | 27 | Razorpay gateway (fake key `rzp_test_Fake…`) |
| test_phase_11_inventory / 12_packaging | 22 / 21 | inventory, packaging |
| test_phase_18_cancellation_refunds | 18 | cancel/refund |
| test_stock_reserve_and_deletes | 17 | reserve levels, deletes |
| test_online_checkout / promotion_flow / phase_10_catalog | 14 / 14 / 14 | checkout, promos, catalog |
| test_delivery_fee | 12 | delivery fee |
| test_architecture | 10 | layering/architecture rules |
| test_admin_customer_account | 9 | admin customer ops |
| test_phase_9_rbac | 8 | RBAC |
| others (health, config, firebase_gateway, shared_stock_pool, dashboard, security, staff_status, exceptions) | 1–6 each | |

Fixtures (`tests/conftest.py`): session engine from `DATABASE_URL` with `/gawachabazaar` → `/gawachabazaar_test` string replace; `db_session` runs `TRUNCATE … CASCADE` on ~50 tables per test; autouse Firebase fake; autouse limiter reset; `client` overrides `get_db`.

## Gaps visible without running anything

- (Resolved) a generated role × operation matrix now exists (`test_authz_matrix.py`).
- No cross-user (IDOR) test suite identified by name — verify by reading before claiming.
- CORRECTION: ~40 real-thread PostgreSQL concurrency tests exist (last-unit race, duplicate/replayed webhooks, webhook-vs-verify, cancel-vs-deliver, concurrent expiry…). The earlier statement here was wrong.
- No migration-from-previous-revision test; `test_architecture` checks code layout, not the DB schema.
- Assertion quality **not yet reviewed** (risk: status-code-only checks, mocks of the thing under test). Planned sample review in Phase 3.
- 5 grep hits for "skip" are domain words, not `pytest.skip`; no `xfail`/skips found.

## Frontends and mobile
Admin, website, mobile: **no test framework installed, no test files.** Static checks available: `next lint`, `next build`, `tsc`.

## CI
`.forgejo/workflows/deploy.yml` only. No test execution anywhere in automation.

## Update after the audit
| Run | Command / env | Result |
|---|---|---|
| Baseline (836 original + 47 SEC-001 tests) | local PG16 container, loopback | **883 passed, 0 failed, 0 errors, 0 skipped**, exit 0, 535.6 s |
| Final regression (adds 12 tests) | same | **894 passed, 1 xfailed (strict, PAY-001), 0 failed, 0 errors**, exit 0, 518.4 s |
Added test files: `test_db_safety.py` (46), `test_fixture_integrity.py` (1), `test_money_integrity.py` (4: 3 pass + 1 strict xfail), `test_authz_matrix.py` (1, covers 196 operations × 8 identities), `test_cross_customer_access.py` (4), `test_refund_integrity.py` (3). Non-collected tooling: `tests/multiproc/` (multi-replica scenarios, load test). Evidence: `evidence/final_pytest.txt`, `final_junit.xml`, `baseline_*`, `aborted/` (a run that correctly refused an unmarked DB).
