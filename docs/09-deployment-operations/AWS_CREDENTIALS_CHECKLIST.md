# Gawacha Bazaar - credentials and settings needed to run on AWS

> **Safe to share:** this file lists **names, purposes and where each value comes from - never a value.**
> Send the *values* separately (AWS Secrets Manager / SSM Parameter Store, or an encrypted channel), never in chat, e-mail or Git.
> Derived from the code on 2026-10-27: `backend/app/core/config.py`, `.env.aws.example`, `docker-compose.aws.yml`,
> `Admin/Dockerfile`, `mobile/eas.json`, `mobile/app.config.js`, `deploy/`. Owner of each value in the last column.

Legend: **SECRET** = must never be committed or logged · **PUBLIC** = shipped inside the app/website by design · **GEN** = generate a new one for production.

---

## A. Things that exist only on the AWS side (not in the code - your infrastructure choices)

| # | Item | Why it is needed | Owner |
|---|---|---|---|
| A1 | AWS account + an IAM user/role for deployment (least privilege) | create and update the resources below | AWS admin |
| A2 | Compute for the backend (EC2 / ECS), **one backend worker only** (rate limit, WebSocket hub and reservation sweep are in-process) | runs the API at `api.gawachabazaar.in` | AWS admin |
| A3 | **PostgreSQL 16** (RDS or container) - host, port, db name, user, password | `DATABASE_URL` | AWS admin |
| A4 | **Redis** (ElastiCache or container) | `REDIS_URL` (route cache; optional - the app still works without it) | AWS admin |
| A5 | DNS for `api.gawachabazaar.in` (and Admin / website domains if hosted on AWS) pointing at the server | `API_DOMAIN`, `ADMIN_DOMAIN`, `SITE_DOMAIN` | domain owner |
| A6 | TLS: Caddy gets Let's Encrypt certificates automatically; needs ports 80/443 open and a contact e-mail | `ACME_EMAIL` | AWS admin |
| A7 | Where database backups are kept (the backup script writes dumps to a mounted `/backups` volume; copy them off the server, e.g. to S3) and **a restore that has been tested** | recovery from a bad migration | AWS admin |
| A8 | Container image registry (ECR / Docker Hub) and the credentials CI uses to push images | deploys | AWS admin / dev |
| A9 | Git access for the server or CI to pull the code (deploy key or read-only token) - GitHub and/or Forgejo | deploys | dev |
| A10 | A secret store (AWS Secrets Manager or SSM Parameter Store) for every **SECRET** below, instead of a plain `.env` file | storage | AWS admin |
| A11 | Monitoring/alerts (CloudWatch or similar) | operations | AWS admin |

## B. Backend (FastAPI) - environment variables

**The production server refuses to start** if: `FIREBASE_PROJECT_ID` is empty; `RAZORPAY_KEY_ID` is set without both `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET`; or `DELIVERY_OTP_SECRET` is shorter than 32 characters while `DELIVERY_OTP_ENFORCED=true`.

### B1. Must provide (secrets / identities)

| Variable | Type | What it is / where to get it | Notes |
|---|---|---|---|
| `DATABASE_URL` | **SECRET** | `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME` | contains the DB password; use a dedicated app user, not the admin user |
| `FIREBASE_PROJECT_ID` | PUBLIC | Firebase console -> Project settings | boot fails if empty |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | **SECRET** | Firebase console -> Project settings -> Service accounts -> *Generate new private key* (raw JSON on one line, or a path to a secret file) | lets the backend verify sign-ins and create staff accounts; without it no login works |
| `RAZORPAY_KEY_ID` | PUBLIC (sent to Checkout) | Razorpay dashboard -> API keys (**live** mode for production) | key id only |
| `RAZORPAY_KEY_SECRET` | **SECRET** | same page | never the test key in production |
| `RAZORPAY_WEBHOOK_SECRET` | **SECRET** | Razorpay -> Webhooks: create a webhook to `https://api.gawachabazaar.in/api/v1/payments/webhooks/razorpay`, copy the secret you set | must match exactly or payments are rejected |
| `CLOUDINARY_CLOUD_NAME` | PUBLIC | Cloudinary dashboard | product image uploads |
| `CLOUDINARY_API_KEY` | **SECRET** | Cloudinary dashboard | |
| `CLOUDINARY_API_SECRET` | **SECRET** | Cloudinary dashboard | |
| `DELIVERY_OTP_SECRET` | **SECRET, GEN** | generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` | >= 32 characters; keys the COD delivery-code hash. **Do not change it after go-live** unless you accept that codes already issued stop verifying |

### B2. Settings to set deliberately (not secret)

| Variable | Production value / note |
|---|---|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `ALLOWED_ORIGINS` | the exact Admin/website origins, e.g. `["https://admin.gawachabazaar.in"]` (not `*`, not localhost) |
| `DELIVERY_OTP_ENFORCED` | `true` |
| `REFERRAL_ENABLED` | `false` unless the owner decides otherwise |
| `DELIVERY_BASE_FEE`, `DELIVERY_PER_KM`, `DELIVERY_MAX_CHARGED_KM`, `DELIVERY_MAX_DISTANCE_KM`, `DELIVERY_MIN_ORDER_VALUE`, `FREE_DELIVERY_MIN_ITEMS` | pricing rules (defaults: 20 / 10 / 30 / 0 = no limit / 0 / 10); make sure the host environment does not override the base fee with an old value |
| `PACKING_POINT_LATITUDE`, `PACKING_POINT_LONGITUDE` | the real warehouse (or set it in Admin -> Settings); needed for per-km delivery pricing |
| `OSRM_BASE_URL` | self-hosted OSRM (the public demo server is development-only; delivery quotes fail rather than guess if routing is down) |
| `NOMINATIM_BASE_URL`, `NOMINATIM_USER_AGENT` | address search; the user-agent must contain a real contact e-mail (OpenStreetMap policy) |
| `REDIS_URL` | optional route cache (`redis://...`; may embed a password -> SECRET) |
| `ROUTING_PROVIDER`, `ROUTING_TIMEOUT_SECONDS`, `ROUTE_CACHE_TTL_SECONDS`, `GEOCODING_PROVIDER` | defaults are fine |
| `DELIVERY_OTP_EXPIRY_MINUTES`, `DELIVERY_OTP_MAX_ATTEMPTS`, `DELIVERY_OTP_RESEND_LIMIT`, `DELIVERY_OTP_RESEND_WINDOW_MINUTES` | defaults are fine |
| `PARTNER_EARNING_BASE`, `PARTNER_EARNING_PER_KM`, `PARTNER_EARNING_COD_BONUS`, `REFERRAL_*` | business decisions (current values are placeholders) |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `MAX_INFLIGHT_REQUESTS`, timeouts | keep defaults unless load testing says otherwise |
| `API_DOMAIN`, `ADMIN_DOMAIN`, `SITE_DOMAIN`, `ACME_EMAIL` | used by `docker-compose.aws.yml` / Caddy |

## C. Admin web panel (Next.js) - **build-time** variables (baked into the build)

All **PUBLIC** (Firebase web config is public by design; the real protection is Firebase rules and the backend):
`NEXT_PUBLIC_API_BASE_URL` (= `https://api.gawachabazaar.in/api/v1`), `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`, `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`.
Firebase console -> Authentication -> Settings -> **Authorized domains** must include the Admin domain.

## D. Customer mobile app (Expo / EAS)

| Item | Type | Notes |
|---|---|---|
| `EXPO_PUBLIC_API_BASE_URL` | PUBLIC | `https://api.gawachabazaar.in/api/v1` (production build must not point at a dev backend) |
| `EXPO_PUBLIC_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_STORAGE_BUCKET`, `_MESSAGING_SENDER_ID`, `_APP_ID` | PUBLIC | Firebase web config |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | PUBLIC | Google sign-in (Firebase -> Authentication -> Google -> web client ID) |
| `google-services.json` (Android) / `GoogleService-Info.plist` (iOS) | file, gitignored | Firebase console -> Project settings -> Your apps; supplied to EAS as the file secret `GOOGLE_SERVICES_JSON` |
| Google sign-in **SHA-1 / SHA-256 fingerprints** of the signing key | public but must be registered | register each release key's fingerprint in Firebase (Android app), or Google sign-in fails |
| **FCM credentials for push** (Firebase service-account key uploaded to the Expo/EAS project) | **SECRET** | without it push notifications (order updates, delivery codes) are not delivered; status for the current EAS project is unverified |
| Expo account / EAS project (`eas login`, or `EXPO_TOKEN` for CI) | **SECRET** | the app belongs to the Expo account that owns the project |
| Android signing key (EAS-managed keystore, or your own upload keystore) | **SECRET** | **keep a backup**; changing it later prevents updating installed apps. Package id is `com.gawachabazaar.customer`. Note: the native `android/` folder currently uses `com.gawacha.bazaar`; decide which id is the real one before the first store release |
| Play Console / App Store accounts | accounts | needed only to publish to the stores |

## E. Website (promo site) and delivery partners
- The promo site has **no credentials** (static pages, no API).
- Delivery partners use the customer app with a staff-assigned role; they need no separate keys.

## F. Source-control and CI credentials (not needed by the running app)
GitHub and/or Forgejo access token or deploy key; container-registry token (e.g. `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`); AWS access keys or an OIDC role for CI. Store them as repository/CI secrets.

## G. Before go-live checklist (credentials-related)
1. Every **SECRET** above is in the secret store, not in a file in the repo, and none has ever been pasted into chat, tickets or e-mail (rotate any that were).
2. Razorpay is in **live** mode, with the webhook pointing at the production URL; run one real small payment and refund.
3. `FIREBASE_SERVICE_ACCOUNT_JSON` is the production project's key; Authentication providers (phone, Google, e-mail) are enabled.
4. `ALLOWED_ORIGINS`, `APP_ENV=production`, `DEBUG=false`, `DELIVERY_OTP_ENFORCED=true`, `REFERRAL_ENABLED=false` are confirmed.
5. A **tested database backup** exists before the first deploy (the inventory migration `e5f6a7b80923` runs on backend start).
6. Admin and mobile builds use the production API URL and production Firebase config.
