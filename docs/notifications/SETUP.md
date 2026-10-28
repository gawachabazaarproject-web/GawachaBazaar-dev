# Setup

No new environment variables. The backend calls the public Expo push API (`https://exp.host/--/api/v2/push/send`) without an access token. Firebase service-account files are **not** used by the backend for push and must never be committed.

## Mobile / Firebase / EAS (manual, one-time)
1. Package `com.gawachabazaar.customer` (`mobile/app.json`); EAS project id `a751e06b-d698-4081-b49d-52bdee248959` (the `yash145` account).
2. Firebase Console -> Project settings -> Cloud Messaging: make sure the FCM V1 API is enabled; create a service-account key.
3. EAS: `eas credentials` -> Android -> Google Service Account Key for push notifications (FCM V1) -> upload the key. Expo stores it; it is not in git.
4. Build a real APK/AAB with EAS (`preview` or `production` profile). Expo Go cannot receive Android remote push.
5. Without step 3, Expo returns `InvalidCredentials` / `MismatchSenderId` (logged as `PUSH_TICKET_ERROR`).

## Backend
`alembic upgrade head` (revision `c3d5e7f9a1b2` adds `notification_events`); follow `docs/04-database/MIGRATIONS.md`. Deploying the backend before the app update is safe because the payload keeps `orderId`.

The new app code (tap routing, token rotation) is JS-only and can ship by OTA on the installed channel.

## Two different Google files (do not mix them up)
| File | Used by | Where it lives |
|---|---|---|
| `GOOGLE_SERVICES_JSON` (`google-services.json`) | the Android **app build** (EAS) | EAS file variable; local copy git-ignored in `mobile/` |
| `google-services-account.json` (service-account key) | the **backend** Firebase Admin SDK (sign-in verification, staff/password admin) | mounted secret file at `/etc/secrets/google-services-account.json` |

`core/firebase.py` loads the Admin credential from `FIREBASE_SERVICE_ACCOUNT_JSON` (inline JSON or a file path) and, if that is empty, from `/etc/secrets/google-services-account.json` automatically. `FIREBASE_PROJECT_ID` must be set (production refuses to start without it). Local development: leave both empty (sign-in still verifies), or set `FIREBASE_SERVICE_ACCOUNT_JSON` to a git-ignored local key file path. Redeploy AWS after adding or changing the secret file.

## Things that are NOT needed
- **No new backend variable.** Push goes through the Expo push service; the FCM V1 key lives in EAS. The Admin SDK credential is not used to send push.
- **EAS build needs `google-services.json`.** It is git-ignored, so a cloud build only gets it from an EAS file variable named `GOOGLE_SERVICES_JSON` (read by `mobile/app.config.js`). Check: `eas env:list` (preview environment). Without it the APK cannot obtain a push token.
- APK for WhatsApp: `cd mobile && eas build --platform android --profile preview` (already APK + internal; `production` stays AAB).

## Secrets
`.mcp.json` held a live-looking API key (the `21st` MCP server header) and was tracked in git; it is now untracked and git-ignored (file kept locally). It remains in git history: **rotate that key** in the 21st dashboard.
