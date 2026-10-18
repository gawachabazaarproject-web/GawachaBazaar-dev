# Troubleshooting

| Log marker / symptom | Meaning | Action |
|---|---|---|
| `PUSH_NO_TOKENS` | User has no registered device | Permission denied, emulator, or the app never reached `POST /push-tokens` |
| `PUSH_TICKET_ERROR ... InvalidCredentials` / `MismatchSenderId` | FCM credentials missing for the EAS project | SETUP.md step 3 |
| `PUSH_TICKET_ERROR ... DeviceNotRegistered` | App uninstalled / token dead | Token is deleted automatically |
| `PUSH_DUPLICATE_SKIPPED` | That order + status was already pushed | Expected on retries |
| `PUSH_SEND_FAILED` | Expo unreachable or timed out (10 s) | Business action unaffected; no retry |
| Tap does nothing | Unknown `type` or bad `orderId`, or signed out | Compare the payload with `notificationRouting.ts` |
| One status never pushes | Only 8 (resource, status) pairs push | See ARCHITECTURE.md |
| Works in dev, not in the Play build | Wrong EAS project or credentials for that build | Check the `app.json` project id and `eas credentials` |
