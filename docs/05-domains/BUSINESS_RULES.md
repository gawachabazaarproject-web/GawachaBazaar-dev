# Business Rules (index)

> **Status:** Verified against source on 2026-10-14. This is the **single index** of the rules that the code enforces; each row names the file that enforces it and the domain document with the detail. Rules that are only in the UI, only in copy, or only in someone's intention are listed separately at the end.
> If you change a rule here, change the code **and** the row, and run the tests named in the domain document.

## Ordering and pricing

| # | Rule | Enforced in | Detail |
|---|---|---|---|
| BR-1 | Prices, fees, discounts and totals are computed only on the server; clients send ids and a promo code, never amounts | `services/order.py` `_plan_checkout` | [CART_AND_CHECKOUT](CART_AND_CHECKOUT.md) |
| BR-2 | The current price of a variant = active row with `valid_from <= now` and (`valid_to` null or `>= now`); newest `valid_from` wins, then highest id | `services/pricing.py` | [CATALOG](CATALOG.md) |
| BR-3 | Money is `NUMERIC(12,2)`; line totals and discounts are rounded half-up to cents; delivery fees round **up** to whole rupees | cart/order/promotion services, `delivery.py` | – |
| BR-4 | Only `ACTIVE` products and variants can be added to a cart or ordered | `cart.py`, `order.py` | [CART_AND_CHECKOUT](CART_AND_CHECKOUT.md) |
| BR-5 | An order stores a snapshot of names, SKUs, units, prices and the delivery address | `order.py`, `order_item`, `order_address` | [ORDERS](ORDERS.md) |
| BR-6 | Delivery is free at ≥ 15 **distinct products**; otherwise `ceil(40 + 10 × min(road km, 30))` (defaults, env-configurable) | `delivery.py` | [DELIVERY](DELIVERY.md) |
| BR-7 | The same function prices the quote and the checkout | `delivery.py` | [DELIVERY](DELIVERY.md) |
| BR-8 | A customer can only order to an address they own (otherwise 404) | `order.py` | – |
| BR-9 | Promotions: one best automatic promotion or the given code; limits re-checked under a lock; redemption reversed on cancel | `promotion.py` | [PROMOTIONS](PROMOTIONS.md) |
| BR-10 | Bulk quotes: only a sent version can be accepted; acceptance after `valid_until` expires it; conversion needs an address and an accepted version | `bulk_order.py` | [BULK_ORDERS](BULK_ORDERS.md) |

## Stock

| # | Rule | Enforced in | Detail |
|---|---|---|---|
| BR-11 | Stock changes only through ledger movements; quantity can never go negative; `0 ≤ reserved ≤ quantity` | `inventory.py`, DB `CHECK` | [INVENTORY](INVENTORY.md) |
| BR-12 | Checkout reserves stock FIFO across lots (and across sizes of the same product pool); it is all-or-nothing | `inventory_reservation.py`, `stock_pool.py` | [INVENTORY](INVENTORY.md) |
| BR-13 | A reservation lasts 30 minutes; expiry marks a still-pending order `EXPIRED`; a late payment never resurrects it | `inventory_reservation.py`, `payment.py` | [INVENTORY](INVENTORY.md), [PAYMENTS](PAYMENTS.md) |
| BR-14 | Physical stock is consumed only when delivery is confirmed | `fulfillment.py` | [ORDERS](ORDERS.md) |
| BR-15 | Admins cannot remove stock that is reserved for orders | `inventory.py` `remove_stock` | [INVENTORY](INVENTORY.md) |
| BR-16 | A product with any order/quote/supplier/packaging history cannot be deleted (archive it); a category with products or children cannot be deleted | `catalog.py` | [CATALOG](CATALOG.md) |
| BR-17 | Reserve levels only raise alerts; they do not block sales | `stock_levels.py` | [INVENTORY](INVENTORY.md) |

## Orders, payments, refunds

| # | Rule | Enforced in | Detail |
|---|---|---|---|
| BR-18 | Order transitions: `PENDING→CONFIRMED/EXPIRED/CANCELLED`, `CONFIRMED→COMPLETED/CANCELLED`; others terminal | `order_state.py` | [ORDERS](ORDERS.md) |
| BR-19 | Cancel is allowed any time before delivery; cancelling releases stock reservation, reverses the promotion, and may create a refund request | `order.py` | [ORDERS](ORDERS.md) |
| BR-20 | COD confirms the order immediately (inside the reservation window); the cash is recorded when delivery is confirmed | `payment.py`, `fulfillment.py` | [PAYMENTS](PAYMENTS.md) |
| BR-21 | Online orders are created only after Razorpay confirms the capture; if they cannot be placed the payment is refunded automatically | `checkout_session.py` | [PAYMENTS](PAYMENTS.md) |
| BR-22 | One payment, one refund, one fulfilment, one reservation per order | DB unique constraints | [DATABASE_SCHEMA](../04-database/DATABASE_SCHEMA.md) |
| BR-23 | Payment status only changes via the state machine, from our own gateway call or an authenticated webhook/verify; late illegal events are ignored | `payment_state.py`, `payment.py` | [PAYMENTS](PAYMENTS.md), [WEBHOOKS](../03-api/WEBHOOKS.md) |
| BR-24 | Webhook amount and currency must match the payment; duplicates are no-ops | `payment.py` | [WEBHOOKS](../03-api/WEBHOOKS.md) |
| BR-25 | Refunds need ADMIN approval and are full-amount only; only cancelled orders with a `PAID` online payment create one | `refund.py` | [REFUNDS](REFUNDS.md) |
| BR-26 | Retry only from `FAILED`/`EXPIRED`; a `PROCESSING` payment must be verified first | `payment.py`, `payment_state.py` | [PAYMENTS](PAYMENTS.md) |
| BR-27 | Fulfilment moves exactly one step forward; assignment needs an active `DELIVERY_PARTNER`; only the assigned partner (or ADMIN) can deliver | `fulfillment*.py` | [ORDERS](ORDERS.md) |

## Accounts and access

| # | Rule | Enforced in | Detail |
|---|---|---|---|
| BR-28 | A user must be `ACTIVE`; email/password users must have a verified email | `services/auth.py` | [AUTHENTICATION](AUTHENTICATION.md) |
| BR-29 | A verified email or phone may link an existing, un-linked user; a conflicting identity returns 409; nothing is auto-merged | `services/auth.py` | [AUTHENTICATION](AUTHENTICATION.md) |
| BR-30 | Roles are read live; permissions are static code; customers get 404 for other customers' objects | `dependencies/auth.py`, `permissions.py` | [USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md) |
| BR-31 | An admin cannot deactivate or reset the password of themself; the last active admin is protected | `staff.py`, `customer.py` | [ADMIN_OPERATIONS](ADMIN_OPERATIONS.md) |
| BR-32 | Customer phone numbers are masked except for `customers.view_sensitive` (with the PRIV-1 leak in order detail) | `customer.py`, `order.py` | [ORDERS](ORDERS.md), [PRIVACY](../08-security/PRIVACY.md) |
| BR-33 | Every admin mutation is recorded (47 action names); records are not exposed generally | `admin_audit.py` | [ADMIN_OPERATIONS](ADMIN_OPERATIONS.md) |

## Rules that exist only in the UI or copy (the backend does **not** enforce them)

- Harvest/delivery slot choice at checkout (local state, never sent).
- Ad images must be 12:5 / 1200 × 500 px (Admin UI check only).
- Bazaar+ "upcoming benefits" (free delivery on every order, priority slots, members-only prices, early access, monthly surprise).
- Customer-support contact details in the app are placeholders (`support@gawachabazaar.example`, `+91 12345 67890`).

## Rules still undecided

Refund policy beyond "full amount, admin approval"; cancellation windows; minimum order value or delivery-area limits; wholesale pricing beyond manual quotes; what Bazaar+ should give ([PRD](../01-requirements/PRD.md) open questions).
