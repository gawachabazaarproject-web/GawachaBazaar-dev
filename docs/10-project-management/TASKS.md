# Tasks

> **Status:** Verified as a **list of evidenced open work** on 2026-10-14. **No task tracker, backlog, owner or deadline exists in the repository, and none is invented here.** Every item below is derived from a confirmed finding in [KNOWN_ISSUES](KNOWN_ISSUES.md), a go-live checklist item in [`deploy/README.md`](../../deploy/README.md), or a proposal already written in the QA audit. "Suggested priority" is **my recommendation**, not a decision; owners are "unassigned".

Legend: **P0** = fix before relying on the system for real money/customers · **P1** = soon · **P2** = when convenient. "Effort" is a rough T-shirt size (S ≤ ½ day, M ≈ 1–3 days, L > 3 days) and is an estimate, not a commitment.

## Needs a decision or action by the owner (not code)

| # | Task | Why | Evidence | Pri |
|---|---|---|---|---|
| O-1 | Rotate/revoke the API key committed in `.mcp.json`, then untrack the file | Key in git history and echoed during this audit | SECR-1 | P0 |
| O-2 | Decide which deployment is production (VPS, EKS, Admin on Vercel) and retire or label the others; document where Admin is built and how its Firebase config is injected | Docs and CI describe different targets | DEP-1/DEP-2/ADM-1 | P0 |
| O-3 | Confirm AWS environment: `APP_ENV=production`, `DEBUG=False`, real `ALLOWED_ORIGINS`, `DELIVERY_BASE_FEE` (40?), valid or absent `FIREBASE_SERVICE_ACCOUNT_JSON` | Defaults are dev-oriented; fee change may be overridden | CFG-1, FEE-1 | P0 |
| O-4 | Fill in the real support email/phone in the app | Placeholders visible to customers | UI-3 | P0 (launch) |
| O-5 | Obtain or confirm FCM credentials for the `yash145` EAS project; register the build SHA-1 in Firebase (done for sign-in on 2026-10-14) | Push delivery unverified; Google Sign-In needs registered keys | NOTIFICATIONS | P1 |
| O-6 | Provide an opt-in staging environment + Razorpay test keys for end-to-end payment testing | Live Razorpay flows have never been exercised | BASELINE_AUDIT §4 | P1 |
| O-7 | Decide retention, account-deletion and export policy; review privacy obligations | No policy, constraints block deletion | DATA-1, PRIVACY | P1 |
| O-8 | Decide what Bazaar+ and the `WHOLESALER` role should do (or remove the claims) | Advertised benefits do not exist | BAZ-1, WHL-1 | P2 |
| O-9 | Run a real backup **restore drill**; set up off-site, encrypted backups; confirm EKS database backups | Backups never restored | BAK-1 | P0 |

## Engineering tasks

| # | Task | Evidence | Effort | Pri |
|---|---|---|---|---|
| E-1 | **Fix the 7 failing tests** caused by the base-fee default (pin `DELIVERY_BASE_FEE` in tests, or update expected totals by +20) and re-run the full suite | FEE-1 | S | P0 |
| E-2 | Fix **PAY-001** (in `CheckoutSessionService._finalize`, when `created is False` require that the order belongs to this session's cart; otherwise refund) — then remove the `xfail` marker | DEFECT_LOG | S–M | P0 |
| E-3 | Add a CI job that runs ruff, the backend suite against a PostgreSQL service container, `alembic upgrade head` (+ `alembic check`), and `tsc` for the apps, and make the deploy job depend on it | CI-001 | M | P0 |
| E-4 | Make Firebase service-account loading fail soft (fall back to anonymous credentials, log loudly) so a bad value cannot take down all sign-ins | observed outage | S | P1 |
| E-5 | Pass the six `NEXT_PUBLIC_FIREBASE_*` values to the Admin image build (Dockerfile `ARG`s, compose, CI) — or retire the Docker path if Vercel is the host | ADM-1 | S | P1 |
| E-6 | Pass the delivery/routing/Bazaar variables through `docker-compose.prod.yml` `x-backend-env` (or remove them from `.env.production.example`) | FEE-2 | S | P1 |
| E-7 | Provide an in-app way to resolve a refund stuck in `PROCESSING` without a gateway id (admin "mark attempt failed" after dashboard check) | G-REF-1 | M | P1 |
| E-8 | Alert on reconciliation markers; add a reconciliation job for unmatched captures and failed automatic refunds | PAY-3, OBS-1 | M | P1 |
| E-9 | Mask customer phone/email in staff order detail and phone search for roles without `customers.view_sensitive` | PRIV-1 | S | P1 |
| E-10 | Add a general audit-log API + Admin page (or remove the placeholder) | UI-1 | M | P2 |
| E-11 | Resolve the single-process constraint: shared rate-limit store, cross-replica events (e.g. PostgreSQL `LISTEN/NOTIFY`), migration job — or cap HPA at 1 | OPS-001/003/002/5 | M–L | P1 |
| E-12 | Align DB pool and request concurrency (PERF-001 mitigations) and add a DB-aware readiness probe | PERF-001 | M | P1 |
| E-13 | Trust only the real proxy range for `--forwarded-allow-ips` (or key limits on the right hop) | SEC-002 | S | P1 |
| E-14 | Add frontend smoke tests (Playwright for Admin/website; jest-expo or Maestro for the app) covering sign-in and checkout totals | TEST-1 | L | P1 |
| E-15 | Make backend validate ad image dimensions if the 12:5 rule matters; sniff upload content types; delete replaced Cloudinary assets (store `public_id`) | ADS-1, UPL-1, DATA-1 | M | P2 |
| E-16 | Add a Python lockfile and dependency/secret/container scanning; drop redundant deps; sync `pyproject.toml` | DEP-3 | S–M | P2 |
| E-17 | Remove the tracked 41 MB APK from the repository (and decide on history) | R-16 | S | P2 |
| E-18 | Clean up stale comments (PNB gateway, JWT sessions, "no audit log"), the stale `alembic.ini` URL and the unwired `PNBGateway`; fix the 7 Ruff findings | LINT-1, DOC-1 | S | P2 |
| E-19 | Replace the public OSRM demo server with a private/paid router or Google; consider fee zones and a minimum order | DELIVERY | M | P1 |
| E-20 | Add the delivery fee and promotions to bulk-converted orders (or document that bulk orders are priced manually) | BULK-1 | S–M | P2 |
| E-21 | Review/replace the migration-seeded live promotion codes before using the migrations on a new environment | MIG-1 | S | P1 |
| E-22 | Test migrations from the previous revision with data; test the Admin ↔ backend permission map equality | TEST-2 | M | P2 |

## Working-tree changes awaiting a decision (uncommitted)

These exist on disk but are **not committed**; each needs a review and a commit decision by the owner (nothing was committed by this task):

| Change | Where | Verified? |
|---|---|---|
| Login screen redesign (artwork-matched), sign-in loader overlay (`syncing`), neutral product-image fallback, removed default "Farm Fresh" tag | `mobile/` (`LoginParts.tsx`, `login.tsx`, `AuthParts.tsx`, `authStore.ts`, `ProductCard.tsx`, `colors.ts`, `assets/login/`) | `tsc` clean; **not seen running on a device** |
| Default `DELIVERY_BASE_FEE` 20 → 40 | `backend/app/core/config.py`, example env files, docs | 7 tests fail (E-1) |
| QA-audit tests and evidence | `backend/tests/*`, `docs/testing/` | suite run recorded in [TESTING_GUIDE](../07-testing/TESTING_GUIDE.md) |
| Push logging improvements + new test | `backend/app/services/push.py`, `backend/tests/test_push_send.py` | made outside this task; tests included in the run |
| This documentation set | `docs/`, `AGENTS.md` | – |

## Done (evidence)

- SEC-001 fixed and regression-tested (`_db_safety.py`, 46 policy tests) — [SEC001_REVIEW](../testing/SEC001_REVIEW.md).
- Sign-in outage of 2026-10-14 resolved by removing `FIREBASE_SERVICE_ACCOUNT_JSON` (confirmed by the owner; Google sign-in worked after registering the new SHA-1).
