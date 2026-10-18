# Architecture

```
Login -> permission -> Expo token -> POST /api/v1/push-tokens -> push_tokens
Order / fulfilment / payment / refund transition
  -> core/realtime.notify_status_event
  -> services/push.notify_user_status   (daemon thread, own DB session)
  -> claim a row in notification_events (unique dedupe_key); duplicate => skipped
  -> Expo push API -> FCM -> device -> tap -> /order/{id}
```

## Delivery path: Expo, not the Firebase Admin SDK
Pushes are sent to the Expo push service (`exp.host`) using Expo push tokens; Expo forwards to FCM with the FCM V1 key stored in **EAS**. The backend never calls `firebase_admin.messaging`, so the Admin SDK service account is not involved in push delivery. It is used only for sign-in verification and admin operations (`core/firebase.py`).

## Already existed (kept, not rebuilt)
`push_tokens` table, `POST /push-tokens` and `/push-tokens/unregister` (auth required; the user id comes from the session, never the body), token-format validation, best-effort background send, removal of `DeviceNotRegistered` tokens, Android channel `orders` (HIGH), foreground banner, logout unregister.

## Added 2026-10-18 (REFUND_INITIATED added the same day)
- **Idempotency:** table `notification_events` (`dedupe_key` unique). Key = `{resource}:{order_id}:{new_status}`, e.g. `order:42:CONFIRMED`. The send thread inserts the key with `ON CONFLICT DO NOTHING`; if no row was inserted it logs `PUSH_DUPLICATE_SKIPPED` and sends nothing. Each status is reached once per order, so this means one push per business event. Trade-off: at-most-once (a failed Expo call is not retried).
- **Payload:** `{ "type": "ORDER_CONFIRMED", "orderId": 42 }`. `orderId` is kept for installed app versions. No addresses, amounts, tokens or personal data.
- **Types:** ORDER_PLACED, ORDER_CONFIRMED, ORDER_PACKED, OUT_FOR_DELIVERY, ORDER_DELIVERED, ORDER_CANCELLED, PAYMENT_RECEIVED, REFUND_INITIATED (refund approved), REFUND_COMPLETED (nine pairs in `_MESSAGES`; no statuses were invented).
- **App:** taps are validated by `notificationRouting.ts` (unknown type or bad id => ignored), stored as a pending route, and opened only when the session is restored, the root navigator is mounted and `AppGate` has left login/onboarding. A tap while signed out is dropped. Token rotation (`addPushTokenListener`) re-registers the token.

## Decisions
- **No `device_tokens` rewrite.** `push_tokens` already has a user FK, unique token, timestamps and multi-device support. `is_active` / `device_id` columns were not added: dead tokens are deleted, which has the same effect with less state.
- **Logout** deletes this device's token for the signed-out user, so the next account on the device does not receive the previous account's pushes. Signing in again registers it again.
- **Preferences:** none exist and none were added (only the OS permission). Minimal later step: one boolean per category on `users`, checked in `notify_user_status`.
- **Reliability:** the push never runs inside the business transaction; failures are only logged.

## Known limits
- **Commit ordering (traced 2026-10-18):** every call site that produces a push (order placed/cancelled/confirmed/completed, fulfilment packed/out-for-delivery/delivered, payment paid, refund approved/refunded) calls `notify_status_event` **after** its `db.commit()`; the payment service queues events and flushes them post-commit. The older note in `core/realtime.py` about pre-commit sites only applies to events that send no push (e.g. fulfilment ASSIGNED). A wait-for-commit check was tried and removed: it would drop "Order placed" when an online order is confirmed in the same flow.
- No receipt polling, retry queue, promotional pushes or admin test endpoint. Single-process thread model, like the rest of the backend.
