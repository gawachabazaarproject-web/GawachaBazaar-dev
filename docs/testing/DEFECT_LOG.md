# Defect Log

Status values: **Confirmed** = reproduced with a test or experiment in this audit. **Suspected** = pattern seen in code, not reproduced. Severity uses the mission scale; likelihood is given separately.
"Fix status" is **Not fixed** for everything in application code: no application source was modified during this audit (all mutation experiments were reverted; `git status` shows only test/doc files changed). Fixes below are *proposals awaiting approval*.

---

## PAY-001 — Captured online payment attached to an unrelated existing order, no refund
- **Severity:** High · **Likelihood:** Low (needs a specific user sequence) · **Status:** Confirmed
- **Location:** `backend/app/services/checkout_session.py` `CheckoutSessionService._finalize` (calls `OrderService.checkout`, ignores its `created` flag) and `OrderService.checkout` (returns the user's *latest* cart's existing order when that cart is already `CHECKED_OUT`).
- **Root cause:** `_finalize` assumes that whatever order `checkout()` returns belongs to this checkout session. `CheckoutSession` stores `cart_id`, but nothing compares it with the order's cart. When the cart was already ordered another way (e.g. Cash on Delivery), the existing order is returned with `created=False`; `_attach_paid_payment` finds the COD `Payment` already there and returns it; the session is marked `COMPLETED`.
- **Reproduction (real PostgreSQL):** start online checkout (Razorpay order created) → place the same basket as COD (`POST /cart/checkout`, `POST /payments` COD) → Razorpay captures the online payment → `POST /payments/online/{session}/confirm`.
- **Actual:** HTTP 200; session `COMPLETED`; still exactly one order and one (COD) payment row; **0 refunds**; Razorpay holds the captured amount with no internal record.
- **Expected:** the captured amount is refunded (session `REFUNDED`, HTTP 409) or the request is rejected and flagged for reconciliation; it must never be marked complete against an order it did not pay for.
- **Test:** `tests/test_money_integrity.py::test_online_payment_for_a_basket_already_ordered_by_cod_is_refunded_not_attached` — `xfail(strict=True)`. The assertion is unchanged; the suite goes red the moment the defect is fixed, forcing removal of the marker.
- **Proposed fix (needs approval, no schema change):** in `_finalize`, when `created is False`, load the order and require `order.cart_id == session.cart_id` and that it has no payment with a different `gateway_order_id`; otherwise run the existing `_refund_and_fail` path. Keeps the legitimate retry case (earlier partial run of *this* session) working.
- **Residual risk:** none known beyond the fix; also review the "latest cart" selection in `checkout()` for the case where the user has built a *new* active cart with an identical total.

## SEC-001 — Test fixtures could TRUNCATE a remote database
- **Severity:** High (test-safety) · **Status:** Confirmed → **Fixed in this audit** (approved by owner)
- **Location:** `backend/tests/conftest.py` (old): `TEST_DATABASE_URL = settings.DATABASE_URL.replace("/gawachabazaar", "/gawachabazaar_test")` with guard `"gawachabazaar_test" in url`.
- **Root cause:** database name derived from the developer's `DATABASE_URL`; with the AWS URL in `backend/.env` the result was `…amazonaws.com/gawachabazaar_test_demo_db`, which passes the guard; `db_session` then runs `TRUNCATE … CASCADE` on ~50 tables. Application code that bypasses the `get_db` override (`app/main.py` sweep loop, `app/services/push.py`) also connected to `settings.DATABASE_URL`.
- **Fix:** `tests/_db_safety.py` + `conftest.py` (details in `SEC001_REVIEW.md`). 46 safety tests + mutation checks + independent review. 
- **Disclosure:** one `pytest -x` was run before the problem was understood; it failed at connection and executed no SQL.

## TEST-REG-001 — My own SEC-001 change held table locks (hang), fixed
- **Severity:** n/a (test infrastructure) · **Status:** Confirmed, fixed, regression-tested
- First full run hung: `verify_live_target(connection, …)` ran on the raw `Connection` before the `Session` was created, autobegan an outer transaction, so `session.commit()` after `TRUNCATE` did not commit and `ACCESS EXCLUSIVE` locks blocked every other connection. Fix: `connection.rollback()` after the check. Regression: `tests/test_fixture_integrity.py` (fails if the rollback is removed).

## SEC-002 — `X-Forwarded-For` spoofing bypasses per-IP rate limits
- **Severity:** Medium · **Likelihood:** High if the ALB appends to client-supplied XFF (AWS default per documentation; **not verified against the live ALB**) · **Status:** Confirmed under simulation
- **Location:** `backend/start.sh` (`--proxy-headers --forwarded-allow-ips "*"`) + `app/core/rate_limit.py` (`get_remote_address`).
- **Evidence** (`docs/testing/evidence/multireplica/results.json`): one uvicorn process started with the production flags; 8 requests with a constant `X-Forwarded-For` → 5 allowed then 3×429 (control). 12 requests with a *different leftmost* XFF value each (`10.9.i.1, 203.0.113.9`, the right-hand entry standing for the address an ALB appends) → **0 rate-limited**.
- **Impact:** limits on login-adjacent endpoints (`/auth/legacy-migrate`, 5/min) can be bypassed by any client → password guessing against legacy accounts.
- **Proposed fix:** trust only the ingress/ALB range (`--forwarded-allow-ips <VPC CIDR>`), or key the limiter on the rightmost trusted hop. Needs approval (deployment config).

## OPS-001 — Rate limit is per replica
- **Severity:** Medium · **Status:** Confirmed
- Same client got 5 allowed requests on replica A and 5 more on replica B (limit is 5/min): **10 allowed**. Counters live in each process (`slowapi` in-memory). With HPA 1→3, the effective limit is up to 3× at exactly the moments traffic is high.

## OPS-003 — WebSocket events do not cross replicas
- **Severity:** Medium (UX/consistency; REST remains source of truth) · **Status:** Confirmed
- A socket on replica A received the event for an order cancelled via A and **no event** for an order cancelled via B (both orders were `CANCELLED` in the DB). `core/realtime.py` keeps sockets in a per-process dict. Mobile push notifications (DB-backed tokens) are unaffected.

## OPS-002 — Concurrent `alembic upgrade head` makes one pod fail at startup
- **Severity:** Low–Medium (availability blip; no corruption observed) · **Status:** Confirmed (6/6 rounds)
- Two processes started simultaneously (empty DB → head ×3; 2-revisions-pending → head ×3): in every round exactly one exited 1 with `psycopg.errors.UniqueViolation` on `pg_type`/`pg_class`; the database always ended at head `f1a2b3c4d5e6`. `start.sh` uses `set -e`, so that pod crashes and Kubernetes restarts it (then it is a no-op). 
- **Proposed fix:** run migrations in a one-off Job/init step, or take `pg_advisory_lock` around `alembic upgrade` in `env.py`.

## OPS-004 — Reservation-expiry sweep runs redundantly on every replica
- **Severity:** Low · **Status:** Confirmed, *safe*
- Two replicas each reported expiring all 12 expired reservations (24 reported vs 12 actual). End state correct: 12 `EXPIRED`, `reserved_quantity` 0, free stock unchanged (no double restore), 0 deadlocks, 0 sweep failures. Cost: duplicate work and over-counted log metrics. Optional hardening: `FOR UPDATE SKIP LOCKED` on candidate selection.

## CI-001 — Production deploys with no test, lint, scan or migration gate
- **Severity:** High · **Status:** Confirmed (`.forgejo/workflows/deploy.yml` builds, pushes and rolls out on every push to `main`).

## SEC-003 (Suspected) — `POST /auth/legacy-migrate` unauthenticated password oracle
Rate-limited, but see SEC-002/OPS-001. Account-enumeration differences between responses not yet tested.

## SEC-005 (Low) — WebSocket auth token in the URL query string
`/api/v1/ws/events?token=<Firebase ID token>`: query strings are routinely recorded by proxies and load-balancer access logs. App access log is off in `start.sh`; ALB access logging status unknown.

## PERF-001 — DB-pool starvation turns overload into a 6-minute outage
- **Severity:** Medium (High if real traffic can reach ~50+ concurrent users per pod) · **Status:** Confirmed (exploratory, local)
- **Location:** `backend/app/db/session.py` (`pool_size=5, max_overflow=10`, default `pool_timeout=30`) vs the worker's default 40-thread request pool; `/health` shares that pool.
- **Evidence:** `PERFORMANCE_RESULTS.md`; 100 VUs → 100 % timeouts, CPU 0.03 core, recovery 362 s after load stopped; 714 `QueuePool … timed out` errors in the server log. 10–50 VUs: 0 errors, plateau ≈ 38 req/s.
- **Proposed fix (approval needed):** align pool and concurrency limits, shorten `pool_timeout`, async `/health`, saturation-aware autoscaling.
- **Regression test:** none yet — needs an agreed concurrency target and a stable CI load profile.
