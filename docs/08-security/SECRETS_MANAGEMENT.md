# Secrets Management

> **Status:** Verified for where secrets are *supposed* to live and for the leak found; **actual secret stores on the VPS, Kubernetes, EAS and CI were not inspected** (they are outside the repository). **Last verified:** 2026-10-14. **No secret value appears in this document.**
> **Evidence:** [`.gitignore`](../../.gitignore), `git ls-files`, `git log -G`, [`deploy/FIREBASE_AUTH.md`](../../deploy/FIREBASE_AUTH.md), [`deploy/README.md`](../../deploy/README.md), [`docker-compose.prod.yml`](../../docker-compose.prod.yml), [`k8s/base/backend-deployment.yaml`](../../k8s/base/backend-deployment.yaml), [`.forgejo/workflows/deploy.yml`](../../.forgejo/workflows/deploy.yml), [`mobile/app.config.js`](../../mobile/app.config.js), [`backend/app/core/config.py`](../../backend/app/core/config.py).
> Names and purposes of every variable: [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md).

## 1. Inventory: what is secret, where it should live

| Secret | Used by | Intended store | Notes |
|---|---|---|---|
| `DATABASE_URL` (contains the DB password) | backend, Alembic, scripts | host environment (`.env.production` `chmod 600`, K8s Secret) | A local untracked `backend/.env` in the audited checkout holds a hosted-database URL in plaintext (R-14) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` (service-account private key) | backend (staff creation, resets, revocation) | secret env / secret file (`/etc/secrets/firebase-service-account.json`), K8s Secret | Gitignored patterns: `*firebase-adminsdk*.json`, `service-account*.json`. **A bad value breaks all sign-ins** ([AUTHENTICATION](../05-domains/AUTHENTICATION.md)) |
| `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | backend | same as above | Key **id** is public (sent to Checkout) |
| `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | backend | same | – |
| `REDIS_URL` | backend | same | Optional (may embed a password) |
| `POSTGRES_PASSWORD` | compose `db`, `db-backup`, `backend` | `.env.production` (never committed; `deploy.sh` refuses `CHANGE_ME`) | – |
| `DOCKERHUB_TOKEN`, `DOCKERHUB_USERNAME`, AWS credentials | CI | Forgejo repository secrets | Not visible here |
| Android **upload keystore** / `GAWACHA_UPLOAD_*` | release signing | `~/.gradle/gradle.properties` on the build machine, or EAS credentials | Never in the repo (`withAndroidRelease.js` comment). The EAS project moved to account `yash145`, creating a **new** signing key (SHA-1 `D26E…365F`) that had to be registered in Firebase |
| `google-services.json`, `GoogleService-Info.plist` | mobile native builds | EAS file secret `GOOGLE_SERVICES_JSON` / local file | Gitignored. Contains public identifiers, not private keys, but is treated as config |
| Expo/FCM credentials for push | EAS project | EAS credentials | Status unknown for the current EAS project |
| Firebase **web** config (API key, app id…) | Admin, mobile web, `eas.json` | public by design | `NEXT_PUBLIC_FIREBASE_*`/`EXPO_PUBLIC_FIREBASE_*` and the values in `mobile/eas.json` are identifiers, not secrets; restrict the API key in Google Cloud if needed |

## 2. What the repository enforces

- `.gitignore` excludes `.env`, `.env.*` (except `.env.example`), keystores, service-account files and native Firebase config; `git ls-files` shows **no** service-account, keystore, `.pem`, `.p12`, `google-services.json` or real `.env` tracked.
- The example files (`backend/.env.example`, `.env.production.example`, `Admin/.env.example`, `mobile/.env.example`) contain placeholders; `.env.production.example` uses `CHANGE_ME…` placeholders (domains, passwords, keys) and `deploy.sh` refuses to run while any `CHANGE_ME` remains.
- Backend start-up refuses a production config with no `FIREBASE_PROJECT_ID` or a half-set Razorpay trio; Razorpay test keys in production only log a warning.
- Logs redact `token=` query values; the request log omits query strings; push tokens are truncated in warnings.
- The test suite blanks Razorpay/Cloudinary/Maps/Firebase-account variables before importing the app, so real keys in a developer `.env` are not used by tests.

## 3. Findings

### SECR-1 — API key committed in `.mcp.json` (High)

`.mcp.json` (repository root, tracked since commit `bff7053 website`) configures an MCP server for the design-component service `21st` with an `x-api-key` header whose value is a **plaintext secret key** (`21st_sk_…`). It is part of every clone and of git history, and its value was **printed to a terminal during this documentation run** (so it should be considered exposed to anyone with access to that transcript). Required actions, in order: **revoke/rotate the key at the provider**; remove the secret from the file (use an environment-variable reference or a per-developer untracked config) and `git rm --cached .mcp.json`; add the file to `.gitignore`; only then consider purging history (a history rewrite does not un-leak a key). No other private-key or live-key patterns were found in the tracked tree or in history by the searches described below.

Searches performed on 2026-10-14 (names only, no values recorded): tracked-file name patterns (`service-account`, `firebase-adminsdk`, `*.pem`, `*.p12`, `*.jks`, `*.keystore`, `google-services*`, `credentials`) → none; content patterns in the current tree (`21st_sk_`, `sk_live_`, `rzp_live_`, AWS access-key shape, PEM private-key header) → only `.mcp.json` (plus the two harmless comments mentioning `rzp_live_` in `.env.production.example` and `main.py`); history search for private-key headers, `rzp_live_<id>` and `21st_sk_` → only commit `bff7053`. This is **not** a complete secret scan (no dedicated scanner is installed or configured).

### Other observations

| ID | Observation |
|---|---|
| SECR-2 | A local untracked `backend/.env` (not in git) points `DATABASE_URL` at a hosted PostgreSQL with a plaintext credential, and the scripts/Alembic default to it. Use a separate local database for development and rotate that credential if the file was shared (R-14) |
| SECR-3 | A stale `JWT_SECRET_KEY` line existed in a developer `.env` although the code no longer reads it; delete unused secrets |
| SECR-4 | `AWS account id` and an ACM certificate ARN are committed in `k8s/overlays/aws/ingress.yaml` and an ECR image in `k8s/backend-deployment.yaml`. They are identifiers, not credentials, but they reveal infrastructure details |
| SECR-5 | Whether the AWS backend uses the service-account secret file is unknown; the observed failure on 2026-10-14 shows the file reference can dangle |
| SECR-6 | No secret rotation procedure, owner or schedule is documented |

## 4. Handling rules for contributors and agents

1. Never write a secret into source, docs, tests, examples, screenshots, commit messages or chat. Examples use obvious placeholders.
2. Do not `cat` or print `.env`, `.mcp.json`, service-account files or `docker inspect` environment blocks; when you must inspect them, extract **names only** or redact values (`sed -E 's/(KEY|SECRET|PASSWORD)=.*/\1=<hidden>/'`).
3. If a secret is exposed, rotate it first, then clean up the repository.
4. Prefer provider-managed secret stores (EAS secrets, Kubernetes Secrets, Forgejo secrets) over `.env` files on shared machines; keep `.env.production` at mode `600` on the VPS.
5. Public-by-design values (`NEXT_PUBLIC_*`, `EXPO_PUBLIC_*`, Firebase web config, Razorpay key **id**) must never be paired with their private counterparts in client bundles.
6. After changing a signing key (new EAS account or keystore), register the new SHA-1/SHA-256 in Firebase and refresh `google-services.json`.

## 5. Recommended (not implemented)

Rotate the committed key; add `.mcp.json` handling; add a secret scanner (e.g. gitleaks) to CI and as a pre-commit hook; move the hosted-database credential out of local files; define a rotation schedule for Razorpay, Cloudinary, Firebase service-account and database credentials; make the Firebase service-account loading fail soft ([AUTHENTICATION](../05-domains/AUTHENTICATION.md)).
