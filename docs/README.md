# Gawacha Bazaar — Documentation

> **Status:** created 2026-10-14 from a systematic inspection of the repository; each document states its own evidence and verification status. Start here, then follow the reading order for your role. For the product in one paragraph see the root [README](../README.md).

## Overview

Gawacha Bazaar is a farm-to-home fresh-food marketplace for Nagpur: a React Native (Expo) customer app, a Next.js Admin panel, a promo website and a FastAPI + PostgreSQL backend that owns every rule. This documentation set explains what exists, how it works, how to run, test, secure, deploy and extend it, and — equally important — where the repository disagrees with itself or is unverified. Documents are **evidence-linked**: they cite real files, routes, tables, variables and commands, and say "unknown" instead of guessing.

## Suggested reading order

**New developer:** [PROJECT_OVERVIEW](00-overview/PROJECT_OVERVIEW.md) → [AI_PROJECT_CONTEXT](00-overview/AI_PROJECT_CONTEXT.md) → [PROJECT_STRUCTURE](00-overview/PROJECT_STRUCTURE.md) → [LOCAL_SETUP](06-development/LOCAL_SETUP.md) → [SYSTEM_ARCHITECTURE](02-architecture/SYSTEM_ARCHITECTURE.md) → [DATA_FLOW](02-architecture/DATA_FLOW.md) → [BUSINESS_RULES](05-domains/BUSINESS_RULES.md) → the domain you will touch → [TESTING_GUIDE](07-testing/TESTING_GUIDE.md) → [CODING_STANDARDS](06-development/CODING_STANDARDS.md) → [KNOWN_ISSUES](10-project-management/KNOWN_ISSUES.md).

**AI coding agent:** [AGENTS.md](../AGENTS.md) → [AI_PROJECT_CONTEXT](00-overview/AI_PROJECT_CONTEXT.md) → [AI_STATUS](00-overview/AI_STATUS.md) → the relevant `05-domains/` document and [API_REFERENCE](03-api/API_REFERENCE.md) / [DATABASE_SCHEMA](04-database/DATABASE_SCHEMA.md) → the source files they cite → [TESTING_GUIDE](07-testing/TESTING_GUIDE.md) before changing anything. Security-sensitive work: also [SECURITY](08-security/SECURITY.md) and [SECRETS_MANAGEMENT](08-security/SECRETS_MANAGEMENT.md).

**Operator / owner:** [PRODUCTION_READINESS](10-project-management/PRODUCTION_READINESS.md) → [DEPLOYMENT](09-deployment-operations/DEPLOYMENT.md) → [INCIDENT_RESPONSE](09-deployment-operations/INCIDENT_RESPONSE.md) → [BACKUP_AND_RECOVERY](09-deployment-operations/BACKUP_AND_RECOVERY.md) → [KNOWN_ISSUES](10-project-management/KNOWN_ISSUES.md) → [TASKS](10-project-management/TASKS.md).

## Index

| Folder | Documents |
|---|---|
| [00-overview](00-overview) | [AI_PROJECT_CONTEXT](00-overview/AI_PROJECT_CONTEXT.md) (map for agents) · [AI_STATUS](00-overview/AI_STATUS.md) (current state) · [PROJECT_OVERVIEW](00-overview/PROJECT_OVERVIEW.md) · [PROJECT_STRUCTURE](00-overview/PROJECT_STRUCTURE.md) · [GLOSSARY](00-overview/GLOSSARY.md) |
| [01-requirements](01-requirements) | [PRD](01-requirements/PRD.md) · [FUNCTIONAL_REQUIREMENTS](01-requirements/FUNCTIONAL_REQUIREMENTS.md) · [NON_FUNCTIONAL_REQUIREMENTS](01-requirements/NON_FUNCTIONAL_REQUIREMENTS.md) · [USER_ROLES_AND_PERMISSIONS](01-requirements/USER_ROLES_AND_PERMISSIONS.md) |
| [02-architecture](02-architecture) | [SYSTEM_ARCHITECTURE](02-architecture/SYSTEM_ARCHITECTURE.md) · [DATA_FLOW](02-architecture/DATA_FLOW.md) · [ARCHITECTURE_DECISIONS](02-architecture/ARCHITECTURE_DECISIONS.md) · [ERROR_HANDLING](02-architecture/ERROR_HANDLING.md) |
| [03-api](03-api) | [API_REFERENCE](03-api/API_REFERENCE.md) (generated) · [API_CONVENTIONS](03-api/API_CONVENTIONS.md) · [WEBHOOKS](03-api/WEBHOOKS.md) |
| [04-database](04-database) | [DATABASE_SCHEMA](04-database/DATABASE_SCHEMA.md) (generated) · [ENTITY_RELATIONSHIPS](04-database/ENTITY_RELATIONSHIPS.md) · [MIGRATIONS](04-database/MIGRATIONS.md) · [DATA_RETENTION](04-database/DATA_RETENTION.md) |
| [05-domains](05-domains) | [BUSINESS_RULES](05-domains/BUSINESS_RULES.md) · [AUTHENTICATION](05-domains/AUTHENTICATION.md) · [CATALOG](05-domains/CATALOG.md) · [INVENTORY](05-domains/INVENTORY.md) · [CART_AND_CHECKOUT](05-domains/CART_AND_CHECKOUT.md) · [ORDERS](05-domains/ORDERS.md) · [PAYMENTS](05-domains/PAYMENTS.md) · [REFUNDS](05-domains/REFUNDS.md) · [DELIVERY](05-domains/DELIVERY.md) · [PROMOTIONS](05-domains/PROMOTIONS.md) · [BULK_ORDERS](05-domains/BULK_ORDERS.md) · [ADMIN_OPERATIONS](05-domains/ADMIN_OPERATIONS.md) · [NOTIFICATIONS](05-domains/NOTIFICATIONS.md) |
| [06-development](06-development) | [LOCAL_SETUP](06-development/LOCAL_SETUP.md) · [ENVIRONMENT_VARIABLES](06-development/ENVIRONMENT_VARIABLES.md) · [CODING_STANDARDS](06-development/CODING_STANDARDS.md) · [GIT_WORKFLOW](06-development/GIT_WORKFLOW.md) · [DEPENDENCY_MANAGEMENT](06-development/DEPENDENCY_MANAGEMENT.md) |
| [07-testing](07-testing) | [TESTING_GUIDE](07-testing/TESTING_GUIDE.md) · [TEST_DATA](07-testing/TEST_DATA.md) · [QUALITY_GATES](07-testing/QUALITY_GATES.md) (strategy: see below) |
| [08-security](08-security) | [SECURITY](08-security/SECURITY.md) · [THREAT_MODEL](08-security/THREAT_MODEL.md) · [SECRETS_MANAGEMENT](08-security/SECRETS_MANAGEMENT.md) · [PRIVACY](08-security/PRIVACY.md) |
| [09-deployment-operations](09-deployment-operations) | [DEPLOYMENT](09-deployment-operations/DEPLOYMENT.md) · [MONITORING_AND_LOGGING](09-deployment-operations/MONITORING_AND_LOGGING.md) · [INCIDENT_RESPONSE](09-deployment-operations/INCIDENT_RESPONSE.md) · [BACKUP_AND_RECOVERY](09-deployment-operations/BACKUP_AND_RECOVERY.md) · [ROLLBACK](09-deployment-operations/ROLLBACK.md) |
| [10-project-management](10-project-management) | [ROADMAP](10-project-management/ROADMAP.md) · [TASKS](10-project-management/TASKS.md) · [KNOWN_ISSUES](10-project-management/KNOWN_ISSUES.md) · [PRODUCTION_READINESS](10-project-management/PRODUCTION_READINESS.md) |
| [11-integrations](11-integrations) | [THIRD_PARTY_SERVICES](11-integrations/THIRD_PARTY_SERVICES.md) · [INTEGRATION_CONTRACTS](11-integrations/INTEGRATION_CONTRACTS.md) |
| [_tools](_tools) | scripts that regenerate the two generated references ([README](_tools/README.md)) |
| Pre-existing (kept) | [ARCHITECTURE.md](ARCHITECTURE.md) and [FEATURES.md](FEATURES.md) (broad overviews, corrected 2026-10-14) · [testing/](testing) (the QA audit: [TEST_STRATEGY](testing/TEST_STRATEGY.md), [BASELINE_AUDIT](testing/BASELINE_AUDIT.md), [DEFECT_LOG](testing/DEFECT_LOG.md), [RISK_REGISTER](testing/RISK_REGISTER.md), [MULTI_REPLICA_ANALYSIS](testing/MULTI_REPLICA_ANALYSIS.md), [PERFORMANCE_RESULTS](testing/PERFORMANCE_RESULTS.md), [SEC001_REVIEW](testing/SEC001_REVIEW.md), evidence files) · [manual_testing/USER_MANUAL_TEST_SCENARIOS.md](manual_testing/USER_MANUAL_TEST_SCENARIOS.md) |
| Elsewhere in the repo | [../backend/README.md](../backend/README.md), [../backend/docs/](../backend/docs) (historical per-phase docs), [../Admin/README.md](../Admin/README.md), [../mobile/README.md](../mobile/README.md), [../deploy/README.md](../deploy/README.md), [../deploy/FIREBASE_AUTH.md](../deploy/FIREBASE_AUTH.md) |

## Authoritative sources

When documents disagree, prefer in this order: **executable code and database constraints → migrations → tests → configuration files → these documents → older READMEs and `backend/docs/`.**

| Question | Authority |
|---|---|
| What endpoints exist and who may call them | `app.openapi()` / [`backend/app/api/v1/`](../backend/app/api/v1) → [API_REFERENCE](03-api/API_REFERENCE.md); access snapshot [`backend/tests/authz_golden.json`](../backend/tests/authz_golden.json) |
| What tables/constraints exist | SQLAlchemy models + Alembic head → [DATABASE_SCHEMA](04-database/DATABASE_SCHEMA.md) |
| Business rules and state machines | [`backend/app/services/`](../backend/app/services) (`*_state.py`) → [BUSINESS_RULES](05-domains/BUSINESS_RULES.md) |
| Configuration | [`backend/app/core/config.py`](../backend/app/core/config.py) → [ENVIRONMENT_VARIABLES](06-development/ENVIRONMENT_VARIABLES.md) |
| Roles and permissions | [`backend/app/core/permissions.py`](../backend/app/core/permissions.py), [`roles.py`](../backend/app/core/roles.py) (not `Admin/lib/permissions.ts`, a UI mirror) |
| Test status | a fresh run ([TESTING_GUIDE](07-testing/TESTING_GUIDE.md)); recorded run in [AI_STATUS](00-overview/AI_STATUS.md) |
| What is deployed | the hosting providers' dashboards (not in the repository) — see [DEPLOYMENT](09-deployment-operations/DEPLOYMENT.md) |
| Known defects and findings | [KNOWN_ISSUES](10-project-management/KNOWN_ISSUES.md); details in [`testing/DEFECT_LOG.md`](testing/DEFECT_LOG.md) |

## Status conventions

Each document carries a status line using these terms consistently:

| Status | Meaning |
|---|---|
| **Verified** | Confirmed in source **and**, where behaviour is runtime-dependent, exercised by something that ran (a passing test, an observed run, a generated cross-check). The document says what was run |
| **Partially verified** | Source read, but only indirectly tested, tested only against fakes, or only some claims checked |
| **Unverified** | Present in source/docs but not run or checked (instructions marked *Unverified* may still be right) |
| **Planned** | Stated as future work somewhere in the repository; not implemented |
| **Placeholder** | A page/permission/table exists but the feature does not |
| **Deprecated** | Superseded but still present (e.g. the unwired `PNBGateway`, legacy password migration) |
| **Unknown / requires investigation** | Cannot be decided from the repository (e.g. which deployment is live) |

Domain tables use *Implemented and verified / Implemented but not verified / Partially implemented / Planned / Deprecated / Unknown* in the same sense. A "Last verified" date means the author actually checked the document against the source on that date — not that the feature works in production.

## Omitted or merged documents

| Reference-structure file | Decision |
|---|---|
| `07-testing/TEST_STRATEGY.md` | **Not duplicated.** An evidence-based strategy already exists at [`docs/testing/TEST_STRATEGY.md`](testing/TEST_STRATEGY.md) (with risk register, defect log, baseline audit); [TESTING_GUIDE](07-testing/TESTING_GUIDE.md) is the practical complement |
| `05-domains/*` | Created for all eleven listed domains; **added** [PROMOTIONS](05-domains/PROMOTIONS.md) and [BULK_ORDERS](05-domains/BULK_ORDERS.md) because they are real, non-trivial domains in the code. Suppliers, packaging and reservations are covered inside [INVENTORY](05-domains/INVENTORY.md) |
| `03-api/WEBHOOKS.md` | Kept: there is exactly one inbound webhook (Razorpay) and no outbound webhooks — the document says so |
| Domains that do **not** exist | Reviews, reports, farm traceability management, in-app chat, email/SMS: documented as absent/placeholder in [ROADMAP](10-project-management/ROADMAP.md) and [FUNCTIONAL_REQUIREMENTS](01-requirements/FUNCTIONAL_REQUIREMENTS.md), never as implemented |
| `_tools/` | Added to make the two generated references reproducible |

## Keeping the documentation current

1. **Change code → change the document.** A change to a route, model, state machine, permission, environment variable or deployment file must update the matching document in the same commit.
2. **Regenerate the generated references** after router/model/migration changes ([_tools/README](_tools/README.md)); then run the test suite and `alembic check`.
3. **Update [AI_STATUS](00-overview/AI_STATUS.md)** when test status, blockers, priorities or the working-tree situation change; update [KNOWN_ISSUES](10-project-management/KNOWN_ISSUES.md) when you find or fix an issue.
4. **Don't copy secrets, `.env` files or customer data** into the docs. Use names and placeholders ([SECRETS_MANAGEMENT](08-security/SECRETS_MANAGEMENT.md)).
5. **Say what you verified.** Record the command and date; mark anything else *Unverified*. Don't change a "Last verified" date unless you re-checked the document.
6. **Fix contradictions at the source.** If a doc and the code disagree, investigate, fix whichever is wrong, and note the discrepancy in KNOWN_ISSUES rather than silently picking one.
7. Remove or correct stale comments and READMEs you find (several are listed in KNOWN_ISSUES DOC-1).
