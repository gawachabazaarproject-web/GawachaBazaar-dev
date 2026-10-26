# Test Data, Fakes and Fixtures

> **Status:** Verified from source on 2026-10-14. Companion to [TESTING_GUIDE](TESTING_GUIDE.md).
> **Evidence:** [`backend/tests/conftest.py`](../../backend/tests/conftest.py), [`firebase_fake.py`](../../backend/tests/firebase_fake.py), [`_db_safety.py`](../../backend/tests/_db_safety.py), [`test_razorpay_payments.py`](../../backend/tests/test_razorpay_payments.py) (`FakeRazorpay`), [`test_phase_14_payments.py`](../../backend/tests/test_phase_14_payments.py) (`FakePNBGateway`), [`test_push_send.py`](../../backend/tests/test_push_send.py), [`backend/scripts/seed_dummy_data.py`](../../backend/scripts/seed_dummy_data.py), [`tests/multiproc/`](../../backend/tests/multiproc).

## Principles actually followed

1. **Real PostgreSQL, fake outside world.** Anything involving locks, constraints or transactions runs against PostgreSQL; Firebase, Razorpay, Expo push, Cloudinary and routing are replaced in-process. No test needs a network, a service account or a payment key.
2. **Isolated, disposable data.** Each test starts from truncated tables in a database that is provably local and marked disposable ([TESTING_GUIDE](TESTING_GUIDE.md)); nothing is shared between tests.
3. **Tests build their own data.** There is no global factory library; test modules create users, roles, products, variants, prices, lots and addresses through small local helpers (e.g. `_customer(db_session, tag)` in `test_phase_13_cart_orders.py`, `_staff(...)` in the phase 15/16/18 files). Tags in emails/phones keep rows distinct within a test.
4. **No production data, no real credentials.** Fake keys use obviously fake values (e.g. a `rzp_test_Fake…` key id in the Razorpay tests); the fixtures blank the real variables (`RAZORPAY_*`, `CLOUDINARY_*`, `GOOGLE_MAPS_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`) before the app is imported.

## The fakes

| Fake | Where | What it simulates | Limits |
|---|---|---|---|
| `FakeFirebase` / `fake_firebase` | `tests/firebase_fake.py`, installed for every test by an autouse fixture | Token issue/verify (`issue()` mints opaque tokens; unknown tokens are rejected like forged ones), expired tokens, user create/update/disable/revoke/delete, email-exists and password-policy errors | Does not model real Firebase timing, revocation propagation, phone OTP or Google; `auth_headers_for(db, user, **claims)` is the usual way to authenticate a test client |
| `FakeRazorpay` | `test_razorpay_payments.py`, an `httpx.MockTransport` handler injected into `RazorpayGateway` | `POST /orders`, `GET /orders/{id}/payments`, refunds, webhook payloads and HMAC signatures built with the test secrets | Not Razorpay's real behaviour; payload shapes were written from the gateway's own parser |
| `FakePNBGateway` | `test_phase_14_payments.py` (subclass of the unwired `PNBGateway`) | A scriptable gateway for the order-first payment API: success/failure/timeout/outcome-unknown, webhook events | Historical name; exercises the generic `PaymentGateway` protocol |
| Expo push | `test_push_send.py` (`monkeypatch` of `httpx.post`) | Ticket responses: ok, `DeviceNotRegistered`, credential errors, no tokens | Real Expo/FCM not contacted |
| Routing (OSRM) / Nominatim / Redis | `test_delivery_fee.py`, `test_delivery_routing.py`, `test_delivery_quote_api.py` stub the provider / `httpx.get` / Redis client | Fees, boundaries, cache hit/miss/expiry/Redis down, quote API, checkout authority | Live providers not exercised |
| Cloudinary | variables blanked; upload paths return 503 in tests | – | Real uploads untested |

## Constants and setup data

- **Roles:** `db_session` truncates `roles`; each test (or helper) inserts the roles it needs. The seven baseline roles come from [`app/core/roles.py`](../../backend/app/core/roles.py).
- **Delivery fee in tests:** `test_delivery_fee.py` pins every fee setting through `monkeypatch`; **other tests rely on the code default** and therefore broke when the default base fee changed (7 failures on 2026-10-14, [TESTING_GUIDE](TESTING_GUIDE.md)). Prefer pinning `DELIVERY_BASE_FEE` in any test that asserts a total.
- **Authorization snapshot:** [`authz_golden.json`](../../backend/tests/authz_golden.json) is data, reviewed by a human; regenerate only with `AUTHZ_REGEN=1` after a deliberate access change.
- **Money:** assertions compare `Decimal` or the API's two-decimal strings (e.g. `'90.00'`).

## Non-test data sets (for exploration, never CI)

| Script | What it does | Safe target |
|---|---|---|
| `backend/scripts/seed_dummy_data.py` | Idempotent dev-only seed of categories, products, variants, prices, supplier, batches and lots so a real checkout can be exercised from the app | a local development database only |
| `backend/scripts/seed_sections.py` | Seeds the "Ready to Cook" and "Juices" storefront sections (categories with photos + a few sellable products), get-or-create on slug; editable afterwards in the Admin panel | local first; it appears intended for real environments too, but creates catalogue data — review before running elsewhere |
| `backend/tests/multiproc/perf.py`, `run_scenarios.py` | Seed 100 customers with products/stock/addresses for load and multi-replica experiments; they **drop and recreate schema `public`** in the target | a `*_test` database passing the safety policy (e.g. `gb_multiproc_test`) |

Migration seed data (roles, support role, four home slides, four starter promotions when an admin exists) is created by Alembic, not by tests ([MIGRATIONS](../04-database/MIGRATIONS.md)).

## Hygiene rules

- Never put a real customer record, phone number, token or key in a fixture or snapshot.
- Do not reuse the QA container for anything you care about: its data is in `tmpfs` and is destroyed whenever it restarts; the suite empties it on every test.
- If you add a table, add it to the `TRUNCATE` list in `conftest.py` when it has no foreign key to an already-truncated table (otherwise it will not be cleaned — currently true of `ads` and `home_slides`).
- Write a failing test first for a defect, mark it `xfail(strict=True)` if it cannot be fixed yet, and note it in [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md).
