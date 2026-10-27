# API Reference

> **Status:** Verified (generated from source). **Generated:** 2026-10-27 by [`docs/_tools/gen_api_reference.py`](../_tools/gen_api_reference.py).
> **Evidence:** router decorators in [`backend/app/api/v1/`](../../backend/app/api/v1), router mounting in [`router.py`](../../backend/app/api/v1/router.py), the app's own OpenAPI document (`app.openapi()`), and the reviewed role matrix [`backend/tests/authz_golden.json`](../../backend/tests/authz_golden.json).

Conventions (envelope, errors, pagination): [API_CONVENTIONS.md](API_CONVENTIONS.md). Webhook: [WEBHOOKS.md](WEBHOOKS.md). Roles and permissions: [USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md).

**239 HTTP operations + 1 WebSocket.** Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are served only when `APP_ENV` is not `production` ([`main.py`](../../backend/app/main.py)).

How to read the **Auth** column: `roles A/B` = caller must hold at least one of those roles (checked live against `user_roles`); `perm x.y` = the caller's roles must grant that permission in the static map ([`permissions.py`](../../backend/app/core/permissions.py)); `signed-in user` = any ACTIVE user whose token verified (email/password users also need a verified email). Router-level role gates apply to every route in that router. **Request** column: `name(p|q|h)` are path/query/header parameters; the schema name is the JSON body model. **Response** lists declared success responses (`code: Schema`); every error uses the uniform envelope.

Field-level request/response schemas live in the OpenAPI document (268 schemas at generation time) and the Pydantic models in [`backend/app/schemas/`](../../backend/app/schemas); they are not repeated here to avoid drift.

## Index

| Module | Operations |
|---|---|
| [addresses](#addresses) | 5 |
| [ads](#ads) | 7 |
| [auth](#auth) | 3 |
| [bazaar](#bazaar) | 2 |
| [bulk_orders](#bulk-orders) | 18 |
| [cart](#cart) | 8 |
| [catalog](#catalog) | 29 |
| [customers](#customers) | 13 |
| [dashboard](#dashboard) | 1 |
| [delivery](#delivery) | 2 |
| [delivery_partner](#delivery-partner) | 23 |
| [fulfillments](#fulfillments) | 8 |
| [home_slides](#home-slides) | 6 |
| [inventory](#inventory) | 33 |
| [offers](#offers) | 1 |
| [orders](#orders) | 10 |
| [packaging](#packaging) | 10 |
| [payments](#payments) | 18 |
| [promotions](#promotions) | 11 |
| [push](#push) | 2 |
| [realtime](#realtime) | 1 |
| [referrals](#referrals) | 7 |
| [staff](#staff) | 6 |
| [suppliers](#suppliers) | 10 |
| [wishlist](#wishlist) | 3 |
| [platform](#platform) | 3 |

## addresses

Source: [`backend/app/api/v1/addresses.py`](../../backend/app/api/v1/addresses.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/addresses` | roles CUSTOMER | - | 200: AddressListResponse | List the current user's addresses [L27](../../backend/app/api/v1/addresses.py#L27) |
| POST | `/api/v1/addresses` | roles CUSTOMER | CreateAddressRequest | 201: AddressResponse | rate limit 20/minute per client IP (in-process); Add a new address to the current user's address book [L40](../../backend/app/api/v1/addresses.py#L40) |
| DELETE | `/api/v1/addresses/{address_id}` | roles CUSTOMER | address_id(p) | 204 | Delete one of the current user's addresses [L83](../../backend/app/api/v1/addresses.py#L83) |
| GET | `/api/v1/addresses/{address_id}` | roles CUSTOMER | address_id(p) | 200: AddressResponse | Get one of the current user's addresses [L54](../../backend/app/api/v1/addresses.py#L54) |
| PATCH | `/api/v1/addresses/{address_id}` | roles CUSTOMER | address_id(p), UpdateAddressRequest | 200: AddressResponse | rate limit 30/minute per client IP (in-process); Update one of the current user's addresses [L68](../../backend/app/api/v1/addresses.py#L68) |

## ads

Source: [`backend/app/api/v1/ads.py`](../../backend/app/api/v1/ads.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/ads` | Public | - | 200: array | List Active Ads [L25](../../backend/app/api/v1/ads.py#L25) |
| GET | `/api/v1/ads/admin` | perm ads.read | - | 200: array | Admin: List All Ads [L32](../../backend/app/api/v1/ads.py#L32) |
| POST | `/api/v1/ads/admin` | perm ads.manage | multipart: Body_admin_create_ad_api_v1_ads_admin_post | 201: AdminAdDetailResponse | Admin: Create Ad (with creative image) [L56](../../backend/app/api/v1/ads.py#L56) |
| DELETE | `/api/v1/ads/admin/{ad_id}` | perm ads.manage | ad_id(p) | 204 | Admin: Delete Ad [L105](../../backend/app/api/v1/ads.py#L105) |
| GET | `/api/v1/ads/admin/{ad_id}` | perm ads.read | ad_id(p) | 200: AdminAdDetailResponse | Admin: Get Ad Detail [L42](../../backend/app/api/v1/ads.py#L42) |
| PATCH | `/api/v1/ads/admin/{ad_id}` | perm ads.manage | ad_id(p), UpdateAdRequest | 200: AdminAdDetailResponse | Admin: Update Ad [L95](../../backend/app/api/v1/ads.py#L95) |
| POST | `/api/v1/ads/admin/{ad_id}/image` | perm ads.manage | ad_id(p), multipart: Body_admin_replace_ad_image_api_v1_ads_admin__ad_id__image_post | 200: AdminAdDetailResponse | Admin: Replace Ad Creative Image [L82](../../backend/app/api/v1/ads.py#L82) |

## auth

Source: [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| POST | `/api/v1/auth/legacy-migrate` | Public (rate-limited) | LegacyMigrationRequest | 200: LegacyMigrationResponse | rate limit 5/minute per client IP (in-process); Upgrade Pre-Firebase Account [L60](../../backend/app/api/v1/auth.py#L60) |
| GET | `/api/v1/auth/me` | signed-in (email-verification gate skipped) | - | 200: AuthUserResponse | Current Authenticated User [L79](../../backend/app/api/v1/auth.py#L79) |
| POST | `/api/v1/auth/sync` | Bearer Firebase ID token verified in service (no existing app account needed; creates/links one) | body | 200: AuthUserResponse | rate limit 20/minute per client IP (in-process); Synchronize Firebase User [L39](../../backend/app/api/v1/auth.py#L39) |

## bazaar

Source: [`backend/app/api/v1/bazaar.py`](../../backend/app/api/v1/bazaar.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/bazaar/delivery-quote` | roles CUSTOMER | address_id(q) | 200: app__schemas__bazaar__DeliveryQuoteResponse | Delivery fee for the current cart (optionally to a saved address) [L29](../../backend/app/api/v1/bazaar.py#L29) |
| GET | `/api/v1/bazaar/status` | roles CUSTOMER | - | 200: BazaarStatusResponse | Bazaar / Bazaar+ progress [L18](../../backend/app/api/v1/bazaar.py#L18) |

## bulk-orders

Source: [`backend/app/api/v1/bulk_orders.py`](../../backend/app/api/v1/bulk_orders.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/bulk-orders/admin/requests` | roles ADMIN/OPERATIONS | status(q), page(q), page_size(q) | 200: AdminBulkOrderRequestListResponse | List all bulk/custom order requests [L175](../../backend/app/api/v1/bulk_orders.py#L175) |
| GET | `/api/v1/bulk-orders/admin/requests/{request_id}` | roles ADMIN/OPERATIONS | request_id(p) | 200: AdminBulkOrderRequestResponse | Get any bulk/custom order request [L189](../../backend/app/api/v1/bulk_orders.py#L189) |
| POST | `/api/v1/bulk-orders/admin/requests/{request_id}/convert` | roles ADMIN/OPERATIONS | request_id(p) | 201: OrderDetailResponse | Convert an accepted request into a real Order (CUSTOMER_ACCEPTED -> CONVERTED_TO_ORDER) [L294](../../backend/app/api/v1/bulk_orders.py#L294) |
| GET | `/api/v1/bulk-orders/admin/requests/{request_id}/quote` | roles ADMIN/OPERATIONS | request_id(p) | 200: QuoteResponse | Get the quote (with full version history) for any request [L243](../../backend/app/api/v1/bulk_orders.py#L243) |
| POST | `/api/v1/bulk-orders/admin/requests/{request_id}/quote` | roles ADMIN/OPERATIONS | request_id(p), CreateQuoteVersionRequest | 201: QuoteResponse | Draft a new quote version (DRAFT - not yet visible to the customer) [L229](../../backend/app/api/v1/bulk_orders.py#L229) |
| POST | `/api/v1/bulk-orders/admin/requests/{request_id}/quote/{version_id}/reject` | roles ADMIN/OPERATIONS | request_id(p), version_id(p) | 200: QuoteResponse | Withdraw a SENT quote version (SENT -> REJECTED) [L268](../../backend/app/api/v1/bulk_orders.py#L268) |
| POST | `/api/v1/bulk-orders/admin/requests/{request_id}/quote/{version_id}/send` | roles ADMIN/OPERATIONS | request_id(p), version_id(p) | 200: QuoteResponse | Send a DRAFT quote version to the customer (DRAFT -> SENT; supersedes the prior SENT version) [L254](../../backend/app/api/v1/bulk_orders.py#L254) |
| POST | `/api/v1/bulk-orders/admin/requests/{request_id}/review` | roles ADMIN/OPERATIONS | request_id(p), ReviewBulkOrderRequestRequest | 200: AdminBulkOrderRequestResponse | Move a request into review (REQUESTED -> UNDER_REVIEW) [L200](../../backend/app/api/v1/bulk_orders.py#L200) |
| POST | `/api/v1/bulk-orders/admin/requests/{request_id}/status` | roles ADMIN/OPERATIONS | request_id(p), UpdateBulkOrderRequestStatusRequest | 200: AdminBulkOrderRequestResponse | Move a request to UNDER_REVIEW/REJECTED/CANCELLED/EXPIRED [L213](../../backend/app/api/v1/bulk_orders.py#L213) |
| GET | `/api/v1/bulk-orders/admin/variants/{variant_id}/availability` | roles ADMIN/OPERATIONS | variant_id(p) | 200: VariantAvailabilityResponse | Read-only available inventory for a variant, for pricing a quote (never reserves) [L282](../../backend/app/api/v1/bulk_orders.py#L282) |
| GET | `/api/v1/bulk-orders/profile` | roles CUSTOMER | - | 200: BulkCustomerProfileResponse | Get the current user's bulk customer profile [L71](../../backend/app/api/v1/bulk_orders.py#L71) |
| PUT | `/api/v1/bulk-orders/profile` | roles CUSTOMER | UpsertBulkCustomerProfileRequest | 200: BulkCustomerProfileResponse | Create or update the current user's bulk customer profile [L58](../../backend/app/api/v1/bulk_orders.py#L58) |
| GET | `/api/v1/bulk-orders/requests` | roles CUSTOMER | page(q), page_size(q) | 200: BulkOrderRequestListResponse | List the current user's bulk/custom order requests [L102](../../backend/app/api/v1/bulk_orders.py#L102) |
| POST | `/api/v1/bulk-orders/requests` | roles CUSTOMER | CreateBulkOrderRequestRequest | 201: BulkOrderRequestResponse | Submit a bulk/custom order request (never creates an Order) [L89](../../backend/app/api/v1/bulk_orders.py#L89) |
| GET | `/api/v1/bulk-orders/requests/{request_id}` | roles CUSTOMER | request_id(p) | 200: BulkOrderRequestResponse | Get one of the current user's bulk/custom order requests [L116](../../backend/app/api/v1/bulk_orders.py#L116) |
| POST | `/api/v1/bulk-orders/requests/{request_id}/accept` | roles CUSTOMER | request_id(p) | 200: BulkOrderRequestResponse | Accept the current active quote version for one of the current user's requests [L157](../../backend/app/api/v1/bulk_orders.py#L157) |
| POST | `/api/v1/bulk-orders/requests/{request_id}/cancel` | roles CUSTOMER | request_id(p) | 200: BulkOrderRequestResponse | Cancel one of the current user's own requests [L129](../../backend/app/api/v1/bulk_orders.py#L129) |
| GET | `/api/v1/bulk-orders/requests/{request_id}/quote` | roles CUSTOMER | request_id(p) | 200: QuoteResponse | Get the quote (with full version history) for one of the current user's requests [L142](../../backend/app/api/v1/bulk_orders.py#L142) |

## cart

Source: [`backend/app/api/v1/cart.py`](../../backend/app/api/v1/cart.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/cart` | roles CUSTOMER | - | 200: CartResponse | Get the current user's active cart [L30](../../backend/app/api/v1/cart.py#L30) |
| POST | `/api/v1/cart` | roles CUSTOMER | - | 200: CartResponse | Ensure and return an active cart [L37](../../backend/app/api/v1/cart.py#L37) |
| POST | `/api/v1/cart/checkout` | roles CUSTOMER | CheckoutRequest | 200: OrderDetailResponse | rate limit 10/minute per client IP (in-process); Checkout the active cart into a PENDING order [L114](../../backend/app/api/v1/cart.py#L114) |
| POST | `/api/v1/cart/evaluate-promo` | roles CUSTOMER | EvaluatePromotionRequest | 200: PromotionEvaluationResponse | Preview a promo code (or the best automatic promotion) against the current cart [L100](../../backend/app/api/v1/cart.py#L100) |
| DELETE | `/api/v1/cart/items` | roles CUSTOMER | - | 204 | Remove all items (cart stays ACTIVE) [L89](../../backend/app/api/v1/cart.py#L89) |
| POST | `/api/v1/cart/items` | roles CUSTOMER | AddCartItemRequest | 201: CartItemResponse | Add an item to the cart (merges quantity if already present) [L49](../../backend/app/api/v1/cart.py#L49) |
| DELETE | `/api/v1/cart/items/{item_id}` | roles CUSTOMER | item_id(p) | 204 | Remove one item from the cart [L76](../../backend/app/api/v1/cart.py#L76) |
| PATCH | `/api/v1/cart/items/{item_id}` | roles CUSTOMER | item_id(p), UpdateCartItemRequest | 200: CartItemResponse | Set a cart item's quantity [L62](../../backend/app/api/v1/cart.py#L62) |

## catalog

Source: [`backend/app/api/v1/catalog.py`](../../backend/app/api/v1/catalog.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/catalog/categories` | Public | parent_id(q), page(q), page_size(q) | 200: CategoryListResponse | List active categories [L180](../../backend/app/api/v1/catalog.py#L180) |
| POST | `/api/v1/catalog/categories` | perm categories.create | CreateCategoryRequest | 201: CategoryResponse | Create a category [L237](../../backend/app/api/v1/catalog.py#L237) |
| GET | `/api/v1/catalog/categories/admin` | perm categories.read | page(q), page_size(q), status(q), parent_id(q), q(q) | 200: AdminCategoryListResponse | List/search/filter every category regardless of status (admin panel) [L132](../../backend/app/api/v1/catalog.py#L132) |
| GET | `/api/v1/catalog/categories/admin/{category_id}` | perm categories.read | category_id(p) | 200: AdminCategoryDetailResponse | Get the complete admin detail for any category regardless of status [L149](../../backend/app/api/v1/catalog.py#L149) |
| GET | `/api/v1/catalog/categories/admin/{category_id}/activity` | perm categories.read | category_id(p) | 200: ProductActivityResponse | Real audit-log activity for this category [L162](../../backend/app/api/v1/catalog.py#L162) |
| PUT | `/api/v1/catalog/categories/reorder` | perm categories.update | ReorderCategoriesRequest | 204 | Set the display order of sibling categories/subcategories [L250](../../backend/app/api/v1/catalog.py#L250) |
| DELETE | `/api/v1/catalog/categories/{category_id}` | perm categories.delete | category_id(p) | 204 | Delete a category that has no products or subcategories [L277](../../backend/app/api/v1/catalog.py#L277) |
| GET | `/api/v1/catalog/categories/{category_id}` | Public | category_id(p) | 200: CategoryDetailResponse | Get an active category (with direct active children) [L194](../../backend/app/api/v1/catalog.py#L194) |
| PATCH | `/api/v1/catalog/categories/{category_id}` | perm categories.update | category_id(p), UpdateCategoryRequest | 200: CategoryResponse | Update a category (including lifecycle status) [L263](../../backend/app/api/v1/catalog.py#L263) |
| DELETE | `/api/v1/catalog/categories/{category_id}/image` | perm categories.update | category_id(p) | 200: CategoryResponse | Remove a category's image [L311](../../backend/app/api/v1/catalog.py#L311) |
| POST | `/api/v1/catalog/categories/{category_id}/image` | perm categories.update | category_id(p), multipart: Body_upload_category_image_api_v1_catalog_categories__category_id__image_post | 200: CategoryResponse | Upload (or replace) a category's image via Cloudinary [L290](../../backend/app/api/v1/catalog.py#L290) |
| DELETE | `/api/v1/catalog/images/{image_id}` | perm products.manage_media | image_id(p) | 204 | Delete a product image [L469](../../backend/app/api/v1/catalog.py#L469) |
| PATCH | `/api/v1/catalog/images/{image_id}` | perm products.manage_media | image_id(p), UpdateProductImageRequest | 200: ProductImageResponse | Update a product image, including primary image handoff [L455](../../backend/app/api/v1/catalog.py#L455) |
| PATCH | `/api/v1/catalog/prices/{price_id}` | perm products.manage_pricing | price_id(p), UpdatePriceRequest | 200: PriceResponse | Activate/deactivate or end a price's validity window [L523](../../backend/app/api/v1/catalog.py#L523) |
| GET | `/api/v1/catalog/products` | Public | category_id(q), q(q), page(q), page_size(q) | 200: ProductListResponse | List active products, optionally filtered by category and/or name search [L205](../../backend/app/api/v1/catalog.py#L205) |
| POST | `/api/v1/catalog/products` | perm products.create | CreateProductRequest | 201: ProductResponse | Create a product [L331](../../backend/app/api/v1/catalog.py#L331) |
| GET | `/api/v1/catalog/products/admin` | perm products.read | page(q), page_size(q), status(q), category_id(q), q(q), price_min(q), price_max(q), created_from(q), created_to(q), updated_from(q), updated_to(q) | 200: AdminProductListResponse | List/search/filter every product regardless of status (admin panel) [L67](../../backend/app/api/v1/catalog.py#L67) |
| GET | `/api/v1/catalog/products/admin/{product_id}` | perm products.read | product_id(p) | 200: AdminProductDetailResponse | Get the complete admin detail for any product regardless of status [L102](../../backend/app/api/v1/catalog.py#L102) |
| GET | `/api/v1/catalog/products/admin/{product_id}/activity` | perm products.read | product_id(p) | 200: ProductActivityResponse | Real audit-log activity for this product and its variants/prices [L115](../../backend/app/api/v1/catalog.py#L115) |
| POST | `/api/v1/catalog/products/quick-create` | perm products.create | QuickCreateProductRequest | 201: ProductResponse | Create a whole product - sizes, prices, photo, opening stock - in one transaction [L345](../../backend/app/api/v1/catalog.py#L345) |
| DELETE | `/api/v1/catalog/products/{product_id}` | perm products.delete | product_id(p) | 204 | Permanently delete a product (refused if it has order/quote/supplier history - archive it instead) [L366](../../backend/app/api/v1/catalog.py#L366) |
| GET | `/api/v1/catalog/products/{product_id}` | Public | product_id(p) | 200: ProductResponse | Get an active product with images, active variants, and current prices [L220](../../backend/app/api/v1/catalog.py#L220) |
| PATCH | `/api/v1/catalog/products/{product_id}` | perm products.update | product_id(p), UpdateProductRequest | 200: ProductResponse | Update a product (including lifecycle status) [L379](../../backend/app/api/v1/catalog.py#L379) |
| POST | `/api/v1/catalog/products/{product_id}/images` | perm products.manage_media | product_id(p), CreateProductImageRequest | 201: ProductImageResponse | Add a product image [L441](../../backend/app/api/v1/catalog.py#L441) |
| POST | `/api/v1/catalog/products/{product_id}/images/upload` | perm products.manage_media | product_id(p), multipart: Body_upload_product_image_api_v1_catalog_products__product_id__images_upload_post | 201: ProductImageResponse | Upload a product image via Cloudinary and attach it to the product [L483](../../backend/app/api/v1/catalog.py#L483) |
| POST | `/api/v1/catalog/products/{product_id}/variants` | perm products.update | product_id(p), CreateProductVariantRequest | 201: ProductVariantResponse | Create a product variant [L394](../../backend/app/api/v1/catalog.py#L394) |
| DELETE | `/api/v1/catalog/variants/{variant_id}` | perm products.delete | variant_id(p) | 204 | Delete a size that was only just added: no orders, quotes, stock, carts or price changes (hide it instead otherwise) [L427](../../backend/app/api/v1/catalog.py#L427) |
| PATCH | `/api/v1/catalog/variants/{variant_id}` | perm products.update | variant_id(p), UpdateProductVariantRequest | 200: ProductVariantResponse | Update a product variant (including lifecycle status) [L408](../../backend/app/api/v1/catalog.py#L408) |
| POST | `/api/v1/catalog/variants/{variant_id}/prices` | perm products.manage_pricing | variant_id(p), CreatePriceRequest | 201: PriceResponse | Create a new price for a variant (preserves price history) [L509](../../backend/app/api/v1/catalog.py#L509) |

## customers

Source: [`backend/app/api/v1/customers.py`](../../backend/app/api/v1/customers.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/customers` | perm customers.view | page(q), page_size(q), q(q), account_status(q), activity(q), has_orders(q), registered_from(q), registered_to(q), last_order_from(q), last_order_to(q), sort_by(q), sort_dir(q) | 200: AdminCustomerListResponse | List/search/filter/sort customers [L65](../../backend/app/api/v1/customers.py#L65) |
| GET | `/api/v1/customers/dashboard` | perm customers.view | - | 200: CustomersDashboardResponse | Customer base overview: status counts, order behavior, realized revenue [L53](../../backend/app/api/v1/customers.py#L53) |
| PATCH | `/api/v1/customers/notes/{note_id}` | perm customers.notes | note_id(p), UpdateCustomerNoteRequest | 200: CustomerNoteResponse | Edit an internal support note [L208](../../backend/app/api/v1/customers.py#L208) |
| GET | `/api/v1/customers/{user_id}` | perm customers.view | user_id(p) | 200: AdminCustomerDetailResponse | Full customer profile + order/spend/promotion summary + addresses [L109](../../backend/app/api/v1/customers.py#L109) |
| GET | `/api/v1/customers/{user_id}/addresses` | perm customers.view | user_id(p) | 200: array | This customer's saved addresses (read-only admin view) [L154](../../backend/app/api/v1/customers.py#L154) |
| PATCH | `/api/v1/customers/{user_id}/contact` | perm customers.manage_contact | user_id(p), UpdateCustomerContactRequest | 200: AdminCustomerDetailResponse | Change a customer's email or phone (admin-verified, audit-logged) [L238](../../backend/app/api/v1/customers.py#L238) |
| GET | `/api/v1/customers/{user_id}/notes` | perm customers.notes | user_id(p) | 200: CustomerNoteListResponse | Internal support notes about this customer [L180](../../backend/app/api/v1/customers.py#L180) |
| POST | `/api/v1/customers/{user_id}/notes` | perm customers.notes | user_id(p), CreateCustomerNoteRequest | 201: CustomerNoteResponse | Add an internal support note about this customer [L194](../../backend/app/api/v1/customers.py#L194) |
| GET | `/api/v1/customers/{user_id}/orders` | perm customers.view | user_id(p), page(q), page_size(q) | 200: AdminOrderListResponse | This customer's order history (same rows/shape as the Orders admin module) [L123](../../backend/app/api/v1/customers.py#L123) |
| POST | `/api/v1/customers/{user_id}/password` | perm customers.reset_password | user_id(p), ResetCustomerPasswordRequest | 204 | Set a new password for a customer and sign them out everywhere [L252](../../backend/app/api/v1/customers.py#L252) |
| GET | `/api/v1/customers/{user_id}/promotions` | perm customers.view | user_id(p), page(q), page_size(q) | 200: CustomerPromotionRedemptionListResponse | This customer's promotion/coupon redemption history [L139](../../backend/app/api/v1/customers.py#L139) |
| POST | `/api/v1/customers/{user_id}/status` | perm customers.manage_status | user_id(p), UpdateCustomerStatusRequest | 200: AdminCustomerDetailResponse | Change a customer's account status (ACTIVE/INACTIVE/SUSPENDED) - enforced on their very next request [L222](../../backend/app/api/v1/customers.py#L222) |
| GET | `/api/v1/customers/{user_id}/timeline` | perm customers.view | user_id(p) | 200: CustomerTimelineResponse | Chronological account/order/promotion events for this customer [L167](../../backend/app/api/v1/customers.py#L167) |

## dashboard

Source: [`backend/app/api/v1/dashboard.py`](../../backend/app/api/v1/dashboard.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/dashboard` | perm reports.read | - | 200: DashboardSummaryResponse | Today's orders, collections, fulfilment backlog, low stock and delivery issues [L24](../../backend/app/api/v1/dashboard.py#L24) |

## delivery

Source: [`backend/app/api/v1/delivery.py`](../../backend/app/api/v1/delivery.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| POST | `/api/v1/delivery/geocode` | roles CUSTOMER | GeocodeRequest | 200: GeocodeResponse | rate limit 10/minute per client IP (in-process); Search an address and return map locations to confirm (not autocomplete) [L48](../../backend/app/api/v1/delivery.py#L48) |
| POST | `/api/v1/delivery/quote` | roles CUSTOMER | DeliveryQuoteRequest | 200: app__schemas__delivery__DeliveryQuoteResponse | rate limit 30/minute per client IP (in-process); Road-distance delivery quote for one of the caller's saved addresses [L33](../../backend/app/api/v1/delivery.py#L33) |

## delivery-partner

Source: [`backend/app/api/v1/delivery_partner.py`](../../backend/app/api/v1/delivery_partner.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/delivery-partner/assignments` | roles DELIVERY_PARTNER | scope(q), status(q), date_from(q), date_to(q), page(q), page_size(q) | 200: AssignmentListResponse | My deliveries (active or history) [L82](../../backend/app/api/v1/delivery_partner.py#L82) |
| GET | `/api/v1/delivery-partner/assignments/{assignment_id}` | roles DELIVERY_PARTNER | assignment_id(p) | 200: AssignmentResponse | One of my deliveries [L100](../../backend/app/api/v1/delivery_partner.py#L100) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/accept` | roles DELIVERY_PARTNER | assignment_id(p) | 200: AssignmentResponse | Accept (ASSIGNED -> ACCEPTED) [L111](../../backend/app/api/v1/delivery_partner.py#L111) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/deliver` | roles DELIVERY_PARTNER | assignment_id(p), DeliverRequest | 200: AssignmentResponse | rate limit 30/minute per client IP (in-process); Complete the delivery; confirms COD cash (must equal the amount due) [L163](../../backend/app/api/v1/delivery_partner.py#L163) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/fail` | roles DELIVERY_PARTNER | assignment_id(p), FailRequest | 200: AssignmentResponse | Delivery could not be completed (back to the dispatch queue) [L197](../../backend/app/api/v1/delivery_partner.py#L197) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/location` | roles DELIVERY_PARTNER | assignment_id(p), LocationUpdateRequest | 200: LocationAck | rate limit 120/minute per client IP (in-process); Share current location (only during an active delivery; rate limited) [L212](../../backend/app/api/v1/delivery_partner.py#L212) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/otp/send` | roles DELIVERY_PARTNER | assignment_id(p) | 200: OtpStatusSummary | rate limit 10/minute per client IP (in-process); At the door: send the COD delivery code to the customer (resend replaces it; rate limited) [L183](../../backend/app/api/v1/delivery_partner.py#L183) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/out-for-delivery` | roles DELIVERY_PARTNER | assignment_id(p) | 200: AssignmentResponse | Leave for the customer (PICKED_UP -> OUT_FOR_DELIVERY) [L149](../../backend/app/api/v1/delivery_partner.py#L149) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/pickup` | roles DELIVERY_PARTNER | assignment_id(p) | 200: AssignmentResponse | Picked up (ACCEPTED -> PICKED_UP) [L136](../../backend/app/api/v1/delivery_partner.py#L136) |
| POST | `/api/v1/delivery-partner/assignments/{assignment_id}/reject` | roles DELIVERY_PARTNER | assignment_id(p), RejectRequest | 200: AssignmentResponse | Decline before accepting (back to the dispatch queue) [L124](../../backend/app/api/v1/delivery_partner.py#L124) |
| GET | `/api/v1/delivery-partner/earnings` | roles DELIVERY_PARTNER | date_from(q), date_to(q), page(q), page_size(q) | 200: EarningsResponse | My earnings ledger [L226](../../backend/app/api/v1/delivery_partner.py#L226) |
| GET | `/api/v1/delivery-partner/me` | roles DELIVERY_PARTNER | - | 200: PartnerMeResponse | My partner profile and today's numbers [L62](../../backend/app/api/v1/delivery_partner.py#L62) |
| PATCH | `/api/v1/delivery-partner/me/availability` | roles DELIVERY_PARTNER | SetAvailabilityRequest | 200: PartnerMeResponse | Go online / offline [L71](../../backend/app/api/v1/delivery_partner.py#L71) |
| GET | `/api/v1/delivery-partners` | perm partners.read | status(q), availability(q), page(q), page_size(q) | 200: AdminPartnerListResponse | List delivery partners (partners.read) [L276](../../backend/app/api/v1/delivery_partner.py#L276) |
| POST | `/api/v1/delivery-partners` | perm partners.manage | AdminCreatePartnerRequest | 201: PartnerProfileResponse | Create a partner profile (partners.manage) [L288](../../backend/app/api/v1/delivery_partner.py#L288) |
| GET | `/api/v1/delivery-partners/active` | perm partners.read | - | 200: array | Active deliveries with last position (partners.read) [L314](../../backend/app/api/v1/delivery_partner.py#L314) |
| GET | `/api/v1/delivery-partners/assignments` | perm partners.read | status(q), partner_user_id(q), page(q), page_size(q) | 200: AssignmentListResponse | All assignments (partners.read) [L299](../../backend/app/api/v1/delivery_partner.py#L299) |
| POST | `/api/v1/delivery-partners/assignments/{assignment_id}/cod-reconcile` | perm partners.cod_reconcile | assignment_id(p), CodReconcileRequest | 200: CodSummaryItem | Mark collected cash as handed over (partners.cod_reconcile) [L337](../../backend/app/api/v1/delivery_partner.py#L337) |
| GET | `/api/v1/delivery-partners/cod` | perm partners.read | reconciled(q), partner_user_id(q), page(q), page_size(q) | 200: CodListResponse | COD cash collected / outstanding (partners.read) [L321](../../backend/app/api/v1/delivery_partner.py#L321) |
| GET | `/api/v1/delivery-partners/earnings` | perm partners.read | date_from(q), date_to(q) | 200: array | Earnings per partner (partners.read) [L347](../../backend/app/api/v1/delivery_partner.py#L347) |
| PATCH | `/api/v1/delivery-partners/{user_id}` | perm partners.manage | user_id(p), AdminUpdatePartnerRequest | 200: PartnerProfileResponse | Update a partner (partners.manage) [L357](../../backend/app/api/v1/delivery_partner.py#L357) |
| GET | `/api/v1/orders/{order_id}/delivery-otp` | roles CUSTOMER | order_id(p) | 200: CustomerDeliveryOtpResponse | rate limit 60/minute per client IP (in-process); My COD delivery code (own order only; the code is shown only while active) [L261](../../backend/app/api/v1/delivery_partner.py#L261) |
| GET | `/api/v1/orders/{order_id}/delivery-tracking` | roles CUSTOMER | order_id(p) | 200: CustomerTrackingResponse | Where is my delivery (own order, only while it is being delivered) [L247](../../backend/app/api/v1/delivery_partner.py#L247) |

## fulfillments

Source: [`backend/app/api/v1/fulfillments.py`](../../backend/app/api/v1/fulfillments.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/fulfillments` | roles ADMIN/HUB_STAFF/OPERATIONS/DELIVERY_PARTNER | status(q), delivery_partner_user_id(q), page(q), page_size(q) | 200: FulfillmentListResponse | List fulfillments (staff see all, a delivery partner sees only their own assignments) [L54](../../backend/app/api/v1/fulfillments.py#L54) |
| GET | `/api/v1/fulfillments/{fulfillment_id}` | roles ADMIN/HUB_STAFF/OPERATIONS/DELIVERY_PARTNER | fulfillment_id(p) | 200: FulfillmentResponse | Get a fulfillment (a delivery partner may only view their own assignment) [L76](../../backend/app/api/v1/fulfillments.py#L76) |
| POST | `/api/v1/fulfillments/{fulfillment_id}/assign` | roles ADMIN/HUB_STAFF/OPERATIONS | fulfillment_id(p), AssignDeliveryPartnerRequest | 200: FulfillmentResponse | Assign a delivery partner (READY_FOR_DELIVERY -> ASSIGNED) [L120](../../backend/app/api/v1/fulfillments.py#L120) |
| POST | `/api/v1/fulfillments/{fulfillment_id}/deliver` | roles ADMIN/DELIVERY_PARTNER | fulfillment_id(p), body | 200: FulfillmentResponse | Confirm delivery - the only action that consumes physical inventory [L165](../../backend/app/api/v1/fulfillments.py#L165) |
| GET | `/api/v1/fulfillments/{fulfillment_id}/order` | roles ADMIN/HUB_STAFF/OPERATIONS/DELIVERY_PARTNER | fulfillment_id(p) | 200: FulfillmentOrderDetailResponse | Get what to pick/pack and where to deliver for a fulfillment (order items, address, customer name, payment method/amount) - a delivery partner may only view their own assignment [L93](../../backend/app/api/v1/fulfillments.py#L93) |
| POST | `/api/v1/fulfillments/{fulfillment_id}/out-for-delivery` | roles ADMIN/DELIVERY_PARTNER | fulfillment_id(p) | 200: FulfillmentResponse | Mark out for delivery (ASSIGNED -> OUT_FOR_DELIVERY; assigned partner or ADMIN only) [L152](../../backend/app/api/v1/fulfillments.py#L152) |
| POST | `/api/v1/fulfillments/{fulfillment_id}/reassign` | roles ADMIN/HUB_STAFF/OPERATIONS | fulfillment_id(p), ReassignRequest | 200: FulfillmentResponse | Reassign to another delivery partner (assignment history is kept) [L136](../../backend/app/api/v1/fulfillments.py#L136) |
| POST | `/api/v1/fulfillments/{fulfillment_id}/status` | roles ADMIN/HUB_STAFF/OPERATIONS | fulfillment_id(p), UpdateFulfillmentStatusRequest | 200: FulfillmentResponse | Advance warehouse status one step (PICKING/PACKED/READY_FOR_DELIVERY) [L106](../../backend/app/api/v1/fulfillments.py#L106) |

## home-slides

Source: [`backend/app/api/v1/home_slides.py`](../../backend/app/api/v1/home_slides.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/home-slides` | Public | - | 200: array | List Active Home Slides [L23](../../backend/app/api/v1/home_slides.py#L23) |
| GET | `/api/v1/home-slides/admin` | perm ads.read | - | 200: array | Admin: List All Home Slides [L30](../../backend/app/api/v1/home_slides.py#L30) |
| POST | `/api/v1/home-slides/admin` | perm ads.manage | multipart: Body_admin_create_home_slide_api_v1_home_slides_admin_post | 201: AdminHomeSlideResponse | Admin: Create Home Slide (with image) [L43](../../backend/app/api/v1/home_slides.py#L43) |
| DELETE | `/api/v1/home-slides/admin/{slide_id}` | perm ads.manage | slide_id(p) | 204 | Admin: Delete Home Slide [L99](../../backend/app/api/v1/home_slides.py#L99) |
| PATCH | `/api/v1/home-slides/admin/{slide_id}` | perm ads.manage | slide_id(p), UpdateHomeSlideRequest | 200: AdminHomeSlideResponse | Admin: Update Home Slide [L87](../../backend/app/api/v1/home_slides.py#L87) |
| POST | `/api/v1/home-slides/admin/{slide_id}/image` | perm ads.manage | slide_id(p), multipart: Body_admin_replace_home_slide_image_api_v1_home_slides_admin__slide_id__image_post | 200: AdminHomeSlideResponse | Admin: Replace Home Slide Image [L74](../../backend/app/api/v1/home_slides.py#L74) |

## inventory

Source: [`backend/app/api/v1/inventory.py`](../../backend/app/api/v1/inventory.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/inventory/admin/dashboard` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | - | 200: InventoryDashboardResponse | Real-time inventory operational summary [L340](../../backend/app/api/v1/inventory.py#L340) |
| GET | `/api/v1/inventory/admin/lots` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | page(q), page_size(q), location_id(q), category_id(q), status(q), operational_status(q), batch_id(q), q(q) | 200: AdminInventoryLotListResponse | List/search/filter inventory lots with product/warehouse/batch context [L477](../../backend/app/api/v1/inventory.py#L477) |
| GET | `/api/v1/inventory/admin/lots/{lot_id}` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | lot_id(p) | 200: AdminInventoryLotDetailResponse | Complete operational detail for one inventory lot [L499](../../backend/app/api/v1/inventory.py#L499) |
| POST | `/api/v1/inventory/admin/lots/{lot_id}/reconcile` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.reconcile | lot_id(p), ReconcileStockRequest | 200: AdminInventoryLotListItemResponse | Reconcile a lot against a physical count - computes and applies the difference [L559](../../backend/app/api/v1/inventory.py#L559) |
| POST | `/api/v1/inventory/admin/lots/{lot_id}/remove` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.adjust | lot_id(p), RemoveStockRequest | 200: AdminInventoryLotListItemResponse | Remove stock from a lot (all available, or a quantity) with a reason [L532](../../backend/app/api/v1/inventory.py#L532) |
| GET | `/api/v1/inventory/admin/products` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | page(q), page_size(q), category_id(q), q(q), status(q) | 200: ProductStockListResponse | Stock per product (shared pool total) with each size's packs and weight [L352](../../backend/app/api/v1/inventory.py#L352) |
| GET | `/api/v1/inventory/admin/products/summary` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | category_id(q), q(q) | 200: ProductStockSummaryResponse | How many products are low, out of stock or expiring (the Inventory filter chips) [L371](../../backend/app/api/v1/inventory.py#L371) |
| GET | `/api/v1/inventory/admin/products/{product_id}` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | product_id(p) | 200: ProductStockItemResponse | One product's current stock (kg, warehouses, expiry) - used to refresh a card before a stock action [L385](../../backend/app/api/v1/inventory.py#L385) |
| POST | `/api/v1/inventory/admin/products/{product_id}/correct` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.reconcile | product_id(p), ProductCorrectStockRequest | 200: ProductStockOperationResponse | Correct a product's stock to a physical count - the server works out the difference (oldest stock first) [L401](../../backend/app/api/v1/inventory.py#L401) |
| POST | `/api/v1/inventory/admin/products/{product_id}/move` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.transfer | product_id(p), ProductMoveStockRequest | 200: ProductStockOperationResponse | Move an amount of a product's stock to another warehouse in one atomic action [L429](../../backend/app/api/v1/inventory.py#L429) |
| POST | `/api/v1/inventory/admin/products/{product_id}/remove` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.adjust | product_id(p), ProductRemoveStockRequest | 200: ProductStockOperationResponse | Remove an amount of a product's stock with a reason (oldest first, never reserved stock) [L415](../../backend/app/api/v1/inventory.py#L415) |
| PUT | `/api/v1/inventory/admin/products/{product_id}/stock-shares` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.adjust | product_id(p), SetStockSharesRequest | 200: ProductStockItemResponse | Assign stock of a product to specific sizes (each size's share), rest stays unassigned [L463](../../backend/app/api/v1/inventory.py#L463) |
| POST | `/api/v1/inventory/admin/receive` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.receive | ReceiveStockRequest | 200: AdminInventoryLotListItemResponse | Receive stock into a (batch, variant, location) lot - creates the lot if needed [L519](../../backend/app/api/v1/inventory.py#L519) |
| POST | `/api/v1/inventory/admin/stock-actions/{operation_id}/undo` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | operation_id(p) | 200: ProductStockOperationResponse | Undo a recent correct/remove/move with compensating movements (refused when unsafe) [L443](../../backend/app/api/v1/inventory.py#L443) |
| GET | `/api/v1/inventory/admin/stock-alerts` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | limit(q) | 200: StockAlertsResponse | Items out of stock, at/below their reserve level, or close to it [L546](../../backend/app/api/v1/inventory.py#L546) |
| POST | `/api/v1/inventory/admin/transfer` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.transfer | TransferStockRequest | 200: TransferStockResponse | Atomically transfer stock from one lot to a different warehouse [L573](../../backend/app/api/v1/inventory.py#L573) |
| GET | `/api/v1/inventory/batches` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | product_id(q), status(q), page(q), page_size(q) | 200: BatchListResponse | List batches [L306](../../backend/app/api/v1/inventory.py#L306) |
| POST | `/api/v1/inventory/batches` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.receive | CreateBatchRequest | 201: BatchResponse | Create a batch (harvest lot) for stock receiving [L293](../../backend/app/api/v1/inventory.py#L293) |
| GET | `/api/v1/inventory/batches/{batch_id}` | roles ADMIN/HUB_STAFF/OPERATIONS; perm inventory.read | batch_id(p) | 200: BatchResponse | Get a batch [L322](../../backend/app/api/v1/inventory.py#L322) |
| GET | `/api/v1/inventory/locations` | roles ADMIN/HUB_STAFF/OPERATIONS | status(q), page(q), page_size(q) | 200: InventoryLocationListResponse | List inventory locations [L90](../../backend/app/api/v1/inventory.py#L90) |
| POST | `/api/v1/inventory/locations` | roles ADMIN/HUB_STAFF/OPERATIONS | CreateInventoryLocationRequest | 201: InventoryLocationResponse | Create an inventory location [L79](../../backend/app/api/v1/inventory.py#L79) |
| DELETE | `/api/v1/inventory/locations/{location_id}` | roles ADMIN/HUB_STAFF/OPERATIONS; roles ADMIN | location_id(p) | 204 | Admin: delete (archive) an inventory location - refused while it holds stock [L129](../../backend/app/api/v1/inventory.py#L129) |
| GET | `/api/v1/inventory/locations/{location_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | location_id(p) | 200: InventoryLocationResponse | Get an inventory location [L104](../../backend/app/api/v1/inventory.py#L104) |
| PATCH | `/api/v1/inventory/locations/{location_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | location_id(p), UpdateInventoryLocationRequest | 200: InventoryLocationResponse | Update an inventory location (lifecycle status included) [L115](../../backend/app/api/v1/inventory.py#L115) |
| POST | `/api/v1/inventory/locations/{location_id}/packing-point` | roles ADMIN/HUB_STAFF/OPERATIONS; roles ADMIN | location_id(p) | 200: InventoryLocationResponse | Admin: make this location the delivery-distance origin (packing point) [L139](../../backend/app/api/v1/inventory.py#L139) |
| GET | `/api/v1/inventory/lots` | roles ADMIN/HUB_STAFF/OPERATIONS | batch_id(q), variant_id(q), location_id(q), status(q), page(q), page_size(q) | 200: InventoryLotListResponse | List inventory lots [L167](../../backend/app/api/v1/inventory.py#L167) |
| POST | `/api/v1/inventory/lots` | roles ADMIN/HUB_STAFF/OPERATIONS | CreateInventoryLotRequest | 201: InventoryLotResponse | Create an inventory lot (batch + variant + location) [L156](../../backend/app/api/v1/inventory.py#L156) |
| GET | `/api/v1/inventory/lots/{lot_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | lot_id(p) | 200: InventoryLotResponse | Get an inventory lot [L186](../../backend/app/api/v1/inventory.py#L186) |
| GET | `/api/v1/inventory/lots/{lot_id}/movements` | roles ADMIN/HUB_STAFF/OPERATIONS | lot_id(p), movement_type(q), performed_by_user_id(q), occurred_from(q), occurred_to(q), page(q), page_size(q) | 200: StockMovementListResponse | List stock movement history for a lot (read-only, immutable) [L215](../../backend/app/api/v1/inventory.py#L215) |
| POST | `/api/v1/inventory/lots/{lot_id}/movements` | roles ADMIN/HUB_STAFF/OPERATIONS | lot_id(p), CreateStockMovementRequest | 201: StockMovementResponse | Record a stock movement (the only way quantity changes) [L201](../../backend/app/api/v1/inventory.py#L201) |
| GET | `/api/v1/inventory/reservations` | roles ADMIN/HUB_STAFF/OPERATIONS | status(q), page(q), page_size(q) | 200: InventoryReservationListResponse | List inventory reservations [L246](../../backend/app/api/v1/inventory.py#L246) |
| GET | `/api/v1/inventory/reservations/{reservation_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | reservation_id(p) | 200: InventoryReservationDetailResponse | Get an inventory reservation, including its FIFO lot allocation [L262](../../backend/app/api/v1/inventory.py#L262) |
| POST | `/api/v1/inventory/reservations/{reservation_id}/expire` | roles ADMIN/HUB_STAFF/OPERATIONS | reservation_id(p) | 200: InventoryReservationResponse | Manually expire an ACTIVE reservation (idempotent no-op if already terminal) [L275](../../backend/app/api/v1/inventory.py#L275) |

## offers

Source: [`backend/app/api/v1/offers.py`](../../backend/app/api/v1/offers.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/offers` | Public | - | 200: array | List live offers for the Home carousel [L16](../../backend/app/api/v1/offers.py#L16) |

## orders

Source: [`backend/app/api/v1/orders.py`](../../backend/app/api/v1/orders.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/orders` | roles CUSTOMER | page(q), page_size(q) | 200: OrderListResponse | List the current user's orders [L58](../../backend/app/api/v1/orders.py#L58) |
| GET | `/api/v1/orders/admin` | perm orders.read | page(q), page_size(q), status(q), payment_status(q), fulfillment_status(q), date_from(q), date_to(q), q(q) | 200: AdminOrderListResponse | List/search/filter every order on the platform (admin panel) [L180](../../backend/app/api/v1/orders.py#L180) |
| GET | `/api/v1/orders/admin/{order_id}` | perm orders.read | order_id(p) | 200: AdminOrderDetailResponse | Get the complete operational detail for any order (admin panel) [L202](../../backend/app/api/v1/orders.py#L202) |
| POST | `/api/v1/orders/admin/{order_id}/cancel` | roles ADMIN | order_id(p), CancelOrderRequest | 200: OrderDetailResponse | Administrative cancellation of any order (any time before delivery is completed) [L166](../../backend/app/api/v1/orders.py#L166) |
| GET | `/api/v1/orders/{order_id}` | roles CUSTOMER | order_id(p) | 200: OrderDetailResponse | Get one of the current user's orders [L72](../../backend/app/api/v1/orders.py#L72) |
| POST | `/api/v1/orders/{order_id}/cancel` | roles CUSTOMER | order_id(p), CancelOrderRequest | 200: OrderDetailResponse | Cancel one of the current user's own orders (any time before delivery is completed) [L152](../../backend/app/api/v1/orders.py#L152) |
| GET | `/api/v1/orders/{order_id}/fulfillment` | roles CUSTOMER | order_id(p) | 200: CustomerFulfillmentResponse | Get the safe fulfillment status for one of the current user's orders [L119](../../backend/app/api/v1/orders.py#L119) |
| GET | `/api/v1/orders/{order_id}/payment` | roles CUSTOMER | order_id(p) | 200: PaymentResponse | Get the payment for one of the current user's orders [L85](../../backend/app/api/v1/orders.py#L85) |
| GET | `/api/v1/orders/{order_id}/refund` | roles CUSTOMER | order_id(p) | 200: RefundResponse | Get the refund status for one of the current user's orders, if any [L139](../../backend/app/api/v1/orders.py#L139) |
| GET | `/api/v1/orders/{order_id}/reservation` | roles CUSTOMER | order_id(p) | 200: InventoryReservationResponse | Get the inventory reservation for one of the current user's orders [L99](../../backend/app/api/v1/orders.py#L99) |

## packaging

Source: [`backend/app/api/v1/packaging.py`](../../backend/app/api/v1/packaging.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/packaging/operations` | roles ADMIN/HUB_STAFF/OPERATIONS | status(q), location_id(q), page(q), page_size(q) | 200: PackagingOperationListResponse | List packaging operations [L54](../../backend/app/api/v1/packaging.py#L54) |
| POST | `/api/v1/packaging/operations` | roles ADMIN/HUB_STAFF/OPERATIONS | CreatePackagingOperationRequest | 201: PackagingOperationResponse | Create a packaging operation (DRAFT) [L41](../../backend/app/api/v1/packaging.py#L41) |
| GET | `/api/v1/packaging/operations/{operation_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p) | 200: PackagingOperationDetailResponse | Get a packaging operation with its inputs and outputs [L69](../../backend/app/api/v1/packaging.py#L69) |
| POST | `/api/v1/packaging/operations/{operation_id}/cancel` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p) | 200: PackagingOperationResponse | Transition DRAFT or IN_PROGRESS -> CANCELLED [L96](../../backend/app/api/v1/packaging.py#L96) |
| POST | `/api/v1/packaging/operations/{operation_id}/complete` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p) | 200: PackagingOperationDetailResponse | Atomically consume inputs, produce outputs, and complete the operation [L107](../../backend/app/api/v1/packaging.py#L107) |
| POST | `/api/v1/packaging/operations/{operation_id}/inputs` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p), CreatePackagingInputRequest | 201: PackagingInputResponse | Record a source inventory lot consumed by this operation [L126](../../backend/app/api/v1/packaging.py#L126) |
| DELETE | `/api/v1/packaging/operations/{operation_id}/inputs/{input_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p), input_id(p) | 204 | Remove a recorded input (only while DRAFT/IN_PROGRESS) [L139](../../backend/app/api/v1/packaging.py#L139) |
| POST | `/api/v1/packaging/operations/{operation_id}/outputs` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p), CreatePackagingOutputRequest | 201: PackagingOutputResponse | Declare a packaged output (resolves/creates its inventory lot) [L156](../../backend/app/api/v1/packaging.py#L156) |
| DELETE | `/api/v1/packaging/operations/{operation_id}/outputs/{output_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p), output_id(p) | 204 | Remove a recorded output (only while DRAFT/IN_PROGRESS) [L169](../../backend/app/api/v1/packaging.py#L169) |
| POST | `/api/v1/packaging/operations/{operation_id}/start` | roles ADMIN/HUB_STAFF/OPERATIONS | operation_id(p) | 200: PackagingOperationResponse | Transition DRAFT -> IN_PROGRESS [L85](../../backend/app/api/v1/packaging.py#L85) |

## payments

Source: [`backend/app/api/v1/payments.py`](../../backend/app/api/v1/payments.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| POST | `/api/v1/payments` | roles CUSTOMER | CreatePaymentRequest | 201: PaymentInitiationResponse | Initiate payment for an order (online via Razorpay, or COD) [L86](../../backend/app/api/v1/payments.py#L86) |
| GET | `/api/v1/payments/admin` | roles ADMIN | page(q), page_size(q), status(q), payment_method(q), order_id(q), date_from(q), date_to(q), q(q) | 200: AdminPaymentListResponse | List/search/filter every payment on the platform (admin panel) [L249](../../backend/app/api/v1/payments.py#L249) |
| GET | `/api/v1/payments/admin/{payment_id}` | roles ADMIN | payment_id(p) | 200: AdminPaymentDetailResponse | Get the complete detail (incl. gateway attempt history) for any payment (admin panel) [L272](../../backend/app/api/v1/payments.py#L272) |
| POST | `/api/v1/payments/online/start` | roles CUSTOMER | StartOnlineCheckoutRequest | 200: OnlineCheckoutResponse | rate limit 10/minute per client IP (in-process); Pay-first online checkout: price the cart and get the Razorpay order to open (no order is created yet) [L157](../../backend/app/api/v1/payments.py#L157) |
| POST | `/api/v1/payments/online/{session_id}/confirm` | roles CUSTOMER | session_id(p), ConfirmCheckoutRequest | 200: OnlineCheckoutCompleteResponse | After Razorpay reports success: verify, then place the order from the cart [L172](../../backend/app/api/v1/payments.py#L172) |
| POST | `/api/v1/payments/online/{session_id}/verify` | roles CUSTOMER | session_id(p) | 200: OnlineCheckoutCompleteResponse | Re-check an online checkout with Razorpay and place the order if it was paid [L187](../../backend/app/api/v1/payments.py#L187) |
| GET | `/api/v1/payments/refunds` | roles ADMIN | status(q), page(q), page_size(q) | 200: AdminRefundListResponse | List refund requests, optionally filtered by status [L286](../../backend/app/api/v1/payments.py#L286) |
| GET | `/api/v1/payments/refunds/{refund_id}` | roles ADMIN | refund_id(p) | 200: AdminRefundResponse | Get one refund request [L300](../../backend/app/api/v1/payments.py#L300) |
| POST | `/api/v1/payments/refunds/{refund_id}/approve` | roles ADMIN | refund_id(p) | 200: AdminRefundResponse | Approve a refund request (PENDING_APPROVAL -> APPROVED) [L309](../../backend/app/api/v1/payments.py#L309) |
| POST | `/api/v1/payments/refunds/{refund_id}/process` | roles ADMIN | refund_id(p) | 200: AdminRefundResponse | Process an approved refund through the payment gateway (APPROVED/FAILED -> PROCESSING) [L350](../../backend/app/api/v1/payments.py#L350) |
| POST | `/api/v1/payments/refunds/{refund_id}/reject` | roles ADMIN | refund_id(p), RejectRefundRequest | 200: AdminRefundResponse | Reject a refund request (PENDING_APPROVAL -> REJECTED) [L322](../../backend/app/api/v1/payments.py#L322) |
| POST | `/api/v1/payments/refunds/{refund_id}/sync` | roles ADMIN | refund_id(p) | 200: AdminRefundResponse | Ask the gateway for a PROCESSING refund's current outcome and apply it [L336](../../backend/app/api/v1/payments.py#L336) |
| POST | `/api/v1/payments/webhooks/{gateway_slug}` | Public; gateway signature verified in service | gateway_slug(p) | 200: WebhookAckResponse, 404 | Payment gateway webhook callback (no JWT - gateway signature verified internally) [L217](../../backend/app/api/v1/payments.py#L217) |
| GET | `/api/v1/payments/{payment_id}` | roles CUSTOMER | payment_id(p) | 200: PaymentResponse | Get a payment (must belong to the current user) [L100](../../backend/app/api/v1/payments.py#L100) |
| GET | `/api/v1/payments/{payment_id}/checkout` | roles CUSTOMER | payment_id(p) | 200: PaymentCheckoutResponse | Details for opening (or re-opening) the gateway checkout for an online payment [L142](../../backend/app/api/v1/payments.py#L142) |
| POST | `/api/v1/payments/{payment_id}/confirm` | roles CUSTOMER | payment_id(p), ConfirmCheckoutRequest | 200: PaymentResponse | Hand off a completed Razorpay Checkout (signature verified, status re-checked with Razorpay) [L201](../../backend/app/api/v1/payments.py#L201) |
| POST | `/api/v1/payments/{payment_id}/retry` | roles CUSTOMER | payment_id(p) | 200: PaymentInitiationResponse | Start a new online attempt for a FAILED/EXPIRED payment [L114](../../backend/app/api/v1/payments.py#L114) |
| POST | `/api/v1/payments/{payment_id}/verify` | roles CUSTOMER | payment_id(p) | 200: PaymentResponse | Reconcile payment status against the gateway (never trusts client claims) [L128](../../backend/app/api/v1/payments.py#L128) |

## promotions

Source: [`backend/app/api/v1/promotions.py`](../../backend/app/api/v1/promotions.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/promotions` | perm promotions.read | page(q), page_size(q), admin_status(q), effective_status(q), q(q) | 200: PromotionListResponse | List/search/filter promotions [L47](../../backend/app/api/v1/promotions.py#L47) |
| POST | `/api/v1/promotions` | perm promotions.create | CreatePromotionRequest | 201: PromotionDetailResponse | Create a promotion (starts as DRAFT unless status is explicitly set) [L67](../../backend/app/api/v1/promotions.py#L67) |
| GET | `/api/v1/promotions/dashboard` | perm promotions.read | - | 200: PromotionsDashboardResponse | Promotions overview: status counts, redemption totals, ending-soon/most-used [L35](../../backend/app/api/v1/promotions.py#L35) |
| GET | `/api/v1/promotions/{promotion_id}` | perm promotions.read | promotion_id(p) | 200: PromotionDetailResponse | Get full promotion detail including performance [L80](../../backend/app/api/v1/promotions.py#L80) |
| PATCH | `/api/v1/promotions/{promotion_id}` | perm promotions.update | promotion_id(p), UpdatePromotionRequest | 200: PromotionDetailResponse | Update a promotion's rules/schedule/targets [L93](../../backend/app/api/v1/promotions.py#L93) |
| POST | `/api/v1/promotions/{promotion_id}/activate` | perm promotions.manage_status | promotion_id(p) | 200: PromotionDetailResponse | Activate a promotion (DRAFT/PAUSED -> ACTIVE) [L166](../../backend/app/api/v1/promotions.py#L166) |
| POST | `/api/v1/promotions/{promotion_id}/disable` | perm promotions.manage_status | promotion_id(p) | 200: PromotionDetailResponse | Disable a promotion permanently (any status -> DISABLED; never usable again, never deleted) [L192](../../backend/app/api/v1/promotions.py#L192) |
| POST | `/api/v1/promotions/{promotion_id}/duplicate` | perm promotions.manage_status | promotion_id(p) | 201: PromotionDetailResponse | Duplicate a promotion as a new DRAFT (no code, no accrued usage) [L134](../../backend/app/api/v1/promotions.py#L134) |
| POST | `/api/v1/promotions/{promotion_id}/image` | perm promotions.update | promotion_id(p), multipart: Body_upload_promotion_image_api_v1_promotions__promotion_id__image_post | 200: PromotionDetailResponse | Upload the banner photo shown on this promotion's card in the app's offers carousel [L107](../../backend/app/api/v1/promotions.py#L107) |
| POST | `/api/v1/promotions/{promotion_id}/pause` | perm promotions.manage_status | promotion_id(p) | 200: PromotionDetailResponse | Pause a promotion (ACTIVE -> PAUSED; no new redemptions until reactivated) [L179](../../backend/app/api/v1/promotions.py#L179) |
| GET | `/api/v1/promotions/{promotion_id}/redemptions` | perm promotions.read | promotion_id(p), page(q), page_size(q) | 200: PromotionRedemptionListResponse | Coupon usage history for one promotion [L205](../../backend/app/api/v1/promotions.py#L205) |

## push

Source: [`backend/app/api/v1/push.py`](../../backend/app/api/v1/push.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| POST | `/api/v1/push-tokens` | signed-in user | PushTokenRequest | 204 | Register a device push token [L21](../../backend/app/api/v1/push.py#L21) |
| POST | `/api/v1/push-tokens/unregister` | signed-in user | PushTokenRequest | 204 | Remove a device push token [L29](../../backend/app/api/v1/push.py#L29) |

## realtime

Source: [`backend/app/api/v1/realtime.py`](../../backend/app/api/v1/realtime.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| WS | `/api/v1/ws/events` | Firebase ID token in `?token=` (checked in handler) | - | - |  [L36](../../backend/app/api/v1/realtime.py#L36) |

## referrals

Source: [`backend/app/api/v1/referrals.py`](../../backend/app/api/v1/referrals.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/referrals/admin` | perm referrals.read | status(q), user_id(q), page(q), page_size(q) | 200: AdminReferralListResponse | Admin: list referrals (referrals.read) [L82](../../backend/app/api/v1/referrals.py#L82) |
| GET | `/api/v1/referrals/admin/{referral_id}` | perm referrals.read | referral_id(p) | 200: AdminReferralDetailResponse | Admin: referral with its ledger (referrals.read) [L100](../../backend/app/api/v1/referrals.py#L100) |
| POST | `/api/v1/referrals/admin/{referral_id}/reverse` | perm referrals.manage | referral_id(p), AdminReferralActionRequest | 200: AdminReferralDetailResponse | Admin: reverse rewards / cancel a referral (referrals.manage) [L113](../../backend/app/api/v1/referrals.py#L113) |
| POST | `/api/v1/referrals/apply` | roles CUSTOMER | ApplyReferralRequest | 200: ApplyReferralResponse | rate limit 10/minute per client IP (in-process); Apply a friend's referral code (once, before the first order) [L48](../../backend/app/api/v1/referrals.py#L48) |
| GET | `/api/v1/referrals/history` | roles CUSTOMER | page(q), page_size(q) | 200: ReferralHistoryResponse | People I referred [L58](../../backend/app/api/v1/referrals.py#L58) |
| GET | `/api/v1/referrals/me` | roles CUSTOMER | - | 200: ReferralMeResponse | rate limit 60/minute per client IP (in-process); My referral code, program rules and stats [L34](../../backend/app/api/v1/referrals.py#L34) |
| GET | `/api/v1/referrals/rewards` | roles CUSTOMER | page(q), page_size(q) | 200: RewardsResponse | My reward ledger and balance [L68](../../backend/app/api/v1/referrals.py#L68) |

## staff

Source: [`backend/app/api/v1/staff.py`](../../backend/app/api/v1/staff.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/staff` | perm staff.read | - | 200: array | List Staff [L27](../../backend/app/api/v1/staff.py#L27) |
| POST | `/api/v1/staff` | perm staff.manage | CreateStaffRequest | 201: StaffDetailResponse | Create Staff Account [L49](../../backend/app/api/v1/staff.py#L49) |
| GET | `/api/v1/staff/{user_id}` | perm staff.read | user_id(p) | 200: StaffDetailResponse | Get Staff Detail [L35](../../backend/app/api/v1/staff.py#L35) |
| POST | `/api/v1/staff/{user_id}/roles` | perm staff.manage | user_id(p), AssignStaffRoleRequest | 200: StaffDetailResponse | Assign Staff Role [L62](../../backend/app/api/v1/staff.py#L62) |
| DELETE | `/api/v1/staff/{user_id}/roles/{role_name}` | perm staff.manage | user_id(p), role_name(p) | 200: StaffDetailResponse | Revoke Staff Role [L76](../../backend/app/api/v1/staff.py#L76) |
| PATCH | `/api/v1/staff/{user_id}/status` | perm staff.manage | user_id(p), UpdateStaffStatusRequest | 200: StaffDetailResponse | Set Staff Account Status [L90](../../backend/app/api/v1/staff.py#L90) |

## suppliers

Source: [`backend/app/api/v1/suppliers.py`](../../backend/app/api/v1/suppliers.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/suppliers` | roles ADMIN/HUB_STAFF/OPERATIONS | status(q), page(q), page_size(q) | 200: SupplierListResponse | List suppliers [L56](../../backend/app/api/v1/suppliers.py#L56) |
| POST | `/api/v1/suppliers` | roles ADMIN/HUB_STAFF/OPERATIONS | CreateSupplierRequest | 201: SupplierResponse | Create a supplier [L49](../../backend/app/api/v1/suppliers.py#L49) |
| GET | `/api/v1/suppliers/{supplier_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | supplier_id(p) | 200: SupplierResponse | Get a supplier [L66](../../backend/app/api/v1/suppliers.py#L66) |
| PATCH | `/api/v1/suppliers/{supplier_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | supplier_id(p), UpdateSupplierRequest | 200: SupplierResponse | Update a supplier [L72](../../backend/app/api/v1/suppliers.py#L72) |
| GET | `/api/v1/suppliers/{supplier_id}/evaluations` | roles ADMIN/HUB_STAFF/OPERATIONS; roles ADMIN | supplier_id(p), page(q), page_size(q) | 200: SupplierEvaluationListResponse | List a supplier's evaluation history (ADMIN only) [L148](../../backend/app/api/v1/suppliers.py#L148) |
| POST | `/api/v1/suppliers/{supplier_id}/evaluations` | roles ADMIN/HUB_STAFF/OPERATIONS; roles ADMIN | supplier_id(p), CreateSupplierEvaluationRequest | 201: SupplierEvaluationResponse | Record a supplier performance evaluation (ADMIN only) [L134](../../backend/app/api/v1/suppliers.py#L134) |
| GET | `/api/v1/suppliers/{supplier_id}/performance` | roles ADMIN/HUB_STAFF/OPERATIONS | supplier_id(p) | 200: SupplierPerformanceResponse | Supplier performance dashboard data (products, supply history, ratings) [L163](../../backend/app/api/v1/suppliers.py#L163) |
| GET | `/api/v1/suppliers/{supplier_id}/products` | roles ADMIN/HUB_STAFF/OPERATIONS | supplier_id(p), page(q), page_size(q) | 200: SupplierProductListResponse | List products linked to a supplier [L100](../../backend/app/api/v1/suppliers.py#L100) |
| POST | `/api/v1/suppliers/{supplier_id}/products` | roles ADMIN/HUB_STAFF/OPERATIONS | supplier_id(p), LinkSupplierProductRequest | 201: SupplierProductResponse | Link a product this supplier can supply [L89](../../backend/app/api/v1/suppliers.py#L89) |
| PATCH | `/api/v1/suppliers/{supplier_id}/products/{supplier_product_id}` | roles ADMIN/HUB_STAFF/OPERATIONS | supplier_id(p), supplier_product_id(p), UpdateSupplierProductRequest | 200: SupplierProductResponse | Update a supplier's product link (e.g. deactivate) [L114](../../backend/app/api/v1/suppliers.py#L114) |

## wishlist

Source: [`backend/app/api/v1/wishlist.py`](../../backend/app/api/v1/wishlist.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/wishlist` | roles CUSTOMER | - | 200: WishlistResponse | List the current user's wishlist [L17](../../backend/app/api/v1/wishlist.py#L17) |
| DELETE | `/api/v1/wishlist/{product_id}` | roles CUSTOMER | product_id(p) | 204 | Remove a product from the wishlist [L36](../../backend/app/api/v1/wishlist.py#L36) |
| PUT | `/api/v1/wishlist/{product_id}` | roles CUSTOMER | product_id(p) | 204 | Add a product to the wishlist [L26](../../backend/app/api/v1/wishlist.py#L26) |

## platform

Source: [`backend/app/api/v1/router.py`](../../backend/app/api/v1/router.py), [`backend/app/main.py`](../../backend/app/main.py)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/api/v1/ping` | Public | - | 200: PingResponse | API v1 Liveness Probe  |
| GET | `/health` | Public | - | 200: HealthResponse | Service Health Check  |
| GET | `/health/db` | Public | - | 200: DatabaseHealthResponse, 503: DatabaseHealthResponse | Database Health Check  |

