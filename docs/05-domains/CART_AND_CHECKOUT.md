# Cart and Checkout

> **Status:** Verified (code + backend tests). **Last verified:** 2026-10-14. UI behaviour in `mobile/app/cart`, `mobile/app/checkout` is **Unverified** (no frontend tests).
> **Source files:** [`services/cart.py`](../../backend/app/services/cart.py), [`services/order.py`](../../backend/app/services/order.py) (`checkout`, `_plan_checkout`, `quote_checkout`), [`checkout_session.py`](../../backend/app/services/checkout_session.py), [`promotion.py`](../../backend/app/services/promotion.py), [`delivery.py`](../../backend/app/services/delivery.py), [`bazaar.py`](../../backend/app/services/bazaar.py); routers `cart.py`, `payments.py`, `bazaar.py`; mobile `src/features/cart`, `src/features/checkout`, `app/cart`, `app/checkout`.
> **Tests:** [`test_phase_13_cart_orders.py`](../../backend/tests/test_phase_13_cart_orders.py), [`test_online_checkout.py`](../../backend/tests/test_online_checkout.py), [`test_money_integrity.py`](../../backend/tests/test_money_integrity.py), [`test_promotion_flow.py`](../../backend/tests/test_promotion_flow.py), [`test_delivery_fee.py`](../../backend/tests/test_delivery_fee.py). Sequence diagrams: [DATA_FLOW](../02-architecture/DATA_FLOW.md) §2–§3.

## Cart

| Rule | Detail | Evidence |
|---|---|---|
| One ACTIVE cart per user | Partial unique index `uq_carts_user_active`; `_get_or_create_active_cart` self-heals the creation race (`IntegrityError` → re-read) | `cart.py`, schema |
| Status | `ACTIVE`, `CHECKED_OUT`, `ABANDONED`. **Nothing ever sets `ABANDONED`** (only `OrderService.checkout` rejects it) — the status is unused | grep of `app/` |
| Reads never create | `GET /cart` returns an empty cart (`id: null`) without inserting | `get_cart` |
| Add item | Variant and product must be `ACTIVE`; quantity is **added** to an existing line; **stock is not checked here** — only at reservation (checkout) | `add_item`, `_validate_variant_purchasable` |
| Items | Unique `(cart_id, variant_id)`, `quantity > 0` (NUMERIC(12,3)); line total `qty × current price` quantized ROUND_HALF_UP | schema, `_line_total` |
| Locking | Mutations lock the user's latest cart row (`FOR UPDATE`) | `_get_locked_active_cart` |
| Clear / remove | `DELETE /cart/items`, `DELETE /cart/items/{id}` | router |
| Price | Current price rule from [CATALOG](CATALOG.md); a missing price is a 409 at checkout | `pricing.py` |

## Pricing a basket (shared by preview, quote and checkout)

`OrderService._plan_checkout` is the single pricing routine used by `checkout` (persists) and `quote_checkout` (read-only, rolls back its locks). Steps and rules:

1. Lock the cart's variants in id order; every variant and product must be `ACTIVE` ("no longer available" → 409); every variant needs a current price (409 otherwise); all prices must share one currency.
2. The address must belong to the user (otherwise **404** "Address not found." — existence is not disclosed).
3. Line totals and `subtotal` (ROUND_HALF_UP to cents). Order lines snapshot product name, variant name, SKU, unit, quantity, unit price, total.
4. **Promotion** ([PROMOTIONS](PROMOTIONS.md)): the client's `promo_code` is only a lookup key; the discount is computed on the server. The usage limit is re-checked under a promotion row lock; if the last use vanished an *automatic* promo drops out silently, whereas an explicit invalid code raises 422 with the reason.
5. **Delivery fee** ([DELIVERY](DELIVERY.md)): `calculate_delivery_fee(distinct_product_count, address lat/lon, origin=packing point)`.
6. `total = (subtotal − discount) + delivery_fee`.
7. If `expected_total` is supplied (pay-first completion) and the recomputed total differs, the checkout is refused **before** creating anything and the caller refunds.

`POST /cart/evaluate-promo` previews the promotion on the user's ACTIVE cart with the same engine. `GET /bazaar/delivery-quote?address_id=` returns the fee quote (including "N more products for free delivery"). Neither writes anything.

## Placing an order

### Cash on Delivery
`POST /cart/checkout {address_id, promo_code?}` → order `PENDING`, reservation `ACTIVE` (30 min), cart `CHECKED_OUT` (one commit). Then `POST /payments {order_id, payment_method: "COD"}` confirms (commits the reservation; order `CONFIRMED`; payment `PENDING` until delivery). The app performs both calls back-to-back ([`useCheckout.ts`](../../mobile/src/features/checkout/useCheckout.ts)). **If the second call never happens** (network loss, app killed) the order sits `PENDING` with stock held until the sweep expires it (≤ ~32 min).

### Online (pay-first)
`POST /payments/online/start` → Razorpay order + `checkout_sessions` row (no order, no reservation, cart untouched; stock is only *checked* for availability) → app pays → `/confirm` or `/verify` (or the webhook) completes. Rules:

- Re-opening the sheet for an unchanged basket (same cart, address, promo, amount) **reuses** the same pending session and Razorpay order.
- Completion asks Razorpay (not the client) whether the order was captured; checks the amount equals the session amount; then runs `OrderService.checkout(expected_total=…)`.
- If the order cannot be placed (insufficient stock, basket changed, promo exhausted, address deleted…) → automatic Razorpay refund → session `REFUNDED` (or `REFUND_FAILED`, logged `PAYMENT_RECONCILIATION`, needs a human) and a 409 "Your payment has been refunded."
- Completing twice returns the same order.

### Retry and idempotency

| Situation | Behaviour |
|---|---|
| `POST /cart/checkout` repeated for a `CHECKED_OUT` cart | Returns the **existing order** (`created=False`) — see PAY-001 for the pay-first consequence |
| `POST /payments` repeated for an order | Returns the existing payment, no second gateway call |
| `/payments/online/start` repeated | Same session/Razorpay order (unchanged basket) |
| Two concurrent checkouts of one cart | The cart row lock serialises; the second sees `CHECKED_OUT` and returns the same order; `uq_orders_cart_id` is the backstop |

## Failure scenarios

| Scenario | Result |
|---|---|
| Not enough stock for any line | 409 naming the product; nothing written (reservation is all-or-nothing) |
| Promo code unknown / inactive / not eligible / used up / minimum not met | 422 (explicit code) with a specific message; automatic promos never error |
| Price changed between quote and payment | Pay-first: payment refunded automatically; COD: order uses the price at checkout time |
| Razorpay unavailable at `start` | 502 gateway error; no session (a successful order creation moves no money, and its failure is reported as a definite failure) |
| Online payments not configured | 503 `ONLINE_PAYMENTS_NOT_CONFIGURED` → offer COD |
| Reservation expired before COD confirmation | `POST /payments` rolls back with 409; the order will be/was `EXPIRED` |

## Known gaps

- **PAY-001** (open): a pay-first payment can be attached to an unrelated existing order when the latest cart was already ordered ([DEFECT_LOG](../testing/DEFECT_LOG.md)).
- Bulk-converted orders carry `delivery_fee = 0` and no promotion ([BULK_ORDERS](BULK_ORDERS.md)).
- **The harvest/delivery slot picker is illustrative.** `HarvestSlotSelector` keeps the day/slot in local component state (the source comment says "illustrative"); it is shown in the summary but **never sent to the backend** — no slot column, field or endpoint exists. `FEATURES.md` lists it as a checkout feature; it does not affect any order.
- Stale `PENDING` checkout sessions are never cleaned up ([DATA_RETENTION](../04-database/DATA_RETENTION.md)).
- The mobile app mirrors `FREE_DELIVERY_MIN_ITEMS` (10) and the Bazaar+ threshold (6) as hard-coded fallbacks in `BazaarSection.tsx`/`bazaar/index.tsx`; the backend values win when the API answers.
