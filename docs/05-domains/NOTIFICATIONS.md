# Notifications (push, realtime) — and what does not exist

> **Status:** Verified for the code paths; backend push error handling is covered by [`test_push_send.py`](../../backend/tests/test_push_send.py) (Expo HTTP call faked). **Delivery to a real device with real FCM credentials is not verified in the repository.** **Last verified:** 2026-10-14. The working tree contains uncommitted edits to `push.py` and its new test file that were **not made by this documentation task** (see [AI_STATUS](../00-overview/AI_STATUS.md)); this document describes the working-tree version.
> **Source files:** [`backend/app/services/push.py`](../../backend/app/services/push.py), [`core/realtime.py`](../../backend/app/core/realtime.py), [`api/v1/push.py`](../../backend/app/api/v1/push.py), [`api/v1/realtime.py`](../../backend/app/api/v1/realtime.py), [`models/push_token.py`](../../backend/app/models/push_token.py); mobile [`usePushNotifications.ts`](../../mobile/src/features/notifications/usePushNotifications.ts), [`useRealtimeSync.ts`](../../mobile/src/features/orders/useRealtimeSync.ts); Admin `lib/realtime-context.tsx`, `components/NewOrderAlarm.tsx`.

## Channels that exist

| Channel | Audience | Mechanism |
|---|---|---|
| **Push** (Expo push service) | Customer who owns the order | `notify_user_status` → background thread → `https://exp.host/--/api/v2/push/send` |
| **Realtime invalidation** (WebSocket `/api/v1/ws/events`) | The order's customer sockets and all staff sockets (not delivery partners) | `notify_status_event` → `asyncio.run_coroutine_threadsafe` onto the main loop |
| Admin new-order alarm | Staff in the Admin panel | Admin listens on the WebSocket and rings for ~10 s (`NewOrderAlarm.tsx`) |
| **Email / SMS / WhatsApp** | – | **None.** The platform sends no email or SMS itself. Firebase sends its own verification/reset emails and OTP SMS |

## Push notifications

- **Registration:** the app asks permission (Android channel `orders`, high importance), obtains an Expo push token (project id from `app.json`) and calls `POST /push-tokens` after sign-in; `POST /push-tokens/unregister` on logout. Token format is validated (`ExpoPushToken[...]`/`ExponentPushToken[...]`, 10–255 chars). Tokens are unique; a token seen under another user is **re-assigned** (device re-used by another account).
- **Events** (exactly eight `(resource, status)` pairs in [`push.py`](../../backend/app/services/push.py)): order `PENDING` ("Order placed"), `CONFIRMED`, `CANCELLED`, `COMPLETED` ("Order delivered"); fulfillment `PACKED`, `OUT_FOR_DELIVERY`; payment `PAID`; refund `REFUNDED`. Everything else (e.g. payment failed, refund approved/rejected/failed, order expired, quote sent) sends **no** push.
- **Sending:** best effort on a daemon thread with its own DB session; failures are logged (`PUSH_SEND_FAILED`) and never affect the business action. Expo ticket errors are logged (`PUSH_TICKET_ERROR` with Expo's reason, e.g. credentials missing); a `DeviceNotRegistered` ticket deletes that token. A user with no token logs `PUSH_NO_TOKENS`. There is **no receipt polling**, retry or queue.
- **App behaviour:** foreground notifications are shown; a received notification invalidates the `orders`/`order` queries; tapping routes to `/order/{id}` (including a cold start).
- **Requirement for real delivery:** the EAS project needs FCM credentials (the log message in `push.py` names `InvalidCredentials`/`MismatchSenderId` as the symptoms when they are missing). Whether they are configured for the current (`yash145`) EAS project is **unknown**.
- `notify_status_event` calls the push path **even when no event loop is registered** (e.g. under pytest) because the push call comes first.

## Realtime events

Message: `{resource: "order"|"fulfillment"|"payment"|"refund", order_id, status, previous_status, occurred_at}` — an invalidation signal, not data. Events are emitted **after the transaction commits** in the payment/refund paths (`_flush_pending_realtime_events`); some other call sites emit just before their own commit (documented in `realtime.py`), so a rollback could produce one harmless extra refetch.

Delivery rules: customers receive events for their own orders; `is_staff` sockets (any of `ADMIN, HUB_STAFF, OPERATIONS, SUPPORT`) receive all; delivery partners are excluded. The socket is server → client; the client may send `ping` and receives `{"type":"pong"}`. Auth: Firebase ID token in the query string; handshake closes with code 1008 on any failure; the handler releases its DB connection immediately so sockets do not exhaust the pool.

Limits: in-process registry — events do not cross replicas (OPS-003); no replay, so a disconnected client misses events and must refetch on reconnect; reconnect behaviour of the apps was **not tested**; no behavioural WebSocket test exists in `backend/tests/` (the QA audit exercised it with the `multiproc` harness).

## Not implemented

In-app notification inbox, marketing/promotional push, quote-sent and refund-approved notifications, email/SMS receipts, notification preferences/opt-out beyond the OS permission, delivery-partner assignment alerts (partners poll the Admin panel).
