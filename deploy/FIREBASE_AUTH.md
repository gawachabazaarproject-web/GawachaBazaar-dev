# Firebase Authentication

Firebase Auth is the identity provider for the customer app (Expo: Android +
web) and the admin panel (Next.js). The FastAPI backend verifies Firebase ID
tokens and maps the verified UID to a PostgreSQL `users` row. PostgreSQL keeps
everything else: profile, roles, addresses, cart, orders, payments, status.

```
Client --(Firebase SDK: email/password | Google | phone OTP)--> Firebase Auth
Client --Authorization: Bearer <Firebase ID token>--> FastAPI
FastAPI --firebase_admin.verify_id_token()--> uid --> users.firebase_uid --> app user
```

| Piece | Where |
|---|---|
| Token verification, user sync, legacy migration | `backend/app/core/firebase.py`, `backend/app/services/auth.py` |
| `get_current_user` / `get_current_customer` / `get_current_admin` | `backend/app/dependencies/auth.py` |
| Endpoints `POST /auth/sync`, `GET /auth/me`, `POST /auth/legacy-migrate` | `backend/app/api/v1/auth.py` |
| Schema change (`firebase_uid`, nullable email/phone/password, drop `auth_sessions`) | `backend/alembic/versions/c5f1a7e3d9b2_firebase_identity.py` |
| Mobile Firebase layer (native / web) | `mobile/src/auth/firebase.native.ts`, `mobile/src/auth/firebase.ts` |
| Mobile auth state (single store) | `mobile/src/store/authStore.ts` |
| Mobile error mapping | `mobile/src/auth/errors.ts` |
| Mobile screens | `mobile/app/(auth)/*`, `mobile/app/account/add-phone.tsx` |
| Route protection | `mobile/src/navigation/AppGate.tsx` |
| Admin | `Admin/lib/firebase.ts`, `Admin/lib/auth-context.tsx`, `Admin/app/login/page.tsx` |

## 1. Firebase Console checklist

1. **Create a project** (or pick the existing one). Note the **Project ID**.
2. **Authentication → Sign-in method**: enable **Email/Password**, **Google**,
   and **Phone**.
3. **Phone**:
   - Phone auth sends billable SMS: upgrade to the **Blaze** plan.
   - **Authentication → Settings → SMS region policy**: allow **India** only.
   - **Phone numbers for testing**: add a few (e.g. `+91 99999 00001` → `123456`)
     and use them for all development and QA, so no real SMS is sent.
4. **Settings → User account linking**: keep **"Link accounts that use the same
   email"** (one account per email, the default).
5. **Settings → Password policy**: require 8+ characters with upper-case,
   lower-case, and a digit, matching `validateStrongPassword` in the app.
   Leave **enforcement** off until existing users have migrated. Legacy
   passwords that fail the policy fall back to a reset email automatically.
6. **Settings → Authorized domains**: add the Vercel admin domain and the
   customer web domain (if the Expo web build is deployed). `localhost` is
   there by default.
7. **Project settings → Your apps**:
   - **Web app** (one is enough for admin + Expo web): copy the 6 config values.
   - **Android app**, package `com.gawachabazaar.customer`: add the **SHA-1 and
     SHA-256** of the **debug** keystore and the **release/upload** keystore
     (and the Play App Signing key once on Play). Google Sign-In and phone
     auth fail without them. Download `google-services.json`.
   - iOS (later): bundle `com.gawachabazaar.customer`, download
     `GoogleService-Info.plist`.
8. **Authentication → Sign-in method → Google → Web SDK configuration**: copy the
   **Web client ID** (`…apps.googleusercontent.com`). Native Google Sign-In
   needs it.
9. **Templates** (optional): set the sender name, and set the action URL to
   `https://<customer-web-domain>/action` to handle reset and verify links
   in-app. Otherwise Firebase's hosted page handles them.
10. **Project settings → Service accounts → Generate new private key**. This
    JSON is a secret. Put it only in the backend host's secret store. Never
    commit it, never add it to a frontend, and never paste it into a chat.
11. Recommended: **App Check** (Play Integrity) and **Identity Platform →
    blocking/abuse protections** once traffic grows.

## 2. Environment variables

| Where | Variable | Secret? |
|---|---|---|
| Backend (Render) | `FIREBASE_PROJECT_ID` | no |
| Backend (Render) | `FIREBASE_SERVICE_ACCOUNT_JSON` (raw JSON on one line, OR path to a Render Secret File e.g. `/etc/secrets/firebase-service-account.json`) | **yes** |
| Admin (Vercel) | `NEXT_PUBLIC_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_STORAGE_BUCKET`, `_MESSAGING_SENDER_ID`, `_APP_ID` | no (public web config) |
| Mobile (EAS / `.env`) | `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | no |
| Mobile web build | `EXPO_PUBLIC_FIREBASE_*` (same 6 values) | no |
| Mobile native build | `google-services.json` via `GOOGLE_SERVICES_JSON` path (EAS file secret) or file next to `app.config.js` | no, but gitignored |

`JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` and
`REFRESH_TOKEN_EXPIRE_DAYS` are no longer used and can be deleted from Render.

With `APP_ENV=production`, the backend refuses to start without
`FIREBASE_PROJECT_ID`. Token verification needs only that. The service
account is needed for staff creation, admin password resets, account
disable/revoke, and legacy migration, which return 503 without it.

## 3. Local development

```bash
cd backend && venv/Scripts/python -m alembic upgrade head
```
Then add `FIREBASE_PROJECT_ID` (and optionally `FIREBASE_SERVICE_ACCOUNT_JSON`) to `backend/.env`.

- **Admin**: copy `Admin/.env.example` to `Admin/.env.local` and fill in the Firebase web config.
- **Mobile**: `@react-native-firebase` is native code, so **Expo Go no longer
  works**. Put `google-services.json` in `mobile/`, then build a dev client once:
  ```bash
  cd mobile && npx expo run:android
  ```
  After that, `npx expo start` connects to the dev client. The web build
  (`npx expo start --web`) needs the `EXPO_PUBLIC_FIREBASE_*` values instead.
- Use Firebase **test phone numbers** for OTP; real numbers cost money.
- Backend tests never touch Firebase. `tests/firebase_fake.py` replaces the SDK:
  ```bash
  cd backend && venv/Scripts/python -m pytest -q
  ```

## 4. Deployment

1. **Render (backend)**: set `FIREBASE_PROJECT_ID` and the secret
   `FIREBASE_SERVICE_ACCOUNT_JSON`, delete the `JWT_*` variables, and deploy.
   `alembic upgrade head` applies `c5f1a7e3d9b2`. **Every existing session ends.**
   Users sign in again, and pre-Firebase accounts migrate on that first
   sign-in, keeping their password.
2. **Vercel (admin)**: set the 6 `NEXT_PUBLIC_FIREBASE_*` values and redeploy
   (they are inlined at build time). Staff sign in with their existing email
   and password; the first sign-in migrates them.
3. **Mobile**: upload `google-services.json` as an EAS file secret, set
   `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`, and build a new release. The release
   keystore's SHA-1/SHA-256 must be registered in Firebase (step 1.7). Old
   app builds stop working against the new backend, because their login
   endpoints are gone, so ship both together.

## 5. How the flows map to Firebase

| Flow | Client | Backend |
|---|---|---|
| Register | `createUserWithEmailAndPassword` → `sendEmailVerification` | `/auth/sync` creates the CUSTOMER with first/last name |
| Email verification | Verify screen: resend (60 s cooldown), "I've verified" + auto-check on app focus → `reload` + fresh token | Protected routes return 403 `EMAIL_NOT_VERIFIED` for unverified email/password sign-ins; `/auth/me` stays open |
| Forgot password | `sendPasswordResetEmail` (same message whether or not the account exists) | none |
| Google | native: Google Sign-In → `signInWithCredential`; web: popup, with redirect fallback | `/auth/sync` links to an existing row by **verified** email, or creates one |
| Phone OTP | `signInWithPhoneNumber` (web: invisible reCAPTCHA). One send per tap, 60 s cooldown, max 3 per number per 15 min | `/auth/sync` links by phone (OTP-verified) or creates one |
| Account linking | Google for an email that already has a password → "You already have an account" → sign in with password → `linkWithCredential`. Account → "Add mobile number" links a phone to the same Firebase user | Same UID means same row; a verified email/phone that is already linked to a *different* UID returns 409 `ACCOUNT_EXISTS_DIFFERENT_METHOD` (never duplicated, never auto-merged) |
| Legacy accounts | Firebase rejects the password → `POST /auth/legacy-migrate` → sign in again | Verifies the old argon2 hash once, creates the Firebase user with the same password, erases the hash |

## 6. Production security checklist

- [x] No passwords, OTPs, or password hashes stored for new accounts; legacy hashes are erased on migration.
- [x] Identity only from `verify_id_token` (signature, expiry, audience = project). User ids/emails in requests are ignored (tested).
- [x] Service-account key only in the backend secret env; `*firebase-adminsdk*.json`, `service-account*.json`, and native config files are gitignored.
- [x] Tokens never logged (only the rejection reason); the realtime `?token=` query is redacted from uvicorn logs.
- [x] Rate limits: `/auth/sync` 20/min, `/auth/legacy-migrate` 5/min per IP. Client-side OTP and verification-email throttles on top of Firebase's own limits.
- [x] Legacy migration returns the same answer and takes the same time for an unknown account and a wrong password.
- [x] Disabled or suspended users are rejected on every request (PostgreSQL status); admins suspending a customer also disables the Firebase user and revokes their sessions.
- [x] CORS limited to `ALLOWED_ORIGINS` (tested).
- [ ] HTTPS only: Render and Vercel provide it; the mobile release uses an `https://` API URL, so cleartext stays off.
- [ ] Firebase SMS region policy set to India; test phone numbers used in QA.
- [ ] App Check / Play Integrity enabled before a public launch.
- [ ] Rate limiter is per-process in memory. Move it to Redis if the backend scales past one instance.

## 7. Known limitations / follow-ups

- An admin changing a customer's email or phone (`PATCH /customers/{id}/contact`) updates only PostgreSQL. The next sign-in resets it to the Firebase value. Updating Firebase too is a follow-up.
- iOS is not configured yet (it needs `GoogleService-Info.plist`, an APNs key for phone auth, and `expo-build-properties` with `useFrameworks: "static"`).
