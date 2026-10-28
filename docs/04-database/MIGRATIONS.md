# Migrations

> **Status:** Verified on 2026-10-14 (Alembic history and drift check run read-only against a disposable local database; no migration was run against any real environment).
> **Evidence:** [`backend/alembic/`](../../backend/alembic) (`env.py`, `versions/` — 38 files), [`alembic.ini`](../../backend/alembic.ini), [`backend/start.sh`](../../backend/start.sh), [`docker-compose.prod.yml`](../../docker-compose.prod.yml), the multi-replica experiments in [`docs/testing/evidence/multireplica/`](../testing/evidence/multireplica).

## Facts

| Item | Value | How verified |
|---|---|---|
| Tool | Alembic 1.20.0, SQLAlchemy models as the source (`target_metadata = Base.metadata`) | `alembic/env.py`, installed version |
| Revision files | **38** | `ls alembic/versions` |
| Heads | **1** — `f1a2b3c4d5e6` ("merge push_tokens and promotion_offers heads") | `alembic heads` |
| Branches/merges | History has two merge points: `e4a7c1b9d036` merges `c1e5f7a9b023` (checkout_sessions) and `d6b1f3a5c024` (ad card text); `f1a2b3c4d5e6` merges `a1c9e3d7b520` (push tokens) and `e4a7c1b9d036` | `alembic history` |
| Database URL | Taken from `settings.DATABASE_URL` in `env.py`; the `sqlalchemy.url` in `alembic.ini` (`postgresql+asyncpg://…`) is a stale placeholder that is always overridden (`asyncpg` is not a dependency) | `env.py`, `alembic.ini` line 48 |
| Transactional DDL | PostgreSQL; each migration runs in one transaction (`context.begin_transaction()`) | `env.py` |
| Models vs migrations | **No drift:** `alembic check` against a database migrated to head reported "No new upgrade operations detected" | run 2026-10-14 on the disposable test DB (table count 51 = 50 models + `alembic_version`) |
| What `alembic check` compares | Alembic defaults (`env.py` sets no `compare_type`/`compare_server_default`): column types are compared by default in Alembic ≥ 1.12, **server defaults are not**, and `CHECK` constraint bodies are not compared by autogenerate, so default-only or CHECK-only drift would not be reported | `env.py` `context.configure`; Alembic documentation behaviour (not re-tested here) |

## How migrations run in each environment

| Where | Mechanism | Risk |
|---|---|---|
| Docker image (`backend/Dockerfile` → `start.sh`) | `alembic upgrade head` at **every container start**, then uvicorn; `set -e` so a failed migration stops the container | With >1 simultaneous start, one process fails with a `UniqueViolation` (OPS-002, 6/6 rounds); the DB still ends at head. Orchestrators restart the failed pod |
| `docker-compose.prod.yml` | A separate one-shot `migrate` service (`alembic upgrade head`) must complete successfully before `backend` starts. Note `backend` *also* runs `start.sh`, so the migration runs a second time (a no-op) | Compose gate protects the old backend if the migration fails |
| `docker-compose.yml` (dev) | Backend command is overridden to plain `uvicorn --reload`; **no migration runs** — run `alembic upgrade head` yourself | Fresh dev DB is empty until you do |
| Kubernetes / EKS (CI workflow) | Only the image's `start.sh` (no migration Job, no init container in the manifests) | The OPS-002 race applies when pods start together |
| AWS | Unknown (service settings are not in the repository) | – |

CI does **not** run migrations, a drift check, or a migrate-from-previous-revision test before deploying ([QUALITY_GATES](../07-testing/QUALITY_GATES.md)).

## Procedures (derived from the files; run against a disposable database first)

Create a revision after changing a model:

```bash
cd backend
alembic revision --autogenerate -m "short description"   # review the generated file by hand
alembic upgrade head
alembic check                                            # must report no new operations
```

Review rules that this repository's history shows: name constraints explicitly (the schema uses named `CHECK`/`UNIQUE` constraints); use `server_default` for new NOT NULL columns on populated tables; keep `downgrade()` meaningful; never edit an applied revision; if two heads appear, add a merge revision (`alembic merge heads`) as was done twice.

Inspect or roll back (rollback caveats below):

```bash
alembic current            # needs DB access
alembic history --verbose
alembic downgrade -1
```

Never run these against a production or shared database without a verified backup ([BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md)).

## Rollback limitations

| Revision | Behaviour |
|---|---|
| `f1a2b3c4d5e6` (merge) | `downgrade()` is `pass` (normal for a merge) |
| `c5f1a7e3d9b2` (Firebase identity) | `downgrade()` **refuses** (`RuntimeError`) if any user lacks email, phone or password hash — i.e. once Firebase-only accounts exist the pre-Firebase schema cannot be restored. Treat as one-way in production |
| `efae4c4402ba` | Drops three verification-code tables; its downgrade recreates them **empty** (data is not restorable) |
| `e4a7c1b9d036` (promotion offers) | Downgrade deletes the four seeded promotions only if `redemption_count = 0` |
| `a8c3d5e7f901` (home slides) | Downgrade drops the table (any admin-edited slides are lost) |
| All others | Standard `op.*` reversals; none were exercised in a downgrade test in this audit (**unverified**) |

## Data-bearing and data-seeding migrations

| Revision | Effect on data |
|---|---|
| `37bbdf459894` seed baseline roles | Inserts the seven roles. Creates **no users** — the first ADMIN must be created with [`backend/scripts/create_admin.py`](../../backend/scripts/create_admin.py) |
| `a3f8c1d2e6b4` seed support role | Adds `SUPPORT` |
| `a8c3d5e7f901` home slides | Creates the table and seeds default slides with **third-party (Unsplash) image URLs** |
| `e4a7c1b9d036` promotion offers | If an ADMIN user already exists, inserts **four ACTIVE promotions** with real codes — `WELCOME50` (Rs 50 off, new customers, min Rs 299), `BAZAAR100` (Rs 100 off, min Rs 999), `FRESH10` (10 %, up to Rs 100, min Rs 399), `WEEKEND15` (15 %, up to Rs 150, min Rs 599) — shown in the offers carousel. On a production database that already has an admin these are **live discount codes created by a migration**. Confirm this was intended before deploying to any new environment, and check the current promotions table |
| `b9d4e6f8a012` order delivery fee | Adds `orders.delivery_fee` (default 0), so pre-existing orders carry 0 |
| `c5f1a7e3d9b2` Firebase identity | Adds `users.firebase_uid`, relaxes email/phone/password, drops `auth_sessions` |

## Known issues (see [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md))

- OPS-002: concurrent `alembic upgrade head` start-up race (proposal: one-off Job/init step or `pg_advisory_lock`).
- No test applies migrations on top of a database holding data from the previous revision, and no test compares `Base.metadata` with the migration result in CI (only the manual `alembic check` above).
- Stale `sqlalchemy.url` in `alembic.ini`.
- Old migration docstrings reference "phase" numbers and design documents under `backend/docs/`; the migration files, not those documents, define the schema.
