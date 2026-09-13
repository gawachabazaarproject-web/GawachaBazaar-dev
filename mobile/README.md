# GawachaBazaar — Customer Mobile App

Phase 20 customer-facing MVP: React Native + Expo (Expo Router, TypeScript), consuming the
existing GawachaBazaar FastAPI backend (Phases 1–19). This app does not implement any business
logic of its own — every state machine (order, payment, fulfillment, refund) lives in the backend;
the app only renders what the backend returns. See `docs/architecture/ARCHITECTURE.md` and
`docs/api/*` in `backend/` for the system of record.

## Running the app

```bash
cd mobile
npm install
npm run android         # or: npm run ios / npm run web
```

The backend must be running (on port 8000, same machine as Metro) and reachable from your
device/emulator - see the root `docker-compose.yml` or `backend/README.md`. No `.env` setup is
needed for local dev: `src/api/client.ts` derives the backend's base URL automatically from the
same host Expo Go/the dev client already used to reach Metro (`Constants.expoConfig.hostUri`), so
it keeps working across DHCP/network changes without editing anything. `.env.example` documents
`EXPO_PUBLIC_API_BASE_URL` as an explicit override, for cases with no dev-server host to derive
from (a production/standalone build) or a backend on a different host/port.

## Architecture

```
mobile/
├── app/                     # Expo Router file-based routes (screens only - no business logic)
│   ├── (auth)/              # Login, register - unauthenticated
│   ├── (onboarding)/        # First-time address setup, shown once per account
│   ├── (tabs)/              # Home, Categories, Search, Orders, Account
│   ├── product/[id].tsx     # Product detail
│   ├── category/[id].tsx    # Category product listing
│   ├── cart/                # Cart
│   ├── checkout/            # Checkout, order success
│   ├── order/[id]/          # Order detail, cancellation, refund status
│   ├── address/             # Address book CRUD
│   ├── account/             # Profile, support, settings
│   └── _layout.tsx          # Root: providers, fonts, splash
├── src/
│   ├── api/                 # The ONE HTTP layer - axios client, auth/refresh, per-domain modules
│   ├── components/          # Reusable UI primitives (Button, ProductCard, Skeleton, ...)
│   ├── features/            # Domain hooks (TanStack Query) grouped by feature
│   ├── navigation/           # AppGate: auth/onboarding redirect logic (not a route)
│   ├── store/                # Small global state (zustand): auth session, toast
│   ├── theme/                # Design tokens - colors, type scale, spacing, motion
│   ├── hooks/, utils/, types/
└── assets/                  # App icons/splash/logo (see Design system)
```

Feature-oriented, matching the brief. Business rules are never re-implemented here - see
`src/utils/statusPresentation.ts`, which is explicitly a presentation-only mapping from backend
status strings to UI labels/colors, not a second state machine.

## API integration

`src/api/client.ts` is the single Axios instance every request goes through: base URL from
`EXPO_PUBLIC_API_BASE_URL`, bearer token attached automatically, and a single-flight refresh
interceptor (concurrent 401s share one `/auth/refresh` call rather than each firing their own).
`src/api/errors.ts` maps every backend/network failure into one `ApiError` with a safe,
user-facing message - no screen ever renders a raw "500 Internal Server Error" or a stack trace.

Per-domain modules (`authApi`, `addressApi`, `catalogApi`, `cartApi`, `orderApi`, `paymentApi`)
wrap the actual, already-documented backend routes 1:1 - no invented endpoints. See
`src/types/api.ts` for the TypeScript mirror of the backend's Pydantic schemas (kept in sync
manually; re-verify against `GET /openapi.json` on the running backend if the backend changes).

**Small, targeted backend changes were made to support this app** - each the smallest fix for a
genuine, confirmed gap, never a redesign:
- `GET /catalog/products` gained an optional `q` query parameter (case-insensitive name search) -
  the backend had no search capability at all before Phase 20.
- `ProductSummaryResponse` (the catalog list/grid shape) gained `starting_price`,
  `default_variant_id`, `default_variant_unit`, and `default_variant_quantity`, resolved from each
  product's lowest-id active variant using the same current-price rule as everywhere else. Without
  this, every Home/Category/Search grid card had no price, no addable variant, and no pack-size
  label - `variant` is only ever populated on the full product-detail response.
- `CartItemResponse` gained `product_id`, `product_slug`, and `primary_image_url`, resolved from
  the item's product. Without this, the cart screen had no way to show a thumbnail or link a line
  item back to its product page - it only ever carried variant-level fields.
- A pre-existing transaction bug in `AuthService`'s `_transaction()` helper was fixed: it branched
  on `db.in_transaction()` to decide between a real transaction and a savepoint, but SQLAlchemy
  autobegins a transaction on a session's first read, so a preceding lookup (e.g. the credential
  check in `authenticate()`) made that check true even when nothing had actually opened a
  transaction the caller owned - routing every login down a savepoint path that released cleanly
  but was never committed, silently rolling back on session close. This is a bug fix, not a new
  endpoint or field.

## Authentication

`expo-secure-store` (Keychain/Keystore-backed) is the only place access/refresh tokens are
persisted - never AsyncStorage. `src/store/authStore.ts` (zustand) owns session state
(`restoring` → `authenticated`/`unauthenticated`); `src/navigation/AppGate.tsx` reacts to it and to
whether the account has at least one saved address to decide between the auth screens, the
one-time address-onboarding screen, and the main tab experience.

## Design system

- **Color**: `src/theme/colors.ts` - a deep pine-forest green primary and warm mustard-gold
  accent, warm off-white background. Deliberately avoids generic "grocery green" and leaf/produce
  iconography.
- **Typography**: a two-typeface system (`src/theme/typography.ts`) - Noto Serif for headlines
  (screen titles, section headers), Plus Jakarta Sans for everything read at speed (body copy,
  labels, prices, buttons). No third face.
- **Spacing/radius**: fixed scales (`src/theme/spacing.ts`) - no ad hoc pixel values in screens.
- **Motion**: `src/theme/motion.ts` - two spring presets and three timing presets, plus
  `PressableScale` (shared press-scale interaction) and staggered entrance fades on grids/lists.
  Restrained - no decorative/continuous animation.
- **Icons**: Feather (`@expo/vector-icons`) for all UI chrome. Category imagery is real photography
  (`src/utils/categoryVisuals.ts`), not icons - see Known Limitations.

## Known limitations (genuine, not deferred silently)

- **UPI payments cannot succeed against the current backend.** `PNBGateway.initiate_payment` is an
  intentional placeholder (Phase 14) that always raises `NotImplementedError`. The app handles
  this honestly (see `app/checkout/index.tsx`'s payment-failure recovery state) rather than faking
  success - COD is the only payment method that can currently complete an order end-to-end.
- **Categories have no image field in the backend** (`app/models/category.py`), and products have
  no subcategory/department field. `src/utils/categoryVisuals.ts` maps each category to a real
  photo (hashed fallback for any category added later); `src/utils/categoryDepartments.ts` groups
  each category's real products into hand-curated "department" tiles for the Categories screen.
  The grouping and photography are a client-side presentation layer - every product and count
  shown is real, and every department slug list exactly partitions its category's real catalog.
- **Profile editing and password reset do not exist** - the backend has no corresponding endpoints
  (profile update, password reset), and neither was fabricated. Login's "Forgot password?" link
  routes to Support rather than a fake reset flow. See the Phase 20 report's Post-MVP Backlog.
- **No MRP/discount pricing.** `PriceTag` supports an optional struck-through MRP, but the backend
  has no MRP field - only a single current price. `src/utils/productEmbellishments.ts` supplies an
  illustrative MRP (and Marathi name/origin/ETA) per product, purely for presentation, clearly
  separated from real backend data - every price shown is real, and MRP never fabricates a discount
  larger than that illustrative value.
