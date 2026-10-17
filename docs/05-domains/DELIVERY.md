# Delivery Pricing, the Bazaar Offer and Delivery Operations

> **Status:** Verified (pricing rule: code + [`test_delivery_fee.py`](../../backend/tests/test_delivery_fee.py)); fulfilment/delivery operations: see [ORDERS](ORDERS.md). Bazaar+ status endpoint and the live routing providers: **Unverified** (no tests for `/bazaar`; the routing APIs are mocked/fallback-tested only). **Last verified:** 2026-10-14.
> **Source files:** [`services/delivery.py`](../../backend/app/services/delivery.py), [`bazaar.py`](../../backend/app/services/bazaar.py), [`core/config.py`](../../backend/app/core/config.py) (settings), [`inventory.py`](../../backend/app/services/inventory.py) (`set_packing_point`), [`order.py`](../../backend/app/services/order.py) (`_plan_checkout`), [`api/v1/bazaar.py`](../../backend/app/api/v1/bazaar.py); mobile `src/utils/delivery.ts`, `src/components/cart/DeliverySummaryCard.tsx`, `app/bazaar/index.tsx`, `src/components/home/BazaarSection.tsx`; Admin `app/(admin)/settings`.

## The fee rule

```
distinct products in the basket  >=  FREE_DELIVERY_MIN_ITEMS (15)   ->  fee = 0   ("a Bazaar")
otherwise  fee = ceil( DELIVERY_BASE_FEE + DELIVERY_PER_KM x charged_km )
             charged_km = min(road_km, DELIVERY_MAX_CHARGED_KM)
```

Defaults (all environment-configurable, [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md)): `FREE_DELIVERY_MIN_ITEMS=15`, **`DELIVERY_BASE_FEE=40`** (changed from 20 on 2026-10-14, uncommitted — see warning below), `DELIVERY_PER_KM=10`, `DELIVERY_MAX_CHARGED_KM=30`. The result is rounded **up** to a whole rupee (`ROUND_CEILING`). Maximum fee at defaults: 40 + 10 × 30 = **Rs 340**.

- **"Items" are distinct products** (`product_id`), not units and not variants: the same product in two sizes counts once (`distinct_product_count`).
- **Order of use:** one pure function, `calculate_delivery_fee`, is called by the cart quote (`GET /bazaar/delivery-quote`) and by checkout, so the two cannot drift.
- **Origin:** the admin-chosen **packing point** (active location with `is_packing_point`, with coordinates); fallback `PACKING_POINT_LATITUDE/LONGITUDE`; with neither, or with no GPS on the address, only the base fee applies and the quote is flagged `distance_estimated = true`.
- **Distance:** driving km via Google Distance Matrix when `GOOGLE_MAPS_API_KEY` is set, otherwise OSRM (`OSRM_BASE_URL`, default the **public demo server**, which the config comment calls "testing only"). Calls time out after `ROUTING_TIMEOUT_SECONDS` (3 s). Results are cached per coordinate pair rounded to 4 decimals (~11 m, `lru_cache` 2048 entries, per process). **Any** routing failure falls back to straight-line (haversine) × `DELIVERY_ROAD_FACTOR` (1.4), logged as `DELIVERY_ROUTING_FAILED`, so checkout never fails because routing is down — it can silently overcharge or undercharge.
- **Free-delivery progress:** `items_to_free_delivery = max(0, 15 − distinct products)`.
- **Bulk-converted orders:** orders created by bulk conversion are created with `delivery_fee = 0` and are not priced by this function ([BULK_ORDERS](BULK_ORDERS.md)).

> **Warning — test suite is red because of the 2026-10-14 base-fee change.** Seven existing tests hard-code the previous default of Rs 20 (they do not pin the fee): `test_online_checkout.py` (4), `test_phase_13_cart_orders.py::test_22/test_26`, `test_promotion_flow.py::test_percentage_code_previews_and_is_charged_at_checkout`. They fail by exactly the Rs 20 difference and pass when `DELIVERY_BASE_FEE=20` is set (verified 2026-10-14). See [AI_STATUS](../00-overview/AI_STATUS.md).
>
> **Which value is live?** `docker-compose.prod.yml` does **not** pass any `DELIVERY_*`, routing, packing-point or `BAZAAR_*` variable to the backend container (its `x-backend-env` block lists only app, database, Firebase, Razorpay, CORS and Cloudinary settings), even though [`.env.production.example`](../../.env.production.example) lists them. In the compose deployment the **code defaults** therefore always apply, regardless of `.env.production`. In Kubernetes they would come from `gawachabazaar-backend-secret` (contents not in the repository); on Render from the service's environment (not visible).

## Bazaar+

- `GET /bazaar/status` (CUSTOMER): counts the customer's orders **placed since the start of the current month** (`BAZAAR_TIMEZONE`, default `Asia/Kolkata`) whose status is not cancelled/expired and that contain ≥ `FREE_DELIVERY_MIN_ITEMS` distinct products; `eligible_for_bazaar_plus = count ≥ BAZAAR_PLUS_ORDERS_REQUIRED` (6). It also returns the live cart's distinct-product count.
- **No benefit is implemented.** The backend has no pricing or access difference for an eligible customer. The app's Bazaar screen lists five *upcoming* benefits (free delivery on every order, priority slots, members-only prices, early access, monthly surprise) — marketing copy only.
- The monthly window resets by calendar month, not rolling 30 days (code comment in `bazaar.py`).

## Packing point administration

Admin → Settings (ADMIN): `POST /inventory/locations/{id}/packing-point` makes one active, geo-located warehouse the origin (the partial unique index guarantees a single packing point); a location's coordinates are set via `PATCH /inventory/locations/{id}`. If none is chosen the env fallback applies.

## Delivery operations

Assignment, out-for-delivery and delivered transitions, COD cash collection, partner visibility: [ORDERS](ORDERS.md) and [DATA_FLOW](../02-architecture/DATA_FLOW.md) §5. There is no delivery-slot concept in the backend; the checkout "harvest slot" picker is local UI state ([CART_AND_CHECKOUT](CART_AND_CHECKOUT.md)).

## Failure scenarios and gaps

| Scenario | Behaviour |
|---|---|
| Routing provider down/slow | Haversine × 1.4 fallback (logged); checkout continues |
| Address without GPS | Base fee only, `distance_estimated = true` |
| Packing point deleted/deactivated | Falls back to env origin, else base fee only |
| Extreme/bad coordinates | Distance capped at 30 km for pricing |
| Client shows a different fee than charged | Not possible by design (same function); the mobile app hard-codes 15 and 6 only as fallbacks before the API answers |

Gaps: public OSRM demo server in the default configuration; fee changes require a deploy or env change (no admin UI for fee parameters — Admin Settings only sets the packing point); no per-zone pricing, surge, minimum-order rule or delivery-time estimate.
