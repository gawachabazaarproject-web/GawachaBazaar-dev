# Privacy and Personal Data

> **Status:** Partially verified — a data inventory and handling review from source; **not legal advice**, and the repository contains **no privacy policy, consent flow, data-processing records or breach procedure**. **Last verified:** 2026-10-14. Related: [DATA_RETENTION](../04-database/DATA_RETENTION.md), [SECURITY](SECURITY.md), [SECRETS_MANAGEMENT](SECRETS_MANAGEMENT.md).

## 1. Personal data inventory

| Data | Subject | Stored in | Source | Visible to |
|---|---|---|---|---|
| Name, email, phone (E.164 `+91…`), Firebase UID, account status | Customers, staff | `users` | Firebase token claims, sign-up form, admin entry | The user; staff per role (phone masked unless `customers.view_sensitive`, except the PRIV-1 paths below) |
| Delivery addresses with GPS coordinates | Customers | `addresses` (editable); **permanent snapshot** in `order_addresses` | Address form, device location (with permission) | The user; staff with `orders.read` (order detail), `customers.view` (addresses), the assigned delivery partner |
| Orders, items, totals, promo used, cancellation reasons | Customers | `orders`, `order_items`, `promotion_redemptions` | Checkout | The user; staff by role |
| Payment records (method, amount, gateway order/payment ids, gateway response JSON) | Customers | `payments`, `payment_transactions` (`gateway_response` text) | Razorpay | ADMIN (payments pages) |
| Webhook payload **hash** only | – | `payment_webhook_events` | Razorpay | – (no raw body stored) |
| Customer notes written by admins | Customers | `customer_notes` | Admin | ADMIN |
| Push token + platform | Customers | `push_tokens` | App | Backend only |
| Wishlist, cart | Customers | `wishlist_items`, `carts`, `cart_items` | App | The user |
| Business details for wholesale (profile) | Business customers | `bulk_customer_profiles` | App | Staff with bulk access (ADMIN/OPERATIONS) |
| Staff identity and actions | Staff | `users`, `admin_action_logs` (audit `reason` may include an email, e.g. `staff.create`) | Admin | ADMIN (no reader exists yet) |
| Device location | Customers | **not stored** — used client-side to prefill the address form; the backend stores only the address the user saves | `expo-location` | – |
| Voice search | Customers | **not stored** — processed on the device/OS speech service (`expo-speech-recognition`) | app | – |

Credentials (passwords) are held only by **Firebase**; the backend never receives them, except during a legacy account migration when the old password is sent once to `/auth/legacy-migrate` over TLS and then discarded (the legacy hash is erased).

## 2. Third parties that receive personal data

| Recipient | Data | Notes |
|---|---|---|
| Google Firebase Authentication | email, phone, name, password hash (Google-managed), sign-in provider, OTP SMS handled by Firebase | [THIRD_PARTY_SERVICES](../11-integrations/THIRD_PARTY_SERVICES.md) |
| Razorpay | amount, order reference, customer name/email/phone passed to Checkout (`prefill` in `OnlineCheckoutResponse`: `customer_name`, `customer_email`, `customer_phone`) | Card/UPI details are entered in Razorpay's UI and never reach the backend |
| Expo push service (and Google FCM) | push token, notification text containing the order number | – |
| Google Distance Matrix or the public OSRM server | **delivery address coordinates** and the packing-point coordinates are sent for pricing. The default configuration uses the **public OSRM demo server**, which the config calls "testing only" | Choose a private router/Google for production privacy |
| Cloudinary | product/ad images only (no personal data intended) | – |
| Hosting providers (Render/Contabo/AWS/Vercel) | everything the backend stores | not inspected |

## 3. Controls in the code

- Phone numbers are masked (`+91******7890`) in the customers module unless the caller has `customers.view_sensitive` (ADMIN); `SUPPORT` is read-only with masked phone.
- **Gap PRIV-1:** staff order detail (`orders.read` → OPERATIONS, HUB_STAFF, ADMIN) returns the customer's **full phone and email**, and order search matches phone numbers, so the masking is bypassable by two roles ([ORDERS](../05-domains/ORDERS.md)). Delivery partners receive the order content they need through `/fulfillments/{id}/order`.
- Customers can see only their own data (404 for others).
- Logs avoid personal data: request logs have method/path/status/duration only; domain log lines use ids; tokens are redacted from WebSocket log lines. Not exhaustively audited.
- Audit rows reference people by `users.id`; some `reason` strings embed an email.
- Backups (`pg_dump`) contain all personal data and sit on the same disk unless copied ([BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md)); backup encryption is not configured.

## 4. Data-subject rights and retention (gaps)

- **No account-deletion or anonymisation feature** for customers; users with orders cannot be hard-deleted (foreign keys `RESTRICT`). The admin "suspend" status is the closest action. A user can delete their addresses, wishlist and (via logout) their push token.
- **No data export** for a customer; no consent records; no cookie/consent handling for the Admin or website (the website sets no cookies in code — not verified at runtime).
- Retention periods are undefined except the 14-day backup default ([DATA_RETENTION](../04-database/DATA_RETENTION.md)). Order and address snapshots keep personal data indefinitely.
- The mobile app asks for location, microphone and notification permissions with purpose strings (`app.json`); there is no in-app privacy notice or link in the code I inspected.
- The in-app Support screen shows placeholder contact details (`support@gawachabazaar.example`, `+91 12345 67890`), so a customer cannot actually reach support for privacy requests until real details are set.

## 5. Breach and incident handling

No breach-notification procedure, owner or contact exists in the repository ([INCIDENT_RESPONSE](../09-deployment-operations/INCIDENT_RESPONSE.md)).

## 6. Questions for the owner

1. Which entity is the data controller and which privacy policy applies (India's DPDP Act obligations are for the owner to determine — not assessed here)?
2. How are deletion/export requests to be handled given the `RESTRICT` constraints?
3. Should staff phone visibility be aligned (fix PRIV-1) and should reads of customer data be logged?
4. Should delivery distance use a private routing service instead of the public OSRM demo server?
5. Where are backups stored and who can read them?
