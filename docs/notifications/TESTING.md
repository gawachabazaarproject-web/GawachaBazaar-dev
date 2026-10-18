# Testing

## Automated (backend, disposable DB)
`TEST_DATABASE_URL=<loopback *_test db> python -m pytest -p no:cacheprovider tests/test_push_send.py`

Covers: credential error keeps the token; `DeviceNotRegistered` removes only that token; no-token case; OK ticket; **the same event key sends once**; payload carries `type` + `orderId` and the dedupe key; same user + same token does not duplicate; a token is re-assigned to another account.

Not automated: unauthenticated registration beyond the authz snapshot, provider timeout, multi-device fan-out, order-flow integration, and all mobile behaviour (the repo has no frontend tests). `notificationRouting.ts` was exercised with a one-off script (valid, string id, unknown type, malformed, null, negative).

## Manual real-device checklist (required before calling it done)
1. EAS build installed on a physical Android phone; FCM credentials uploaded (SETUP.md).
2. Sign in, allow notifications; a `push_tokens` row exists for the user.
3. Advance an order from Admin: foreground shows a banner; background and **killed** app show a system notification.
4. Tap each: it opens `/order/{id}`; for the killed-app case the app opens signed in, then the order.
5. Repeat the same status request: no second notification (`PUSH_DUPLICATE_SKIPPED`).
6. Sign out: that token's row is removed. Deny permission: the app works, no token.

## Exact device procedure
1. `cd mobile && eas build --platform android --profile preview`; download and install the APK.
2. Open the app, sign in, tap Allow on the permission prompt.
3. Backend DB: `SELECT user_id, left(token,22), platform, updated_at FROM push_tokens ORDER BY updated_at DESC LIMIT 5;` shows your user.
4. Place an order, then in Admin confirm -> pack -> out for delivery -> deliver. Check each arrives with the app open, in the background, and swiped away.
5. Tap a notification from the killed state: app opens signed in, then the order screen.
6. Cancel a paid online order, approve then process its refund: "Refund approved" then "Refund processed".
7. Sign out: `push_tokens` row removed. Sign in: row returns. Uninstall/reinstall: new row after sign-in; the old token is removed on the first `DeviceNotRegistered`.
