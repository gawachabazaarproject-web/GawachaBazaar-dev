# Multi-replica correctness analysis

**Why this matters here:** `k8s/base/backend-hpa.yaml` scales the backend 1→3 pods at 70 % CPU of a **250 m request** (pod limit 1 core). Scale-out therefore starts at modest load, so >1 replica is an ordinary operating condition, not an edge case. (The Render deployment, if it is also serving, is a separate single instance; the traffic split between Render and AWS is unresolved.)

**Method:** two real `uvicorn` processes (same flags as `start.sh`, 1 worker each) sharing one disposable PostgreSQL 16 database; harness `backend/tests/multiproc/run_scenarios.py`; raw results `docs/testing/evidence/multireplica/results.json` and replica logs. A portable Firebase fake lets both replicas accept the same tokens, like real Firebase tokens verify on any pod.

| # | Question (from the brief) | Verdict | Evidence | Needed design |
|---|---|---|---|---|
| 1 | Rate limiting differs between replicas? | **Confirmed defect** | Same client: 5 allowed on A + 5 on B = 10 vs limit 5/min (S2). Also bypassable via spoofed XFF (S3, SEC-002). | Shared counter. PostgreSQL-backed counter (UPSERT with window) is enough at this scale; Redis not demonstrated necessary. Or accept per-replica limits and tighten XFF trust. |
| 2 | WebSocket clients miss events from another replica? | **Confirmed defect** | S4: event for action on same replica delivered; event for action on the other replica not delivered; DB state correct on both. | PostgreSQL `LISTEN/NOTIFY` fan-out (each replica listens, forwards to its local sockets) or clients poll REST on reconnect/foreground. Push notifications already cover the mobile app. |
| 3 | Reservation-expiry jobs execute redundantly or miss reservations? | **Redundant, not incorrect; none missed** | S5: both replicas expired the same 12 reservations; final state exact; no deadlocks. Existing tests also prove expiry is idempotent and race-safe (`test_concurrency_c/d`, `test_concurrency_39`). | Optional: `SKIP LOCKED` or an advisory lock so one replica sweeps per tick. Not required for correctness. |
| 4 | Multiple replicas process the same order/reservation concurrently? | **Safe (row locks + unique constraints), proven in-process; cross-process not separately executed for payments** | Existing real-thread PostgreSQL tests for last-unit race, duplicate/replayed webhook, webhook-vs-verify, double cancel; new tests for pay-first confirm/webhook races (mutation-tested). Threads use separate DB connections, which exercise the same row-lock/constraint paths as separate pods. Not run: two-process payment webhook (needs a Razorpay fake inside the replica processes). | None required for the DB-level protections. |
| 5 | Inconsistent behaviour during rolling deploys / restarts? | **Confirmed (migrations); sockets drop on restart (by construction)** | S1: one of two concurrent migrators fails in 6/6 rounds; DB always ends correct. Graceful shutdown is 20 s (`--timeout-graceful-shutdown 20`); WebSocket clients must reconnect — reconnect behaviour of the apps was not tested. | Run migrations once (Job / init container) or advisory lock. |

## Distinguishing defects from architectural risks
- **Defects (reproduced):** per-replica rate limit; cross-replica WebSocket loss; migration start-up race; XFF trust.
- **Architectural risks (not defects today):** redundant sweeps; in-process hub design; clock skew between pods affects `expires_at <= now` comparisons by the skew (not measured).
- **Not demonstrated to need Redis or a queue.** Every gap above has a PostgreSQL-only remedy; no new infrastructure is proposed. Any change requires approval.

## Limits of this analysis
Local processes on one machine, not an EKS cluster; ALB behaviour (XFF handling, connection draining, sticky sessions) not observed; Render-vs-AWS traffic path unknown.
