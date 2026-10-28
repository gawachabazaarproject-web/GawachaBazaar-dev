# AWS production plan - month one (about 1,000 users)

> **Status (2026-10-27): preparation only. Nothing has been deployed to AWS.** No AWS account, CLI or credentials were available, so every statement about AWS behaviour below is either (a) a list price downloaded from AWS's public price list, (b) a design decision, or (c) explicitly marked **NOT VERIFIED**. Everything marked *measured* was measured on the developer's Windows laptop (13th-gen Intel i5, Docker Desktop) with the test environment described in section 6 - **not on AWS and not on production hardware**.
>
> Related: [DELIVERY](../05-domains/DELIVERY.md) (routing/pricing), [DEPLOYMENT](DEPLOYMENT.md) (the existing Contabo/EKS descriptions), [`docker-compose.aws.yml`](../../docker-compose.aws.yml), [`deploy/osrm/`](../../deploy/osrm), [`.forgejo/workflows/`](../../.forgejo/workflows).

## 1. Current architecture (audited)

| Part | What the repository contains |
|---|---|
| Backend | FastAPI 0.141, SQLAlchemy 2 (sync), psycopg 3, **one uvicorn worker by design** (rate limiter, WebSocket hub and reservation sweep are in-process) |
| Database | PostgreSQL 16; 44+ Alembic revisions; `start.sh` and a `migrate` one-shot both run `alembic upgrade head` |
| Redis | **Only** the delivery route cache (`services/routing/cache.py`). Rate limiting is in memory, not Redis (audited by grep) |
| Routing / geocoding | OSRM (`OSRM_BASE_URL`), Nominatim; no Google |
| Auth | Firebase Authentication (backend verifies ID tokens; roles read from the DB per request) |
| Payments | Razorpay (pay-first sessions + webhook, idempotent: unique `(gateway, event_id)`, `idempotency_key`, one payment/order) |
| Images | **Cloudinary** (admin upload through FastAPI, 8 MB cap, JPEG/PNG/WebP/GIF by client content type). No file storage on the server disk |
| Background jobs | One in-process reservation-expiry sweep (lifespan task); push via Expo |
| Email / SES / SQS / Lambda | none in use |
| Existing deployment | Contabo single-VPS compose (`docker-compose.prod.yml`, Caddy, Postgres container, nightly `pg_dump`), plus EKS manifests (`k8s/`) and a Forgejo workflow that deploys to EKS on every push to `main` with no checks (KNOWN_ISSUES CI-001) |
| Clients | Expo customer app; Next.js Admin (port 3001) and promo website (port 3000), Node 22 standalone images |

## 2. Capacity assumptions (estimates, not measurements)

No real traffic exists, so these are planning numbers. **Estimate:** 1,000 registered users -> about 150 daily active (15%) -> about 30 active in the busiest 10 minutes -> each active user makes roughly one API call every 3-4 s while browsing -> **about 8-10 requests/s at the busiest moment, well under 1 request/s on average**; about 30-60 orders/day (assuming 20-40% of daily actives order); checkout under 1 request/minute on average and a handful per minute at peak; delivery quotes about 1 per active user per session, mostly served from the route cache; OSRM calls only on a cache miss (distinct address cell), a few per hour. Images are served by Cloudinary, not AWS.

## 3. Decision: smallest sensible AWS footprint

```
                       EXTERNAL (not AWS)
        Firebase Auth     Razorpay     Cloudinary     Nominatim (rare, user-triggered)
             ^               ^             ^                ^
             |               |             |                |
 Customer apps / Admin ---HTTPS 443--> [ PUBLIC  EC2 t4g.medium, Elastic IP ]
 (Expo, browsers)                         |  Caddy :80/:443  (only published ports)
                                          |    -> backend :8000   (FastAPI, 1 worker)  ----> Razorpay/Firebase/Cloudinary (outbound 443)
                                          |    -> admin   :3001   (Next.js)
                                          |    -> website :3000   (Next.js)
                                          |  PRIVATE docker network `backend` (no published ports):
                                          |    redis :6379   route cache, 64 MB, allkeys-lru, no persistence
                                          |    osrm  :5000   prebuilt Nagpur data, read-only volume
                                          v
                                  [ PRIVATE subnet  RDS PostgreSQL 16, db.t4g.micro, not publicly accessible ]
                                          5432 <- security group of the EC2 instance only
```

| Service | Why needed | Why a cheaper/simpler option was rejected | Resources (measured unless noted) | Failure mode | Scaling path |
|---|---|---|---|---|---|
| **EC2 `t4g.medium`** (2 vCPU Graviton, 4 GB), 30 GB gp3, Elastic IP | Runs the existing compose stack unchanged (the repo already deploys this way on one VPS). One host holds backend + Redis + OSRM + Caddy + Admin + website | Lambda/API Gateway: in-process WebSocket + single-worker design, cold starts. Fargate/ECS: ~2-3x the cost for no benefit at this size, plus an ALB. App Runner: no sidecar Redis/OSRM, no WebSocket story. `t4g.small` (2 GB) fits the measured memory (about 190 MB backend + 90 MB OSRM + 5 MB Redis + Caddy) but leaves little headroom for the two Next.js servers (**not measured**) and the OS - $8/month saved is not worth the risk | Backend RSS <= 176 MB at 100 concurrent users; OSRM 89 MiB; Redis 5 MiB; backend CPU about 1.2-1.5 cores when saturated | Instance failure = full outage until replaced (single host, accepted for month one; AMI/snapshot + compose = rebuild in minutes). `restart: unless-stopped` covers container crashes | Move up one size; then split OSRM/Redis to a second instance; then ALB + 2 backends once rate limit/WebSocket/sweep move to Redis |
| **RDS PostgreSQL 16 `db.t4g.micro`**, 20 GB gp3, single-AZ, private | Managed backups + PITR + patching; the user asked for RDS | Postgres in Docker on the EC2 box: no PITR, backups are our job. Multi-AZ doubles the instance cost ($15.33 -> $30.66) - **not** needed for month one if an RPO of 5 minutes and a restore time of 20-40 minutes is acceptable (decision for the owner) | DB time per query < 3 ms on the 1,000-user seed; max 25 connections under load | AZ/instance failure = restore from PITR (RTO tens of minutes, **NOT VERIFIED on AWS**) | Resize instance (minutes of downtime) or enable Multi-AZ; add read replica only if reports are heavy |
| **Redis in Docker** (not ElastiCache) | Shared route cache + single-flight lock | ElastiCache `cache.t4g.micro` is $11.68/month for a cache holding ~1 MB; the app already works without it (in-process fallback, circuit breaker) | 5 MiB RSS, 64 MB `maxmemory`, `allkeys-lru`, no persistence | Redis down = more OSRM calls, same fees (tested live) | ElastiCache only when a second backend instance needs a shared limiter/WebSocket state |
| **OSRM in Docker** | Road distance (core delivery rule) | Public OSRM: no SLA. ECS/EC2 of its own: not needed - 89 MiB RSS | 98 MB data, 89 MiB RAM, 414-452 req/s per CPU (measured) | OSRM down = quotes/checkout for paid-delivery baskets return 503 (by design); cached routes still answer | Second container/instance; widen bbox |
| **Caddy** (in compose) | TLS (Let's Encrypt), HSTS, compression, redirects | CloudFront/ALB add cost and a second TLS layer; not needed for an API | tens of MB (not measured) | Cert renewal failure = TLS errors; monitor expiry | Put CloudFront in front of Admin/website only if static traffic grows |
| **EBS gp3 30 GB** | OS, images, OSRM data (0.1 GB), logs | - | - | Volume loss = rebuild from AMI/compose (state is in RDS) | Grow volume |
| **Route 53** hosted zone | DNS | Registrar DNS works too; $0.50/month is negligible | - | - | - |
| **CloudWatch** (alarms, agent metrics, capped logs) | Minimum monitoring (section 12) | Self-run Prometheus is more to operate | about 8-15 alarms | - | - |
| **SSM Parameter Store** (SecureString) | Secrets | Secrets Manager costs $0.40/secret/month and gives rotation we do not need yet | - | - | Secrets Manager later for RDS rotation |
| **S3** | **Not used in month one** (Cloudinary stays; DB backups are RDS's) | - | - | - | S3 + CloudFront if images leave Cloudinary |
| **NOT used:** ALB ($0.0239/h = $17.45/mo + LCU), NAT Gateway ($0.056/h = $40.88/mo + $0.056/GB), ElastiCache, ECS/Fargate, Lambda, API Gateway, Cognito, CloudFront, SQS/EventBridge/SES | No concrete requirement; the EC2 host sits in a public subnet with a security group, so it needs no NAT | | | | |

## 4. Monthly cost (USD, ap-south-1, on-demand list prices)

Prices come from AWS's public price list files downloaded 2026-10-27 (EC2 published 2026-10-23, RDS 2026-10-20): t4g.small $0.0112/h, t4g.medium $0.0224/h, t3.medium $0.0448/h, RDS db.t4g.micro PostgreSQL single-AZ $0.021/h (Multi-AZ $0.042/h), RDS gp3 $0.131/GB-month single-AZ ($0.262 Multi-AZ), EBS gp3 $0.0912/GB-month, public IPv4 $0.005/h, CloudWatch alarm $0.10, custom metric $0.30, log ingestion $0.67/GB, log storage $0.03/GB-month, internet data transfer out $0.1093/GB (first 10 TB), Route 53 zone $0.50. 730 hours/month. **Not in the price list / not included:** RDS backup storage beyond the free allowance (AWS gives free backup storage up to the provisioned size - **not verified here**), any data-transfer free tier (ignored, so costs are slightly overstated), taxes (GST on AWS invoices), Reserved/Savings Plan discounts, Firebase phone-auth SMS, Razorpay fees, Cloudinary.

| Line | Minimum | Expected | Higher than expected | Type |
|---|---|---|---|---|
| EC2 (t4g.small / t4g.medium / t4g.medium) | 8.18 | 16.35 | 16.35 | fixed |
| EBS gp3 (20 / 30 / 50 GB) | 1.82 | 2.74 | 4.56 | fixed |
| Public IPv4 | 3.65 | 3.65 | 3.65 | fixed |
| RDS instance (single / single / Multi-AZ) | 15.33 | 15.33 | 30.66 | fixed |
| RDS storage (20 / 20 / 50 GB) | 2.62 | 2.62 | 13.10 | fixed (grows) |
| CloudWatch alarms (6 / 8 / 15) | 0.60 | 0.80 | 1.50 | fixed |
| CloudWatch custom metrics (0 / 3 / 3) | 0.00 | 0.90 | 0.90 | fixed |
| CloudWatch logs (1 / 3 / 10 GB per month) | 0.70 | 2.10 | 7.00 | usage |
| Data transfer out (2 / 8 / 50 GB) | 0.22 | 0.87 | 5.46 | usage |
| Route 53 | 0.50 | 0.50 | 0.50 | fixed |
| **Total** | **33.62** | **45.86** | **83.69** | |

About 85% of the expected total is fixed (EC2, RDS, IPv4, EBS); the dominant lines are RDS and EC2. Avoided by design: NAT $40.88, ALB $17.45, ElastiCache $11.68 per month. The 1-year Savings Plan / Reserved options could lower EC2/RDS but were not priced here.

## 5. Security architecture

| Resource | Inbound | Outbound |
|---|---|---|
| **EC2 SG `gb-app`** | TCP 80 and 443 from `0.0.0.0/0` (Caddy; 80 only for the HTTPS redirect/ACME). **No port 22**: administer through **SSM Session Manager** (instance profile with `AmazonSSMManagedInstanceCore`). If SSH is unavoidable: 22 from the admin's `/32` only, key-only, and document the exception | 443 to the internet (Firebase, Razorpay, Cloudinary, Nominatim, package registries), 5432 to `gb-rds` |
| **RDS SG `gb-rds`** | TCP 5432 from `gb-app` **only** (SG reference, not CIDR). `PubliclyAccessible=false`, private subnet group, `rds.force_ssl=1` / `sslmode=require` in `DATABASE_URL` | none needed |
| **Redis, OSRM** | not on any security group at all: they listen on the docker `backend` network and publish no host ports (verified in the rendered `docker-compose.aws.yml`: only `caddy` has `ports`) | - |
| **IAM** | EC2 instance profile: `AmazonSSMManagedInstanceCore` + a policy allowing `ssm:GetParameter(s)` on `arn:...:parameter/gawacha/<env>/*` and `kms:Decrypt` on that key; CloudWatch agent write policy. No `*:*`, no S3/RDS admin. Humans: SSO/IAM users with MFA; CI never holds AWS keys (it deploys over SSM/SSH to the host) | - |
| **Secrets** | SSM Parameter Store `SecureString` under `/gawacha/<env>/…`; a small script on the host renders `.env.aws` (mode 600, owned by the deploy user) at deploy time. Nothing in Git, nothing baked into images (images are built from the repo without `.env`) | - |

Mobile app: contains only public identifiers (API base URL, Firebase web config, Google web client id, Razorpay key id comes from the API). Never AWS keys, DB/Redis/OSRM credentials or the Firebase service account. Network: one VPC, one public subnet (EC2) + two private subnets in different AZs (RDS subnet-group requirement); **no NAT**, no VPC endpoints needed at this size.

## 6. Measured results (test environment - not AWS)

**Environment:** Windows 11 laptop, i5-13420H (12 logical CPUs), Docker Desktop (8 GB VM); PostgreSQL 16 native on loopback; Redis 7-alpine container; OSRM `osrm-backend` v26.10.0 container (1 CPU, 384 MB limit) with the Nagpur extract; one uvicorn worker of the real app with **Firebase replaced by a fake that accepts `lt-<n>` tokens** (`scripts/loadtest_server.py`, refuses to start in production). Load generator on the same machine. 1,000 users, 200 products (400 variants), 1,000 addresses seeded. Each virtual user picks a user and loops: browse 60% (categories + product list + product), cart + delivery quotes 25%, checkout 5%, order history 10%, with the think time shown. Route cache flushed before every run. **These numbers do not represent production capacity.** A Graviton2 core is slower than this laptop's core; the factor was **not measured**.

### 6.1 API (final configuration: pool 12+12, in-flight cap 24, 60 s per run)

| Virtual users (think time) | req/s | Errors | p50 / p95 / p99 of the slowest common read (`GET products`) | Backend RSS max | CPU max | DB connections max | Redis memory |
|---|---|---|---|---|---|---|---|
| 10 (1-3 s) | 13.2 | 0 | 43 / 118 / 286 ms | 150 MB | 108% of one core | 11 | 1.1 MB |
| 25 (1-3 s) | 30.8 | 0 | 79 / 249 / 859 ms | 158 MB | 145% | 24 | 1.2 MB |
| 50 (1-3 s) | 40.2 | 0 | 392 / 1354 / 1751 ms | 164 MB | 150% | 25 | 1.2 MB |
| 100 (1-3 s) | 40.6 | 0 | 1603 / 2409 / 2682 ms | 171 MB | 146% | 25 | 1.2 MB |
| 100 (no think time) | 47.0 | 0 | 1995 / 2575 / 2865 ms | 176 MB | 146% | 25 | 1.3 MB |

Per-endpoint p50/p95/p99 for every run are in `scripts/loadtest_api.py` output (reproduce with the commands in its docstring). At 25 users the heaviest calls were checkout (p50 308 ms, p95 1.8 s) and cart add (p50 111 ms); the delivery quote was p50 102 ms / p95 319 ms. Throughput saturates at about **40-47 req/s on this machine because one Python process is CPU-bound** (about 60 ms of CPU per request as seen by a sampling profiler, whose own overhead inflates the absolute figure: FastAPI route matching about 28% of CPU - it walks about 200 routes, 146 `matches()` calls per request - and SQLAlchemy ORM overhead; PostgreSQL itself used < 3 ms per query). Redis: 8,460 commands for roughly 5 minutes of mixed load, keys 93.

**Findings from the load test (all fixed unless stated):**
- **P1 (fixed): collapse at 100 concurrent users.** With the old pool (5+10) 92% of requests failed (500/ReadError, p50 about 20 s): sync endpoints hold a connection for their whole life while waiting for AnyIO thread slots, and threads blocked waiting for a connection - a stall that only ended at `pool_timeout`. Fix: an in-flight cap (`MAX_INFLIGHT_REQUESTS=24`, `app/core/concurrency.py`) at the pool size (`DB_POOL_SIZE=12`+`DB_MAX_OVERFLOW=12`), shedding with `503 SERVER_BUSY` + `Retry-After` after 15 s of queueing. Result above: 0 errors at 100 users. With the 20+20 pool and no cap the same run also had 0 errors, but that needs 40 connections; the cap makes the guarantee structural.
- **P2 (fixed): rate-limit artifact.** The first load-test run hit 429s because my fake tokens were shorter than the 20-character threshold of the per-user rate-limit key and fell back to the shared IP key (real Firebase tokens are about 900 characters). Not a product bug.
- **P2 (open): per-request CPU.** Throughput per core is the scaling limit. Options (not done, need a product decision): short in-process TTL cache for the anonymous catalog GETs (60% of the mix; trades up to N seconds of price/stock staleness), flatten/reorder the route table, or a second worker once the in-process state (rate limiter, WebSocket hub, reservation sweep) is moved to Redis.

### 6.2 OSRM (Nagpur extract, via the AWS compose service: `cpus: 1.0`, `mem_limit: 384m`, private network, load through a temporary socat proxy; 20 s per level, random point pairs in the Nagpur box)

| Concurrency | req/s | p50 | p95 | p99 | Non-OK / client errors | Peak CPU | RAM |
|---|---|---|---|---|---|---|---|
| 10 | 422 | 19.7 ms | 49.2 ms | 61.7 ms | 0 / 1 (transient connect error through the proxy) | 100.6% | 86.5 MiB |
| 50 | 452 | 95.7 ms | 231 ms | 334 ms | 0 / 0 | 103.9% | 88.7 MiB |
| 100 | 414 | 177.9 ms | 515 ms | 720.8 ms | 0 / 0 | 76.3% | 89.4 MiB |

The same test on the full western-India extract (222 MB source, 2 CPUs): 421-481 req/s, 1.8 GiB RSS - the clipped extract needs 20x less RAM for the same answers (identical distances on 3 test routes: 6 713.7 m, 11 362.5 m, 16 108.7 m). Month-one demand (a few route lookups per hour after the cache fills) is five orders of magnitude below this capacity.

**Restart test (compose):** `docker compose restart osrm` -> serving a correct route again in about 4.3 s (includes launching the curl probe container). **Data volume is read-only**; nothing is downloaded or built at start.

### 6.3 DEL-14: where the CPU goes, and 1 vs 2 workers (decision: keep 1 worker, no catalog cache)

Profile (yappi, CPU clock, in-process TestClient, 40 calls per endpoint, 1,000-user dataset; shares of own-time - absolute ms are inflated by the profiler): SQLAlchemy ORM 38-43% on the catalog reads and 47% on checkout; PostgreSQL driver 4-16%; route matching 5-39% (noisy); Redis 0-2%; OSRM/HTTP client 0-3% (routes were cache hits); pydantic/JSON do not show up as separate buckets. About 11-18 ms of profiled CPU per read request and about 35 ms for checkout. **The bottleneck is ORM object construction, not Redis, OSRM or serialization.**

| Workers | Virtual users | req/s | Errors | RSS total | CPU | DB connections (max) | `GET products` p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|
| 1 | 25 | 33.2 | 0 | 160 MB | 123% | 21 | 42 / 408 / 468 ms |
| 1 | 50 | 51.4 | 0 | 165 MB | 150% | 24 | 232 / 616 / 890 ms |
| 1 | 100 | 49.2 | 0 | 171 MB | 149% | 25 | 1197 / 1584 / 1721 ms |
| 2 | 25 | 33.9 | 0 | 421 MB | 170% | 27 | 31 / 139 / 411 ms |
| 2 | 50 | 45.6 | 0 | 430 MB | 175% | 34 | 321 / 919 / 1192 ms |
| 2 | 100 | 70.6 | 0 | 438 MB | 219% | 40 | 727 / 1255 / 1350 ms |

Same laptop and method as 6.1; run-to-run variation is large (the 1-worker/100-user rate was 40.6 req/s in the earlier run). RSS for 2 workers includes the supervisor process and double-counted shared pages. Two workers only help once the single worker is saturated (+43% at 100 users) and do nothing at 25-50 users. **Maximum DB connections = workers x (pool 12 + overflow 12) = 24 with one worker, 48 with two** - both below the RDS `db.t4g.micro` limit (about 112, NOT VERIFIED on AWS).

**Decision:** one worker. The expected month-one peak (about 10 req/s, an estimate) is a fraction of the measured 33-51 req/s, and a second worker would break the in-process rate limiter, WebSocket hub and reservation sweep. No catalog cache: it would remove roughly a quarter of total CPU (catalog reads are 60% of the modelled traffic and ORM is about 40% of their cost) but is not needed at this load and risks showing stale price/stock text; checkout always re-prices on the server. Revisit at sustained utilisation above 50%.

### 6.4 Android device run (2026-10-27, local backend - NOT AWS)

Device: Xiaomi 22041216I, Android 14, arm64, USB. A debug build was installed beside the production app as `com.gawacha.bazaar` (a package already registered in `google-services.json`), JS served by Metro, API reached through `adb reverse` on a local backend with a disposable PostgreSQL database, a Redis container and the self-hosted Nagpur OSRM. Firebase: **real** project `gawachabazaar-ac900` (the user signed in on the phone; the backend verified the real ID token using only the project id - no service account, so revocation checks fail open and log `FIREBASE_REVOCATION_CHECK_FAILED`). Razorpay: **real test-mode API** using the test key from the developer's `backend/.env` (the launcher refuses to start unless the key starts with `rzp_test_`). **The warehouse was a stand-in** (Zero Mile Stone, an inventory location flagged as the packing point and named "TEST warehouse"), not the real Gawacha warehouse.

| Step | Evidence |
|---|---|
| Real Firebase login, address save | `POST /auth/sync` 200, `POST /addresses` 201; the address is in Nagpur 440017 with coordinates (device GPS, no map-search provider id) |
| Cart | `POST /cart/items` 201, quantity 2: Brinjal 2 x 35 = Rs 70 |
| Delivery quote | `routing cache=miss provider=osrm distance_m=7170 latency_ms=256`, then `delivery_priced distance_m=7170 fee=112 free=False warehouse_id=1` (40 + 10 x 7.17 = 111.7, rounded up to Rs 112). The straight line to the same pin is 4.71 km, so 7.17 km is a road distance |
| Redis | the following requests logged `cache=hit`; keys are `route:v1:osrm:driving:<endpoint-hash>:...` with TTL about 604 700 s |
| Razorpay (test mode) | `POST /payments/online/start` 200 (Razorpay order created, 1.47 s); the user completed the test payment in the Razorpay sheet; `POST /payments/online/1/verify` 200, `PAYMENT_STATE_TRANSITION PROCESSING -> PAID`, `PAYMENT_ORDER_CONFIRMED` |
| Order | `ORDER_CREATED order_id=1 warehouse_id=1 provider=osrm distance_m=7170 delivery_fee=112.00 total=182.00`. Row: subtotal 70.00, discount 0.00, delivery_fee 112.00, total 182.00, `delivery_distance_meters` 7170, `routing_provider` osrm, `warehouse_id` 1, status CONFIRMED. Payment 182.00 PAID, UPI, RAZORPAY. Checkout session COMPLETED with `order_id` 1; cart CHECKED_OUT; reservation COMMITTED |
| Phone screen | Order details: Brinjal 500 G x 2 Rs 70, Delivery fee Rs 112, Total Rs 182, Paid online Rs 182 - equal to the database row |

Not captured on the device: the checkout screen's "distance by road" text (the quote API returned 7.17 km; the app shows one decimal), payment failure/cancel/duplicate-confirm (covered by automated tests only), logout and session restore, tampering from the phone (automated regression tests cover it), push notifications (`PUSH_TICKET_ERROR InvalidCredentials`: no FCM credentials for Expo push on this build).

### 6.5 Rollback

- **Application / containers:** deploy by git tag and keep the previous image. Roll back with `git checkout <previous-tag>` then `ENV_FILE=.env.aws COMPOSE_FILE_NAME=docker-compose.aws.yml deploy/scripts/deploy.sh`. The `migrate` service runs `alembic upgrade head`, a no-op for older code when the schema change was backward compatible.
- **Database:** **no destructive downgrades in production.** Migrations are expand-then-contract: add nullable columns/tables first (like `d7e9a1c3b5f2`), ship code that works with both shapes, and drop or rename only in a later release once the old code is gone. Take a manual RDS snapshot before every schema-changing release; if a migration goes wrong, restore the snapshot to a new instance and repoint `DATABASE_URL` instead of running `alembic downgrade`.
- **Configuration:** `.env.aws` is rendered from SSM Parameter Store, which keeps version history; roll a parameter back to its previous version and re-run `deploy.sh`. Keep the previously rendered file as `.env.aws.prev` on the host.
- **Routing data:** keep the previous OSRM data directory; point `OSRM_DATA_DIR` back, `docker compose up -d osrm`, then flush Redis.

## 7. OSRM data (reproducible)

`deploy/osrm/build.sh` (run on demand, never at start). Executed 2026-10-26/27:

| Item | Value |
|---|---|
| Source | Geofabrik `asia/india/western-zone-261025.osm.pbf` (snapshot dated 2026-10-25), 221,588,529 bytes, MD5 `fc396c6c2fc048ed0c6fcc5b9182ce6d` (matches Geofabrik's published `.md5`) |
| Coverage | clipped to bbox `78.7,20.8,79.5,21.5` (min lon, min lat, max lon, max lat), about 80 x 78 km around Nagpur (covers Kamptee, the airport, Hingna, Butibori edge); `--strategy=complete_ways` |
| Clipped input | 5,719,404 bytes (128,237 ways, 796,987 nodes) |
| Build | `osrm-extract -p /opt/car.lua`, `osrm-partition`, `osrm-customize` (MLD) with `osrm-backend@sha256:55dbfd47...` (v26.10.0): 96 s total including installing `osmium-tool` from Debian; peak RAM 388 MB (extract) |
| Output | `nagpur.osrm*` about 98 MB on disk; `BUILD_INFO.json` records source, md5, bbox, image digest, UTC time, seconds |
| Runtime | 72 MiB right after start, 86-90 MiB under load |
| Refresh | Only when you decide (roads change slowly; suggest every 3-6 months or when the delivery area changes): edit `PBF_URL`/`PBF_MD5`/`BBOX`, run `build.sh` into a new directory, point `OSRM_DATA_DIR` at it, `docker compose up -d osrm`. The route cache key contains a hash of `OSRM_BASE_URL`; because the URL (`http://osrm:5000`) is unchanged after a refresh, **flush Redis (or wait for the 7-day TTL) so old distances are not served** |

## 8. Database review

- **Connections:** workers x (pool_size + max_overflow) = 1 x (12 + 12) = **24**, plus 1 for the `migrate` one-shot and a reserve of 5 for admin/psql = about 30. RDS `db.t4g.micro` (1 GiB) default `max_connections` is derived from memory (formula `LEAST(DBInstanceClassMemory/9531392, 5000)` gives about 112) - **NOT VERIFIED on AWS: run `SHOW max_connections;` after creating the instance.** Each extra worker would add 24; do not add workers without moving the in-process state first. Measured peak: 25.
- **Timeouts (server-side, every connection):** `statement_timeout` 20 s, `idle_in_transaction_session_timeout` 60 s (above Razorpay's 10 s + OSRM's 3 s) - verified against `pg_settings`. `pool_pre_ping`, `pool_recycle` 1800 s, `pool_timeout` 10 s.
- **Indexes:** reviewed the executed queries of 9 hot endpoints (58 distinct statements, `EXPLAIN ANALYZE` on the 1,000-user dataset): every statement < 3 ms (slowest: category product counts, 2.45 ms); all lookup columns already indexed (`users.firebase_uid`, `addresses.user_id`, `orders.user_id/placed_at/status`, `cart_items`, `prices.variant_id`, `inventory_lots(variant_id,status,created_at,id)`, partial unique indexes for the active cart/default address). **No index was added** - there is no evidence one would help at this scale. Revisit when `orders` exceeds about 100k rows (a composite `(user_id, placed_at DESC)` would then serve order history) - the benefit would be avoiding a sort per customer's history, the cost a few MB.
- **Transactions:** DEL-1/DEL-7 (no network call under row locks) remain in force and tested. Checkout issues up to 26 statements in one transaction (measured).
- **Migrations:** run by the `migrate` one-shot before the backend starts; take a manual RDS snapshot before each release that changes the schema. `alembic upgrade/downgrade/upgrade` and `alembic check` verified on a fresh PostgreSQL 16 (local).
- **Not verified:** RDS parameter group, `rds.force_ssl`, storage autoscaling, Performance Insights (free tier for 7 days retention - **not verified**).

## 9. Redis review

Audited: Redis is used **only** by `RouteCache` (route distances + a 15 s single-flight lock). Essential: no (delivery works without it). Optional: the cache and lock. Unnecessary: persistence, replication, AUTH on an internal-only network (the container has no published port; add `requirepass` if you ever share the network). Settings: `--save "" --appendonly no --maxmemory 64mb --maxmemory-policy allkeys-lru`, keys `route:v1:osrm:driving:<endpoint-hash>:<olat>,<olng>:<dlat>,<dlng>`, TTL 604 800 s (verified `TTL` on a real key), fees never cached, circuit breaker + in-process fallback when Redis fails (verified live by stopping the container). Memory in the 5-minute 1,000-user run: 1.3 MB.

## 10. Docker / compose hardening

Done in `docker-compose.aws.yml`: only Caddy publishes ports; `osrm` image pinned by digest and mounted read-only; `redis:7-alpine` with a memory bound; `mem_limit` backend 640 MB (measured peak 176 MB), redis 128 MB (measured 5 MB), osrm 384 MB (measured 89 MB) with `cpus: 1.0`; json-file log rotation 10 MB x 5; `restart: unless-stopped`; the backend image already runs as non-root `appuser` (uid 1000) with a Python-based `HEALTHCHECK` on `/health`. **Not done / recommendations:** pin `python:3.11-slim`, `postgres`, `redis`, `caddy` base images by digest (needs a pull on the build host); `requirements.txt` uses ranges with no lock file (generate a Linux lock with `pip-compile` in CI); the Admin/website containers have no measured memory figure, so no limit was set for them; the `osrm` image runs as root inside the container (upstream image) with a read-only data mount.

## 11. Cloudinary, Firebase, Razorpay (kept)

- **Cloudinary:** server-side upload via `POST /catalog/.../images/upload` (admin permission required); limit 8 MB; allowed `image/jpeg|png|webp|gif` **by the client-declared content type only** (no magic-byte check; Cloudinary rejects non-images itself); `secure=True` URLs stored; credentials only in backend env. Deleting a product image removes the DB row but **does not call Cloudinary's destroy** (orphaned assets, P3). Uploading through FastAPI ties up a worker thread for the transfer; for month one (admin-only, few uploads) that is acceptable; move to signed direct uploads if bulk image import appears.
- **Firebase credentials by component:** *backend* - `FIREBASE_PROJECT_ID`, optionally `FIREBASE_SERVICE_ACCOUNT_JSON` (secret; SSM SecureString); *mobile* - only the public web config (`EXPO_PUBLIC_FIREBASE_*`, `google-services.json`) and Google web client id; *Admin (Next.js)* - `NEXT_PUBLIC_FIREBASE_*` public web config only. The service account must never be in a `EXPO_PUBLIC_`/`NEXT_PUBLIC_` variable (audited: none are). Separate Firebase projects for dev/staging/production (needs the owner to create them).
- **Razorpay:** `RAZORPAY_KEY_ID` (returned to the app by the API), `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` backend-only (SSM). Test keys in dev/staging, live keys in production only; the backend logs a warning at boot if production uses `rzp_test_` keys. Server-side signature verification, webhook de-duplication and retry behaviour are covered by the existing tests (`test_online_checkout.py`, `test_razorpay_payments.py`: confirm twice returns the same order, webhook retry after transient error, duplicate session reuse, refund on failure). **Razorpay sandbox end to end: NOT VERIFIED (no keys).**

## 12. Observability (minimum)

Alarms (about 8): EC2 `StatusCheckFailed`, EC2 CPU > 80% for 10 min, **memory used > 85%** and **disk used > 80%** (CloudWatch agent), RDS CPU > 80% for 10 min, RDS `FreeStorageSpace` < 4 GB, RDS `DatabaseConnections` > 80, API 5xx via a log metric filter on `-> 5` lines or an external uptime check of `/readiness` (recommended: a free external probe + one CloudWatch alarm on probe failure). Application signals already logged (no PII): `routing cache=hit|miss ... latency_ms`, `delivery_priced`, `load_shed`, `route_cache redis_unavailable`, `ORDER_CREATED`, `PAYMENT_RECONCILIATION`, `CHECKOUT_SESSION_*`, request id + status + duration per request. Metric filters for `status=failed`, `load_shed`, `PAYMENT_` and `-> 5xx` give checkout/payment/quote failure counts. Log retention: 14 days for the backend group, 7 for Caddy. Logs redact `token=` query values; tokens, passwords and payment secrets are not logged; addresses are logged by id only.

## 13. Backups, recovery, CI/CD

- **RDS:** automated backups on, **retention 7 days** (raise to 14 if affordable), PITR (enabled by default when retention > 0), a manual snapshot before every schema-changing release, deletion protection on, final snapshot on delete. **Restore drill (do it in staging before launch):** 1) restore the latest snapshot / a PITR timestamp to a *new* instance `gb-restore-<date>` in the same subnet group and SG; 2) connect from the EC2 host, compare row counts (`users`, `orders`, `order_items`, `addresses`) and `alembic_version` against production; 3) boot a throwaway backend container against it and run the smoke test; 4) delete the instance. **NOT VERIFIED on AWS.** What *was* verified locally: a logical `pg_dump -Fc` / `pg_restore` round trip of the 1,000-user database (346,044-byte dump, 1 s / 2 s) reproduced identical counts (1,001 users, 402 orders, 1,332 order items, 1,000 addresses, same `alembic_version` and order total sum 244,155.00).
- **CI:** `.forgejo/workflows/ci.yml` (ruff, Alembic upgrade + `alembic check`, full pytest against a PostgreSQL service container, `tsc` for mobile and Admin, both compose files render). **Written, not yet run on a Forgejo runner.** The existing `deploy.yml` (EKS on every push to `main`, no checks) is untouched but should be disabled once the AWS path is live.
- **CD:** `.forgejo/workflows/deploy-aws.yml` - manual `workflow_dispatch` with a git ref; deploys to **staging**, runs `deploy/scripts/smoke-test.sh` (now includes `/readiness`), then **production behind the `production` environment approval**. It deploys over SSH using the repo's `deploy.sh` (which now accepts `ENV_FILE`/`COMPOSE_FILE_NAME`); nothing deploys from a laptop. **Not yet run.**

## 14. Staging plan (exact order, none executed yet)

1. AWS: create the account hygiene (MFA root, an admin SSO user, budget alarm at $60); region `ap-south-1`.
2. VPC with 1 public + 2 private subnets (2 AZs), internet gateway, **no NAT**; security groups `gb-app`, `gb-rds` as in section 5.
3. RDS PostgreSQL 16 `db.t4g.micro`, private, 20 GB gp3, backups 7 days, deletion protection; note the endpoint; `SHOW max_connections;`.
4. Create SSM parameters under `/gawacha/staging/` (DATABASE_URL with `?sslmode=require`, Firebase project id/service account, Razorpay **test** keys + webhook secret, Cloudinary, `PACKING_POINT_*` **= the real warehouse coordinates**, `NOMINATIM_USER_AGENT`).
5. Launch EC2 `t4g.medium` (Amazon Linux 2023 ARM), instance profile, 30 GB gp3, Elastic IP; install Docker (`deploy/scripts/bootstrap-server.sh` as a base; skip SSH hardening that assumes port 22).
6. Clone the repo to `/opt/gawachabazaar`; run `deploy/osrm/build.sh` with `OUT=/opt/gawachabazaar/osrm-data`; set `OSRM_DATA_DIR`.
7. AWS `.env.aws` from SSM; `ENV_FILE=.env.aws COMPOSE_FILE_NAME=docker-compose.aws.yml deploy/scripts/deploy.sh` (migrations run first); create the first admin (`backend/scripts/create_admin.py`); in Admin -> Settings choose the packing point.
8. DNS (Route 53): `api-staging`, `admin-staging`, `staging` A records -> the Elastic IP; Caddy obtains certificates.
9. `deploy/scripts/smoke-test.sh .env.aws`; check `/readiness`.
10. Mobile: build a *preview* profile with `EXPO_PUBLIC_API_BASE_URL` = staging API and the **staging Firebase project**; log in with a Firebase test user.
11. Razorpay sandbox: set the webhook URL to the staging API; run success / failure / retry payments; check `payments`, `orders`, stock.
12. Real addresses: save three Nagpur addresses via "Find this address on the map"; quote each; place an order; run the acceptance test below.
13. Load test on the staging host: `scripts/loadtest_api.py` (needs `LOADTEST_ALLOW_FAKE_AUTH=1`, disposable DB only - **do not run against production**) and `scripts/loadtest_osrm.py`; compare with section 6.
14. Restore drill (section 13), then repeat steps 1-9 for production with separate RDS, SSM path `/gawacha/production/`, live Razorpay keys and the production Firebase project.

## 15. Production acceptance test (record every value)

Real customer (Firebase) -> real Nagpur address (coordinates confirmed on the map) -> `POST /delivery/quote` -> cart -> checkout -> Razorpay **test** payment (staging) -> order -> inventory -> order history -> SQL.

| Check | API | Mobile screen | Database |
|---|---|---|---|
| Distance | `distance_meters` = ____ | "Distance: __ km by road" | `orders.delivery_distance_meters` = ____ |
| Fee | `delivery_fee` = ₹____ | "Delivery ₹__" | `orders.delivery_fee` = ₹____ |
| Total | checkout `total_amount` = ₹____ | order total ₹____ | `orders.total_amount` = ₹____ (= subtotal - discount + fee) |
| Provider / warehouse | - | - | `routing_provider='osrm'`, `warehouse_id` = ____ |
| Redis | first quote `cache=miss` then `cache=hit` in logs | - | `TTL` of the key > 0 |
| Tampering | checkout with `delivery_fee:1,distance_km:0.1,warehouse_id:99999` ignored | - | stored values are the server's |
| Payment | `payments.status='PAID'`, one row | - | one order for the cart; stock reserved/consumed as expected |

Verified locally with the test double (not the real stack): order 1, distance 6 712 m, fee ₹108, total ₹158 for the same value in API, response and database.

## 16. Remaining blockers before production

1. No AWS account/credentials were available: **nothing was created or tested on AWS**.
2. Mobile: **run once on a physical Android device** against a local backend with real Firebase login and a Razorpay test-mode payment (section 6.4, one order end to end). Not yet done: payment failure/cancel/duplicate on the device, tamper attempts from the phone, session restore/logout, any run against an AWS staging backend.
3. Real warehouse coordinates not supplied (`PACKING_POINT_*` / Admin packing point) - delivery pricing is not production-ready until they are set.
4. Per-core API throughput on Graviton is unmeasured; month-one demand (about 10 req/s at peak, an estimate) is under the measured 40 req/s on a faster core but the margin on `t4g.medium` must be re-measured in staging.
5. Restore drill, CloudWatch alarms and the CI/CD workflows are written but unrun.
6. Single host, single worker, single-AZ database = no redundancy (accepted for month one).

## 17. 1,000-user assessment and 10,000-user path

**1,000 users:** the architecture above is sufficient on paper (estimated peak about 10 req/s; measured saturation 40-47 req/s per core on a faster CPU; DB at 25 connections; OSRM at 0.001% of its capacity). It is **NOT VERIFIED** on AWS hardware. **10,000 users (evolution, not a rewrite):** (1) Multi-AZ RDS and a larger instance; (2) move rate limiting, the WebSocket hub and the reservation-expiry sweep to Redis (ElastiCache then becomes justified) so the backend can run 2-4 workers/instances; (3) ALB in front of 2+ backend instances (the existing `k8s/` manifests or ECS are then reasonable); (4) CloudFront for Admin/website/static; (5) catalog read caching; (6) images to S3 + CloudFront only if Cloudinary costs/limits require it; (7) OSRM as a second container/instance. Rough infrastructure cost scales from about $46 to a few hundred dollars (**not estimated**).

## 18. Production deployment checklist

- [ ] AWS account, MFA, budget alarm
- [ ] IAM least privilege (instance profile only; no keys in Git)
- [ ] VPC, subnets, `gb-app` / `gb-rds` security groups (no 22, no public RDS)
- [ ] RDS PostgreSQL 16 private, backups 7+ days, deletion protection, `sslmode=require`
- [ ] EC2 + Elastic IP + SSM agent, Docker
- [ ] OSRM data built (`deploy/osrm/build.sh`), `BUILD_INFO.json` archived
- [ ] SSM parameters (production Firebase project, **live** Razorpay keys, Cloudinary, warehouse coordinates)
- [ ] `docker-compose.aws.yml` deployed; migrations succeeded; first admin created; packing point chosen
- [ ] DNS + HTTPS (Caddy certificates issued), HSTS present (smoke test)
- [ ] CloudWatch agent + about 8 alarms + log retention
- [ ] RDS restore drill done in staging
- [ ] CI green; staging deploy + smoke test; production approval gate configured
- [ ] Load test repeated on the staging host
- [ ] Mobile production build with production API/Firebase; EAS channel set
- [ ] Real warehouse coordinates configured; delivery pricing verified with 3 real addresses
- [ ] One real order verified end to end (section 15)
- [ ] Rollback: previous image tag kept; `git checkout <last tag>` + `deploy.sh`; RDS snapshot taken before migration

## 19. Addendum 2026-10-27 - partners, referrals, pricing

* No new infrastructure: partner location is a latest-only PostgreSQL table (no Redis dependency); referral rewards and partner earnings are PostgreSQL ledgers. Redis remains the optional route cache.
* Production configuration checklist additions: `DELIVERY_BASE_FEE=20` (decided; make sure no host override); `OSRM_BASE_URL` must be the self-hosted OSRM (default still the public demo server); `REFERRAL_*` / `PARTNER_*` placeholders; `DELIVERY_PARTNER` accounts created by an admin.
* Backup/restore: the new ledgers are append-only and must be included in the dump (they are ordinary tables).
