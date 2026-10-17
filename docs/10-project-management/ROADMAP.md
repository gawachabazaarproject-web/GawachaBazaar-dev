# Roadmap

> **Status:** Verified as a list of **stated intents found in the repository**, 2026-10-14. **The repository contains no roadmap, release plan, milestone, owner or deadline, and none is invented here.** Every row below cites where the intent is written (a code comment, UI copy, a doc). Whether any of it is still wanted, and in what order, is for the product owner ([PRD](../01-requirements/PRD.md) open questions). Evidence-based engineering work is in [TASKS](TASKS.md); defects are in [KNOWN_ISSUES](KNOWN_ISSUES.md).

Status vocabulary: **Placeholder** (UI/permission exists, feature does not) · **Planned** (stated as future work) · **Deferred** (explicitly postponed) · **Proposed** (suggested in the QA audit, not a product decision).

## Product capabilities

| Item | Source of intent | State today | Notes |
|---|---|---|---|
| Customer **reviews** and admin review moderation | `permissions.py` (`reviews.*` "stay stable across the phase that adds it"), Admin Reviews page copy | Placeholder — no model, no endpoints | – |
| **Reports** (analytics) | Admin Reports placeholder, `reports.read` | Placeholder — only the dashboard tiles exist | – |
| **Unified audit log** (viewer + API) | Admin Audit Log page text ("Phase 22 adds a unified audit-log domain") | Records are written (47 actions); no reader | [ADMIN_OPERATIONS](../05-domains/ADMIN_OPERATIONS.md) |
| **Bazaar+ benefits**: free delivery on every order, priority delivery slots, members-only prices, early access, monthly surprise | `mobile/app/bazaar/index.tsx` (`UPCOMING_BENEFITS`) | Planned (marketing copy) — only eligibility is computed | [DELIVERY](../05-domains/DELIVERY.md) |
| **Delivery/harvest slot** as a real feature | Checkout picker exists as illustrative UI | Placeholder — not sent to the backend | [CART_AND_CHECKOUT](../05-domains/CART_AND_CHECKOUT.md) |
| **Featured/seasonal merchandising** fields and a `products.manage_merchandising` permission | `permissions.py` comment ("will be added alongside that backend work") | Planned | – |
| **`SUPER_ADMIN`** role above ADMIN | `permissions.py` ("explicitly deferred") | Deferred | – |
| **Farmer / farm** roles and farm traceability | `core/roles.py` ("Farmer/Farm are future capabilities"), `farms`/`quality_checks` tables | Planned — tables exist, no API | [INVENTORY](../05-domains/INVENTORY.md) |
| Per-step **order timestamps** (confirmed, picking, out-for-delivery) | `FEATURES.md` §4 | Not built | [ORDERS](../05-domains/ORDERS.md) |
| **Email/SMS** from the platform, in-app chat support | `FEATURES.md` §4, `deploy/README.md` ("No email or SMS is sent by the platform") | Not built | – |
| Real **support contact** in the app | `deploy/README.md` checklist, `support.tsx` comment | Pending | – |
| iOS distribution | iOS identifiers in `app.json`; no iOS project/build evidence | Unknown | – |
| Wholesale/`WHOLESALER` experience | Role seeded, wholesale mode in the app | Partial — works through `CUSTOMER` | [BULK_ORDERS](../05-domains/BULK_ORDERS.md) |

## Platform and operations

| Item | Source of intent | State | Notes |
|---|---|---|---|
| **Horizontal scaling** (Redis or PostgreSQL-based shared rate limiter and event fan-out; single scheduled sweep) | `docs/ARCHITECTURE.md` §10, `rate_limit.py`/`realtime.py` docstrings, [MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md) | Proposed — current design requires one process | Audit found PostgreSQL-only remedies suffice |
| **CI quality gate** before deploy | [TEST_STRATEGY](../testing/TEST_STRATEGY.md) "Release gates recommended" | Proposed | [QUALITY_GATES](../07-testing/QUALITY_GATES.md) |
| **Frontend test suites** (Playwright for web, jest-expo/Maestro for the app) | `TEST_STRATEGY.md` | Proposed | – |
| **Firebase App Check** (Play Integrity), blocking functions | `deploy/FIREBASE_AUTH.md` ("Recommended… once traffic grows") | Planned | – |
| Strict **CSP** for Admin/website | `Admin/next.config.mjs` ("documented follow-up") | Deferred | – |
| Self-hosted/paid **routing** instead of the public OSRM demo | `config.py` comment | Planned | – |
| **Off-server backups** and a tested restore | `deploy/README.md` checklist | Pending | [BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md) |
| Live **Razorpay** keys, ₹1 real payment/refund test | `deploy/README.md` checklist | Pending (state unknown) | – |
| Updating Firebase when an admin edits a customer's email/phone | `FEATURES.md` "known gaps" | Open | [AUTHENTICATION](../05-domains/AUTHENTICATION.md) |
| AI-assisted-engineering risk research document | `docs/testing/RISK_REGISTER.md` R-22 ("not yet produced") | Not started | – |

## What this roadmap deliberately does not say

No sequencing, quarters, owners, effort commitments, launch dates or success metrics — none are recorded in the repository. If the owner provides them, record them here with a date and source.
