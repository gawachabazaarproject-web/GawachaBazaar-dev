# Gawacha Bazaar - Admin Panel

Next.js (App Router) + Tailwind internal tool for staff. It signs in with Firebase, talks to the
FastAPI backend, and shows each person only the pages their role allows. All rules are enforced
by the backend; the UI hides what you cannot use. System overview:
[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md); features: [../docs/FEATURES.md](../docs/FEATURES.md).

## Running

```bash
cd Admin
cp .env.example .env.local     # API base URL + Firebase web config (public identifiers)
npm install
npm run dev                    # http://localhost:3001
npx tsc --noEmit               # type-check
```

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend, default `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_FIREBASE_*` | Firebase web app config (API key, auth domain, project id, ...) |

The first admin account is created on the backend with `python scripts/create_admin.py`.

## Structure

```text
Admin/
├── app/
│   ├── login/                       Firebase sign-in
│   └── (admin)/                     authenticated area (layout wraps AdminShell)
│       ├── dashboard/  orders/[id]/  products/(new,[id])  categories/(new,[id])
│       ├── inventory/[id]  promotions/(new,[id])  customers/[id]  delivery/  payments/[id]
│       ├── content/ (home slides)  ads/  settings/ (packing point)  staff/  audit-log/
│       └── reports/  reviews/       placeholders
├── components/                      AdminShell (sidebar + header), PageHeader, EmptyState,
│                                    ImageDropzone, dialogs, NewOrderAlarm, status badges
└── lib/                             auth-context, api, realtime-context, permissions,
                                     one typed client per module (orders, products, inventory, ads, ...)
```

## How it works

- **Auth** (`lib/auth-context.tsx`): Firebase `onIdTokenChanged` keeps the ID token current;
  the profile is loaded from `/auth/me` (linking the account via `/auth/sync` when needed) and
  accounts without an admin role are signed out. The token is also refreshed on tab focus,
  network reconnect and every 5 minutes, because browsers throttle background tabs and an
  hour-old token would otherwise fail with "Your session has expired".
- **Permissions** (`lib/permissions.ts`): a hand-kept mirror of `backend/app/core/permissions.py`
  used only to filter the sidebar and buttons. Keep it in sync by hand; the backend always
  re-checks.
- **Realtime** (`lib/realtime-context.tsx`): one WebSocket to `/api/v1/ws/events`. Components
  subscribe with `useOrderEvents`. It drives the new-order alarm, live lists, and the pending
  orders count bubble on the sidebar Orders item.
- **Images**: uploaded through the backend (Cloudinary). Ads are validated client-side to
  **1200 x 500 px (12:5)** (`AD_IMAGE`, `validateAdImage` in `lib/ads.ts`) to match the mobile card.
- **Settings -> Packing point**: lists active warehouses; set a warehouse's latitude/longitude
  (paste "lat, lng" from Google Maps or use current location), then "Use as packing point".
  Delivery fees are measured by road from that warehouse.

## Adding a page

1. Add the typed API client in `lib/<module>.ts` (follow `lib/ads.ts`).
2. Add `app/(admin)/<module>/page.tsx` using `PageHeader`, `EmptyState`, `TableSkeleton`.
3. Add the nav entry in `components/AdminShell.tsx` with the permission that gates it.
4. Make sure the backend route uses the same permission via `require_permission(...)`.
