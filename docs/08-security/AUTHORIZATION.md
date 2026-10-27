# Authorization

> **Status (2026-10-27).** Short map of how access is decided. The per-operation, machine-checked truth is `backend/tests/authz_golden.json` (every HTTP operation × every role; a new or widened endpoint fails `tests/test_authz_matrix.py` until a human reviews the diff and regenerates with `AUTHZ_REGEN=1`).

1. **Authentication:** Firebase ID token → `users` row by `firebase_uid`; user must be ACTIVE.
2. **Roles** are read from `user_roles` on every request (never from the token). `require_roles(...)` gates a route; `require_permission("x.y")` checks the static `ROLE_PERMISSIONS` map in `core/permissions.py`.
3. **Object ownership** is checked in services and answered with **404, not 403**, for other people's objects (customers' orders/payments/addresses, partners' assignments, referral history).
4. **Never trusted from a client:** amounts, fees, distances, statuses, user ids, roles, COD expected amount, earnings.

Additions on 2026-10-27: roles/permissions and the full partner/referral matrix are in [DELIVERY_PARTNER](../05-domains/DELIVERY_PARTNER.md#authorization-matrix) and [REFERRAL_SYSTEM](../05-domains/REFERRAL_SYSTEM.md). New permissions: `referrals.read/manage` (ADMIN), `partners.read` (ADMIN, OPERATIONS), `partners.manage`, `partners.cod_reconcile` (ADMIN). Reviewed golden diff: 23 new operations, none widening an existing one. COD delivery OTP (same day): 2 new operations (`GET /orders/{id}/delivery-otp` CUSTOMER only; `POST /delivery-partner/assignments/{id}/otp/send` DELIVERY_PARTNER only), plus an optional body on `POST /fulfillments/{id}/deliver` (roles unchanged).
