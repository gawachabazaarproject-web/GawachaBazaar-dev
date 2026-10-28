# Android device test (USB) against a local backend

Used on 2026-10-27 to run the real app on a Xiaomi phone (Android 14) with **real Firebase login** and **Razorpay test mode**, against a **local disposable database**. Results: [AWS_PRODUCTION_PLAN.md](../09-deployment-operations/AWS_PRODUCTION_PLAN.md) section 6.4.

## Safety rules
- `backend/.env` may contain the **hosted `DATABASE_URL`**. Never start the backend for a device test without overriding `DATABASE_URL` to a local `*_test` database. Environment variables override `.env`; do not rely on `.env`.
- Use Razorpay **test** keys only (`rzp_test_...`). The launcher used for the run refuses to start otherwise.
- The debug build is installed as a **different application id** so the user's production app is untouched.

## Procedure
1. **Local stack:** PostgreSQL 16 (disposable DB, `alembic upgrade head`), Redis (`redis:7-alpine`, 64 MB, LRU), OSRM with the Nagpur data (`deploy/osrm/build.sh`), seed a few products (`backend/scripts/loadtest_api.py seed --users 1 --products 12`, DB name must end in `_test`).
2. **Backend:** `uvicorn app.main:app --host 127.0.0.1 --port 8000` with explicit env: `DATABASE_URL` (local), `REDIS_URL`, `OSRM_BASE_URL`, `APP_ENV=development`, `FIREBASE_PROJECT_ID` (the app's real project id; token verification works without a service account), `RAZORPAY_*` test keys, `PACKING_POINT_*` or a packing-point inventory location, `CLOUDINARY_*` empty.
3. **Build the debug APK** (debug builds allow cleartext HTTP): in `mobile/android/app/build.gradle` temporarily set `applicationId` to `com.gawacha.bazaar` (a package already present in `google-services.json`; `android/` is gitignored/generated), then `cd mobile/android && ./gradlew assembleDebug -PreactNativeArchitectures=arm64-v8a` with `EXPO_PUBLIC_API_URL_OVERRIDE=http://localhost:8000/api/v1`.
4. **Device:** `adb devices`; `adb reverse tcp:8000 tcp:8000`; `adb reverse tcp:8081 tcp:8081`; `adb install -r app-debug.apk`; start Metro (`npx expo start --dev-client --port 8081` with the same `EXPO_PUBLIC_*` variables); open the app with `adb shell am start -a android.intent.action.VIEW -d "exp+gawachabazaar://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081" com.gawacha.bazaar`.
5. **Drive the flow on the phone:** sign in (email/password; **Google sign-in does not work in a debug build** because the debug signing key is not registered in Firebase), add an address, add a product, View Cart, checkout, pay with a Razorpay test option, open the order.
6. **Verify** from the backend log (`routing cache=...`, `delivery_priced`, `ORDER_CREATED`, `PAYMENT_STATE_TRANSITION`) and the database (`orders`, `payments`, `checkout_sessions`).

## Xiaomi / MIUI notes
- `adb shell input ...` fails with `INJECT_EVENTS` unless **Developer options -> USB debugging (Security settings)** is enabled; without it a person must tap.
- `adb exec-out screencap -p > shot.png` works without extra permissions and was used for evidence.
- Login and payment entry are always done by the user; automation never types passwords or payment details.
