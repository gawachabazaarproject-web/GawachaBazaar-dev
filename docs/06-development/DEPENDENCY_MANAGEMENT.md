# Dependency Management

> **Status:** Verified from manifests, lockfiles and installed packages on 2026-10-14. No vulnerability scan was run (none is configured; running one would need network access and was outside this task).
> **Evidence:** [`backend/requirements.txt`](../../backend/requirements.txt), [`requirements-dev.txt`](../../backend/requirements-dev.txt), [`pyproject.toml`](../../backend/pyproject.toml), `mobile/package.json`, `Admin/package.json`, `website/package.json`, the four `package-lock.json` files, the backend `venv` (`pip list`).

## Backend (Python 3.11)

| Aspect | Reality |
|---|---|
| Source of truth | `requirements.txt` (production) and `requirements-dev.txt` (adds pytest, pytest-asyncio, httpx, ruff). The Docker image installs `requirements.txt` only |
| Pinning | **Ranges only**, e.g. `fastapi>=0.110.0,<1.0.0`; **no lockfile, no hashes** — two builds on different days can resolve different versions. The audit venv resolved FastAPI 0.141.1, Starlette 1.7.0, SQLAlchemy 2.1.1, Pydantic 2.13.5, Alembic 1.20.0, psycopg 3.3.6, uvicorn 0.54.0, slowapi 0.1.10, httpx 0.28.1, cloudinary 1.46.2, argon2-cffi 25.1.0, PyJWT 2.15.1, ruff 0.16.9, pytest 8.4.2 |
| `pyproject.toml` | Duplicates only part of the list (omits `firebase-admin`, `slowapi`, `python-multipart`, `cloudinary`, `httpx` in runtime deps) and has `[tool.ruff]`/`[tool.pytest]` config. **It is not used to install anything** (nothing runs `pip install .`); treat `requirements.txt` as authoritative and keep the two in sync if you edit either |
| Redundant / indirect entries | `PyJWT` and `python-dotenv` are listed but no `app/`, `scripts/` or `alembic/` file imports them (leftover from the pre-Firebase design; `firebase-admin` and `pydantic-settings` need them anyway). `email-validator` is needed by `EmailStr` (`schemas/staff.py`); `python-multipart` is needed by FastAPI for file uploads |
| Python version | `requires-python >=3.11`; image `python:3.11-slim`; the system interpreter on the audit machine was 3.14.7 (not used) |

**Reproducible builds (DEL-16, 2026-10-27).** `backend/requirements.in` holds the version *ranges* (edit this); `backend/requirements.txt` is the **generated lock** - every direct and transitive package pinned with SHA-256 hashes, compiled on Linux/Python 3.11 with `pip-tools`. The Dockerfile installs it with `--require-hashes` and its base image is pinned by digest (`python:3.11-slim@sha256:b7a9e5f6...`). Render, Docker and CI all use the lock. **Windows developers** cannot install the Linux lock (`uvloop`): use `pip install -r requirements.in -r requirements-dev.txt` locally and rely on CI/Docker for the locked set. Dev tools (`requirements-dev.txt`) are installed in a second `pip install` because a hashed file cannot be mixed with an unhashed one.

**Update procedure** (monthly, or for a security advisory):
1. Edit ranges in `requirements.in` if needed.
2. Regenerate the lock in the same environment as production:
   `docker run --rm -v "$PWD:/w" -w /w python:3.11-slim@sha256:<pinned> sh -c "pip install pip-tools==7.4.1 && pip-compile --generate-hashes --strip-extras --allow-unsafe --upgrade --output-file requirements.txt requirements.in"`
3. Rebuild the image, run the full suite **inside the new image** (CI does this) plus the live integration suite, and read the diff of `requirements.txt` for major jumps.
4. Update the base-image digest the same way (`docker pull python:3.11-slim`, copy `RepoDigests`) and do steps 3 again; commit lock + Dockerfile together.
5. Rollback = revert that commit (the previous lock and digest are in Git).

## JavaScript apps

| App | Manager | Lockfile | Pin style | Notable |
|---|---|---|---|---|
| `mobile/` | npm | `package-lock.json` | mixed: 17 `^`, 21 `~` (Expo-aligned), 7 exact | Expo ~57.0.22, React Native 0.86.3, React 19.2.3; **native modules** (`@react-native-firebase/*`, `@react-native-google-signin/google-signin`, `expo-notifications`, …) mean adding/upgrading one requires a **new build**, not an OTA update |
| `Admin/` | npm (`npm ci` in Docker) | yes | exact (12) + one `^` | Next 16.3.5, React 19.1.1, Tailwind 3.4.10, TypeScript 5.5.4 |
| `website/` | npm | yes | exact (14) | same stack, no Firebase |
| repo root | npm | yes | `^1.63.0` | only `playwright` (no test uses it) |

Docker builds use `npm ci` against the lockfile, so Admin and website builds are reproducible; the mobile app is built by EAS from its lockfile.

### Mobile-specific rules

- Expo SDK packages should stay on the versions Expo expects (`npx expo install <pkg>` rather than `npm install`) — the `~` ranges reflect that.
- `runtimeVersion` follows the app `version` (`policy: appVersion`): bumping the version in `app.json` creates a **new runtime** and installed apps stop receiving OTA updates until rebuilt. Native dependency changes need a version bump + rebuild; JS-only changes can ship via `eas update` ([DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md)).
- `expo-linear-gradient`, `expo-image`, `react-native-reanimated` are already in the installed build; anything newer than the last build is not (check `git log -S"<package>" -- mobile/package.json` against the build date before shipping JS that imports it).

## Security and maintenance

- No automated dependency scanning or update bot is configured (no Dependabot/Renovate config; no `pip-audit`/`npm audit` in CI).
- `backend/` base images (`python:3.11-slim`, `postgres:16-alpine`, `caddy:2-alpine`, `node:22-alpine`) float on their tags.
- A **41 MB APK is tracked in git** (`mobile/GawachaBazaar-1.0.0.apk`, added in commit `ae2d5db`). `.gitignore` lists the path, but ignore rules do not untrack a file that was already committed, so it is still in every clone and in the history — binary artefacts do not belong in the repository (R-16 in [RISK_REGISTER](../testing/RISK_REGISTER.md)).
- Third-party services, with their own versions and contracts, are listed in [THIRD_PARTY_SERVICES](../11-integrations/THIRD_PARTY_SERVICES.md).
