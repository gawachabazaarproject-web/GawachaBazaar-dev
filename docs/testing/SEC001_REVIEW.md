# SEC-001 review — test-database safety

Scope reviewed: full diff of `backend/tests/conftest.py` (modified), new `backend/tests/_db_safety.py`, `backend/tests/test_db_safety.py`, `backend/tests/test_fixture_integrity.py`.

## Policy (all must hold, else every DB fixture raises before any connection)
`TEST_DATABASE_URL` set explicitly · driver `postgresql[+psycopg]` · exactly one host in {127.0.0.1, localhost (must resolve only to loopback), ::1} · explicit port, not 5432/5433 · database name `^[a-z][a-z0-9_]*_test$` · query keys limited to `connect_timeout, application_name, sslmode` · no `PGHOST/PGHOSTADDR/PGPORT/PGDATABASE/PGSERVICE/PGSERVICEFILE/PGPASSFILE/PGOPTIONS` in the environment · not identical to `DATABASE_URL` · **after connecting**, `current_database()` equals the validated name **and** the database carries the comment `gb-disposable-test-db` (so a loopback tunnel to a remote `*_test` database is refused).

## Checks performed
| Question | Result | Evidence |
|---|---|---|
| Is there exactly one destructive statement, and is it guarded? | Yes: only `TRUNCATE … RESTART IDENTITY CASCADE` in `db_session`, preceded by `verify_live_target` on the same connection. Teardown only closes the session/connection. | `grep` of `tests/` + `scripts/` for TRUNCATE/DROP/DELETE FROM/create_all/drop_all/downgrade |
| Alternate engines / cached sessions / background connections? | Engines in the process: `app.db.session.engine` (global), `test_engine`, and sessionmakers bound to `test_engine`/the fixture connection. The global engine feeds the reservation-expiry sweep and `push._send`; it is pinned because `DATABASE_URL` is overwritten in `os.environ` **before** `app` is imported. | `grep create_engine|sessionmaker|SessionLocal`; `test_global_engine_is_pinned_to_loopback…` |
| Does the active test process use the intended DB? | Yes. During the full run, the pytest process had 4 sockets to `127.0.0.1:15432`, 2 loopback self-sockets, **no non-loopback peers**; server-side `pg_stat_activity` showed only `gawachabazaar_test`. | `Get-NetTCPConnection` + `pg_stat_activity` captured during the run |
| External-service credentials disabled in ordinary tests? | `RAZORPAY_*`, `CLOUDINARY_*`, `GOOGLE_MAPS_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON` forced to `""`; Firebase replaced by the in-memory fake; Razorpay by `FakeRazorpay`. Asserted by a test. | `test_global_engine_is_pinned…` |
| Fails closed when misconfigured? | Missing / remote / unsafe → DB fixtures raise `UnsafeTestDatabaseError`; global `DATABASE_URL` becomes `127.0.0.1:1` (unroutable). Verified in a fresh pytest subprocess for three bad configurations. | `test_real_fixtures_refuse_unsafe_configuration_before_connecting[3 cases]` |
| Do the tests detect regressions? | Mutation checks: allow any host → 4 failures; allow port 5432 → 2; loosen DB-name regex → 3; remove live check → 1; remove marker check → covered by marker tests; remove `connection.rollback()` → fixture-integrity test fails. | recorded runs in this session |
| Independent review | A separate reviewer agent attacked the policy (host-parsing tricks, `%`-encodings, IPv4-mapped IPv6, libpq env/query overrides, import order, settings precedence). **No confirmed bypass.** Its gaps (PG* env overrides, deny-list query keys, loopback port-forward) were fixed and tested. One "finding" (`if False:` in the host check) was my own concurrent mutation test, not a defect. | reviewer report |

## A regression my change introduced (found by the first full run)
Calling `verify_live_target` on the raw connection autobegan a transaction that the `Session` then joined, so `session.commit()` after the `TRUNCATE` did not commit and `ACCESS EXCLUSIVE` locks hung the suite. Fixed with `connection.rollback()`; guarded by `test_fixture_integrity.py` (verified to fail without the fix). The first aborted run is **not** counted as a baseline.

## Residual risks (not fixed — outside the test package)
1. Importing `app` from a plain shell/script (not through pytest's conftest) uses whatever `.env` says. Same for `alembic` and `backend/scripts/*.py` (`seed_dummy_data.py`, `create_admin.py`, …): run against `backend/.env`, i.e. the AWS demo database, if invoked by hand.
2. A deliberately mis-labelled remote database (marker comment + `*_test` name) reached through a loopback tunnel would pass; this needs intent, not accident.
3. `localhost` is resolved once at validation and again by libpq (theoretical race).
4. `backend/.env` contains a plaintext remote database credential on disk (gitignored). Consider rotating it, since it was visible to tooling during this audit; I did not print or alter it.
