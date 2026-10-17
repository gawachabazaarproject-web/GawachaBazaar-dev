# Promotions and Offers

> **Status:** Verified (code + [`test_promotion_flow.py`](../../backend/tests/test_promotion_flow.py)). **Last verified:** 2026-10-14. One test in that file currently fails because of the base delivery-fee change, not because of promotion logic ([DELIVERY](DELIVERY.md) warning).
> **Source files:** [`services/promotion.py`](../../backend/app/services/promotion.py), [`promotion_state.py`](../../backend/app/services/promotion_state.py), [`offers.py`](../../backend/app/services/offers.py), [`order.py`](../../backend/app/services/order.py) (`_plan_checkout`, cancel), routers `promotions.py`, `cart.py` (`/cart/evaluate-promo`), `offers.py`; models `promotion`, `promotion_target`, `promotion_eligible_customer`, `promotion_redemption`; Admin `app/(admin)/promotions`.

## Model (`promotions`)

| Field(s) | Rule |
|---|---|
| `code` | Optional, unique (case-insensitive lookup: codes are upper-cased). **No code = an *automatic* promotion** |
| `discount_type` / `discount_value` | `PERCENTAGE` (value ≤ 100) or `FIXED_AMOUNT`; `discount_value > 0` |
| `max_discount_amount`, `min_order_value`, `min_quantity` | Optional caps/thresholds |
| `customer_scope` | `ALL`, `NEW_CUSTOMERS` (no prior CONFIRMED/COMPLETED order), `EXISTING_CUSTOMERS` (has one), `SPECIFIC` (listed in `promotion_eligible_customers`) |
| `status` (admin) | `DRAFT`, `ACTIVE`, `PAUSED`, `DISABLED`; `stacking_policy = SINGLE_BEST` (the only value) |
| `starts_at` / `ends_at` | `ends_at > starts_at` when set |
| `usage_limit_total`, `usage_limit_per_customer`, `redemption_count` | Limits (> 0 when set); counters maintained by redemption/reversal |
| `priority` | Lower first among automatic promotions |
| `show_in_carousel`, `image_url`, `customer_title/description` | Offers carousel content |
| `promotion_targets` | Optional `PRODUCT` or `CATEGORY` targets (generic `target_type`+`target_id`, no foreign key) |

**Effective status** is computed, never stored: an admin-`ACTIVE` promotion is `SCHEDULED` before `starts_at`, `ACTIVE` inside the window, `EXPIRED` after `ends_at`; `DRAFT/PAUSED/DISABLED` stay as set regardless of dates (`promotion_state.compute_effective_status`).

## Evaluation (`evaluate_for_cart`, same engine for preview and checkout)

1. **With a code:** unknown → "doesn't exist"; not currently redeemable → "not currently active"; customer not eligible; usage limit reached; no qualifying discount → "Minimum order of X required" or "doesn't qualify". Each returns an error result (HTTP 422 at checkout, a message at preview).
2. **Without a code:** the single best **automatic** promotion (`code IS NULL`, `ACTIVE`) by largest discount; never an error when none qualifies.
3. **Discount:** applicable lines = lines matching a target product/category (all lines if no targets); `min_order_value` is checked against the **whole** cart, `min_quantity` against the applicable lines; percentage on the applicable subtotal or the fixed amount, capped at the applicable subtotal and then `max_discount_amount`; quantized ROUND_HALF_UP.
4. At checkout the usage limit is **re-checked under a row lock** (`FOR UPDATE`); if the last use was taken meanwhile an automatic promo drops out, an explicit code fails.

## Redemption and reversal

`record_redemption` (inside the checkout transaction) locks the promotion, re-validates global and per-customer limits, increments `redemption_count` and inserts an `APPLIED` redemption (unique per order). **Cancellation** marks it `REVERSED` and decrements the counter, freeing the limit; the order's own discount amount is never changed.

## Admin management

`/promotions` (perms `promotions.read|create|update|manage_status`, ADMIN only): list/dashboard/detail, create/update, activate/pause/disable, duplicate, image upload, redemption list. Audited: `promotion.create|update|duplicate|image`, and every status change is recorded as `promotion.active`, `promotion.paused` or `promotion.disabled` (the router builds the action name from the new status).

## Offers carousel

`GET /offers` (public): up to 10 promotions that are `ACTIVE`, `show_in_carousel`, not `SPECIFIC`-scoped, **currently redeemable** and with usage left — the same rule checkout applies, so the carousel cannot advertise something checkout would refuse. Ordered by `priority`. Four starter promotions (`WELCOME50`, `BAZAAR100`, `FRESH10`, `WEEKEND15`) are inserted by migration `e4a7c1b9d036` when an admin exists ([MIGRATIONS](../04-database/MIGRATIONS.md)).

## Concurrency and failure scenarios

| Scenario | Behaviour |
|---|---|
| Two customers redeem the last use | Promotion row lock serialises; the loser's explicit code fails (422/409), an automatic promo silently drops |
| Order cancelled | Redemption reversed, limit freed |
| Promotion deleted | There is no delete; `DISABLED` instead (FK `RESTRICT` from orders) |
| Target product/category deleted | Target rows dangle (no FK); a promotion whose targets all vanished yields no discount |
| Customer uses an automatic promo and a code | Only one promotion applies (`SINGLE_BEST`/code takes precedence when given) |

## Gaps

- No tests for the offers carousel UI or for promo images; stacking beyond `SINGLE_BEST` is not modelled.
- `NEW_CUSTOMERS` is defined by *confirmed/completed* orders; a customer whose only order is pending still counts as new.
- Promotions apply to cart checkout only; bulk-converted orders carry no promotion.
