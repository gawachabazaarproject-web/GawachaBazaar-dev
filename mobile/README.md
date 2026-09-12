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
cp .env.example .env   # then edit EXPO_PUBLIC_API_BASE_URL - see comments in the file
npm run android         # or: npm run ios / npm run web
```

The backend must be running and reachable from your device/emulator - see the root
`docker-compose.yml` or `backend/README.md`. `.env.example` documents the right
`EXPO_PUBLIC_API_BASE_URL` for the Android emulator, iOS simulator, and a physical device.

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
│   ├── _layout.tsx          # Root: providers, fonts, splash
│   └── _appGate.tsx         # Auth/onboarding redirect logic (not a route - `_`-prefixed)
├── src/
│   ├── api/                 # The ONE HTTP layer - axios client, auth/refresh, per-domain modules
│   ├── components/          # Reusable UI primitives (Button, ProductCard, Skeleton, ...)
│   ├── features/            # Domain hooks (TanStack Query) grouped by feature
│   ├── store/                # Small global state (zustand): auth session, toast
│   ├── theme/                # Design tokens - colors, type scale, spacing, motion
│   ├── hooks/, utils/, types/
└── assets/                  # Placeholder app icons (see Known Limitations)
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

**One backend change was made to support this app**: `GET /catalog/products` gained an optional
`q` query parameter (case-insensitive name search) - the backend had no search capability at all
before Phase 20, and the brief explicitly permits "the smallest backend change if absolutely
necessary" for a genuine, confirmed gap. No other backend code was touched.

## Authentication

`expo-secure-store` (Keychain/Keystore-backed) is the only place access/refresh tokens are
persisted - never AsyncStorage. `src/store/authStore.ts` (zustand) owns session state
(`restoring` → `authenticated`/`unauthenticated`); `app/_appGate.tsx` reacts to it and to whether
the account has at least one saved address to decide between the auth screens, the one-time
address-onboarding screen, and the main tab experience.

## Design system

- **Color**: `src/theme/colors.ts` - a restrained deep-forest-green primary and warm terracotta
  accent, warm off-white background. Deliberately avoids generic "grocery green" and leaf/produce
  iconography.
- **Typography**: Inter only, four weights, one type scale (`src/theme/typography.ts`).
- **Spacing/radius**: fixed scales (`src/theme/spacing.ts`) - no ad hoc pixel values in screens.
- **Motion**: `src/theme/motion.ts` - two spring presets and three timing presets, used for
  add-to-cart, the cart bar, order success, and screen-level fades. No decorative/continuous
  animation.
- **Icons**: Feather (`@expo/vector-icons`) exclusively, one family throughout.

## Known limitations (genuine, not deferred silently)

- **App icon/splash/brand imagery are Expo's generic placeholders.** No real GawachaBazaar logo
  or icon assets exist in the repository yet; `src/components/Wordmark.tsx` is a text-based
  stand-in used on the login/register screens until real brand assets are provided.
- **UPI payments cannot succeed against the current backend.** `PNBGateway.initiate_payment` is an
  intentional placeholder (Phase 14) that always raises `NotImplementedError`. The app handles
  this honestly (see `app/checkout/index.tsx`'s payment-failure recovery state) rather than faking
  success - COD is the only payment method that can currently complete an order end-to-end.
- **No GPS-assisted address entry.** Addresses are entered manually only; there is no reverse-geocoding
  provider configured, and the brief explicitly permits GPS to be optional.
- **Profile editing, password reset, and a combined offers/promotions section do not exist** - the
  backend has no corresponding endpoints (profile update, password reset) or concept (promotions),
  and none were fabricated. See the Phase 20 report's Post-MVP Backlog.
- **"Buy again" on Home is a lightweight recent-orders shortcut**, not a one-tap re-add-to-cart
  (the backend has no bulk re-order endpoint); full order contents and a manual re-add path are
  available from Order Details.
