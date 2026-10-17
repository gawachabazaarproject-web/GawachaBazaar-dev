# Integration Contracts

> **Status:** Verified from the adapter code and fake-based tests on 2026-10-14 — these are the contracts **as this codebase uses them**. Third-party API documentation was **not** consulted or re-verified, and no live call to Firebase, Razorpay, Cloudinary, Expo, Google or OSRM was made. Overview and failure impact: [THIRD_PARTY_SERVICES](THIRD_PARTY_SERVICES.md).

## 1. Firebase Authentication

**Inbound token (client → backend):** `Authorization: Bearer <Firebase ID token>`. Claims read ([`FirebaseAdminGateway.verify_id_token`](../../backend/app/core/firebase.py)): `uid`, `email`, `email_verified` (default false), `phone_number`, `name`, `firebase.sign_in_provider` (`password`, `google.com`, `phone`, …), `iat` (compared with the user's `tokens_valid_after`). Verified with `firebase_admin.auth.verify_id_token(token, app, clock_skew_seconds=10)` against `FIREBASE_PROJECT_ID`.

**Admin SDK operations used:** `auth.get_user(uid)` (revocation/disabled check, cached 60 s), `auth.create_user(email, email_verified, [password], [display_name])`, `auth.update_user(uid, password=…)`, `auth.update_user(uid, disabled=…)`, `auth.revoke_refresh_tokens(uid)`, `auth.delete_user(uid)`. Errors mapped: expired/revoked/invalid ID token → `FirebaseTokenError("expired"|"revoked"|"invalid")`; certificate fetch or credential failure → `FirebaseUnavailableError` (HTTP 503); email already exists → `FirebaseEmailExistsError`; weak password → `FirebasePasswordRejectedError`.

**Credentials:** `FIREBASE_SERVICE_ACCOUNT_JSON` (inline JSON or file path); otherwise anonymous credentials (verification works; admin operations fail). Behaviour of every combination: [AUTHENTICATION](../05-domains/AUTHENTICATION.md).

**Client side:** mobile uses `@react-native-firebase/auth` + Google Sign-In (native) and the Firebase JS SDK on web; Admin uses the Firebase JS SDK with `browserLocalPersistence`. Phone auth numbers are E.164 `+91…` (`mobile/src/auth/phone.ts`). Email links (verify/reset) are Firebase-hosted unless the app handles them in `(auth)/action.tsx`.

## 2. Razorpay

Adapter: [`razorpay_gateway.py`](../../backend/app/services/razorpay_gateway.py) via `httpx`, HTTP Basic auth (`key_id:key_secret`), timeout `RAZORPAY_TIMEOUT_SECONDS` (10 s), base `RAZORPAY_BASE_URL` (`https://api.razorpay.com/v1`). Amounts are **integer paise** (`to_paise`/`from_paise`); the adapter is the only place that converts.

| Call | Request fields used | Response fields used | Error handling |
|---|---|---|---|
| `POST /orders` | `amount` (paise), `currency`, `receipt` (≤ 40 chars of the reference), `notes{reference, idempotency_key}` | `id`, `amount`, `currency` (must equal the request, else `GatewayRejectedError`) | Any gateway error creating an order is reported as a definite failure (no money moved) |
| `GET /orders/{id}/payments` | – | `items[]`: `id`, `status` (`captured`/`refunded` ⇒ success), `amount`, `currency`, `error_description`; newest first | Timeout/connection ⇒ `GatewayTimeoutError`/`GatewayConnectionError` (outcome unknown); HTTP ≥ 500 ⇒ `GatewayError`; 4xx ⇒ `GatewayRejectedError` |
| `POST /payments/{payment_id}/refund` | `amount` (paise), `speed: "normal"`, `notes{idempotency_key}` | `id`, `status` (`processed`→success, `pending`/`created`→processing, `failed`), `error_description` | If no `pay_…` id is known the payment id is resolved from the order's captured payment first |
| `GET /refunds/{id}` | – | `id`, `status`, `error_description` | as above |

**Checkout (client):** the app loads `https://checkout.razorpay.com/v1/checkout.js` in a WebView with options `{key, order_id, amount, currency, name, description, prefill{name,email,contact}, theme.color, retry.enabled}` built from `OnlineCheckoutResponse` ([`razorpayOptions.ts`](../../mobile/src/features/payment/razorpayOptions.ts)); success payload `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` is posted to `/payments/online/{id}/confirm` or `/payments/{id}/confirm`. UPI app hand-off relies on `<queries>` entries added by `plugins/withAndroidRelease.js`.

**Signatures:** checkout = hex HMAC-SHA256 of `"{razorpay_order_id}|{razorpay_payment_id}"` with the **key secret**; webhook = hex HMAC-SHA256 of the **raw body** with the **webhook secret**; both compared with `hmac.compare_digest`.

**Webhook payloads read:** `event`; `payload.payment.entity` (`id`, `order_id`, `amount`, `currency`), `payload.order.entity` (`id`, `amount_paid`, `currency`), `payload.refund.entity.id`; header `X-Razorpay-Event-Id` (fallback: SHA-256 of the body) and `X-Razorpay-Signature`. Event list and semantics: [WEBHOOKS](../03-api/WEBHOOKS.md).

**Test-mode vs live:** a `rzp_test_` key in production only logs a warning. Required account settings: automatic capture; webhook to `/api/v1/payments/webhooks/razorpay`.

**Not covered by the contract:** idempotency headers (none sent), partial refunds, payment links, subscriptions, settlement reconciliation, disputes.

## 3. Cloudinary

[`image_upload.py`](../../backend/app/services/image_upload.py): `cloudinary.uploader.upload(file, folder=…, resource_type="image")`; returns `secure_url` and `public_id` (only `secure_url` is persisted). Folders: `gawachabazaar/products/{product_id}`, `gawachabazaar/categories/{category_id}`, `gawachabazaar/ads`, `gawachabazaar/home-slides`. Pre-checks: declared type in {`image/jpeg`,`image/png`,`image/webp`,`image/gif`}, size 1 B–8 MB. Errors: not configured → 503 `UPLOADS_NOT_CONFIGURED`; Cloudinary error → 502 `UPLOAD_FAILED` with Cloudinary's message. No transformation parameters, signed delivery URLs or deletion are used.

## 4. Routing (delivery distance)

**Google Distance Matrix** (`GET https://maps.googleapis.com/maps/api/distancematrix/json`): params `origins=lat,lon`, `destinations=lat,lon`, `mode=driving`, `key`; reads `rows[0].elements[0].status` (must be `OK`) and `distance.value` (metres → km). **OSRM** (`GET {OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false`): reads `code == "Ok"` and `routes[0].distance` (metres → km). Both: timeout `ROUTING_TIMEOUT_SECONDS` (3 s), `raise_for_status`; **any exception** ⇒ haversine × `DELIVERY_ROAD_FACTOR`. Coordinates are rounded to 4 decimals for caching (per-process `lru_cache`, 2048). The default OSRM host is the public demo server (not for production use per the project's own comment).

## 5. Expo push

[`push.py`](../../backend/app/services/push.py): `POST https://exp.host/--/api/v2/push/send` with a JSON array of `{to, title, body, data{orderId}, sound:"default", channelId:"orders"}` (timeout 10 s). Response: `data[]` tickets; a ticket with `status == "error"` is logged with `details.error` and `message`; `DeviceNotRegistered` deletes the token. No receipts API polling. Registration contract: `POST /push-tokens {token: "ExponentPushToken[…]"|"ExpoPushToken[…]", platform?}`; unregister is `POST /push-tokens/unregister`. Notification copy for the eight events: [NOTIFICATIONS](../05-domains/NOTIFICATIONS.md).

## 6. Expo Updates (OTA)

Update URL `https://u.expo.dev/<project id>` (`app.json`), `runtimeVersion` policy `appVersion`, channel per build (`eas.json`), `checkAutomatically: ON_LOAD`, `fallbackToCacheTimeout: 3000`. An update is delivered only to builds with the same runtime version and channel. In-app manual check/restart: `src/features/updates/useAppUpdates.ts`.

## 7. Contracts the apps rely on from this backend

The REST API ([API_REFERENCE](../03-api/API_REFERENCE.md)), the error envelope and codes ([ERROR_HANDLING](../02-architecture/ERROR_HANDLING.md)), the WebSocket message shape ([NOTIFICATIONS](../05-domains/NOTIFICATIONS.md)), and the rule that money is a two-decimal string. The apps and the API deploy independently, so **never remove or rename a field an installed app version uses.** There is no API version negotiation or minimum-app-version check.

## Unverified

Real payload shapes beyond what the tests construct; Razorpay and Expo rate limits and retry policies; Firebase token revocation propagation timing; Google/OSRM response variations (e.g. `ZERO_RESULTS`) beyond the `status != OK` branch.
