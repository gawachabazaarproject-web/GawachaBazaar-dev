# Product Requirements Document (reverse-engineered)

> **Status:** Partially verified. **Last verified:** 2026-10-14.
> **Read this first:** the repository contains **no product requirements document, roadmap, or decision log**. This PRD is **reconstructed from the implemented system** and the existing docs ([`README.md`](../../README.md), [`FEATURES.md`](../FEATURES.md), [`deploy/README.md`](../../deploy/README.md)). Facts are labelled; goals, metrics and priorities that nobody wrote down are listed as **open questions**, not invented.

## 1. Purpose and context

*Stated in the README:* Gawacha Bazaar is a farm-to-home fresh-food marketplace for Nagpur: customers order vegetables, fruit and groceries on a mobile app, staff run the business from an Admin panel, and one backend owns every rule, price and state change.

*Evident from the code:* the product sells loose produce in several pack sizes, delivers from a single packing warehouse with a distance-based fee, accepts cash on delivery and Razorpay payments, and has a wholesale (bulk quote) path. Product names can carry Marathi/Devanagari text, and suppliers/farms/batches are tracked for traceability ([`models/farm.py`](../../backend/app/models/farm.py), [`batch.py`](../../backend/app/models/batch.py), [`quality_check.py`](../../backend/app/models/quality_check.py) — the farm/quality-check tables exist, but no route uses them; see [CATALOG](../05-domains/CATALOG.md) / [INVENTORY](../05-domains/INVENTORY.md)).

## 2. Users and jobs to be done (inferred from the role model)

| User | Job | Where |
|---|---|---|
| Household customer | Choose fresh items, see the price and delivery fee, pay online or in cash, track delivery, cancel or get a refund | Mobile app |
| Wholesale / business buyer | Request bulk quantities, review a quote, accept | Mobile app wholesale mode |
| Operations / hub staff | Receive stock, keep stock accurate, pick and pack, assign deliveries | Admin panel |
| Delivery partner | See assigned deliveries, mark out-for-delivery and delivered, collect cash | Admin panel (restricted view) |
| Support agent | Look up a customer and their orders | Admin panel (read-only) |
| Admin / owner | Everything above plus catalogue, pricing, promotions, content, refunds, staff, settings, audit | Admin panel |

## 3. Scope

**In scope today (implemented):** see [FUNCTIONAL_REQUIREMENTS](FUNCTIONAL_REQUIREMENTS.md) — catalogue, ordering (COD and online), inventory and reservation, fulfilment and delivery, refunds, promotions/offers, bulk quotes, push notifications, realtime staff alerts, audit log, customer and staff management.

**Present but incomplete:** Admin Reports and Reviews (placeholders); `WHOLESALER` role (no dedicated capability); Bazaar+ (eligibility flag only, no benefit); farm/quality-check tables (no API).

**Out of scope / absent (verified):** customer reviews, in-app chat support, email/SMS sent by the platform, iOS distribution evidence, multi-city or multi-warehouse routing (delivery distance is measured from exactly one packing point), multiple currencies (INR only), saved payment methods, order edits after placement, partial delivery or substitution (fulfilment is all-or-nothing and strictly forward).

## 4. Product rules that shape the experience (all implemented; details in [BUSINESS_RULES](../05-domains/BUSINESS_RULES.md))

1. A basket with 15+ different products ships free; otherwise Rs 20 + Rs 10 per whole km of road distance, minimum 1 km (capped at 30 km). *(Defaults; configurable; base fee Rs 20 confirmed by the owner 2026-10-27.)*
2. Stock is held for 30 minutes at checkout; unpaid holds expire automatically.
3. Online orders are created only after the payment is confirmed; if the order cannot be placed the money is refunded automatically.
4. Orders can be cancelled until delivery; refunds for paid online orders need explicit admin approval.
5. Staff mutations are recorded for audit (no general viewer yet); staff see only what their role permits.
6. The backend decides every price, fee, discount and status; the apps display.

## 5. Success measures

**Not defined in the repository.** No analytics SDK, KPI dashboard definition or target was found. The only business metrics computed in code are operational (dashboard tiles: orders, revenue, unpicked orders, low stock, delivery issues — [`dashboard.py`](../../backend/app/services/dashboard.py)).

## 6. Assumptions (stated so they can be challenged)

- Single-city, single-warehouse operation (derived from the single packing point and Nagpur-specific copy).
- A small operations team using the Admin panel in a browser during working hours (derived from the realtime alarm and queue-style pages; not stated).
- COD remains a first-class payment method (derived from the COD collection logic at delivery).

## 7. Open questions for the product owner

1. Intended launch date, traffic expectations and growth plan (drives capacity work — [NON_FUNCTIONAL_REQUIREMENTS](NON_FUNCTIONAL_REQUIREMENTS.md)).
2. Which deployment is the production system (Contabo VPS compose or AWS)? ([DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md))
3. What should Bazaar+ actually give a customer? What should the `WHOLESALER` role be able to do?
4. Should reviews, reports, farm traceability (farm/quality checks) and in-app support be built, and in what order? ([ROADMAP](../10-project-management/ROADMAP.md))
5. Refund policy (automatic vs approval-gated; partial refunds) and cancellation window beyond "before delivery".
6. Data retention and customer data deletion expectations ([DATA_RETENTION](../04-database/DATA_RETENTION.md), [PRIVACY](../08-security/PRIVACY.md)).
