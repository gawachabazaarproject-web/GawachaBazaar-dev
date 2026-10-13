# Gawacha Bazaar - Customer Mobile App

React Native 0.86 + Expo 57 (Expo Router, TypeScript) customer app for the Gawacha Bazaar
FastAPI backend. The app contains **no business rules**: prices, delivery fees, discounts and
every status transition (order, payment, fulfillment, refund) come from the backend; the app
only renders them. System overview: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md). Feature
list: [../docs/FEATURES.md](../docs/FEATURES.md).

## Running

```bash
cd mobile
npm install
npx expo start -c          # -c clears the Metro cache - use it after adding fonts/assets/packages
npm run android            # builds and runs the dev client (expo run:android)
```

- Firebase Auth and Google sign-in are **native modules**, so use the **dev client**
  (`expo-dev-client`, `npm run android`/`ios`), not Expo Go.
- In development the API base URL is derived from the Metro host
  (`Constants.expoConfig.hostUri`), so the backend on port 8000 on the same machine just works.
  Set `EXPO_PUBLIC_API_BASE_URL` to override it (standalone builds use the values in `eas.json`).
- Firebase and Google client IDs come from `EXPO_PUBLIC_FIREBASE_*` /
  `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` and `google-services.json`.
- Builds: `eas.json` defines `development`, `preview` (APK) and `production` profiles.

Type-check with `npx tsc --noEmit`.

## Structure

```text
mobile/
├── app/                      Expo Router routes (screens only)
│   ├── (auth)/               login, register, phone + OTP, verify-email, forgot-password, link-account
│   ├── (onboarding)/         first-time address setup
│   ├── (tabs)/               Home, Shop (categories), Search, Orders, Account
│   ├── product/[id].tsx      product detail
│   ├── category/[id].tsx     category listing
│   ├── cart/                 cart
│   ├── checkout/             checkout + success
│   ├── order/[id]/           order details, cancel, refund status
│   ├── wishlist.tsx          saved products
│   ├── address/              address book
│   ├── account/              profile, add-phone, settings, support
│   ├── bulk/                 bulk requests: review, list, detail, success
│   └── _layout.tsx           root: providers, fonts, splash, cart bar
├── src/
│   ├── api/                  the single HTTP layer: axios client + one module per domain
│   ├── auth/                 Firebase wrappers (native + web), error mapping, phone helpers
│   ├── components/           shared UI (ProductCard, CartBar, Skeleton, ...); home/, cart/, checkout/, payment/
│   ├── features/             TanStack Query hooks per domain: auth, address, bazaar, bulkOrders,
│   │                         cart, catalog, checkout, orders, payment, wishlist
│   ├── navigation/           AppGate: routes between auth / onboarding / main tabs
│   ├── store/                zustand: auth session, toast, wholesale mode + bulk draft
│   ├── theme/                design tokens: colors, typography, spacing, shadows, motion
│   ├── hooks/, utils/, types/
├── assets/                   icons, splash, artwork (order/orders hero art, product imagery)
├── plugins/                  Expo config plugins (Android release)
└── eas.json, app.json, app.config.js
```

## API layer

`src/api/client.ts` is the only axios instance. It attaches the **Firebase ID token**
(`Authorization: Bearer`) to every request. On `401 TOKEN_EXPIRED` it refreshes the token and
retries once (concurrent failures share one refresh) instead of signing the user out.
`src/api/errors.ts` turns every failure into one `ApiError` with a safe, user-facing message and
the backend's stable `code`. Domain modules (`authApi`, `addressApi`, `catalogApi`, `cartApi`,
`orderApi`, `paymentApi`, `wishlistApi`, `bazaarApi`, `bulkOrderApi`, `adsApi`, `homeSlidesApi`)
mirror the backend routes 1:1. `src/types/api.ts` is the hand-maintained TypeScript mirror of the
backend schemas - re-check it against `GET /openapi.json` when the backend changes.

Server state lives in TanStack Query. The cart and wishlist use **optimistic updates** with
rollback; Clear Cart, quantity steppers and hearts feel instant and recover on error.

## Authentication flow

Firebase handles sign-in (email + password, Google, phone OTP). `src/store/authStore.ts`
(zustand) holds the session; `AppGate` redirects between the auth screens, the one-time address
onboarding and the main tabs. After a Firebase sign-in the app loads `/auth/me`; if the backend
answers `ACCOUNT_NOT_REGISTERED` it calls `/auth/sync` and retries. Email/password accounts must
verify their email. See [../deploy/FIREBASE_AUTH.md](../deploy/FIREBASE_AUTH.md).

## Payments

Cash on Delivery or online via **Razorpay Checkout in a WebView**
(`src/components/payment/RazorpayCheckout.tsx`, with a web variant). The app only relays
Razorpay's result to the backend, which verifies the signature and re-checks the order; the app
never decides an order is paid. If the backend has no Razorpay keys, online payment shows a clear
"not available" message and COD still works. An unfinished payment can be completed from the order
page.

## Design system

- **Color** (`src/theme/colors.ts`): deep forest green primary, mustard-gold accent, warm cream
  background, plus tokens `surfaceTint` and `brandGreen` used by the order screens.
- **Typography** (`src/theme/typography.ts`): Bodoni Moda for headlines, Instrument Serif italic
  for script accents, Plus Jakarta Sans for body/UI, Lora for numerals, Baloo 2 for Devanagari
  (and the product-card names). Fonts are registered in `app/_layout.tsx` - add a font there
  and restart Metro with `-c`.
- **Spacing / radius / shadows / motion**: fixed scales in `src/theme`; no ad hoc pixel values
  for layout.
- **Icons**: Feather (`@expo/vector-icons`). Artwork (hero crates, order bag) lives in `assets/`.

## Notable screens

- **Home**: hero carousel from `/home-slides`, regular/wholesale toggle, brand-ads carousel
  (12:5 cards with brand name, title, subtitle and "See more" when the ad has a link), rails,
  Bazaar section with free-delivery and Bazaar+ progress.
- **Product detail**: gallery, variants, related products, sticky add footer with the floating
  cart pill above it.
- **Cart**: free-delivery progress, promo codes, delivery fee, optimistic Clear.
- **Orders tab**: stats, filter, order-ID search, order cards. **Order details**: status card,
  five-step tracker, items with photos, totals, payment, address, Reorder, Get help.
- **Account**: profile, saved addresses, Wishlist (with count bubble), orders, bulk requests,
  support, settings, log out.

## Known limitations

- Support is contact details only (no in-app chat); no push notifications.
- Order tracker shows real times only for placed and delivered; other steps have no timestamp.
- `src/utils/productEmbellishments.ts` supplies an illustrative MRP / Marathi name / origin /
  ETA per product purely for presentation - prices actually charged are always the backend's.
- Category photography/department grouping (`categoryVisuals.ts`, `categoryDepartments.ts`) is a
  client-side presentation layer over real catalog data.
- Order-level "Delivery fee" appears only when it is non-zero.
