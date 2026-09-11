# Phase 10 — Catalog & Product API

Turns the existing Phase 3 catalog schema (`categories`, `products`,
`product_variants`, `product_images`, `prices`) into a real API: public
browsing (no auth) plus ADMIN-only management. No schema migration was
required or created — the tables already had the correct shape.

All endpoints are under `/api/v1/catalog`, registered in
[`app/api/v1/router.py`](../../app/api/v1/router.py). Implementation:
[`app/api/v1/catalog.py`](../../app/api/v1/catalog.py) (routes, HTTP only) →
[`app/services/catalog.py`](../../app/services/catalog.py) (`CatalogService`,
all business logic and queries) →
[`app/schemas/catalog.py`](../../app/schemas/catalog.py) (Pydantic v2
contracts) → existing SQLAlchemy models.

## Public Endpoints (no authentication)

| Method | Path | Behavior |
|---|---|---|
| GET | `/catalog/categories` | Paginated, `status='ACTIVE'` only. Optional `parent_id` filter. |
| GET | `/catalog/categories/{id}` | 404 unless `status='ACTIVE'`. Includes direct `children` (one level, ACTIVE only - not recursive). |
| GET | `/catalog/products` | Paginated, `status='ACTIVE'` only. Optional `category_id` filter. Lightweight item shape (`ProductSummaryResponse`): id, name, slug, category_id, status, primary_image_url. |
| GET | `/catalog/products/{id}` | 404 unless `status='ACTIVE'`. Full detail: category, all images, and **only ACTIVE variants**, each with its current price (or `null` if none is currently eligible). |

## Admin Endpoints (`require_roles("ADMIN")`)

All use the existing `get_current_user` → `require_roles` dependency chain
(Phase 9). No new authentication or authorization mechanism was introduced.

| Method | Path | Notes |
|---|---|---|
| POST | `/catalog/categories` | 409 on duplicate slug. 404 if `parent_id` doesn't exist. |
| PATCH | `/catalog/categories/{id}` | Partial update (`exclude_unset`). 422 if `parent_id == id` (self-parent, matches `ck_categories_parent_not_self`). Any status transition allowed - no state-machine enforcement, per project policy. |
| POST | `/catalog/products` | 404 if `category_id` doesn't exist. 409 on duplicate slug. |
| PATCH | `/catalog/products/{id}` | Partial update. 404 if a changed `category_id` doesn't exist. |
| POST | `/catalog/products/{product_id}/variants` | 404 if product doesn't exist. 409 on duplicate SKU. |
| PATCH | `/catalog/variants/{id}` | Partial update. 409 on duplicate SKU. |
| POST | `/catalog/products/{product_id}/images` | Setting `is_primary=true` atomically unsets any existing primary image for that product first (single commit - both writes succeed or fail together). |
| PATCH | `/catalog/images/{id}` | Same primary-swap handling as create. |
| DELETE | `/catalog/images/{id}` | 204. No special handling needed if the deleted image was primary - a product simply has none until one is set again. |
| POST | `/catalog/variants/{variant_id}/prices` | Creates a new price row; **never** rewrites an existing one. `valid_from` defaults to now. 422 if `valid_to < valid_from`. |
| PATCH | `/catalog/prices/{id}` | Only `is_active` and `valid_to` may change - `price`, `currency`, `variant_id`, `valid_from` are immutable via this endpoint, preserving price history. |

Public GET endpoints intentionally still return the same `status` field
values regardless of caller - it's never sensitive, and reusing one response
shape for both public and admin avoids schema duplication. What differs
between public and admin is *which rows are visible* (filtered to ACTIVE at
the query level), not the shape of a given row.

## Current Price Selection

Implemented in `CatalogService._get_current_prices_for_variants` - one query
for an arbitrary batch of variant IDs (used both for a single product detail
and, internally, for the same helper if it were ever reused for a listing),
not one query per variant:

```
WHERE variant_id IN (:ids)
  AND is_active = true
  AND valid_from <= now()
  AND (valid_to IS NULL OR valid_to >= now())
ORDER BY variant_id, valid_from DESC
```

The first row per `variant_id` (most recent `valid_from`) wins when more
than one row is technically eligible. This matches the given selection rule
exactly and means creating a new current price does **not** require closing
out the old one - the newer `valid_from` already wins the tie-break.

## Pagination

`page` (default 1, `ge=1`) and `page_size` (default 20, `ge=1, le=100`) query
parameters on both list endpoints. Response shape:

```json
{ "items": [...], "page": 1, "page_size": 20, "total": 137 }
```

`page_size` above 100 is rejected with 422 (Pydantic `Query(le=100)`), not
silently clamped.

## Validation & Error Behavior

- `status`/`unit` fields are Pydantic `Literal` types matching the DB CHECK
  constraints exactly (`CategoryStatus`, `ProductStatus`, `VariantStatus`,
  `VariantUnit`) - an invalid value is a 422 before any query runs.
- Duplicate `slug` (categories/products) or `sku` (variants) → the
  `IntegrityError` from the DB's unique constraint is caught and translated
  to `ConflictError` (409, `CONFLICT_ERROR`) - never a raw SQL error.
- A referenced `parent_id`/`category_id`/`product_id`/`variant_id` that
  doesn't exist → `NotFoundError` (404).
- `valid_to < valid_from` on a price → `BusinessValidationError` (422,
  `BUSINESS_VALIDATION_ERROR`) - checked in the service before insert, ahead
  of the DB's own `ck_prices_valid_to` constraint.
- No route-level or router-level exception handling was added - everything
  flows through the existing centralized handlers in
  [`app/exceptions/handlers.py`](../../app/exceptions/handlers.py).

## Explicit Domain Boundaries (unchanged)

- **No inventory join.** Stock quantities, `inventory_lots`, and
  `stock_movements` are never queried here. Catalog visibility is governed
  purely by `products.status`/`product_variants.status`.
- **No cart/order/payment logic.** This phase only makes variant IDs, SKUs,
  and current prices available for those domains to consume later.
- **No wholesaler catalog ownership.** Wholesalers remain represented only
  through `batches.wholesaler_user_id`/`batches.product_id`; nothing here
  changes or depends on that relationship. The catalog is centrally managed
  by ADMIN.
- **No Farmer/Farm exposure.** Not touched, not referenced.
- **No search infrastructure, no image upload/storage service.** `image_url`
  is a plain client-supplied string field; basic PostgreSQL `WHERE`
  filtering is the only query mechanism.

## Known Limitation Found & Fixed During This Phase

An early implementation of the image primary-swap logic used a
`with db.begin():`-based explicit transaction wrapper (copied from
`AuthService`'s pattern) *after* an initial existence-check read had already
run in the same request. Because SQLAlchemy 2.0 auto-begins a transaction on
that first read, `db.in_transaction()` was already `True` by the time the
explicit wrapper ran, so it silently took a nested-savepoint path instead of
owning the top-level transaction - the savepoint released fine, but the
*outer* transaction was never committed, and the image insert was rolled
back invisibly when the request's session closed. Endpoint responses still
reported `201 Created` with correct-looking data, but a follow-up read found
nothing. Caught by `test_12_primary_image_swap_unsets_previous_primary`
re-fetching the product after both writes. Fixed by dropping the explicit
transaction wrapper for this case in favor of two plain statements followed
by one `commit()` - correct because no commit happens between them, and
simpler than replicating `AuthService`'s nested-transaction helper for a
case that doesn't need it.
