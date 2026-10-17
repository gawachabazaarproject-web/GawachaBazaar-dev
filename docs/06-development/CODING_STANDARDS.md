# Coding Standards (as practised in this repository)

> **Status:** Partially verified. **Last verified:** 2026-10-14. There is **no written style guide**; this document records (a) the conventions that are *configured or enforced*, (b) the conventions the code *consistently follows* (stated in comments/docstrings or observed), and (c) where the code departs from its own stated rules. Nothing here is imposed by a tool unless marked **Enforced**.
> **Evidence:** [`backend/pyproject.toml`](../../backend/pyproject.toml), [`backend/tests/test_architecture.py`](../../backend/tests/test_architecture.py), module docstrings in `backend/app/`, `mobile/tsconfig.json`, `Admin/tsconfig.json`, [`mobile/src/theme/colors.ts`](../../mobile/src/theme/colors.ts), [`.gitattributes`](../../.gitattributes).

## Backend (Python 3.11, FastAPI)

### Tooling
| Item | State |
|---|---|
| Linter | **Enforced only when run by hand:** Ruff, target `py311`, line length 88 (but `E501` ignored), rules `E,W,F,I,B,UP`, `B008` ignored (FastAPI `Depends`), isort first-party `app`. Last run: 7 findings (`E741` ×3 in `inventory_reservation.py`, `F841` ×2 and `I001` ×2 in tests) |
| Formatter | None configured (no `ruff format`/`black` settings); the code is consistently formatted but not by a tool you can run to check |
| Types | Type hints are used throughout; **no type checker** (mypy/pyright) is configured |
| Tests | pytest, `asyncio_mode=auto` ([TESTING_GUIDE](../07-testing/TESTING_GUIDE.md)) |

### Architecture rules the code follows
1. **Layering:** router → dependency → service → model. Routers stay thin (validation, auth dependency, one service call, response model); **every rule lives in a service**; lifecycles are pure modules named `*_state.py`.
2. **Never trust the client:** amounts, totals, fees, statuses and identities come from the server or the verified token, not the request body.
3. **Transactions:** services own `commit()`/`rollback()`; lock rows in a fixed order (Order → Payment → …; lots by ascending id); never call an external service while holding a row lock; emit realtime/push **after** the commit.
4. **Idempotency by design:** re-entrant services return the existing result; rely on unique constraints and re-read the winner of a race (`IntegrityError` path).
5. **Errors:** raise `AppException` subclasses (`NotFoundError`, `ConflictError`, `BusinessValidationError`, …) with stable `code`s; never leak internals; unexpected errors are logged with traceback and returned as `INTERNAL_SERVER_ERROR` ([ERROR_HANDLING](../02-architecture/ERROR_HANDLING.md)).
6. **Existence is not disclosed:** a missing object and another customer's object both return 404.
7. **Money:** `Decimal` only; quantize explicitly (`ROUND_HALF_UP` for line totals, `ROUND_CEILING` for the delivery fee).
8. **Schemas:** Pydantic v2 models subclass `BaseSchema` (strips whitespace, `from_attributes=True`); list endpoints use `page`/`page_size` with `MAX_PAGE_SIZE = 100`.
9. **Configuration:** only `app.core.config.Settings` reads the environment (exception: `GOOGLE_APPLICATION_CREDENTIALS` in `firebase.py`); new settings get a default and appear in both example env files ([ENVIRONMENT_VARIABLES](ENVIRONMENT_VARIABLES.md)).
10. **Logging:** `from app.core.logging import logger`; messages carry a stable upper-case marker (`PAYMENT_RECONCILIATION: …`) so they can be searched; never log tokens or full request bodies (`?token=` is redacted).
11. **Routes:** declare `summary`, `response_model` and `status_code`; mount order in `api/v1/router.py` matters; after adding or re-gating a route update `tests/authz_golden.json` deliberately.
12. **Migrations:** autogenerate, then hand-review; name constraints; keep `downgrade()` honest ([MIGRATIONS](../04-database/MIGRATIONS.md)).
13. **Comments:** the code uses long explanatory docstrings that record *why* (lock order, race behaviour). Several mention historical "Phase N" decisions and are partly stale (PNB gateway, JWT sessions) — verify against the code before trusting a comment.

### Where the code departs from its own rules
- The `colors.ts` rule "only this file may define raw colour values" (below) is not followed everywhere.
- Some dependency/ruff leftovers: `E741` ambiguous names, unused local variables in test harness files.
- Several permission strings are defined but not enforced by `require_permission` ([USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md)).

## Frontend (TypeScript)

| Item | Mobile (`mobile/`) | Admin (`Admin/`) | Website |
|---|---|---|---|
| Strict mode | `strict: true` | `strict: true` | `strict: true` |
| Path alias | `@/*` → `src/*` | `@/*` → repo root of the app | `@/*` |
| Lint config | **none** (no ESLint/Prettier config files; no `lint` script) | `npm run lint` → `next lint`, no ESLint config file in the folder (behaviour on Next 16 not checked) | same |
| Type check | `npx tsc --noEmit` (clean on 2026-10-14) | same (clean) | not run |
| Framework conventions | Expo Router file routes in `app/`; one API module per backend area in `src/api/`; TanStack Query hooks per domain in `src/features/`; Zustand stores in `src/store/`; components in `src/components/` (shared) | App Router pages in `app/(admin)/<page>/page.tsx`; typed API clients in `lib/<module>.ts`; shared UI in `components/` | components in `components/` |

Conventions observed in the mobile app:
- **No business rules in the client.** Components render API values; `statusPresentation.ts` and similar files are presentation only.
- **Design tokens:** colours, spacing, radii and typography come from `src/theme` (`colors.ts` states "Only this file may define raw color values"). A `git grep` on 2026-10-14 found **26 raw `#rrggbb` literals outside `src/theme`** (e.g. in `app/checkout/index.tsx`, `SearchHome.tsx`, `app/bazaar/index.tsx`, and the login artwork-matching colours), so the rule is a convention, not enforced. New colours should be added as tokens.
- **Server state vs client state:** TanStack Query for server data (with optimistic updates for cart/wishlist), Zustand for session/UI state.
- **Auth/network:** all HTTP goes through `src/api/client.ts` (token attach, one refresh-and-retry, error normalisation); screens do not call axios or Firebase directly — they call store actions (`authStore.ts`).
- **Scale-to-device layouts:** the login screen scales artwork pixel values by `screenWidth / 819` (`useLoginScale`); other screens use the theme spacing scale.
- **Admin:** the permission list in `lib/permissions.ts` is a manual mirror of the backend and only hides UI.

## Cross-cutting

- Line endings: `*.sh`, `Caddyfile`, `Dockerfile`, `*.yml` are forced to LF in `.gitattributes`; Git on Windows warns that other files will convert LF → CRLF.
- Do not commit `.env*` (ignored except `.env.example`), `google-services.json`, keystores or service-account files; never paste secrets into docs or chat ([SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md)).
- Prefer the smallest change; do not add dependencies or restructure without need ([AGENTS.md](../../AGENTS.md)).
- Keep documentation next to the change: update the matching file in [`docs/`](../README.md) when behaviour changes.
