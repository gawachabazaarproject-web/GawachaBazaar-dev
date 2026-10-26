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
- **Distance:** driving metres from OSRM (`ROUTING_PROVIDER=osrm`, `OSRM_BASE_URL`; coordinates sent as `lon,lat`, `overview=false`), 3 s timeout (`ROUTING_TIMEOUT_SECONDS`). Code: `services/routing/{base,osrm,cache,service}.py`; pricing is separate in `services/delivery_pricing.py`. **No straight-line fallback (changed 2026-10-26):** if the router is down/slow/malformed the quote and checkout fail with **503**; "no route" or an out-of-range stored coordinate is a 422 (`DELIVERY_UNAVAILABLE`). Google Distance Matrix support and `DELIVERY_ROAD_FACTOR` were removed.
- **Route cache (hardened 2026-10-26):** key `route:v1:osrm:driving:{sha1(OSRM_BASE_URL)[:8]}:{olat:.4f},{olng:.4f}:{dlat:.4f},{dlng:.4f}` (~11 m cells; the origin coordinates identify the warehouse, the endpoint hash isolates public vs self-hosted OSRM, `v1` is the key-format version). The value is only `{distance_meters, distance_km, duration_seconds, provider}` - never fees, which are always recomputed from the current rules. Redis if `REDIS_URL` is set, else an in-process TTL dict. TTL `ROUTE_CACHE_TTL_SECONDS` = 7 days (verified on real Redis: `TTL` = 604800 on the key); failures are never cached. **Single-flight:** an in-process per-key lock plus a Redis `SET lock:<key> NX EX 15` lock, so N identical concurrent requests - also across workers/replicas - make **one** OSRM call (verified: 10 simultaneous -> 1 call). **Redis policy: non-critical.** On any Redis error the worker opens a 30 s circuit breaker, logs `route_cache redis_unavailable ...` at WARNING and serves from its own in-process cache until Redis returns; delivery keeps working and fees stay correct (the cache holds only deterministic route distances). In production an empty `REDIS_URL` logs a startup warning. If you need Redis to be mandatory, fail startup on an empty `REDIS_URL` - not done, by choice.
- **No router call under row locks (DEL-1, fixed):** `OrderService.checkout` / `quote_checkout` resolve the route (`resolve_route`, plain reads + network) *before* the cart/variant `FOR UPDATE` locks; `_plan_checkout` only prices it (`price_delivery`, pure) and re-checks that the address pin and packing point still match the route that was resolved - otherwise 409 "try again". Tested with a separate-connection `FOR UPDATE NOWAIT` probe inside the router call (fails if the old order of operations is restored). Pay-first (DEL-7, fixed): `CheckoutSessionService.complete`/`verify`/`complete_from_webhook` call `_route_before_lock` (plain read + router) first, then lock the checkout-session row and hand the result to `checkout(route_outcome=...)`; `_plan_checkout` re-validates it. The session lock is still held across the Razorpay status call - that is by design (it serialises finalisation) and is not a router wait. Caveat: `complete_from_webhook` is entered by the payment webhook handler, which already inserted its dedup row in the same transaction; that row is unrelated to carts/variants/sessions.
- **Unroutable pins:** OSRM answers "Ok" for points far from any road (swapped lat/lng returned `distance: 0` on the live server). The provider rejects a snap distance over 2000 m (`MAX_SNAP_METERS`) as "no route" -> 422.
- **Addresses without a map location:** when an origin is configured, checkout refuses the address (422, "confirm its location on the map"), and `GET /bazaar/delivery-quote` returns `needs_location: true`. With **no origin configured** the old behaviour remains (base fee only, `distance_estimated: true`).
- **Maximum radius / minimum order:** `DELIVERY_MAX_DISTANCE_KM` (0 = unlimited; applies to Bazaar orders too, which then also need a route) and `DELIVERY_MIN_ORDER_VALUE` (0 = off; compared with the post-discount goods total at checkout).
- **Free-delivery progress:** `items_to_free_delivery = max(0, 15 − distinct products)`.
- **Bulk-converted orders:** orders created by bulk conversion are created with `delivery_fee = 0` and are not priced by this function ([BULK_ORDERS](BULK_ORDERS.md)).

> **Note:** seven tests used to hard-code the previous Rs 20 base fee; the suite now pins `DELIVERY_BASE_FEE`/`DELIVERY_PER_KM` in `tests/conftest.py`, so they no longer depend on the deployable default.
>
>
> **Which value is live?** `docker-compose.prod.yml` forwards the delivery/routing variables since 2026-10-26 (earlier it forwarded none, so the code defaults silently applied). Kubernetes: from `gawachabazaar-backend-secret` (contents not in the repository); Render: from the service's environment (not visible). The base fee tests no longer depend on the default (the suite pins it).

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
| Routing provider down/slow | Quote and checkout fail with 503 (nothing is guessed); the app shows the message and disables Place order |
| Address without GPS | Base fee only, `distance_estimated = true` |
| Packing point deleted/deactivated | Falls back to env origin, else base fee only |
| Extreme/bad coordinates | Out-of-range coordinates -> 422; a real route longer than 30 km is billed as 30 km; beyond `DELIVERY_MAX_DISTANCE_KM` -> not deliverable |
| Client shows a different fee than charged | Not possible by design (same function); the mobile app hard-codes 15 and 6 only as fallbacks before the API answers |

Gaps: public OSRM demo server in the default configuration (see below); fee changes require a deploy or env change (no admin UI for fee parameters — Admin Settings only sets the packing point); no per-zone pricing, surge, minimum-order rule or delivery-time estimate.

## `POST /delivery/quote` and address search (added 2026-10-26)

`POST /api/v1/delivery/quote` (CUSTOMER) `{"address_id": 127}` -> `{available, distance_km, distance_meters, estimated_duration_minutes, delivery_fee, free_delivery, currency, reason}`. The address must belong to the caller (404 otherwise, also when missing); no coordinates -> 422; origin not configured -> 422; outside `DELIVERY_MAX_DISTANCE_KM` -> **200** with `available:false`, `delivery_fee:null` and a `reason`; routing down -> 503. The fee uses the caller's current cart (15+ distinct products = free) through the same `calculate_delivery_fee` as checkout, which re-derives distance and fee itself and stores `orders.delivery_distance_meters`, `routing_provider`, `warehouse_id` (the packing-point location, null for the env-var origin). The client can send nothing but an address id; `CheckoutRequest` carries no amounts. The older `GET /bazaar/delivery-quote` (used by the app) shares the same function.

`POST /api/v1/delivery/geocode` (CUSTOMER, 10/min) `{"query": "..."}` -> candidate map locations via Nominatim (`countrycodes=in`, 1 request/s spacing, identifying `User-Agent`). It is meant for a **Search** button followed by the customer confirming the pin - never for search-as-you-type on the public server. Saving an address stores `geocode_provider`, `geocode_provider_id` (optional, from the chosen candidate) and a server-set `geocoded_at`; latitude/longitude are range-validated. The mobile address form now has **Find this address on the map** (calls `/delivery/geocode`, customer taps the right result) next to **Use current location** (device GPS, only a helper); both are **unverified on a device**.

### Changing the rules
All in environment variables (restart required; today they live in `core/config.py`, read through `PricingRules.from_settings()` in `services/delivery_pricing.py`, the one place to change when moving them to an admin-editable table): base fee `DELIVERY_BASE_FEE`, per-km `DELIVERY_PER_KM`, billing cap `DELIVERY_MAX_CHARGED_KM`, radius `DELIVERY_MAX_DISTANCE_KM`, free-delivery threshold `FREE_DELIVERY_MIN_ITEMS`, minimum order `DELIVERY_MIN_ORDER_VALUE`. The tiered model in the original proposal (e.g. 20 / 30+8 per km / 54+10 per km) is **not** implemented; the existing linear rule was kept. Remember that `docker-compose.prod.yml` does not forward these variables (see above).

### Public OSRM / Nominatim vs self-hosting
The public `router.project-osrm.org` demo and `nominatim.openstreetmap.org` are community-run, best-effort, with no SLA; the OSRM demo is documented as for light/testing use, and Nominatim's policy limits to about 1 request/second and forbids bulk or autocomplete use. Acceptable for development and a small pilot where cached routes keep traffic tiny; **not** a dependable production dependency (an outage now blocks checkout for non-free baskets). Self-host OSRM before launch: the `osrm-backend` Docker image with the OSM extract for Central India/Maharashtra (Geofabrik), `osrm-extract/partition/customize` with the MLD profile, then `osrm-routed`; roughly 2 vCPU / 2-4 GB RAM and a few GB disk for a state extract (**estimate, unverified here**). Point `OSRM_BASE_URL` at it; no code change. Redis is optional until more than one worker exists; with several workers it becomes the shared cache.

### Live integration run (2026-10-26)
`backend/tests/integration/test_live_delivery.py` (marker `integration`, skipped unless `GB_INTEGRATION=1`; never part of the normal suite) drives the real FastAPI app (in-process `TestClient`) against **PostgreSQL 16, Redis 7 (docker), the public OSRM server and the public Nominatim**. Run it with a disposable `*_test` database and a throw-away Redis:

```
docker run -d --name gb-itest-redis -p 127.0.0.1:16379:6379 redis:7-alpine
GB_INTEGRATION=1 GB_INTEGRATION_REDIS_URL=redis://127.0.0.1:16379/0 GB_INTEGRATION_REDIS_CONTAINER=gb-itest-redis TEST_DATABASE_URL=<disposable *_test db> python -m pytest -p no:cacheprovider tests/integration -m integration -s
```

Locations are public Nagpur landmarks whose coordinates came from Nominatim; the "packing point" is a stand-in (Zero Mile Stone 21.1497877, 79.0806859), **not** the real warehouse.

| Destination (landmark) | OSRM road distance | Duration | Straight line | Fee (40 + 10/km, ceil) |
|---|---|---|---|---|
| Ambazari Lake | 6 712-6 714 m | 433 s | 4.32 km | Rs 108 |
| Airport (Dr. Babasaheb Ambedkar Intl) | 11 361 m | 807 s | 7.61 km | Rs 154 |
| Kamptee | 16 443 m | 911 s | 14.14 km | Rs 205 (not deliverable with `DELIVERY_MAX_DISTANCE_KM=12`) |

Measured on the developer machine against public services (several runs, not benchmarks): OSRM call 480-600 ms; route-cache hit 1.5-2.6 ms; `/delivery/quote` 560-650 ms on a miss and 22-50 ms on a hit; checkout 116-395 ms; first quote with Redis stopped ~1.4 s (socket timeouts before the breaker opens), then cache-less/in-process.

**Verified live:** real OSRM parsing (response `distance` == stored value, `lon,lat` order proven - the swapped request returns 0 m); Redis miss -> SET -> hit with no second OSRM call; TTL present; expired key re-fetched; 10 simultaneous identical requests -> 1 OSRM call (and 10 simultaneous API quotes -> 1); Redis container stopped mid-flight -> quote and checkout still succeed with the correct fee, outage logged; OSRM unreachable -> 503 and no order; Nominatim unreachable -> saved addresses still quote (geocoding is not on the checkout path); real Nominatim search + 1 s spacing + empty result; address saved with a Nominatim place id -> quote -> checkout with tampered `delivery_fee`/`distance_km`/`warehouse_id` -> order row has the server's distance, `routing_provider=osrm`, `warehouse_id` of the packing point, fee == quote, total = subtotal - discount + fee; 5 simultaneous checkouts of one cart -> 1 order.

**Not verified (updated 2026-10-27, still true):** the mobile app on any emulator or device (none available in this environment; Expo web start-up is broken, see `AI_STATUS`); real Firebase sign-in (the harness uses the Firebase test double); real payments (the Razorpay gateway is only exercised through its fake; no live or test keys were used); the Render deployment and `docker-compose.prod.yml` (the compose file was only syntax-checked with `docker compose config`); a self-hosted OSRM; load beyond 10 concurrent requests.

**Known limitations:** public OSRM/Nominatim are best-effort (one transient Nominatim read timeout was seen in a run -> the app shows "Address search is unavailable right now"); multi-replica deployments still break rate limiting, the WebSocket hub and the reservation sweep (the route cache and its lock are the only delivery parts that are multi-replica safe); no tax concept exists in the order model (`tax` is not a column).

**Future improvements:** self-hosted OSRM; an admin-editable pricing table; a map-pin picker (needs a native map dependency); a persistent Nominatim result cache; moving the pay-first finalize route lookup out of the session-row lock.

### Local testing
Set `PACKING_POINT_LATITUDE=21.1458`, `PACKING_POINT_LONGITUDE=79.0882` (Nagpur centre) or choose a packing point in Admin, add an address with coordinates (e.g. Sitabuldi 21.1463, 79.0849 to a Dharampeth address around 21.1360, 79.0670), then `POST /api/v1/delivery/quote` with the customer's Firebase token. Not exercised against the live OSRM in this change (tests stub the network).

## Public OSRM: pilot or production? (decision, 2026-10-27)

**Conclusion: public OSRM (`router.project-osrm.org`) is development / pilot infrastructure only - not production.** It is a community demo server with no SLA; its operators describe it as for light use (check the current usage policy yourself - not verified here). Nominatim's public instance is likewise limited to about one request per second and may not be used for autocomplete or bulk work.

1. *Acceptable for the pilot?* Yes, for a small pilot: routes are cached for 7 days per ~11 m cell, so the call volume is the number of **distinct** (packing point, address) pairs plus one per address edit, not the number of orders or cart views.
2. *Expected volume.* No real traffic data exists in the repository, so there is no measured figure. Rule of thumb: N active customers x ~1.5 addresses = about 1.5 N lookups per 7-day TTL window, i.e. roughly 6 N per month in the worst case - 1 000 customers is ~6 000 lookups/month (an estimate, not a measurement).
3. *If public OSRM is down.* Quotes for non-free baskets and checkout return 503 (customers see "Delivery distance cannot be calculated right now"); cached routes and free-delivery (Bazaar) baskets keep working. There is no silent straight-line fallback by design, so an outage of more than a few minutes is a revenue incident.
4. *Self-hosting.* `osrm-backend` Docker image, a Geofabrik extract (the Maharashtra/Nagpur area is in `asia/india/western-zone`), `osrm-extract` + `osrm-partition` + `osrm-customize` (MLD), then `osrm-routed --algorithm mld`. Measured on this machine, see "Self-hosted OSRM trial" below.
5. *Switching.* Only `OSRM_BASE_URL` changes (`ROUTING_PROVIDER` stays `osrm`); pricing code is untouched. The cache key includes a hash of the endpoint, so the two never share entries (unit-tested; live-tested below).

### Self-hosted OSRM trial (2026-10-27, local Docker, verified)
```
curl -O https://download.geofabrik.de/asia/india/western-zone-261025.osm.pbf        # 222 MB (Maharashtra, Gujarat, Goa...)
docker run --rm -v $PWD:/data ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/western-zone-261025.osm.pbf
docker run --rm -v $PWD:/data ghcr.io/project-osrm/osrm-backend osrm-partition /data/western-zone-261025.osrm
docker run --rm -v $PWD:/data ghcr.io/project-osrm/osrm-backend osrm-customize /data/western-zone-261025.osrm
docker run -d -p 5000:5000 -v $PWD:/data ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/western-zone-261025.osrm
# then: OSRM_BASE_URL=http://<host>:5000   (ROUTING_PROVIDER=osrm unchanged)
```
Measured on a 8 GB Docker VM: extract+partition+customize about 13 min, peak 2.2 GB RAM while building; `osrm-routed` steady state 1.75 GB RAM; 2.8 GB disk including the download. Route Zero Mile Stone -> Ambazari: 6 713.7 m (public: 6 714 m). The whole live suite (17 tests) passes against it with only `OSRM_BASE_URL` changed: OSRM call 43 ms (public 480-600 ms), quote miss 65 ms, cache hit ~1 ms. Sizing for production: 2 vCPU / 4 GB RAM / 10 GB disk is a reasonable starting point (extrapolated from this trial, not load-tested). Map data is a static snapshot: schedule a re-extract (e.g. monthly). Keep the OSRM port private (backend network only) - it has no authentication.
