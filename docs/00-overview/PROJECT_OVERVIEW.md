# Project Overview

> **Status:** Verified (product description from [`README.md`](../../README.md) and [`docs/FEATURES.md`](../FEATURES.md), re-checked against the code on 2026-10-14). Business motivation beyond what the repository states is **not** asserted here.

## What it is

Gawacha Bazaar is a farm-to-home fresh-food marketplace for **Nagpur, India**. It consists of:

- a **customer mobile app** (Android build via EAS; iOS config exists but no iOS build evidence) for browsing, wishlist, cart, checkout, orders and bulk requests;
- an **Admin panel** (web) where staff manage orders, products, inventory, delivery, payments/refunds, promotions, content, customers and staff;
- a **FastAPI backend** that holds every business rule;
- a **promo website** (marketing pages only; it makes no API calls — no `process.env`/fetch usage was found in `website/`).

## Who uses it

| Audience | Uses | Notes |
|---|---|---|
| Customers | Mobile app | Sign in with email+password, Google or phone OTP (all via Firebase) |
| Admin / operations / hub staff / support / delivery partners | Admin panel (web) | Access is restricted to staff roles; each role sees only permitted pages ([USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md)) |
| Wholesale buyers | Mobile app "wholesale" mode (bulk request → quote) | Implemented through the `CUSTOMER` role; the `WHOLESALER` role exists but grants no extra endpoint ([USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md)) |

## What the product does today (verified in code)

- **Catalogue:** categories (one nesting level), products with multiple sizes ("variants"), time-ranged prices, images on Cloudinary.
- **Ordering:** server-owned cart; checkout with address, optional promo code, delivery fee; **Cash on Delivery** or **online payment through Razorpay**.
- **Delivery fee and the "Bazaar" offer:** free delivery for baskets with 15+ *different products*; otherwise base fee plus a per-km charge by road distance from the packing point ([DELIVERY.md](../05-domains/DELIVERY.md)). "Bazaar+" tracks six Bazaar orders per calendar month.
- **Stock:** lots per warehouse, FIFO allocation at checkout, 30-minute reservation, consumption on delivery, reserve levels and alerts ([INVENTORY.md](../05-domains/INVENTORY.md)).
- **Fulfilment:** picking → packed → ready → assigned to a delivery partner → out for delivery → delivered; COD cash is recorded as collected at delivery.
- **Cancellation and refunds:** customers or admins cancel before delivery; paid online orders create a refund request that an admin approves and processes ([REFUNDS.md](../05-domains/REFUNDS.md)).
- **Promotions and offers:** rule-based discounts, targeting, usage limits, and a carousel of live offers.
- **Bulk commerce:** request → versioned quotes → accept → convert to an order.
- **Operations tooling:** realtime new-order alarm (WebSocket), admin actions recorded for audit (read back only through product/category activity feeds), dashboards, push notifications to customers (Expo push).

Complete feature-by-audience list: [`docs/FEATURES.md`](../FEATURES.md) (with corrections noted in [AI_STATUS](AI_STATUS.md)); requirements view: [FUNCTIONAL_REQUIREMENTS](../01-requirements/FUNCTIONAL_REQUIREMENTS.md).

## What is not built (verified)

Admin **Reports**, **Reviews** and **Audit Log** pages are placeholders (19-line empty-state pages; the `reviews.*`, `reports.read` and `audit.read` permissions exist; no review domain exists in the backend, and although admin actions are *recorded* in `admin_action_logs`, no general API or page reads them). Customer reviews, in-app chat support and email/SMS sending by the platform do not exist. Order-tracker per-step times (confirmed, preparing, out for delivery) are not recorded. Details: [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md), [ROADMAP](../10-project-management/ROADMAP.md).

## Maturity

The backend has a large automated suite (see [AI_STATUS](AI_STATUS.md) for the latest recorded run) and an independent QA audit under [`docs/testing/`](../testing). The frontends have **no** automated tests, CI does not gate deployment, and the deployment target is described three different ways in the repository. Anything beyond that — launch readiness, traffic expectations, SLAs — is not stated in the repository; see [PRODUCTION_READINESS](../10-project-management/PRODUCTION_READINESS.md) for the evidence-based checklist.
