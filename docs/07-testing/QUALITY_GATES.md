# Quality Gates

> **Status:** Verified on 2026-10-14 — and the finding is that **no automated quality gate stands between a commit and production**. **Last verified:** 2026-10-14.
> **Evidence:** [`.forgejo/workflows/deploy.yml`](../../.forgejo/workflows/deploy.yml) (the only CI file; `.github/` does not exist), [`backend/pyproject.toml`](../../backend/pyproject.toml), the three `package.json` files, [`.gitignore`](../../.gitignore), absence of `.pre-commit-config.yaml`, `.coveragerc`, `codecov*`, `CODEOWNERS`, `.github/`. CI-001 in [DEFECT_LOG](../testing/DEFECT_LOG.md).

## What runs automatically today

| Trigger | What | Gate? |
|---|---|---|
| Push to `main` (Forgejo Actions) | Build three Docker images (`backend`, `website`, `Admin`), push to Docker Hub, point the EKS deployments at the new image tag, wait for `rollout status` (5 min timeout each), print pods/HPA | **None before deploy.** No test, lint, type-check, migration check, dependency/secret/container scan, or approval step; the "deploy" job is the only job; a failing build or rollout stops the workflow but a bad change that builds is deployed |
| Docker build | `pip install -r requirements.txt`, `npm ci` + `next build` (Admin uses `--webpack`), image `HEALTHCHECK`s | The build fails on install/compile errors only |
| Container start | `alembic upgrade head` then uvicorn (`start.sh`, `set -e`) | A failing migration stops the container |
| Kubernetes | readiness/liveness on `/health` (backend), rollout status | Detects a process that does not start, not a functional regression |
| Compose production | `deploy.sh` refuses `CHANGE_ME` placeholders, runs `docker compose config --quiet`, the `migrate` job must succeed before `backend` starts; `smoke-test.sh` is run **manually** afterwards | Manual |

## Checks that exist but are run by hand

| Check | Command | State on 2026-10-14 |
|---|---|---|
| Backend tests | `pytest` with a disposable DB ([TESTING_GUIDE](TESTING_GUIDE.md)) | 891 passed, 7 failed (base-fee change), 1 xfailed |
| Backend lint | `python -m ruff check .` (rules `E,W,F,I,B,UP`, `E501` and `B008` ignored, line length 88) | 7 findings |
| Type checks | `npx tsc --noEmit` in `mobile/` and `Admin/` | no diagnostics (not wired to any script) |
| Model/migration drift | `alembic check` on a migrated disposable DB | clean |
| Authorization snapshot | `test_authz_matrix.py` | part of the suite |
| Smoke test | [`deploy/scripts/smoke-test.sh`](../../deploy/scripts/smoke-test.sh) against public URLs | not run in this audit |

## What is missing (facts, not recommendations)

- No CI job runs any test, linter or type checker; no required status checks are configured in the repository (branch-protection settings live on the Git host and were not inspected).
- No automated tests exist for `mobile/`, `Admin/` or `website/`; their `package.json` files define no `test` script (`Admin`/`website`: `lint` = `next lint`; `mobile`: none).
- No coverage tool or threshold is configured, so there is **no established coverage requirement**.
- No pre-commit hooks, formatter configuration (no `black`/`prettier` config found), commit-message linting or `CODEOWNERS`.
- No dependency-vulnerability scan (`pip-audit`, `npm audit`), secret scan or container scan in CI — and a real API key is committed in `.mcp.json` (see [SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md)).
- No migration test from the previous revision with data; no check that a fresh database reaches head except by running the app.
- No performance or load gate (only exploratory numbers, [PERFORMANCE_RESULTS](../testing/PERFORMANCE_RESULTS.md)).

## Proposed gate (from the QA audit; **not implemented**)

[`docs/testing/TEST_STRATEGY.md`](../testing/TEST_STRATEGY.md) recommends a CI job that must pass before deploy: ruff + type check; pytest against a PostgreSQL service container with an explicit `TEST_DATABASE_URL` (port not 5432/5433; the job must set the disposable-marker comment); `alembic upgrade head` on an empty DB and from the previous release; frontend type-check and smoke tests; dependency, secret and container scans; and a `needs:` dependency so the deploy job only runs when the checks pass. Adopting it would also require fixing the 7 failing tests first.

## Definition of done used by this documentation set

A change is only reported as done when the relevant checks above were actually run and their result recorded — see [AGENTS.md](../../AGENTS.md).
