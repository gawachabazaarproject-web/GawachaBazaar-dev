# Data Retention

> **Status:** Verified for what the code and scripts do; **no retention policy exists in the repository**, so periods other than the backup window are *not defined*. **Last verified:** 2026-10-14.
> **Evidence:** [`ENTITY_RELATIONSHIPS.md`](ENTITY_RELATIONSHIPS.md) (delete rules), [`deploy/scripts/backup-db.sh`](../../deploy/scripts/backup-db.sh), [`inventory_reservation.py`](../../backend/app/services/inventory_reservation.py), [`push.py`](../../backend/app/services/push.py), [`catalog.py`](../../backend/app/services/catalog.py), [`main.py`](../../backend/app/main.py).
> Related: [PRIVACY](../08-security/PRIVACY.md), [BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md).

## Summary

The application **never purges data on a schedule**. The only automatic data lifecycle actions are (1) expiring reservations and the still-pending orders attached to them, (2) removing dead push tokens when Expo reports `DeviceNotRegistered`, and (3) the compose stack's backup pruning (14 days). Everything else is kept indefinitely unless an admin deletes it through the few `DELETE` endpoints.

## By data category

| Data | Where | Retention behaviour (verified) | Defined policy |
|---|---|---|---|
| Customer identity (name, email, phone, `firebase_uid`) | `users` | Kept indefinitely. **No endpoint deletes or anonymises a user**; foreign keys from orders etc. are `RESTRICT`, so a user with any order could not be hard-deleted anyway. Inactivation (`status`) exists | None |
| Credentials | Firebase (not in the database); `users.password_hash` only for un-migrated legacy accounts | Hash is erased when the account migrates to Firebase | – |
| Addresses (with GPS) | `addresses` | Customer can delete their own addresses; cascade-deleted with the user | None |
| Order history, items, delivery address snapshot | `orders`, `order_items`, `order_addresses` | Never deleted by the application; snapshots keep the delivery address text/coordinates and prices permanently | None |
| Payments, transactions, refunds | `payments`, `payment_transactions`, `refunds` | Never deleted; `payment_transactions` keep gateway responses (JSON text) and failure reasons | None |
| Webhook events | `payment_webhook_events` | Never deleted: only a payload **hash** is stored (not the raw body), plus status | None |
| Carts / cart items | `carts`, `cart_items` | Active and checked-out carts are kept; cart items are deleted with the cart or when a product is hard-deleted | None |
| Checkout sessions | `checkout_sessions` | Kept (status `PENDING/COMPLETED/REFUNDED/REFUND_FAILED`); stale `PENDING` rows are never cleaned | None |
| Reservations | `inventory_reservations(+items)` | Expired/released rows are kept; `ACTIVE` overdue rows are expired by the sweep (≤ 500 per 120 s tick) | 30-minute window (code constant) |
| Stock ledger | `stock_movements` | Append-only, kept; only deleted together with a product that has **no** order/quote/supplier/packaging history | None |
| Customer notes (admin-written) | `customer_notes` | Kept; cascade-deleted with the user | None |
| Audit records | `admin_action_logs` | Kept indefinitely; no API reads them in general ([FR-OPS-3](../01-requirements/FUNCTIONAL_REQUIREMENTS.md)) | None |
| Push tokens | `push_tokens` | Re-assigned when a device signs in as another user; removed on logout (`/push-tokens/unregister`) or when Expo says the device is unregistered | None |
| Wishlist | `wishlist_items` | Customer removes; cascade with user/product | None |
| Bulk requests, quotes (all versions) | `bulk_order_requests`, `quotes`, `quote_versions`, `quote_items` | Kept as commercial history | None |
| Images | Cloudinary | The database stores only the delivery URL (`secure_url`); the `public_id` is **not stored** and the code never calls Cloudinary's delete/destroy API (verified by search), so replaced or deleted images remain in Cloudinary indefinitely | None |
| Application logs | stdout; compose rotates (`json-file`, 5 × 10 MB per service) | Rotation by Docker only; no central log store configured | None |
| Database backups | `./backups/*.dump` on the VPS | `pg_dump -Fc` every `BACKUP_INTERVAL_SECONDS` (default 86 400 s); files older than `BACKUP_RETENTION_DAYS` (default 14) are deleted; same disk as the database unless copied off | 14 days (config default) |

## Gaps and open questions

1. **Right-to-erasure / account deletion** is not implementable through the product today; deleting a customer with orders would violate `RESTRICT` constraints and no anonymisation routine exists. Owner decision needed on how to satisfy Indian data-protection obligations ([PRIVACY](../08-security/PRIVACY.md)).
2. Unbounded growth: `payment_webhook_events`, `stock_movements`, `admin_action_logs`, `checkout_sessions` have no archival or partitioning.
3. Order and address snapshots hold personal data permanently by design.
4. Backup retention is only defined for the compose stack; the EKS databases' backup settings are outside the repository.
5. Seeded demo/starter data (home slides, four promotions) lives in production unless removed ([MIGRATIONS](MIGRATIONS.md)).
