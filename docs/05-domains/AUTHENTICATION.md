# Authentication and Account Identity

> **Status:** Verified against source and tests on 2026-10-14; live Firebase sign-in on a device was observed manually the same day (not a repository artefact). Role/permission model: [USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md). Setup checklist for Firebase: [`deploy/FIREBASE_AUTH.md`](../../deploy/FIREBASE_AUTH.md).
> **Source files:** [`backend/app/core/firebase.py`](../../backend/app/core/firebase.py), [`services/auth.py`](../../backend/app/services/auth.py), [`api/v1/auth.py`](../../backend/app/api/v1/auth.py), [`dependencies/auth.py`](../../backend/app/dependencies/auth.py), [`core/security.py`](../../backend/app/core/security.py), [`models/user.py`](../../backend/app/models/user.py), [`services/staff.py`](../../backend/app/services/staff.py), `mobile/src/auth/`, `mobile/src/store/authStore.ts`, `Admin/lib/auth-context.tsx`.
> **Tests:** [`test_auth.py`](../../backend/tests/test_auth.py), [`test_firebase_gateway.py`](../../backend/tests/test_firebase_gateway.py), [`test_phase_9_rbac.py`](../../backend/tests/test_phase_9_rbac.py), [`test_staff_status.py`](../../backend/tests/test_staff_status.py), [`test_cross_customer_access.py`](../../backend/tests/test_cross_customer_access.py), [`test_authz_matrix.py`](../../backend/tests/test_authz_matrix.py), fake in [`firebase_fake.py`](../../backend/tests/firebase_fake.py).

## Purpose and scope

Firebase Authentication owns **every credential** (email/password, Google, phone OTP, email verification, password-reset links). The backend verifies the Firebase **ID token** on each request and maps the verified identity to one `users` row. The backend stores no passwords for Firebase accounts (`users.password_hash` is only for not-yet-migrated legacy accounts).

## Sign-in methods and clients

| Method | Mobile | Admin | Notes |
|---|---|---|---|
| Email + password | Yes (`login.tsx`, `register.tsx`) | Yes (`/login`) | New email accounts must verify the address before any protected route works (`EMAIL_NOT_VERIFIED`) |
| Google | Yes — native `@react-native-google-signin` with the Web client id (`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`) | Not found in `Admin/` | Needs the app's signing **SHA-1/SHA-256 registered in the Firebase Android app**, otherwise the app logs `GOOGLE_SIGNIN_FAILED code 10 DEVELOPER_ERROR` (observed 2026-10-14 after the EAS account change) |
| Phone OTP | Yes (`phone.tsx`, `otp.tsx`; client-side throttles: 60 s per number, 3 sends / 15 min) | No | Firebase also rate-limits; OTP SMS cost is Firebase's |
| Link a second method | Yes (`link-account.tsx`, `add-phone.tsx`) | – | Uses `linkWithCredential`; same UID ⇒ same row |

## Backend flow

1. **Token verification** (`FirebaseAdminGateway.verify_id_token`): signature, expiry and audience against `FIREBASE_PROJECT_ID`, using Google's public certificates (no service account needed); `clock_skew_seconds=10`.
2. **Revocation/disabled check:** `auth.get_user(uid)` result cached per uid for 60 s; tokens issued before `tokens_valid_after`, or for a disabled Firebase user, are refused. If this lookup *itself* fails (any exception) the token is **accepted** (the signature was verified) — a deliberate availability trade-off.
3. **Errors:** expired → 401 `TOKEN_EXPIRED`; invalid/revoked → 401 `AUTHENTICATION_ERROR` ("Could not validate credentials."); Firebase not configured/unreachable or credential problem → 503 `AUTH_UNAVAILABLE`.
4. **User resolution:** `users.firebase_uid` lookup; none → 401 `ACCOUNT_NOT_REGISTERED` (client then calls sync); non-`ACTIVE` → 401; email/password with unverified email → 403 `EMAIL_NOT_VERIFIED` (not applied to Google or phone sign-ins; skipped for `GET /auth/me`).
5. **`POST /auth/sync`** — find, link or create (details in [DATA_FLOW](../02-architecture/DATA_FLOW.md) §1). Link rules: only a *verified* email or a phone claim may link an existing row that has no Firebase UID; a row already tied to a different UID returns 409 `ACCOUNT_EXISTS_DIFFERENT_METHOD`; email and phone resolving to two different accounts returns 409; linking erases `password_hash`. A new row gets role `CUSTOMER` (primary). A missing baseline role is a 500 configuration error.
6. **Legacy accounts:** `POST /auth/legacy-migrate` (5/min) — the client calls it only after Firebase rejected an email/password sign-in. It verifies the old Argon2 hash (a dummy hash equalises timing for unknown accounts), creates the Firebase user with the same password (or without a password and `PASSWORD_RESET_REQUIRED` if Firebase's policy rejects it), links the row and erases the hash, so it can succeed at most once per account. Staff emails count as verified; customer emails must still be verified.
7. **Per-request roles:** `require_roles` / `require_permission` read `user_roles` live (see roles document).

## Staff accounts

`POST /staff` (ADMIN, `staff.manage`): checks email/phone are free, creates the Firebase user (`email_verified=True`, so the person can sign in immediately), then the `users` row + role + audit record in one transaction; if the database step fails the Firebase user is deleted again (no orphan). Role assign/revoke, activate/deactivate (an admin cannot deactivate themself; the last active admin is protected). Admin password reset for customers: `CustomerService.admin_reset_password` sets the Firebase password and **revokes all sessions** (or, for an un-migrated legacy account, stores a new hash).

## What needs the service account (`FIREBASE_SERVICE_ACCOUNT_JSON`)

| Needs it | Does not need it |
|---|---|
| Creating staff accounts, admin password reset, disabling/revoking, legacy migration | Verifying ID tokens and `POST /auth/sync` (only `FIREBASE_PROJECT_ID`) |

Without it the gateway uses anonymous credentials so token verification still works; the operations in the left column fail with `AUTH_UNAVAILABLE`/503 ([`firebase.py`](../../backend/app/core/firebase.py) lines 160–171). The revocation lookup also silently degrades (`FIREBASE_REVOCATION_CHECK_FAILED` warning) because `get_user` needs credentials, so **without the service account, disabled/revoked Firebase sessions remain valid until the ID token expires (≤ 1 h)**.

### Observed incident (2026-10-14)

Every client showed "Could not validate credentials." and then "Sign-in is temporarily unavailable". The AWS backend had `FIREBASE_SERVICE_ACCOUNT_JSON` set to a **file path** (`/etc/secrets/firebase-service-account.json`) with no usable file behind it. `_get_app()` treats a non-file value as inline JSON, raised "not valid JSON", and every token verification returned 503. Deleting the variable restored password sign-in (verified by the user). Lesson recorded in [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md): a bad service-account value takes down all sign-ins even though token verification does not need it. A proposed fix (fall back to anonymous credentials when the account fails to load) was offered but **not implemented**.

## Business rules and constraints

- Email and phone are normalised (`normalize_email`, `normalize_phone` — Indian numbers to `+91…`); `users.email` and `users.phone` are unique; `CHECK (email IS NOT NULL OR phone IS NOT NULL)`.
- Status `ACTIVE/INACTIVE/SUSPENDED`; only `ACTIVE` may use the API.
- Admins can change a customer's email/phone in PostgreSQL only; the next sync can overwrite the phone from the Firebase claim and only fills a *missing* email ([`_refresh_contact_details`](../../backend/app/services/auth.py)) — Firebase is not updated (documented limitation in [`FEATURES.md`](../FEATURES.md) §known gaps).

## Concurrency and idempotency

`sync_user` is idempotent; a concurrent first sign-in loses the unique-constraint race and re-reads the winner (`IntegrityError` path); `legacy-migrate` runs the Firebase create before the database commit and deletes the Firebase user again if the commit fails.

## Failure scenarios

| Scenario | Result |
|---|---|
| Firebase public-key fetch fails | 503 `AUTH_UNAVAILABLE` |
| Token for another Firebase project | 401 "Could not validate credentials." |
| Token expired mid-session | 401 `TOKEN_EXPIRED`; clients refresh once and retry |
| Backend asleep (AWS cold start ≈ 44 s) | Mobile retries sync with back-off and shows a loader; first request may exceed the 15 s client timeout |
| User disabled in Firebase | Refused after the (cached 60 s) revocation lookup — only when the service account is configured |

## Security notes and gaps

- The WebSocket token travels in the query string (SEC-005); redacted in logs.
- `POST /auth/legacy-migrate` is a public password oracle by nature, rate-limited per process/IP (SEC-003 suspected, SEC-002 XFF).
- `PyJWT` is listed in `requirements.txt` but **no backend code imports it** (a leftover from the pre-Firebase JWT design); `firebase-admin` depends on it anyway, so the direct pin is redundant rather than harmful ([DEPENDENCY_MANAGEMENT](../06-development/DEPENDENCY_MANAGEMENT.md)).
- Account-enumeration differences between responses were not tested.
- Live Firebase behaviours (token revocation timing, phone OTP, Google) are untested by the suite, which uses a fake.
