# Error Handling

> **Status:** Verified against source on 2026-10-14.
> **Evidence:** [`backend/app/exceptions/base.py`](../../backend/app/exceptions/base.py), [`handlers.py`](../../backend/app/exceptions/handlers.py), [`main.py`](../../backend/app/main.py), [`services/auth.py`](../../backend/app/services/auth.py), [`test_exceptions.py`](../../backend/tests/test_exceptions.py), [`mobile/src/api/errors.ts`](../../mobile/src/api/errors.ts), [`Admin/lib/api.ts`](../../Admin/lib/api.ts).

## 1. The error envelope

Every error the backend produces uses one JSON shape:

```json
{ "code": "MACHINE_READABLE_CODE", "message": "Human-readable text", "details": null }
```

`details` carries a structured value only for validation errors (the Pydantic error list) and for a few business errors (e.g. `PASSWORD_RESET_REQUIRED` returns `{"email": …}`). Clients branch on `code`, never on `message`.

## 2. Where errors come from

| Source | HTTP | `code` | Notes |
|---|---|---|---|
| `NotFoundError` | 404 | `NOT_FOUND` | Also used for "exists but belongs to someone else" so existence is not disclosed |
| `AuthenticationError` | 401 | `AUTHENTICATION_ERROR` | Missing/invalid token, inactive user, bad webhook signature |
| `AuthorizationError` | 403 | `AUTHORIZATION_ERROR` | Role or permission missing |
| `ConflictError` | 409 | `CONFLICT_ERROR` | Illegal state transition, duplicate, insufficient stock, stale basket… |
| `BusinessValidationError` | 422 | `BUSINESS_VALIDATION_ERROR` | Rule violations that are not request-shape errors |
| `RateLimitError` / slowapi | 429 | `RATE_LIMIT_EXCEEDED` | slowapi's exception is mapped to this envelope in `main.py` |
| Request validation (FastAPI) | 422 | `REQUEST_VALIDATION_ERROR` | `details` = Pydantic error list |
| Specific `AppException(code=…)` | varies | see §3 | Used where clients must react differently |
| Payment gateway failures (`GatewayError` family) | 502 | `PAYMENT_GATEWAY_REJECTED` / `PAYMENT_GATEWAY_UNAVAILABLE` / `PAYMENT_GATEWAY_ERROR` | Message avoids claiming a timed-out payment failed |
| Anything else (`Exception`) | 500 | `INTERNAL_SERVER_ERROR` | Stack trace logged server-side; client receives "An unexpected internal server error occurred" |

## 3. Codes that clients are expected to handle

| Code | HTTP | Meaning / expected client behaviour | Defined in |
|---|---|---|---|
| `TOKEN_EXPIRED` | 401 | Refresh the Firebase ID token and retry once; do **not** sign the user out | `services/auth.py` |
| `ACCOUNT_NOT_REGISTERED` | 401 | Valid Firebase user without an application row: call `POST /auth/sync`, then retry | `services/auth.py` |
| `EMAIL_NOT_VERIFIED` | 403 | Show the verify-email screen | `services/auth.py` |
| `AUTH_UNAVAILABLE` | 503 | Sign-in temporarily unavailable (Firebase unreachable or misconfigured); retry later | `services/auth.py` |
| `ACCOUNT_EXISTS_DIFFERENT_METHOD` | 409 | Same person, different Firebase user: sign in with the original method, then link | `services/auth.py` |
| `PASSWORD_RESET_REQUIRED` | 409 | Legacy migration succeeded but the old password fails Firebase policy: send a reset email | `services/auth.py` |
| `ONLINE_PAYMENTS_NOT_CONFIGURED` | 503 | Offer COD instead | `services/payment.py` |
| `PAYMENT_NOT_CONFIRMED` | 409 | Razorpay has not confirmed the payment yet; the order will appear automatically if money was taken | `services/checkout_session.py` |
| `UPLOADS_NOT_CONFIGURED` | 503 | Cloudinary is not configured | `services/image_upload.py` |
| `UPLOAD_FAILED` | 502 | Cloudinary rejected the upload (bad credentials, quota, outage); the message carries Cloudinary's text | `services/image_upload.py` |

## 4. Transactions and failure semantics

- Services own their transaction boundaries and call `commit()` explicitly; any exception path must `rollback()`. The pattern for multi-row work is: lock rows in a fixed order, validate, write, commit once, and only **after** a successful commit emit realtime/push events (`PaymentService._flush_pending_realtime_events`).
- `IntegrityError` at commit is translated to `ConflictError` ("conflicting update") in the main workflows; lost races on unique rows (first sync, payment create, session attach) re-read the winner instead of failing.
- **Never hold a row lock across a gateway call:** `_initiate_upi` and `process_refund` commit before calling Razorpay; a timeout leaves the object in `PROCESSING` (outcome unknown), never `FAILED`.
- A late or out-of-order gateway event that would be an illegal transition (`PAID → FAILED`) is **logged and ignored**, not raised, so a webhook is always acknowledged.
- Reconciliation conditions are logged with stable markers: `PAYMENT_RECONCILIATION` (amount/currency mismatch, COD in an unexpected state, refund-after-capture failure), `PAYMENT_RESERVATION_MISMATCH`, `PAYMENT_WEBHOOK_UNKNOWN_REFERENCE`, `INVENTORY_RESERVATION_LATE_PAYMENT`. Nothing alerts on them automatically ([MONITORING_AND_LOGGING](../09-deployment-operations/MONITORING_AND_LOGGING.md)).

## 5. Client behaviour

- **Mobile** (`src/api/client.ts`, `errors.ts`): maps failures to an `ApiError` with `isNetworkError` (no response / timeout) and `status/code/details`; retries a `TOKEN_EXPIRED` once; the auth store retries `/auth/sync` with back-off for transient errors (network, 502/503/504) so a sleeping host does not bounce the user to the login screen; default request timeout 15 s.
- **Admin** (`lib/api.ts`): `ApiError(status, code, message, details)`; falls back to "Something went wrong" when the body is not the envelope.
- **Observed on 2026-10-14:** a misconfigured server-side service-account setting made every sign-in return `AUTH_UNAVAILABLE`, which both clients surfaced as "Sign-in is temporarily unavailable"; it is not distinguishable from a Firebase outage by clients (see [AUTHENTICATION](../05-domains/AUTHENTICATION.md) for the cause).

## 6. Known gaps

- Unhandled database exceptions become `INTERNAL_SERVER_ERROR` 500s with no specific code for clients ([`handlers.py`](../../backend/app/exceptions/handlers.py)); there is no retry guidance.
- `/health` does not touch the database, so a DB outage does not fail container health checks (by design, documented in the Dockerfile); `/health/db` is for smoke tests only.
- Stale comments in several modules still describe the pre-Firebase JWT/session design (e.g. [`api/v1/realtime.py`](../../backend/app/api/v1/realtime.py) mentions "type=access, live un-revoked session"; [`router.py`](../../backend/app/api/v1/router.py) mentions a "PNB gateway"). They do not affect behaviour; see [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md).
