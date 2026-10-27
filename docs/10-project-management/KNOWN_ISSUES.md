# Known Issues

> **Status:** Verified (each row cites its evidence) as of 2026-10-14. This is the **single consolidated register**. Entries from the earlier QA audit keep their IDs and link to [`docs/testing/DEFECT_LOG.md`](../testing/DEFECT_LOG.md) / [`RISK_REGISTER.md`](../testing/RISK_REGISTER.md) for full reproduction details; entries found while writing this documentation set carry new IDs and are marked **(new)**. "Confirmed" = reproduced by test/experiment or unambiguous in code; "Suspected" = pattern seen, not reproduced. **Nothing here has been fixed by this task.** Severity is my assessment, not the owner's.

## A. Money, correctness and data integrity

| ID | Severity | Status | Issue | Evidence / detail |
|---|---|---|---|---|
| PAY-001 | High | Fixed 2026-10-18, regression test passes against a disposable DB | A captured online payment is attached to an unrelated, already-existing order (latest cart already checked out, e.g. by COD) with no refund | strict `xfail` test; [DEFECT_LOG](../testing/DEFECT_LOG.md), [PAYMENTS](../05-domains/PAYMENTS.md) |
| G-REF-1 (new) | Medium | Found by code inspection, not reproduced | A refund whose gateway response is lost before an id is stored stays `PROCESSING`; "process" and "check status" both refuse; no in-app recovery | [REFUNDS](../05-domains/REFUNDS.md) |
| PAY-2 (new) | Low | Confirmed (code/docstring mismatch) | `payment_state.py` says a `CANCELLED` payment is superseded via `/retry`, but `can_retry_payment` allows only `FAILED`/`EXPIRED` | [PAYMENTS](../05-domains/PAYMENTS.md) |
| PAY-004 (new) | High | Fixed 2026-10-18, regression test passes against a disposable DB | A transient Razorpay error during webhook-driven checkout completion commits the dedup row, so Razorpay's retry is dropped and the order is never created | [PAYMENT_AUDIT](../testing/PAYMENT_AUDIT_2026-10-18.md) |
| PAY-005 (backend sweep + start re-check fixed and tested 2026-10-18), PAY-006 + mobile session persistence (fixed 2026-10-18, `tsc` clean, never run on a device), PAY-008 and PAY-009 (fixed and tested 2026-10-18; PAY-009 = automatic retry + lookup, still no admin screen for REFUND_FAILED sessions), PAY-010 (new) | High–Medium | PAY-006/008–010 found by code reading 2026-10-18, not reproduced | No reconciliation of paid-but-no-order; app shows an error after a successful payment; concurrent `start` makes two Razorpay orders; locks held across gateway calls; auto-refund failures invisible; test keys only warn in production | [PAYMENT_AUDIT](../testing/PAYMENT_AUDIT_2026-10-18.md) |
| PAY-3 (new) | Medium | Confirmed | Money captured for a payment/session nothing matches (`PAYMENT_WEBHOOK_UNKNOWN_REFERENCE`) and automatic refunds that fail (`REFUND_FAILED`) are only logged — no job, queue or alert; pay-first automatic refunds have no `refunds` row | [WEBHOOKS](../03-api/WEBHOOKS.md), [REFUNDS](../05-domains/REFUNDS.md) |
| INV-1 (new) | Medium | Open (by design) | Lots whose old pack quantity was not a whole number of grams/ml/pieces (e.g. 0.416 dozen) are **quarantined** by migration `e5f6a7b80923`: never sold or moved until an admin confirms the amount (`POST /inventory/admin/lots/{id}/resolve-base`). Listed in `inventory_base_migration_report` | [INVENTORY](../05-domains/INVENTORY.md) |
| INV-2 (new) | Low | Open | Historical drift caused by the old rounding (e.g. 2 g per order from awkward-size lots) is not recoverable by the migration; an admin-resolved lot is quarantined again if the migration is downgraded and re-applied (its derived pack value is not exact) | [INVENTORY](../05-domains/INVENTORY.md) |
| INV-3 (new) | Medium | Open | Old pack columns (`inventory_lots.quantity/reserved_quantity`, movement and reservation-item `quantity`) are kept as derived display values and a DB trigger (`trg_gb_sync_lot_base`) still lets legacy writers use packs; retire both only after confirming no consumer writes them | [INVENTORY](../05-domains/INVENTORY.md) |
| INV-4 (new) | Low | Open | Legacy per-size low-stock levels (`variant.reserve_level`, packs of that size, default 10) still apply to products with no product-level reserve; the migration moved only unambiguous products (rest are in the report as `RESERVE_LEVEL_AMBIGUOUS`) | [INVENTORY](../05-domains/INVENTORY.md) |
| INV-5 (new) | Medium | Open (unverified) | The inventory UI changes (Add stock preview, product low-stock alert, shared `units.ts`) have not been seen in a browser; the deployed Admin predates them | [AI_STATUS](../00-overview/AI_STATUS.md) |
| OTP-1 (new) | Medium | Open (by design) | Delivery OTP is delivered only via push and the customer app (no SMS fallback); a customer without the app/push cannot receive a code and needs support/ADMIN override | [COD_OPERATIONS](../05-domains/COD_OPERATIONS.md) |
| OTP-2 (new) | Medium | Open (unverified) | OTP push, notification tap routing and the OTP screens have never run on a device; FCM delivery unverified | [AI_STATUS](../00-overview/AI_STATUS.md) |
| OTP-3 (new) | Low | Open (by design) | ADMIN completing via `/fulfillments/{id}/deliver` bypasses the code (audited as `DELIVERY_OTP_ADMIN_OVERRIDE`); the legacy `autouse` test fixture runs older suites with enforcement off, the OTP suite (`delivery_otp` marker) with it on | [COD_OPERATIONS](../05-domains/COD_OPERATIONS.md) |
| FEE-1 | resolved 2026-10-27 (base fee back to Rs 20 by owner decision; tests pinned) | ~~Confirmed, open~~ | The 2026-10-14 change of the default base delivery fee (20 → 40) broke **7 existing tests** that hard-code the old default; they pass with `DELIVERY_BASE_FEE=20` | [TESTING_GUIDE](../07-testing/TESTING_GUIDE.md), [DELIVERY](../05-domains/DELIVERY.md) |
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
| DEL-1 | P0 | **Fixed 2026-10-26** | Router was called inside `_plan_checkout` while cart/variant row locks were held. Now resolved before locking; proven by a `FOR UPDATE NOWAIT` probe test | `services/order.py`, `tests/test_delivery_hardening.py` |
| DEL-2 | P1 | **Fixed** | Blank numeric env values (`PACKING_POINT_LATITUDE=` as in `.env.example`) crashed startup; `env_ignore_empty=True` | `core/config.py` |
| DEL-3 | P1 | **Fixed (not deployed)** | `docker-compose.prod.yml` forwarded no delivery/routing/Redis variables and had no Redis; added both (defaults = code defaults) | `docker-compose.prod.yml` |
| DEL-4 | P1 | **Fixed** | OSRM answers "Ok"/0 m for points far from any road (swapped lat/lng proven live); snap guard -> 422 | `services/routing/osrm.py` |
| DEL-5 | P1 | **Fixed** | Address without map location could be ordered with only the base fee; now 422 (origin configured) and `needs_location` in the quote | `services/order.py`, `services/bazaar.py` |
| DEL-6 | P1 | **Open - launch decision** | Public OSRM/Nominatim are best-effort without SLA; self-host OSRM before real traffic | [DELIVERY](../05-domains/DELIVERY.md) |
| DEL-7 | P2 | **Fixed 2026-10-27** | Pay-first `complete`/`verify`/webhook now resolve the route BEFORE locking the checkout-session row and pass it to `OrderService.checkout(route_outcome=...)`; proven by `tests/test_delivery_payfirst_locks.py` (probe fails if the old order is restored) | `services/checkout_session.py` |
| DEL-8 | P2 | **Blocked (external)** | Mobile flow not run on any emulator/device. Needs: an Android emulator image (not installed; ~2-3 GB) or a USB device, a dev build, a Firebase test account for the app's Firebase project, and a backend reachable from the device | [DELIVERY](../05-domains/DELIVERY.md) |
| DEL-9 | P2 | **Blocked (external)** | Real Firebase login and Razorpay payment not exercised (test double / fake gateway only). Needs a Firebase test user and Razorpay *test-mode* keys; neither was provided | tests |
| DEL-10 | P3 | **Fixed 2026-10-27** | Removed the dead `addressApi.deliveryQuote`, the unused `useDeliveryQuote` in `features/address`, the `DeliveryQuote` type and `utils/delivery.ts`; the only delivery-quote call left is the real `/bazaar/delivery-quote` | mobile |
| DEL-11 | P3 | **Fixed** | 7 tests hard-coded the old Rs 20 base fee (FEE-1); the suite now pins the fee rule | `tests/conftest.py` |

## Product / inventory UX milestone (2026-10-26)

| ID | Pri | Status | Issue | Where |
|---|---|---|---|---|
| UX-1 | P1 | **Fixed (uncommitted)** | Slug function produced an empty web address for Marathi/Devanagari names; Add product could leave a half-built draft (≈11 separate requests) | `Admin/lib/product-form.ts`, `POST /catalog/products/quick-create` |
| UX-2 | P1 | **Fixed (uncommitted)** | Normal stock receipts created a delivery with no expiry, so expiry alerts could never fire for them; `expiry_date` is now accepted on receive | `ReceiveStockRequest`, [INVENTORY](../05-domains/INVENTORY.md) |
| UX-3 | P2 | **Fixed (uncommitted)** | Correct / remove / move worked per lot, in packs, from the lot page; now product-level, in kg, atomic, with Undo | `services/product_stock.py` |
| UX-4 | P2 | **Fixed (uncommitted)** | `PATCH /products/{id}` allowed `ACTIVE` with no size or an unpriced size; now refused (422) when a product goes live | `CatalogService._require_publishable` |
| UX-5 | P2 | **Open - client decision** | Oldest-first allocation of count/remove/move differences is a business-rule assumption; confirm with the client | [INVENTORY](../05-domains/INVENTORY.md) |
| UX-6 | P2 | **Open - client decision** | `CATALOG_STAFF` role exists but nobody holds it; decide who gets it. Catalogue staff can also delete a *size* (`DELETE /variants/{id}` is gated `products.update`; refused when it has order/quote/stock history) | `core/permissions.py` |
| UX-7 | P2 | **Open** | Admin UI changes (Add product, product page, Inventory page, dialogs) were built and type-checked (`tsc`, `next build`) and the pure logic has `node --test` tests, but they were **never run signed-in in a browser**; usability not tested with real staff | `Admin/` |
| UX-8 | P3 | **Open** | Inventory "Low / Out / Expiring" filters judge every product (slower path, chunked); fine for hundreds of products, revisit at thousands | `InventoryService.admin_list_product_stock` |
| UX-9 | P3 | **Open** | Per-user warehouse access, category shelf life, bulk import / CSV, bulk price and stock updates, server-side "needs attention" list filter are not built | [PRODUCT_INVENTORY_SIMPLIFICATION_AUDIT](PRODUCT_INVENTORY_SIMPLIFICATION_AUDIT.md) |
| DEL-12 | P1 | **Open (external)** | The real Gawacha warehouse coordinates are not in the repo or the dev database; all live validation used a stand-in. Set `PACKING_POINT_*` or choose the packing point in Admin -> Settings, then re-run the live suite with `GB_WAREHOUSE_LAT/LNG` | [DELIVERY](../05-domains/DELIVERY.md) |

## Validation pass (2026-10-26, after the UX milestone)

| ID | Pri | Status | Issue | Where |
|---|---|---|---|---|
| VAL-1 | P1 | **Fixed (uncommitted)** | `DELETE /variants/{id}` (gated `products.update`) also deleted a size's customer cart lines and its **price history**; it is now `products.delete` (ADMIN) only and refused when the size has orders, quotes, stock, a cart line, more than one price row, or is the only size of a live product - hide it instead | `CatalogService.delete_variant` |
| VAL-2 | P1 | **Fixed (uncommitted)** | "Today" for expiry used the server's / UTC date: in India between 00:00 and 05:30 an item expiring today showed "tomorrow". Expiry now follows `BAZAAR_TIMEZONE` (default Asia/Kolkata) | `app/core/business_time.py` |
| VAL-3 | P1 | **Fixed (uncommitted)** | The header alert counted **sizes** ("3 items need restocking" for one tomato product) while the Inventory chips counted products. One rule now (`stock_levels.product_status`): header, chips and Products list agree, and only live (ACTIVE) products can be low/out | `services/stock_levels.py`, `stock_alerts.py` |
| VAL-4 | P2 | **Fixed (uncommitted)** | Stock dialogs could be opened from a stale card; the numbers are now re-read from `GET /inventory/admin/products/{id}` just before a dialog opens, and the list reloads when the tab regains focus | Admin `ProductStockView`, product page |
| VAL-5 | P2 | **Fixed (uncommitted)** | Catalogue staff could change low-stock levels (`PATCH /variants` with `reserve_level` needed only `products.update`); now needs `inventory.adjust` | `api/v1/catalog.py` |
| VAL-6 | P3 | **Fixed (uncommitted)** | Products list showed a unit-less pack count and the raw status "Active"; now "118 kg" / Live-Draft-Hidden, with the Inventory page's low/out status | `AdminProductListItemResponse.stock_text` |
| VAL-7 | P2 | **Open - client decision** | Warehouse staff can operate on every warehouse: no user-to-warehouse link exists anywhere in the model, and the PRD describes single-warehouse operation. Limiting a user to one warehouse needs a new table/column and enforcement on every inventory route | [INVENTORY](../05-domains/INVENTORY.md) |
| VAL-8 | P2 | **Open - client decision** | Oldest-first allocation for count/remove/move differences is an implementation assumption, not an approved business rule (see UX-5). It is isolated in `ProductStockService._fifo` so a different strategy is a one-function change. Note: a correction takes from the *oldest* lot, which may not be the lot that is about to expire | `services/product_stock.py` |
| VAL-9 | P3 | **Open** | "Needs attention" on the Products list is computed per page row (no server-side filter or tab); Inventory has real server-side Low / Out / Expiring filters | Admin |
| VAL-10 | P3 | **Open** | Real usability test with staff not done; browser run used a local stand-in for Firebase sign-in (see the final report) | - |

## Pre-client hardening pass (2026-10-26, last)

| ID | Pri | Status | Issue | Where |
|---|---|---|---|---|
| HARD-1 | P2 | **Fixed (uncommitted)** | The floating "Alarm on" pill covered the confirm button of open dialogs on a phone; it is hidden while a dialog is open | `NewOrderAlarm.tsx` |
| HARD-2 | P2 | **Fixed (uncommitted)** | A stock action refused because someone else changed the stock now says "Stock changed by another user. The latest available is X" and refreshes the dialog's numbers | `StockDialogs.tsx` |
| HARD-3 | P3 | **Fixed (uncommitted)** | Add stock showed this delivery's packs only; it now shows what each size will be after adding ("250 g -> 480 packs") | `StockDialogs.tsx` |
| HARD-4 | P3 | **Fixed (uncommitted)** | Unsupported / over-8-MB photos are explained before saving; a failed upload names the reason; "Publish" is not offered for products that cannot be published; Delete size is not offered where it must fail, and a refused delete offers "Hide size" | Admin |
| HARD-5 | P3 | **Documented** | `/readiness` (other session) is public on purpose and exposes only database/redis/origin state strings; covered by a test | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| HARD-6 | P2 | **Open - business** | Real Firebase sign-in was not tested (no credentials available here); all browser runs used a local sign-in stand-in | - |
| HARD-7 | P3 | **Open** | Three small copies of the unit-family table remain (`inventory.ts`, `product-form.ts`, `ProductStockView.tsx`); stock status, readiness, expiry wording and stock dialogs are single implementations | Admin |
| DEL-13 | P1 | **Fixed 2026-10-27** | Load test: at 100 concurrent users the API collapsed (92% 500/ReadError) - pool 5+10 vs 40 AnyIO threads, each request holding a connection while waiting for threads. Fix: in-flight cap = pool size (`core/concurrency.py`), pool 12+12, 503 `SERVER_BUSY` shedding; 0 errors at 100 users afterwards | `app/core/concurrency.py`, [AWS plan](../09-deployment-operations/AWS_PRODUCTION_PLAN.md) §6.1 |
| DEL-14 | P2 | **Closed as a measured decision (2026-10-27)** - 1 worker kept, no catalog cache for month one (see AWS plan §6.3). One Python process is CPU-bound at ~40-47 req/s on a fast desktop core (~60 ms CPU/request: ~28% FastAPI route matching over ~200 routes, rest ORM). Graviton capacity unmeasured. Options: TTL cache for anonymous catalog GETs, route-table flattening, 2+ workers after moving rate limiter/WebSocket hub/sweep to Redis | AWS plan §6.1 |
| DEL-15 | P3 | **Fixed 2026-10-27** | Uploads are validated by content (signature, full decode with Pillow, 16-8000 px sides, 40 MP cap, declared type must match), random public_id (client file name never used), and replaced/deleted images are released from Cloudinary (own cloud + `gawachabazaar/` folders only, best effort after commit). 27 tests, no network. Not covered: deleting a whole product/category that owns images | `services/image_upload.py`, `tests/test_image_upload.py` |
| DEL-16 | P2 | **Fixed, validation pending** | `requirements.in` (ranges) -> `requirements.txt` (pip-compile lock with hashes, Linux/py3.11); Dockerfile installs with `--require-hashes` and pins `python:3.11-slim` by digest; update procedure in DEPENDENCY_MANAGEMENT. The lock resolved newer FastAPI/Starlette than the dev venv, so the full suite must pass INSIDE the locked image before this is closed (run started, result in the report) | `backend/requirements.*`, `backend/Dockerfile` |
| DEL-17 | P2 | **Blocked (external)** | AWS: no account/credentials - nothing created, restored or load-tested on AWS; CI/CD workflows written but never run | AWS plan §16 |
| DEL-18 | P2 | **Open** | Firebase revocation check needs the service account: without `FIREBASE_SERVICE_ACCOUNT_JSON` every request logs `FIREBASE_REVOCATION_CHECK_FAILED` and a revoked session is not detected. Set the key (SSM SecureString) in staging/production | `core/firebase.py` |
| DEL-19 | P3 | **Open** | Expo push: `PUSH_TICKET_ERROR InvalidCredentials` (no FCM server credentials for the build) - order notifications are not delivered | `services/push.py` |
| DEL-20 | P2 | **Partly verified 2026-10-27** | Android device (Xiaomi, USB): real Firebase login, address, cart, quote 7 170 m / Rs 112, Razorpay TEST payment, order 1 CONFIRMED with distance/provider/warehouse stored, screen total equals DB. Not done: payment failure/cancel/duplicate on the device, tamper from the phone, real warehouse, AWS | [AWS plan](../09-deployment-operations/AWS_PRODUCTION_PLAN.md) section 6.4 |

## How to use this register

Add a row (with evidence) when you find an issue; mark it **Fixed** with the commit when it is; never delete history silently. Link the fix to the domain document it changes and update [AI_STATUS](../00-overview/AI_STATUS.md).

## Delivery pricing / Refer & Earn / delivery partners pass (2026-10-27)

| ID | Severity | Item |
|---|---|---|
| DEC-1 | closed | Base delivery fee decided by the owner: Rs 20 everywhere (2026-10-27). Release check: the live host must not override it. |
| DEC-2 | decision | Referral reward values, windows and cap are placeholders; program is OFF. **Rewards cannot be spent yet** (no checkout redemption). |
| DEC-3 | decision | Partner earning formula and payout are placeholders; no payout flow. |
| COD-1 | P2 | No delivery OTP / proof of delivery for COD ([COD_OPERATIONS](../05-domains/COD_OPERATIONS.md)). |
| MOB-1 | P3 | Mobile has no customer-facing partner-tracking map (API `GET /orders/{id}/delivery-tracking` exists). Partners poll for new jobs (15 s), no push. |
| MOB-2 | P3 | Referral/partner screens were verified by `tsc` only unless the release report says otherwise. |
| DOC-1 | P3 | Pricing change: tests that asserted fractional-km fees (e.g. 4.7 km = Rs 67) were deliberately updated to the whole-km rule (4.7 km = Rs 70). |
| ENV-1 | note | Docker Desktop stopped during the test run (not by this work); the tmpfs test DB was recreated and re-migrated, then the suite rerun. |
