# AGENTS.md — instructions for AI coding assistants

Gawacha Bazaar: FastAPI + PostgreSQL backend (`backend/`), Expo customer app (`mobile/`), Next.js Admin (`Admin/`), promo site (`website/`). Money, stock and identity are involved — be careful, verify, and say what you did not verify. (No earlier `AGENTS.md`/`CLAUDE.md` existed in this repository, so nothing was merged.)

## Before substantial work

1. Read [`docs/README.md`](docs/README.md) and [`docs/00-overview/AI_PROJECT_CONTEXT.md`](docs/00-overview/AI_PROJECT_CONTEXT.md).
2. Read [`docs/00-overview/AI_STATUS.md`](docs/00-overview/AI_STATUS.md) to learn the current status, failing tests, blockers and **uncommitted work by others** (the working tree is shared and dirty).
3. Read the domain document for what you will change (`docs/05-domains/`), plus [`BUSINESS_RULES`](docs/05-domains/BUSINESS_RULES.md), [`API_REFERENCE`](docs/03-api/API_REFERENCE.md) or [`DATABASE_SCHEMA`](docs/04-database/DATABASE_SCHEMA.md) as relevant.
4. Inspect the actual source, tests and configuration before proposing a change. **Executable code, migrations, the OpenAPI document and tests are the evidence of real behaviour**; documentation (including these docs) can be stale. If a document and the code disagree, investigate, trust the code, and record the discrepancy in [`docs/10-project-management/KNOWN_ISSUES.md`](docs/10-project-management/KNOWN_ISSUES.md).

## Rules

- **Keep it minimal.** No new dependencies, frameworks or architectural changes unless asked and justified. Match surrounding code style ([`CODING_STANDARDS`](docs/06-development/CODING_STANDARDS.md)).
- **Preserve invariants:** the backend alone computes prices, fees, discounts and status changes; state machines (`*_state.py`) and DB constraints stay authoritative; lock order Order → Payment (→ Fulfillment), lots by ascending id; never hold a row lock across a gateway call; one backend worker (rate limit, WebSocket hub and reservation sweep are in-process). See the invariant list in `AI_PROJECT_CONTEXT.md` §6.
- **Security and authorization:** every new/changed route needs an explicit auth gate and an updated, *reviewed* [`backend/tests/authz_golden.json`](backend/tests/authz_golden.json) (`AUTHZ_REGEN=1` only after a deliberate review). Customers get 404 (not 403) for other customers' objects. Never trust client-supplied amounts, ids of other users, roles or statuses.
- **Database integrity and migrations:** change models and add an Alembic revision together; run `alembic check` against a migrated disposable database; keep `downgrade()` honest; never run migrations, seeds or destructive SQL against a shared or production database ([`MIGRATIONS`](docs/04-database/MIGRATIONS.md)). `backend/scripts/seed_dummy_data.py` is dev-only.
- **API compatibility:** installed mobile apps deploy independently of the API — never remove or rename fields they use ([`INTEGRATION_CONTRACTS`](docs/11-integrations/INTEGRATION_CONTRACTS.md) §7).
- **Secrets and data:** never print, log, commit or paste secrets, tokens, `.env` contents, service-account files, `.mcp.json` values or customer data. When inspecting config, extract **names only** or redact values. If a secret is exposed, say so and recommend rotation ([`SECRETS_MANAGEMENT`](docs/08-security/SECRETS_MANAGEMENT.md)).
- **Tests may only truncate a disposable local database:** set `TEST_DATABASE_URL` to a loopback `*_test` database carrying the comment `gb-disposable-test-db` (never 5432/5433, never derived from `DATABASE_URL`). Do not weaken `backend/tests/_db_safety.py` ([`TESTING_GUIDE`](docs/07-testing/TESTING_GUIDE.md)).
- **Pushing to `main` deploys to production without any automated check.** Do not commit or push unless the user asks; never force-push; do not bundle unrelated changes ([`GIT_WORKFLOW`](docs/06-development/GIT_WORKFLOW.md)). Mobile JS-only changes can ship by OTA (`eas update`, channel of the installed build); native/dependency/`app.json` changes need a rebuild ([`DEPLOYMENT`](docs/09-deployment-operations/DEPLOYMENT.md)).

## Verify before you report

- Run the relevant checks and **report their real result**: backend `python -m pytest -p no:cacheprovider` (disposable DB), `python -m ruff check .`, `alembic check`; `npx tsc --noEmit` in `mobile/` and `Admin/`. There are no frontend tests.
- **Never claim a test, deployment, migration, build or fix succeeded without checking its output.** Say what you ran, what you did not, and what remains unverified. Known baseline on 2026-10-14: 7 backend tests fail because the default `DELIVERY_BASE_FEE` was changed 20 → 40 (see `AI_STATUS.md`); don't report "all tests pass" without re-running.
- UI changes cannot be validated by the tests; say so, or verify on a device/browser when possible. The Expo web target currently crashes at start (push notifications).

## Keep the documentation true

- When behaviour changes, update the matching document in `docs/` in the same change; regenerate [`API_REFERENCE`](docs/03-api/API_REFERENCE.md) and [`DATABASE_SCHEMA`](docs/04-database/DATABASE_SCHEMA.md) with the scripts in [`docs/_tools/`](docs/_tools/README.md) after route/model/migration changes.
- **Update [`docs/00-overview/AI_STATUS.md`](docs/00-overview/AI_STATUS.md)** when active development status, blockers or priorities change (test results, working-tree state, new/closed issues). Update `KNOWN_ISSUES.md` when you find or fix an issue.
- Mark unverified statements as unverified; don't invent endpoints, tables, variables, features or test results.

## Quick commands

```bash
cd backend && python -m ruff check .
cd backend && TEST_DATABASE_URL=<local *_test db> python -m pytest -p no:cacheprovider -q
cd backend && DATABASE_URL=<migrated disposable db> python -m alembic check
cd mobile && npx tsc --noEmit        # also: cd Admin && npx tsc --noEmit
```

Setup, environment variables and deployment: [`docs/06-development/LOCAL_SETUP.md`](docs/06-development/LOCAL_SETUP.md), [`ENVIRONMENT_VARIABLES.md`](docs/06-development/ENVIRONMENT_VARIABLES.md), [`docs/09-deployment-operations/DEPLOYMENT.md`](docs/09-deployment-operations/DEPLOYMENT.md).
