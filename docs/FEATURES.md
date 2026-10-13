# Gawacha Bazaar - Features

What the product does, by audience. Each feature notes the rule behind it. Status legend:
**Live** = built and wired end to end; **Placeholder** = page exists but the feature is not built.
For how it is built see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Customer app (mobile)

### Account and sign-in
- **Live.** Email + password, Google, and phone OTP, all through Firebase.
- Email/password sign-ups must verify their email before using the app; Google and phone
  sign-ins are treated as verified.
- Link or add a phone number later; forgot-password by email; session restored on launch;
  expired tokens refresh silently.
- **Profile**, **settings** and **support** (email / phone contact) under the Account tab.
- Existing pre-Firebase customers keep their password through a one-time silent migration.

### Onboarding and addresses
- First-time **address setup** is required once per account.
- **Address book**: add, edit, delete, set default; addresses carry GPS coordinates (used for
  delivery pricing) and can be filled from the device location.

### Discover and shop
- **Home**: promotional hero carousel (admin-managed slides), regular/wholesale toggle,
  brand-ads carousel (see Ads below), category panels, product rails, the **Bazaar** section,
  brand and village-story sections.
- **Shop (categories)** and **category pages** with product grids and infinite scroll.
- **Search** with **voice search**.
- **Product detail**: image gallery, size/variant chips, price (and MRP discount where known),
  availability, origin and freshness notes, description, related products, wishlist heart, and a
  sticky Add/quantity footer with a floating cart pill above it.
- **Product cards**: name, size, price, add/stepper control, wishlist heart.
- **Wishlist**: save products with a heart anywhere; the Account -> Wishlist row shows a count
  bubble; optimistic add/remove.
- **Wholesale mode**: the Home toggle switches to a bulk-request experience - pick products and
  quantities into a draft that is submitted as a bulk order *request* (not a priced order); see
  Bulk and custom orders.

### Cart and checkout
- **Cart** with quantity steppers, per-line totals, **Clear** (optimistic with rollback and an
  error toast), promo codes (preview uses the same engine as checkout), and a **free-delivery
  progress** bar.
- A floating **cart bar** shows item count and total on the main screens.
- **Checkout**: address selection, harvest/delivery slot, summary, **delivery fee** and
  discount lines, payment choice - **Cash on Delivery** or **online** (UPI, cards, netbanking,
  wallets through Razorpay Checkout). Retry or complete payment later from the order page.
- Order success screen.

### Delivery fee and the Bazaar offer
- A basket with **15 or more different products** ships **free** - a "Bazaar".
- Smaller baskets pay **Rs 20 + Rs 10 per km of road distance** from the packing point to the
  delivery address (capped at 30 km). The cart shows a live quote and "add N more products for
  free delivery".
- **Gawacha Bazaar+**: six Bazaar orders in a calendar month unlocks Bazaar+; progress is shown
  in the Bazaar section. See ARCHITECTURE section 6 for the exact rules.

### Orders
- **Orders tab**: stats (total / delivered / cancelled), filter (all, active, delivered,
  cancelled), search by order ID, order cards with status pill.
- **Order details**: status card, five-step tracker (placed, confirmed, preparing, out for
  delivery, delivered) with real times where recorded, items with photos, price breakdown
  (discount, delivery fee, total), payment details, delivery address, **Reorder** (adds the
  items back to the cart), **Get help**, and a menu with cancel / refund.
- **Cancel order** (with reason) while the order is still cancellable, and **refund status**
  tracking when a refund exists.
- Order status updates arrive as the backend changes them (list refreshes; order page polls).

### Bulk and custom orders
- **Live.** Businesses request bulk quantities, review itemised **quotes** (versioned),
  accept, and see request status; staff convert accepted quotes to orders.

---

## 2. Admin panel (staff)

Sign-in is restricted to staff roles; the sidebar shows only pages the role may use.

| Page | What staff can do | Needed permission |
|---|---|---|
| **Overview** | Live snapshot: orders, revenue, stock alerts, recent activity | any staff |
| **Orders** | Search/filter all orders, open detail (customer, items, payment, fulfillment, refund), cancel with reason. A **count bubble on the sidebar** shows orders still pending. New orders trigger a **sound alarm and toast** in real time. | `orders.read`, `orders.cancel` |
| **Products** | Create/edit products, multiple sizes with prices and units (SKUs auto-generated), photo upload, publish/visibility, slug/SKU under "advanced" | `products.*` |
| **Categories** | Create/edit categories with images, ordering, status | `categories.*` |
| **Inventory** | Stock by lot and warehouse (on-hand / reserved / available), receive stock, adjust, transfer, reconcile, low/expiring alerts, **add warehouses** | `inventory.*` |
| **Promotions** | Create/edit promotions (discount rules, targets, eligibility, status) | `promotions.*` |
| **Customers** | Profiles, order history, notes, contact changes, status, password reset; phone masked unless `customers.view_sensitive` | `customers.*` |
| **Delivery** | Fulfillment queue, assign delivery partners, move orders picking -> delivered | `delivery.*` |
| **Payments** | Payment list/detail, refund approval, rejection and processing | `orders.refund` |
| **Home slides** | Manage the home hero carousel (image, label, title, script word, body, CTA, link, order) | `ads.*` |
| **Ads** | Brand ad cards: image, brand name, optional **title and subtitle** shown on the card, link, order, active/inactive. Images **must be 1200 x 500 px (12:5)**; the upload is validated so nothing gets cropped. | `ads.*` |
| **Settings** | **Packing point**: choose which warehouse delivery distance is measured from; set a warehouse's map position by pasting coordinates from Google Maps or using the current location. | `settings.manage` (choosing is ADMIN-only) |
| **Staff** | Create/deactivate staff, assign roles (cannot deactivate yourself) | `staff.*` |
| **Audit log** | Searchable record of admin actions | `audit.read` |
| **Reports** | **Placeholder** - not built yet | `reports.read` |
| **Reviews** | **Placeholder** - no review domain yet | `reviews.read` |

Also: session tokens refresh automatically (including after the tab sits in the background),
and the sidebar can collapse (the Orders count becomes a dot).

---

## 3. Backend capabilities

| Domain | Capabilities |
|---|---|
| Auth | Firebase token verification, account sync/link, legacy migration, email-verification gating, roles read live |
| Catalog | Categories, products, variants, prices, images (Cloudinary), public browsing, admin management |
| Inventory | Warehouses (with coordinates and packing-point flag), lots, stock movements, receiving, adjusting, transferring, reconciling, expiry/low-stock status |
| Reservations | Stock reserved at checkout, released on cancel/expiry, proactive expiry sweep every 120 s |
| Packaging | Packaging operations turning input lots into labelled output lots |
| Cart and orders | Server-owned cart, checkout transaction, order snapshots, cancellation, order history |
| Delivery pricing | Free for 15+ distinct products, else base + per-km by road distance; Bazaar+ eligibility; quote endpoint |
| Payments | COD and Razorpay, server-side verification, signed webhooks (idempotent), retry, refund workflow (approve / reject / process) |
| Fulfillment | Picking -> packed -> ready -> assigned -> out for delivery -> delivered; delivery-partner views |
| Suppliers | Supplier records, supplied products, performance evaluations |
| Bulk commerce | Bulk requests, quotes with versions, accept, convert to order |
| Promotions | Rules, targeting, eligibility, redemptions, auto/promo-code evaluation |
| Customers and staff | Admin customer management, notes, staff management, audit log |
| Content | Ads and home slides with image upload |
| Realtime | WebSocket stream of order/fulfillment/payment/refund changes to staff |
| Operations | Health and DB-health endpoints, request IDs, security headers, rate limits on auth, structured logging |

---

## 4. Not built / known gaps

- Admin **Reports** and **Reviews** pages are placeholders.
- Per-step order times (confirmed, preparing, out for delivery) are not recorded, so the tracker
  shows only placed/delivered times.
- Multi-replica deployment needs Redis for rate limiting and realtime (ARCHITECTURE section 10).
- Customer-side reviews, in-app chat support (support is contact details only) and push
  notifications are not implemented.
