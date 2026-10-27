# AI Status

> **Last verified:** 2026-10-14 (≈ 12:00–13:10 IST), branch `docs-and-primary-testing`, `HEAD` `8d6229e` ("chore(mobile): link EAS project under yash145"), **dirty working tree** (see §5).
> **Purpose:** the "where are we right now" page for agents and developers: what works (and how that was checked), what is broken or unverified, what changed recently *according to the repository*, and what to do next. **Update this file whenever active development status, blockers or priorities change** ([AGENTS.md](../../AGENTS.md)). It is a snapshot; where it conflicts with the code or a fresh test run, trust those.

## 0. COD delivery OTP - status on 2026-10-27 (uncommitted, not deployed, not built)

| Check | Result |
|---|---|
| Full backend suite (disposable DB, before the final test additions) | 1251 collected: **1233 passed, 17 skipped, 1 failed** in 29 min 19 s. The one failure was `test_authz_matrix` - expected drift of exactly the 2 new operations; fixed by the reviewed `AUTHZ_REGEN=1` regeneration (golden diff = 6 added lines, nothing widened). No pre-existing failures appeared in this run. |
| `tests/test_delivery_otp.py` | 32 passed (valid/invalid/expired/locked code, regeneration, resend limit, IDOR/roles, concurrency, logs, DB constraint, admin override audit, production startup rule, push failure) |
| Migration `d3e4f5a60712` | upgrade → downgrade -1 → upgrade → `alembic check` clean on the disposable DB |
| Ruff | passes on every touched Python file; the repo-wide pre-existing findings (14, none in touched files) were left alone |
| TypeScript | `mobile/` and `Admin/` `npx tsc --noEmit`: exit 0 |
| References | `API_REFERENCE` (239 ops) and `DATABASE_SCHEMA` (60 tables) regenerated with `docs/_tools` |

**Not verified:** any physical Android run; FCM/Expo push delivery of the code; notification tap routing; the customer/partner OTP screens on a device or emulator; Admin in a browser; the production host's environment (`DELIVERY_OTP_SECRET` / `DELIVERY_OTP_ENFORCED` / `REFERRAL_ENABLED` could not be inspected from the repository - the local `.env` is development with no secret).

**Release blockers (as of this note):** set a >= 32-char `DELIVERY_OTP_SECRET` on the real host (production refuses to start without it while enforcement is on); decide rollout order (deploy backend + ship the partner app together - a partner on an old app cannot complete unpaid-COD deliveries once enforcement is on; `DELIVERY_OTP_ENFORCED=false` is the temporary switch); device test. See [COD_OPERATIONS](../05-domains/COD_OPERATIONS.md#delivery-otp-proof-of-delivery---implemented).

## 1. Verified status (what was actually run on 2026-10-14)

| Check | Command / method | Result |
|---|---|---|
| Backend test suite | `pytest -p no:cacheprovider` against the disposable PostgreSQL 16 container (loopback `15432`, tmpfs), 06:32 UTC start | **899 collected: 891 passed, 7 failed, 1 xfailed** in 10 min 18 s |
| Cause of the 7 failures | re-ran only those 7 with `DELIVERY_BASE_FEE=20` | 7 passed; with the new default (40) all 7 fail by exactly Rs 20 → the **base delivery fee was changed 20 → 40 on the same day** and these tests hard-code 20 |
| Strict xfail | `test_money_integrity.py::…refunded_not_attached` | still xfail ⇒ defect **PAY-001 still open** |
| Lint | `python -m ruff check .` | 7 findings (3 `E741` in `inventory_reservation.py`, 4 in test files) |
| Model/migration drift | `alembic check` on a DB migrated to head | "No new upgrade operations detected." Alembic: 38 files, single head `f1a2b3c4d5e6` |
| Fresh migration + boot | throw-away DB in the disposable container: `alembic upgrade head`, then `uvicorn` | head reached in ≈ 4 s, 51 tables, 7 roles, 4 home slides, 0 users, 0 promotions; `/health`, `/health/db`, `/api/v1/ping`, public catalogue, home slides, offers → 200; `/api/v1/cart` → 401; `/docs` → 200 |
| Route inventory vs OpenAPI | AST of `api/v1/*.py` vs `app.openapi()` | 193 routes + `/health`, `/health/db`, `/ping` = **196 operations** (12 public) + 1 WebSocket; sets equal |
| Auth column vs golden matrix | derived roles/permissions vs `authz_golden.json` | 180/180 gated operations match |
| Type checks | `npx tsc --noEmit` in `Admin/` and `mobile/`, re-run at ≈ 12:56 IST **after** the other session's mobile edits (§5) | exit code 0, no diagnostics in both |
| Live probes (read-only GET) | Render backend | `/health` → 200 `environment: production`; sign-in verification returns 401 for a garbage token (503 during the earlier incident) |

**Not run:** any frontend test (none exist), `multiproc` harness, live Razorpay/Firebase/Expo/Cloudinary calls, `npm install`/`expo`/EAS builds, docker compose stacks, VPS/EKS/Render deployments, backup/restore, `next lint`.

## 2. Component status

| Area | Status | Notes |
|---|---|---|
| Backend API (catalogue, cart, orders, payments, refunds, fulfilment, inventory, promotions, bulk, staff, customers, content, push, realtime) | **Implemented and verified** against fakes; red suite due to the fee change | [API_REFERENCE](../03-api/API_REFERENCE.md), domain docs |
| Online payments (Razorpay) | Implemented; verified with a fake gateway only; PAY-001 open | [PAYMENTS](../05-domains/PAYMENTS.md) |
| Authentication | Implemented (Firebase); working again after the 2026-10-14 config fix; Google needs the registered SHA-1 | [AUTHENTICATION](../05-domains/AUTHENTICATION.md) |
| Customer app | Implemented; no automated tests; unreleased UI changes in the working tree | §5 |
| Admin panel | Implemented except placeholders (Reports, Reviews, Audit Log); usability pass 2026-10-17 (grouped/sticky/mobile nav, working search, Delivery queue page, error/404 pages, Docker Firebase build args) — `tsc` and `next build` pass, **not exercised signed-in**; no automated tests; hosting unclear | [ADMIN_OPERATIONS](../05-domains/ADMIN_OPERATIONS.md) |
| Promo website | Static marketing pages, no API | – |
| Deployment | **Unresolved** (VPS vs EKS vs Render vs Vercel) | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| Observability, backups, incident process | Largely absent | [PRODUCTION_READINESS](../10-project-management/PRODUCTION_READINESS.md) |
| Bazaar+ benefits, reviews, reports, audit viewer, farm traceability | Planned / placeholder | [ROADMAP](../10-project-management/ROADMAP.md) |

## 3. Known bugs and blockers (top items; full list: [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md))

1. **FEE-1:** 7 failing tests after the base-fee change (mechanical fix; not done).
2. **SECR-1:** a live-looking API key is committed in `.mcp.json` (rotate).
3. **PAY-001:** online payment can attach to an unrelated existing order.
4. **CI-001:** pushes to `main` deploy to EKS with no checks.
5. **DEP-1/ADM-1:** unclear production target; Docker/CI Admin image has no Firebase config.
6. **BAK-1, OBS-1:** untested on-host backups only; no alerts.
7. **UI-3:** support contact details in the app are placeholders.

## 4. Documentation status

This documentation set (the numbered folders under `docs/`) was created on 2026-10-14. Each document names its evidence and its own verification status. Corrections made to existing documents (verified against code):

| File | Correction |
|---|---|
| [`docs/FEATURES.md`](../FEATURES.md) | Push notifications **are** implemented; Audit log page is a placeholder; checkout slot picker is illustrative; ad ratio check is UI-only; added Bazaar+/WHOLESALER notes; fee text updated to Rs 40 |
| [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) | Added pay-first online checkout (the old text described only reserve-then-pay); `WHOLESALER` caveat; audit-log wording; deployment ambiguity pointer; fee text updated to Rs 40 |
| Backend/other READMEs | Not changed except `backend/README.md` (fee default row, earlier in the day); they may still contain stale statements (e.g. `backend/README.md` says "~36 test modules" — there are 42 `test_*.py` files; "35+ revisions" is still true at 38) |

`docs/testing/` (the QA audit) was left as is; where it disagrees with this set the newer verification here wins (e.g. its "196 operations" and "51 tables" agree; its fixtures description in `EXISTING_TEST_INVENTORY.md` predates SEC-001).

## 5. Working-tree state (uncommitted — **nothing was committed or pushed by the documentation task**)

| Group | Files | By whom / evidence |
|---|---|---|
| Delivery base fee 20 → 40 | `backend/app/core/config.py`, `backend/app/services/delivery.py` (docstring), `backend/.env.example`, `.env.production.example`, `backend/README.md`, `docs/ARCHITECTURE.md`, `docs/FEATURES.md` | earlier in the same working session at the owner's request |
| Login redesign, sign-in loader (`syncing`), product-image fallback, removed default "Farm Fresh" tag | `mobile/app/(auth)/login.tsx`, `mobile/src/features/auth/LoginParts.tsx` (new), `AuthParts.tsx`, `mobile/src/store/authStore.ts`, `mobile/src/components/ProductCard.tsx`, `mobile/src/theme/colors.ts`, `mobile/assets/login/*` (new) | earlier in the same working session; `tsc` clean at the time; **never seen on a device** |
| Responsive / text-style work | `mobile/app/(tabs)/account.tsx`, `orders.tsx`, `search.tsx`, `checkout/index.tsx`, `order/[id]/index.tsx`, `Text.tsx`, `TextField.tsx`, `WholesaleProductCard.tsx`, `SearchHome.tsx`, `PhoneSteps.tsx`, `mobile/src/theme/textStyle.ts`, `mobile/src/utils/responsive.ts`, `mobile/scripts/check-text-style.mjs` (new) | **not made by this task or by me** (file times 12:28–12:31 IST) — another session/person is editing the app concurrently; coordinate before committing |
| Push logging + test | `backend/app/services/push.py`, `backend/tests/test_push_send.py` (new) | not made by this task |
| QA-audit artefacts | `backend/tests/{_db_safety.py, authz_golden.json, multiproc/, test_authz_matrix.py, test_cross_customer_access.py, test_db_safety.py, test_fixture_integrity.py, test_money_integrity.py, test_refund_integrity.py}`, `backend/tests/conftest.py` (modified), `docs/testing/` | earlier QA audit sessions |
| This documentation | `docs/00-… 11-…`, `docs/_tools/`, `AGENTS.md`, edits to `docs/FEATURES.md` and `docs/ARCHITECTURE.md` | this task |

The latest EAS OTA update availability was **not** checked; the installed APK listens on channel `preview`, runtime `1.0.0`.

**2026-10-18 push work (uncommitted):** `notification_events` model + migration `c3d5e7f9a1b2`, `services/push.py` (de-dupe + `type`), `tests/test_push_send.py` (+3 tests), `mobile/src/features/notifications/{notificationRouting.ts,usePushNotifications.ts}`, `docs/notifications/`, regenerated `DATABASE_SCHEMA.md`. Real-device delivery **not** verified. See [`../notifications/`](../notifications/README.md).

**2026-10-26 delivery routing work (uncommitted):** new `services/routing/*` (OSRM provider, Redis/in-process route cache), `services/geocoding/*` (Nominatim), `services/delivery_pricing.py`, `services/delivery_quote.py`, `api/v1/delivery.py` (`POST /delivery/quote`, `POST /delivery/geocode`), migration `d7e9a1c3b5f2` (addresses geocode metadata; orders `delivery_distance_meters`, `routing_provider`, `warehouse_id`), `redis` added to `requirements.txt`; the haversine fallback and Google Distance Matrix were removed (routing failure -> 503); mobile checkout shows distance / quote errors. See [DELIVERY](../05-domains/DELIVERY.md). Verified against a throw-away local PostgreSQL 16 (port 15432): migration up/down/up and `alembic check` clean; new tests pass. Never exercised against live OSRM/Nominatim/Redis; mobile change checked with `tsc` only.

**2026-10-26 delivery hardening milestone (uncommitted):** DEL-1 fixed (route resolved before row locks; `resolve_route`/`price_delivery` split in `services/delivery.py`), versioned route-cache key, Redis single-flight lock + circuit breaker, OSRM snap guard, `env_ignore_empty`, prod compose forwards delivery/Redis variables and runs Redis, addresses without a map location refused at checkout, mobile address form "Find this address on the map" + checkout messages, live integration suite `backend/tests/integration` (real PostgreSQL 16 + Redis 7 + public OSRM + Nominatim: 16 passed). **Not verified:** mobile on emulator/device, real Firebase, real payments, deployment. Full details and findings: [DELIVERY](../05-domains/DELIVERY.md), [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md) (DEL-*).

**2026-10-26 product + inventory UX milestone (uncommitted):** backend - `CATALOG_STAFF` role (migration `a8d2f4b6c0e1`, chained after the uncommitted `d7e9a1c3b5f2`), `POST /catalog/products/quick-create` (one transaction), receive with `expiry_date`, product-level correct/remove/move/undo (`services/product_stock.py`), inventory cards data (`stock_status`, warehouses, expiry, summary/filters), publish guard on `PATCH status=ACTIVE`, catalogue staff excluded from the order-event broadcast; Admin - product-first Inventory page with Add/Correct/Remove/Move dialogs and Undo, Add product via quick-create, product page with readiness + "Fix now", list readiness, role labels. Verified against a throw-away PostgreSQL 16 (`gb-ux-test-db`, loopback 15434): full backend suite, `alembic check`, Admin `tsc`, `next build`, `node --test` (see the final report in the session). **Not verified:** any signed-in browser run of the new screens, mobile/tablet layout by eye, usability with real staff. See [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md) UX-1..9.

**2026-10-27 delivery closure pass (uncommitted):** DEL-7 fixed (pay-first routes before the session lock), DEL-10 fixed (dead mobile endpoint, hook, type and util removed), DEL-3 verified locally via `docker compose config` (not deployed), self-hosted OSRM trial built and run (live suite 17/17 against public and against self-hosted OSRM; only `OSRM_BASE_URL` changed). **Still blocked (external):** mobile run (no emulator/device; needs a Firebase test account and the real warehouse coordinates), real Firebase login, Razorpay sandbox keys, staging deployment. See [DELIVERY](../05-domains/DELIVERY.md) and `KNOWN_ISSUES` DEL-*.

**2026-10-26 validation pass (uncommitted):** the new Admin screens were driven in the built-in browser against the real backend (fake Firebase sign-in stand-in, disposable PostgreSQL) for create product, receive (with expiry), correct, remove, undo, move, "Fix now", duplicate, role views (admin / catalogue / hub) and a phone-width layout; friction found was fixed (see KNOWN_ISSUES VAL-1..10). Backend suite 1043 tests, `alembic check`, ruff on touched files, Admin `tsc` / `next build` / 12 `node --test` tests all green at the last run. No real staff usability test yet.

**2026-10-27 AWS preparation (uncommitted):** new `docs/09-deployment-operations/AWS_PRODUCTION_PLAN.md` (architecture, costs from AWS's public price lists, security groups, measured load tests), `docker-compose.aws.yml` (EC2 + RDS + private OSRM + Redis), `deploy/osrm/build.sh` (reproducible Nagpur extract, 98 MB, 89 MiB RAM), `.forgejo/workflows/{ci,deploy-aws}.yml` (unrun), `.env.aws.example`, `/readiness`, DB pool/timeouts, in-flight cap (fixed a collapse at 100 concurrent users), per-user rate limits, load-test scripts. **Nothing was deployed to AWS.** Still blocked: AWS credentials, device/Firebase/Razorpay test inputs, real warehouse coordinates.

**2026-10-27 device run:** the real app ran on a USB Android phone (Xiaomi, Android 14) with real Firebase login and a Razorpay TEST payment against a local backend: quote 7 170 m / Rs 112, order 1 CONFIRMED, screen total equals the database ([AWS plan](../09-deployment-operations/AWS_PRODUCTION_PLAN.md) section 6.4, procedure in [ANDROID_DEVICE_TEST](../07-testing/ANDROID_DEVICE_TEST.md)). Also this session: DEL-15 (image validation + Cloudinary release) fixed, DEL-14 measured and closed (1 worker), DEL-16 hashed lock + pinned base image, legacy EKS deploy made manual-only, two timezone-dependent tests fixed. Still open: real warehouse coordinates, AWS staging, payment failure/duplicate on device.

## 6. Recommended next steps (grounded in the findings above)

1. Rotate the committed key (SECR-1) and confirm Render's production variables (CFG-1, FEE-1/O-3).
2. Fix the 7 fee-dependent tests; then PAY-001; then a CI gate that runs ruff + pytest + `alembic check` + `tsc` ([TASKS](../10-project-management/TASKS.md) E-1…E-3).
3. Review the three mobile change groups separately and commit them as separate commits (type checks were clean at ≈ 12:56 IST, but others are still editing `mobile/`; re-run before committing).
4. Resolve the deployment ambiguity and the Admin Firebase-config path (O-2, E-5).
5. Run a backup restore drill and add alerts for the reconciliation markers (O-9, E-8).

## 7. How to update this file

After any session that changes behaviour, test status, blockers or priorities: refresh §1 with the commands you actually ran and their results, move items between §2/§3, adjust §5 to match `git status`, and change the "Last verified" line. Do not mark anything verified that you did not run.
