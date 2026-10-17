# Known Issues

> **Status:** Verified (each row cites its evidence) as of 2026-10-14. This is the **single consolidated register**. Entries from the earlier QA audit keep their IDs and link to [`docs/testing/DEFECT_LOG.md`](../testing/DEFECT_LOG.md) / [`RISK_REGISTER.md`](../testing/RISK_REGISTER.md) for full reproduction details; entries found while writing this documentation set carry new IDs and are marked **(new)**. "Confirmed" = reproduced by test/experiment or unambiguous in code; "Suspected" = pattern seen, not reproduced. **Nothing here has been fixed by this task.** Severity is my assessment, not the owner's.

## A. Money, correctness and data integrity

| ID | Severity | Status | Issue | Evidence / detail |
|---|---|---|---|---|
| PAY-001 | High | Confirmed, **open** | A captured online payment is attached to an unrelated, already-existing order (latest cart already checked out, e.g. by COD) with no refund | strict `xfail` test; [DEFECT_LOG](../testing/DEFECT_LOG.md), [PAYMENTS](../05-domains/PAYMENTS.md) |
| G-REF-1 (new) | Medium | Found by code inspection, not reproduced | A refund whose gateway response is lost before an id is stored stays `PROCESSING`; "process" and "check status" both refuse; no in-app recovery | [REFUNDS](../05-domains/REFUNDS.md) |
| PAY-2 (new) | Low | Confirmed (code/docstring mismatch) | `payment_state.py` says a `CANCELLED` payment is superseded via `/retry`, but `can_retry_payment` allows only `FAILED`/`EXPIRED` | [PAYMENTS](../05-domains/PAYMENTS.md) |
| PAY-3 (new) | Medium | Confirmed | Money captured for a payment/session nothing matches (`PAYMENT_WEBHOOK_UNKNOWN_REFERENCE`) and automatic refunds that fail (`REFUND_FAILED`) are only logged — no job, queue or alert; pay-first automatic refunds have no `refunds` row | [WEBHOOKS](../03-api/WEBHOOKS.md), [REFUNDS](../05-domains/REFUNDS.md) |
| FEE-1 (new) | **High (suite red)** | Confirmed, **open** | The 2026-10-14 change of the default base delivery fee (20 → 40) broke **7 existing tests** that hard-code the old default; they pass with `DELIVERY_BASE_FEE=20` | [TESTING_GUIDE](../07-testing/TESTING_GUIDE.md), [DELIVERY](../05-domains/DELIVERY.md) |
| FEE-2 (new) | Medium | Confirmed | `docker-compose.prod.yml` does not pass `DELIVERY_*`, routing, packing-point or `BAZAAR_*` variables to the backend, so `.env.production` cannot change them (code defaults apply); the effective fee on other hosts depends on unseen environment settings | [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md) |
| BULK-1 (new) | Low–Medium | Confirmed | Orders converted from bulk quotes get `delivery_fee = 0` and no promotion | [BULK_ORDERS](../05-domains/BULK_ORDERS.md) |
| PROMO-1 (new) | Low | Confirmed | `promotion_targets` has no foreign key; deleting a product/category leaves dangling targets | [PROMOTIONS](../05-domains/PROMOTIONS.md) |
| MIG-1 (new) | Medium | Confirmed | Migration `e4a7c1b9d036` inserts four **ACTIVE** discount promotions (`WELCOME50`, `BAZAAR100`, `FRESH10`, `WEEKEND15`) when an admin exists — live codes created by a migration; Unsplash-hosted images | [MIGRATIONS](../04-database/MIGRATIONS.md) |
| CART-1 (new) | Info | Confirmed | Cart status `ABANDONED` is defined but never set | [CART_AND_CHECKOUT](../05-domains/CART_AND_CHECKOUT.md) |
| DATA-1 (new) | Medium | Confirmed | No customer deletion/anonymisation/export; unbounded growth of event/audit tables; Cloudinary assets never deleted (`public_id` not stored) | [DATA_RETENTION](../04-database/DATA_RETENTION.md) |
| FIRE-1 (new) | Low | Documented limitation | Admin contact edits update PostgreSQL only; the next sync can overwrite the phone from Firebase | [AUTHENTICATION](../05-domains/AUTHENTICATION.md) |

## B. Security and privacy

| ID | Severity | Status | Issue | Evidence |
|---|---|---|---|---|
| SECR-1 (new) | **High** | Confirmed, **open** | A live-looking API key is committed in `.mcp.json` (commit `bff7053`, still tracked) and was displayed during this audit; rotate it | [SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md) |
| SEC-002 | Medium | Confirmed (simulated) | `X-Forwarded-For` spoofing bypasses per-IP limits with `--forwarded-allow-ips "*"` unless the proxy overwrites the header | [DEFECT_LOG](../testing/DEFECT_LOG.md) |
| OPS-001 | Medium | Confirmed | Rate limit is per process/replica | DEFECT_LOG |
| REV-1 (new) | Medium | Confirmed (code) | Token revocation/disabled-user checks are skipped when the Firebase service account is absent or the lookup fails (tokens valid ≤ 1 h) | [AUTHENTICATION](../05-domains/AUTHENTICATION.md) |
| PRIV-1 (new) | Medium | Confirmed (code) | Staff order detail exposes the customer's unmasked phone/email to `orders.read` roles; order search matches phones | [ORDERS](../05-domains/ORDERS.md), [PRIVACY](../08-security/PRIVACY.md) |
| CFG-1 (new) | Medium | Confirmed (code) | Defaults are dev-oriented (`APP_ENV=development`, `DEBUG=True`, localhost CORS); production validation covers only Firebase/Razorpay; top-level `k8s/backend-deployment.yaml` sets `APP_ENV=staging` | [SECURITY](../08-security/SECURITY.md) |
| SEC-003 | Low–Med | Suspected | `legacy-migrate` as an unauthenticated password oracle; enumeration differences untested | DEFECT_LOG |
| SEC-005 | Low | Confirmed (code) | WebSocket token in URL query | DEFECT_LOG |
| UPL-1, HLTH-1 (new) | Low | Confirmed (code) | Upload type trusted from the declared content type; `/health/db` is public | [SECURITY](../08-security/SECURITY.md) |
| SEC-001 | High | **Fixed** (this audit) | Test fixtures could TRUNCATE a remote database | [SEC001_REVIEW](../testing/SEC001_REVIEW.md) |
| R-14/R-16 | Medium/Low | Confirmed | Plaintext hosted-DB credential in a local `.env`; 41 MB APK tracked in git | [RISK_REGISTER](../testing/RISK_REGISTER.md) |

## C. Deployment, operations and scale

| ID | Severity | Status | Issue | Evidence |
|---|---|---|---|---|
| CI-001 | High | Confirmed | Production (EKS) deploys on every push to `main` with no test, lint, scan or migration gate | [QUALITY_GATES](../07-testing/QUALITY_GATES.md) |
| DEP-1 (new) | High | Unresolved | Three backend deployment descriptions (VPS compose, EKS, Render) plus Admin on Vercel; the repository cannot say which is production; the AWS hostname was found not to serve the API (commit `88d6090`) | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| DEP-2 (new) | Medium | Confirmed | Two diverging K8s backend manifests; ALB ingress exposes no Admin route; Admin Deployment has no Firebase config | DEPLOYMENT |
| ADM-1 (new) | High (for Docker/CI Admin) | Confirmed | The Admin image built by Docker/compose/CI receives no `NEXT_PUBLIC_FIREBASE_*` values (only the API URL), so sign-in cannot work in that image | [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md) §4 |
| OPS-002 | Low–Med | Confirmed | Concurrent `alembic upgrade head` start-up race (6/6) | DEFECT_LOG |
| OPS-003 | Medium | Confirmed | WebSocket events do not cross replicas | DEFECT_LOG |
| OPS-004 | Low | Confirmed, safe | Redundant reservation sweep per replica | DEFECT_LOG |
| OPS-5 (new) | Medium | Contradiction | K8s HPA scales the backend 1→3 although the design requires a single process | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| PERF-001 | Medium | Confirmed (exploratory) | DB pool 5+10 vs 40 request threads ⇒ 100 users → 100 % timeouts, ~6 min recovery; CPU-based HPA cannot see it | [PERFORMANCE_RESULTS](../testing/PERFORMANCE_RESULTS.md) |
| OBS-1 (new) | Medium | Confirmed | No metrics, error tracking, uptime monitoring or alerting; reconciliation markers are unmonitored | [MONITORING_AND_LOGGING](../09-deployment-operations/MONITORING_AND_LOGGING.md) |
| BAK-1 (new) | High (if relied on) | Confirmed | Backups exist for the compose stack only, same disk, unencrypted, never restored; unknown for Render/EKS | [BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md) |
| COLD-1 (new) | Medium (UX) | Observed 2026-10-14 | Render free-tier cold start ≈ 44 s vs a 15 s client timeout (mitigated by retries/loader in the working tree, uncommitted) | [NON_FUNCTIONAL_REQUIREMENTS](../01-requirements/NON_FUNCTIONAL_REQUIREMENTS.md) |

## D. Product gaps and misleading UI

| ID | Severity | Status | Issue | Evidence |
|---|---|---|---|---|
| UI-1 (new) | Medium | Confirmed | Admin **Reports**, **Reviews** and **Audit Log** pages are 19-line placeholders; the audit rows are written but only product/category activity feeds read them | [ADMIN_OPERATIONS](../05-domains/ADMIN_OPERATIONS.md) |
| UI-2 (new) | Medium | Confirmed | Checkout's harvest/delivery slot picker is local state, never sent to the backend | [CART_AND_CHECKOUT](../05-domains/CART_AND_CHECKOUT.md) |
| UI-3 (new) | High (launch) | Confirmed | Support screen shows placeholder contact details (`support@gawachabazaar.example`, `+91 12345 67890`); the deploy checklist lists this as unchecked | `mobile/app/account/support.tsx`, [`deploy/README.md`](../../deploy/README.md) |
| BAZ-1 (new) | Low | Confirmed | Bazaar+ has no benefit; the app advertises five "upcoming" ones | [DELIVERY](../05-domains/DELIVERY.md) |
| WHL-1 (new) | Low | Confirmed | `WHOLESALER` role grants nothing | [USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md) |
| PERM-1 (new) | Low | Confirmed | 10 of 41 permissions are not enforced via `require_permission` (UI-only or unused) | same |
| FARM-1 (new) | Low | Confirmed | `farms` and `quality_checks` tables have no API/service | [INVENTORY](../05-domains/INVENTORY.md) |
| MOB-1 (new) | Low | Observed | Expo web (`npm run web`) crashes at start on push-notification code (unsupported on web) | [LOCAL_SETUP](../06-development/LOCAL_SETUP.md) |
| ADS-1 (new) | Low | Confirmed | Ad image ratio (12:5) is enforced only by the Admin UI | [CATALOG](../05-domains/CATALOG.md) |

## E. Quality, tests and documentation

| ID | Severity | Status | Issue | Evidence |
|---|---|---|---|---|
| TEST-1 | High | Confirmed | No automated tests for `mobile/`, `Admin/`, `website/` | [QUALITY_GATES](../07-testing/QUALITY_GATES.md) |
| TEST-2 (new) | Low | Confirmed | No behavioural test for WebSocket, ads, home slides, wishlist, `/bazaar`; no migration-from-previous-revision test; suite has no coverage measurement | [TESTING_GUIDE](../07-testing/TESTING_GUIDE.md) |
| LINT-1 (new) | Low | Confirmed | Ruff reports 7 findings (3 in app code); no ESLint/Prettier config in the apps; no pre-commit hooks | [CODING_STANDARDS](../06-development/CODING_STANDARDS.md) |
| DEP-3 (new) | Low | Confirmed | No Python lockfile or dependency scan; `pyproject.toml` out of sync with `requirements.txt`; redundant `PyJWT`/`python-dotenv`; stale `alembic.ini` URL | [DEPENDENCY_MANAGEMENT](../06-development/DEPENDENCY_MANAGEMENT.md), [MIGRATIONS](../04-database/MIGRATIONS.md) |
| DOC-1 (new) | Medium | Confirmed | Existing docs contained errors, now corrected where verified: `FEATURES.md` said push notifications are not implemented (they are), described an Audit-log page as live, listed the slot picker as a feature; `ARCHITECTURE.md` described only the reserve-then-pay flow and omitted pay-first checkout sessions. Stale comments remain in code (PNB gateway, JWT sessions, "no audit log exists yet", missing `PHASE_14_PAYMENTS.md`) | [AI_STATUS](../00-overview/AI_STATUS.md) |
| DOC-2 (new) | Info | Confirmed | `docs/testing/EXISTING_TEST_INVENTORY.md` still describes the pre-SEC-001 fixtures (string-replace test DB) in places | that file |

## How to use this register

Add a row (with evidence) when you find an issue; mark it **Fixed** with the commit when it is; never delete history silently. Link the fix to the domain document it changes and update [AI_STATUS](../00-overview/AI_STATUS.md).
