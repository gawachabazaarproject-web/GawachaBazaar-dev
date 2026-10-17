# Performance results (exploratory)

**These are exploratory capacity tests, not production requirements.** No peak-concurrency requirement exists in the repository and none is assumed. Load generator (asyncio + httpx), one uvicorn worker (started like `start.sh`, `DEBUG=false`) and PostgreSQL 16 (Docker, tmpfs) all share one 12-thread / 15.6 GB developer machine, so absolute numbers are not transferable to EKS (pod limit 1 CPU) or Render. Database: disposable `gb_multiproc_test`. Never run against any remote or shared environment.

## Method
`backend/tests/multiproc/perf.py`. Closed-loop virtual users, think time 0.2–0.6 s, 100 seeded customers each with own product/stock/address. Per iteration: catalog list, catalog search, product detail, home-slides, offers, `/auth/me`, add to cart, get cart, (every 8th iteration) **Cash-on-Delivery checkout with real stock reservation**, order list. Users start staggered over a ramp; statistics use only requests that *started* after the ramp. Stop rules: error rate > 5 %, p99 > 8 s, or integrity failure. After each level: no duplicate order numbers, reserved quantity within `[0, quantity]`, every order has a reservation, reserved total equals ordered units of open orders, order count equals successful checkouts.

## Results (valid runs)
| VUs | window | req/s | p50 | p95 | p99 | 5xx / timeouts | server CPU (cores) | RSS | DB conns | integrity |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 (service time) | — | — | 24–63 ms depending on endpoint | | | 0 | | | | |
| 10 | 45 s | 26.2 | 270 ms | 834 ms | 1.76 s | 0 % | 0.78 | 126 MB | 13 | OK |
| 25 | 45 s | 38.8 | 540 ms | 874 ms | 1.11 s | 0 % | 1.10 | 130 MB | 15 | OK |
| 50 | 45 s | 38.4 | 1.01 s | 1.74 s | 2.30 s | 0 % | 1.10 | 135 MB | 15 | OK |
| **100** | 60 s | 15.0 | 30.9 s | 31.3 s | 31.3 s | **100 %** (all `ReadTimeout`) | 0.03 | 142 MB | 15 | OK |

Earlier interrupted run with the same method (10 VU: 33 req/s p99 0.66 s; 25 VU: 29 req/s p99 1.2 s) agrees within run-to-run variance (±25 % on this shared machine). Treat the capacity plateau as **≈ 30–40 req/s per worker** for this mix on this hardware.

**Recovery after the 100-VU overload (load stopped):** the server answered normally again after **362 s** (about 6 minutes) without a restart. Server log of the earlier full run: 714 × `QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30`.

## Findings
- **PERF-001 (Medium, confirmed): connection-pool starvation causes a cliff, not graceful degradation.** The worker's request threadpool (anyio default 40) is larger than the DB pool (`pool_size=5, max_overflow=10` = 15, `pool_timeout` 30 s). Beyond ~50 concurrent users, requests block up to 30 s on a connection; clients time out and retry while abandoned requests keep occupying threads, so a one-minute overload became six minutes of unavailability. CPU is idle during the collapse (0.03 core).
- **Consequence for autoscaling:** the HPA scales on CPU (70 % of a 250 m request). During pool starvation CPU is near zero, so scale-out would not trigger. Between 10 and 50 users CPU is ≈ 1 core, which with the pod limit of 1 CPU means CPU throttling at the same time.
- **Consequence for probes:** liveness/readiness use `/health` (sync, no DB). Under starvation it queues behind the same threadpool; with `timeoutSeconds 5`, `failureThreshold 3`, a pod would likely be killed (~1 min) — recovery by restart, dropping in-flight work. Not observed on Kubernetes; inferred.
- **Per-request cost:** single-user service times 24–63 ms; catalog list/search/detail are the slowest reads (52–63 ms with only 100 products). CPU, not the database, is the limit up to 50 users.
- **No integrity violations at any level**, including the overload.

## Proposed mitigations (none applied; each needs approval)
1. Size DB pool to the threadpool (e.g. `pool_size` 20–30) **or** cap request concurrency (`--limit-concurrency`, or anyio thread limiter) below the pool size.
2. Lower `pool_timeout` (e.g. 3–5 s) so overload yields fast 503s instead of 30 s hangs.
3. Make `/health` not depend on the saturated pool (async handler) and add `/ready` that checks the DB.
4. Autoscale on a signal that sees saturation (requests in flight / latency) in addition to CPU; consider 2 workers per pod or a higher CPU limit.
5. Profile the catalog list (most expensive read).

## Not done
50/100-user runs with a longer soak; Render/EKS environments; DB slow-query analysis; Redis (not present); worker-failure injection; retry-storm modelling; memory-leak soak (RSS rose only 126 → 142 MB over the runs).

## Invalid runs kept for transparency (`evidence/performance/results_INVALID_*.json`)
Run 1: server ran with `DEBUG=true` so SQLAlchemy echoed every statement (47 MB log) — numbers discarded. Run 2: all users started simultaneously on the heaviest endpoint (thundering herd) and the measurement window was too short — discarded; method fixed with staggered ramp and in-window statistics.
