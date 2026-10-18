# Push notifications

Order updates reach customers as Expo push notifications (Expo push service -> FCM -> Android). This folder is the operational guide; the domain summary is [`../05-domains/NOTIFICATIONS.md`](../05-domains/NOTIFICATIONS.md).

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Flow, payload contract, idempotency, token lifecycle, decisions |
| [SETUP.md](SETUP.md) | Firebase / EAS / Render configuration |
| [TESTING.md](TESTING.md) | Automated tests and the manual real-device checklist |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Log markers and common failures |

**Verification status (2026-10-18):** backend sending, de-duplication and token registration are covered by `backend/tests/test_push_send.py` (Expo HTTP faked). Payload routing was checked with a throw-away script (see TESTING). **Delivery to a physical Android device has not been verified** by this change.
