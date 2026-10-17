# Catalogue, Pricing and Content

> **Status:** Verified for catalogue and pricing (code + tests); **Unverified** for ads/home slides/wishlist (no behavioural tests). **Last verified:** 2026-10-14.
> **Source files:** [`services/catalog.py`](../../backend/app/services/catalog.py), [`services/pricing.py`](../../backend/app/services/pricing.py), [`stock_pool.py`](../../backend/app/services/stock_pool.py), [`image_upload.py`](../../backend/app/services/image_upload.py), [`ad.py`](../../backend/app/services/ad.py), [`home_slide.py`](../../backend/app/services/home_slide.py), [`wishlist.py`](../../backend/app/services/wishlist.py), [`offers.py`](../../backend/app/services/offers.py); routers `catalog.py`, `ads.py`, `home_slides.py`, `wishlist.py`, `offers.py`; models `category`, `product`, `product_variant`, `product_image`, `price`, `ad`, `home_slide`, `wishlist_item`.
> **Tests:** [`test_phase_10_catalog.py`](../../backend/tests/test_phase_10_catalog.py), [`test_shared_stock_pool.py`](../../backend/tests/test_shared_stock_pool.py), [`test_stock_reserve_and_deletes.py`](../../backend/tests/test_stock_reserve_and_deletes.py). Operation list: [API_REFERENCE](../03-api/API_REFERENCE.md#catalog).

## Model

```
categories (parent_id, one nesting level) 1─* products 1─* product_variants 1─* prices
                                               └─* product_images (one primary per product)
```

| Entity | Key rules (from schema/code) |
|---|---|
| `categories` | `slug` unique; status `ACTIVE/INACTIVE/ARCHIVED`; `CHECK parent_id <> id`; **one nesting level** enforced in `CatalogService._validate_parent` (category → subcategory); optional image |
| `products` | `slug` unique; status `DRAFT/ACTIVE/INACTIVE/ARCHIVED`; belongs to one category |
| `product_variants` | A sellable size: `name`, unique `sku`, `unit ∈ {KG, G, L, ML, UNIT, DOZEN, BOX, PACK}`, `quantity > 0`, optional `reserve_level`, status `ACTIVE/INACTIVE/ARCHIVED` |
| `prices` | Per variant: `price > 0`, `currency`, `valid_from`, optional `valid_to`, `is_active`; history is preserved (rows are added/edited, none deleted via the API) |
| `product_images` | URLs (Cloudinary uploads or a supplied URL); exactly one primary per product (partial unique index `uq_product_images_product_primary`) |

## Public browsing (no authentication)

- `GET /catalog/categories[/{id}]`, `GET /catalog/products[/{id}]` — only `ACTIVE` products (and their `ACTIVE` variants) are exposed. A parent category listing includes the products of its active subcategories. `q` filters by case-insensitive **name** match (`ILIKE`, wildcards escaped) — no full-text search.
- **Current price** (`get_current_prices_for_variants`, shared by catalogue, cart and checkout): `is_active AND valid_from <= now AND (valid_to IS NULL OR valid_to >= now)`; the most recent `valid_from` wins; ties broken by highest `id`. A variant with no eligible price makes a cart line/checkout fail ("no longer has a valid price").
- **Availability** shown to customers is derived from the shared stock pool (see [INVENTORY](INVENTORY.md)): sellable packs per variant, ACTIVE lots only, minus reservations, rounded **down** to thousandths.
- Product summaries include a default variant, its price and its pack size (used by the cards in the app).

## Admin management (permission-gated; every mutation is audited)

| Area | Operations (permission) |
|---|---|
| Categories | create/update/delete, image upload/delete (`categories.*`) |
| Products | create/update/delete, list/detail, activity feed (`products.*`) |
| Variants | create/update/delete (`products.update`) |
| Prices | create for a variant, update (`products.manage_pricing`) |
| Images | add by URL, upload (multipart → Cloudinary), update, delete (`products.manage_media`) |
| Activity feeds | `GET /catalog/{categories,products}/admin/{id}/activity` read `admin_action_logs` — the **only** place audit rows are read |

Deletion rules (code-verified): a **category** can be deleted only when it has no products/children; a **product** can be hard-deleted only if it has **no** order, quote, bulk-request, supplier-listing, reservation or packaging history — otherwise `409` and the advice to set status `ARCHIVED`. When allowed, deletion also removes the product's stock movements, lots, batches, quality checks, cart items, prices and variants (stock history for a never-sold product is lost). `promotion_targets` pointing at the product or category are **not** cleaned up (no foreign key).

## Images

`ImageUploadService` ([`image_upload.py`](../../backend/app/services/image_upload.py)): allowed types JPEG, PNG, WebP, GIF; maximum **8 MB**; uploaded to Cloudinary; when `CLOUDINARY_*` is unset the endpoint returns 503 `UPLOADS_NOT_CONFIGURED` and production logs a start-up warning. Content-type is taken from the upload's *declared* type (no magic-byte sniffing or image decoding was found). The "ads must be 1200 × 500 px (12:5)" rule in [`FEATURES.md`](../FEATURES.md) is enforced by the Admin UI only: the ad service, router and upload service contain no dimension or ratio check. The mobile product card shows a neutral placeholder tile when an image URL is missing or fails to load (changed 2026-10-14, uncommitted).

## Content: home slides, ads, offers

| Item | Behaviour |
|---|---|
| Home slides (`home_slides`) | Public list returns `ACTIVE` slides ordered by `display_order`; admin CRUD + image; seeded with default slides by migration `a8c3d5e7f901` (third-party Unsplash URLs) |
| Ads (`ads`) | Brand cards (`brand_name`, image, optional `title`/`subtitle`, `link_url`, `display_order`, `ACTIVE/INACTIVE`); public list returns active ads |
| Offers | `GET /offers` returns up to 10 live promotions with `show_in_carousel` (never customer-specific ones); same redeemability rule as checkout ([PROMOTIONS](PROMOTIONS.md)) |
| Admin permission | Home slides and ads both use `ads.read` / `ads.manage` |

## Wishlist

`PUT/DELETE /wishlist/{product_id}`, `GET /wishlist` (CUSTOMER). Unique `(user_id, product_id)`; cascade with user/product. Optimistic updates in the app.

## Failure scenarios and gaps

- Price missing/expired between cart and checkout → 409, nothing written.
- Product made inactive after it is in a cart → checkout 409 "no longer available".
- No tests cover ads, home slides or the wishlist beyond the role-matrix test, and the backend does not validate ad image dimensions.
- Names/slugs are not validated beyond uniqueness; marathi/Devanagari text is supported by the database (UTF-8) and the app font — not separately tested.
- `farms` and `quality_checks` tables exist but nothing creates them ([INVENTORY](INVENTORY.md)).
