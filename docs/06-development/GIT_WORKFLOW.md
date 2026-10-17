# Git Workflow

> **Status:** Partially verified. **Last verified:** 2026-10-14. **No written branching or review policy exists in the repository** (no `CONTRIBUTING.md`, no PR template, no `CODEOWNERS`); this document describes what the Git history and configuration show, labelled as observed practice — not as policy.
> **Evidence:** `git branch -a`, `git remote -v`, `git log` (144 commits on this branch), [`.gitattributes`](../../.gitattributes), [`.gitignore`](../../.gitignore), [`.forgejo/workflows/deploy.yml`](../../.forgejo/workflows/deploy.yml).

## Remotes and branches (observed)

| Item | Observation |
|---|---|
| Remotes | `origin` → GitHub `gawachabazaarproject-web/GawachaBazaar-dev`; `forgejo` → a Forgejo instance `Pavan9974/GawachaBazaar-prod` (embedded credentials in the URL, if any, must not be copied) |
| Long-lived branches | `main` (the CI deploy trigger, remote `forgejo/HEAD → forgejo/main`) and `develop` |
| Short-lived branches (local/remote) | `chore/pre-deploy-fixes`, `merge-main-into-develop`, `mobile-ui-phase-3`, `next-phase-ui`, `docs-and-primary-testing` (current), `forgejo/business-logic-hardening` |
| Integration | GitHub pull requests are visible in history (`Merge pull request #43 … mobile-ui-phase-3`, `#44`, `#45`, `#46 develop`, `#47 merge-main-into-develop`); `main` and `develop` are periodically merged into each other (`Merge main into develop`, `Merge origin/main (incl. develop) into main`) |
| Deployment relation | A push to **`main` on the Forgejo remote** triggers the production deploy workflow ([DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md)); whether pushes to GitHub mirror to Forgejo is not recorded |

## Commit messages (observed)

Of 144 commits on this branch, about 54 use Conventional-Commit prefixes (`feat` ≈ 32, `fix` ≈ 18, `chore` 2, `release`, `security`), often with a scope (`fix(auth): …`, `feat(admin): …`, `fix(mobile): …`); of the remaining 90, 62 are merge commits and about 28 are free-form (`mobile ui updated bazaar added`, `inventory fix`, `docs fix`). Convention to follow for new work: `type(scope): imperative summary` (matches the majority of recent commits), body explaining *why*, and the attribution trailer(s) required by the current tooling. Do not squash unrelated changes (login UI, delivery fee, docs) into one commit.

## Guidelines derived from the repository's own rules

1. **Never push untested money/auth changes to `main`** — a push to `main` deploys to production without any automated check ([QUALITY_GATES](../07-testing/QUALITY_GATES.md)). Run the backend suite against a disposable database and `tsc` for the apps first.
2. **Keep secrets out of commits.** `.env*`, `google-services.json` and keystores are ignored; `.mcp.json` is *tracked and contains a live-looking API key* — rotate it and untrack the file ([SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md)).
3. **Do not commit build artefacts or binaries** (a 41 MB APK is tracked today).
4. **Migrations ship with the model change** in the same commit, and `alembic check` must stay clean.
5. **Route/permission changes ship with the updated `authz_golden.json`** (reviewed).
6. **Documentation ships with behaviour changes** ([docs/README](../README.md#keeping-the-documentation-current)).
7. **Mobile JS-only changes** can be published with `eas update`; native/dependency/`app.json` changes need a rebuild ([DEPENDENCY_MANAGEMENT](DEPENDENCY_MANAGEMENT.md)).
8. Prefer a new commit over amending; do not force-push shared branches; do not rewrite history to remove a leaked secret without first rotating the secret.

## Working tree state when this documentation was written

Branch `docs-and-primary-testing`, base `8d6229e`. Uncommitted: the QA-audit tests and evidence (`backend/tests/*`, `docs/testing/`), the login-screen/loader/product-card changes in `mobile/`, the delivery-fee default change (backend config, example env files, docs), edits by others to `backend/app/services/push.py`, and this documentation set. **Nothing was committed or pushed by the documentation task.** See [AI_STATUS](../00-overview/AI_STATUS.md).
