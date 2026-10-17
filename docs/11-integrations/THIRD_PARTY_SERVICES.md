# Third-Party Services

> **Status:** Verified from source on 2026-10-14 (what the code calls and how it fails); the **accounts, plans, quotas, credentials and live behaviour of every service are outside the repository and were not inspected**. Request/response details: [INTEGRATION_CONTRACTS](INTEGRATION_CONTRACTS.md). Personal data sent to each: [PRIVACY](../08-security/PRIVACY.md).

## Runtime dependencies of the application

| Service | Purpose | Used by | Configuration | If it fails | Evidence |
|---|---|---|---|---|---|
| **Firebase Authentication** (Google) | Identity: email/password, Google, phone OTP, email verification, password-reset links; Admin SDK for staff creation, password reset, disable/revoke | mobile, Admin, backend | `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`; client config `EXPO_PUBLIC_FIREBASE_*`, `NEXT_PUBLIC_FIREBASE_*`, `google-services.json` | Backend: 503 `AUTH_UNAVAILABLE` (cert fetch/credential errors); a misconfigured service account broke **all** sign-ins on 2026-10-14. Clients cannot sign in | `core/firebase.py`, `services/auth.py` |
| **Google Sign-In** (native) | Google account sign-in on Android | mobile | `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`; signing SHA-1 registered in Firebase | Code 10 `DEVELOPER_ERROR` when the build's SHA-1 is not registered (observed 2026-10-14) | `mobile/src/auth/firebase.native.ts` |
| **Razorpay** | Online payments (UPI, cards, netbanking, wallets) via Orders API, Standard Checkout, webhooks, refunds | backend, mobile (WebView loads `checkout.razorpay.com/v1/checkout.js`) | `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET/BASE_URL/TIMEOUT_SECONDS`; dashboard: auto-capture, webhook URL + events | Without keys: COD only (503 `ONLINE_PAYMENTS_NOT_CONFIGURED`). Outage/timeouts: 502 `PAYMENT_GATEWAY_*`; payments stay `PROCESSING`; refunds stay `PROCESSING` | `razorpay_gateway.py`, [PAYMENTS](../05-domains/PAYMENTS.md) |
| **Cloudinary** | Image storage/delivery (products, categories, ads, home slides) | backend (upload), all clients (display URLs) | `CLOUDINARY_*` | Uploads fail 503/502; existing images keep loading from stored URLs. **Assets are never deleted by the app** | `image_upload.py` |
| **Google Distance Matrix** / **OSRM** | Road distance for the delivery fee | backend | `GOOGLE_MAPS_API_KEY` (else OSRM), `OSRM_BASE_URL` (default: the **public demo server**), `ROUTING_TIMEOUT_SECONDS` | Falls back to straight-line × 1.4; checkout is not blocked | `delivery.py` |
| **Expo push service** (+ Google FCM) | Customer push notifications | backend, mobile | no env var; EAS project needs FCM credentials | Logged, best effort; never blocks business flow | `services/push.py` |
| **Expo EAS Update / Build** | OTA JavaScript updates, native builds, credentials | mobile | `app.json` (`updates.url`, `runtimeVersion`), `eas.json` channels; account `yash145`, project `a751e06b-…` | App keeps running its current bundle; builds cannot be produced | `mobile/app.json`, `eas.json` |
| **Unsplash** (image hosting) | Hotlinked stock images in **seeded** home slides and promotions | data created by migrations `a8c3d5e7f901`, `e4a7c1b9d036` | URLs stored in the database | Images disappear if the URLs break; the app depends on a third party's terms and availability | `alembic/versions/` |
| **Google Fonts** (build time) / jsDelivr / FastAPI CDN | Admin uses `next/font/google` (fonts are fetched when the Admin is built, then self-hosted); the mobile app bundles its fonts through `@expo-google-fonts` packages; the dev-only `/docs` page loads Swagger assets from jsDelivr/tiangolo (allowed by its CSP) | Admin build, mobile bundle, dev docs | – | A Google Fonts outage can fail an Admin build; cosmetic otherwise | `Admin/app/layout.tsx`, `mobile/app/_layout.tsx`, `security_headers.py` |

## Hosting and delivery infrastructure (described in the repository; live state unverified)

| Service | Role | Evidence |
|---|---|---|
| **Render** | Hosts the backend (and its PostgreSQL) that the installed app talks to (probed `/health` 200 on 2026-10-14; free-tier cold start ≈ 44 s) | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| **Vercel** | Admin panel hosting (per `Admin/.env.example` and an observed `*.vercel.app` login page) | – |
| **Contabo VPS + Caddy + Let's Encrypt + Docker Compose** | Documented single-server production stack (not shown to be live) | `deploy/`, `docker-compose.prod.yml` |
| **AWS EKS, ALB, ACM, ECR/Docker Hub** | CI/CD target and Kubernetes manifests (not shown to serve the API) | `.forgejo/workflows/deploy.yml`, `k8s/` |
| **Docker Hub** | Image registry used by CI (`DOCKERHUB_USERNAME/…-backend|website|admin:<sha>`) | workflow |
| **Forgejo / GitHub** | Source hosting; Forgejo Actions runs CI; GitHub PRs visible in history | [GIT_WORKFLOW](../06-development/GIT_WORKFLOW.md) |
| **PostgreSQL 16** | Primary database | compose/test containers |

## What is *not* integrated

No email, SMS or WhatsApp provider (Firebase sends its own emails/OTPs), no analytics/crash-reporting SDK, no CDN/WAF in front of the API, no error tracker, no payment provider other than Razorpay (a `PNBGateway` placeholder class exists but is unwired), no maps SDK in the apps beyond the device location API and Admin map links.

## Cross-cutting notes

- **Costs/limits to watch:** Firebase phone-OTP SMS (billable), Razorpay fees, Google Distance Matrix billing, Cloudinary credits, Expo push/EAS quotas, Render free-tier sleep.
- **Credentials:** see [SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md) — including the committed `21st` MCP key (that service is a developer-tooling dependency, not part of the application runtime).
- **Failure isolation:** only Firebase and the database are on the critical path of every request; Razorpay is on the path of online payment only; Cloudinary/routing/Expo failures degrade gracefully.
- **Terms/licensing** of third-party content (Unsplash images, fonts) were not reviewed.
