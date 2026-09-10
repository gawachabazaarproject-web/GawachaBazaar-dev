# Gawacha Bazaar — Backend Application Architecture V1

## 1. Architecture Overview

Gawacha Bazaar is a production-grade, farm-to-home fresh food commerce platform. This document establishes the foundational application architecture for the FastAPI backend service following the completion of the 25-table database foundation (Phases 1–7).

The primary goal of this architecture checkpoint is to establish clean structural boundaries, standard conventions, transaction semantics, dependency injection patterns, request correlation, error formatting, and structured logging **without implementing business CRUD prematurely**.

```
HTTP Client (Mobile / Web / Admin / Delivery)
       │
       ▼
[ASGI Middleware: RequestIDMiddleware]
       │
       ▼
[FastAPI Router: /api/v1/...]
       │
       ▼
[FastAPI Dependencies: get_db, auth boundaries]
       │
       ▼
[Pydantic v2 Request Validation Schemas]
       │
       ▼
[Domain Services: Business Logic & Transactions]
       │
       ▼
[SQLAlchemy 2.0 ORM Models]
       │
       ▼
[PostgreSQL 16 Engine via psycopg 3]
       │
       ▼
[Pydantic v2 Response Serialization Schemas]
       │
       ▼
HTTP Response (with X-Request-ID header)
```

---

## 2. Modular Monolith Decision

Gawacha Bazaar adopts a **Modular Monolith** architecture.

### Rationale
- **Domain Cohesion**: The 7 core domains (Identity, Farm Traceability, Catalog, Inventory, Packaging, Commerce, Payments) share transactional boundaries and data models within PostgreSQL.
- **Operational Simplicity**: Avoids premature distributed complexity, network latency, multi-service deployment synchronization, and distributed transaction pitfalls (e.g. two-phase commit, saga orchestration) during early product evolution.
- **Strict Domain Boundaries**: Domains are structured with modular boundaries (isolated models, domain services, explicit schemas). This preserves future autonomy: any domain (e.g., Catalog, Inventory, or Payments) can be cleanly extracted into an independent microservice later if traffic or organizational scale warrants it.

---

## 3. Dependency Direction

All application layers adhere to a strict unidirectional dependency hierarchy:

$$\text{API Routes} \longrightarrow \text{Dependencies / Schemas} \longrightarrow \text{Domain Services} \longrightarrow \text{SQLAlchemy Models} \longrightarrow \text{Database Layer}$$

### Strict Invariants
1. **Higher layers depend on lower layers; lower layers NEVER depend on higher layers.**
2. **Database Models** know nothing about FastAPI, Pydantic schemas, HTTP routing, or domain services.
3. **Domain Services** know nothing about HTTP routes, status codes, query parameters, or FastAPI request objects. They operate purely on domain parameters, Pydantic schemas, and SQLAlchemy sessions.
4. **Schemas** know nothing about SQLAlchemy database connections or ORM session lifecycles.
5. **Routes** are thin coordinators: parsing input, invoking dependencies, delegating to domain services, and returning Pydantic response models.

---

## 4. Repository Directory Structure

```
backend/
├── alembic/                      # Alembic migrations (Phases 1-7 frozen)
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory, lifespan, root health checks
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py         # Central v1 router registry
│   │
│   ├── core/
│   │   ├── config.py             # pydantic-settings configuration
│   │   ├── logging.py            # Structured logging with RequestIDFilter
│   │   ├── request_id.py         # Request correlation middleware & ContextVar
│   │   └── security.py           # Argon2 password hashing & JWT primitives
│   │
│   ├── db/
│   │   ├── __init__.py           # Base, engine, SessionLocal exports
│   │   ├── base.py               # DeclarativeBase foundation
│   │   └── session.py            # Engine and SessionLocal factory
│   │
│   ├── dependencies/
│   │   ├── __init__.py           # Dependency exports
│   │   ├── auth.py               # Authentication & RBAC dependency boundaries
│   │   └── database.py           # Request-scoped get_db session dependency
│   │
│   ├── exceptions/
│   │   ├── __init__.py           # Exception exports
│   │   ├── base.py               # AppException hierarchy
│   │   └── handlers.py           # Uniform JSON exception handlers
│   │
│   ├── models/                   # 25 domain SQLAlchemy ORM models (Frozen)
│   │   ├── address.py
│   │   ├── batch.py
│   │   ├── cart.py
│   │   ├── cart_item.py
│   │   ├── category.py
│   │   ├── farm.py
│   │   ├── inventory_location.py
│   │   ├── inventory_lot.py
│   │   ├── order.py
│   │   ├── order_address.py
│   │   ├── order_item.py
│   │   ├── packaging_input.py
│   │   ├── packaging_operation.py
│   │   ├── packaging_output.py
│   │   ├── payment.py
│   │   ├── payment_transaction.py
│   │   ├── price.py
│   │   ├── product.py
│   │   ├── product_image.py
│   │   ├── product_variant.py
│   │   ├── quality_check.py
│   │   ├── role.py
│   │   ├── stock_movement.py
│   │   ├── user.py
│   │   └── user_role.py
│   │
│   ├── schemas/
│   │   ├── __init__.py           # Schema architecture conventions
│   │   └── base.py               # BaseSchema & shared response schemas
│   │
│   └── services/
│       └── __init__.py           # Domain service & transaction conventions
│
├── docs/
│   ├── architecture/
│   │   └── BACKEND_ARCHITECTURE_V1.md  # (This document)
│   └── database/                 # Phase 1-7 schema documentations
│
└── tests/
    ├── conftest.py               # Test engine & db_session fixture
    ├── test_architecture.py      # Architecture checkpoint test suite
    ├── test_config.py
    ├── test_exceptions.py        # Error contract test suite
    ├── test_health.py            # Health and liveness test suite
    ├── test_security.py          # Cryptographic hashing & token tests
    └── test_phase_[1-7]_models.py# Full database model verification
```

---

## 5. API Versioning

All business APIs reside under the versioned prefix:

```
/api/v1/<domain>
```

- Main application includes `api_router` from `app.api.v1.router` under `prefix="/api/v1"`.
- Domain routers (e.g. `auth_router`, `catalog_router`, `cart_router`, etc.) will be mounted inside `app/api/v1/router.py`.
- Root health endpoints are exempt from versioning to accommodate standard infrastructure health probes:
  - `GET /health` (service health and environment metadata)
  - `GET /health/db` (database connectivity probe)

---

## 6. Dependency Injection

FastAPI dependency injection (`Depends`) provides modular, testable request-scoped resource management:

### 1. Database Session (`get_db`)
Located in [database.py](file:///d:/Gawachabazaar/backend/app/dependencies/database.py):
```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
- A fresh, scoped session is opened per request.
- The session is guaranteed to be closed upon request exit, preventing connection leaks.
- In test environments, `app.dependency_overrides[get_db]` cleanly substitutes test or mock sessions.

### 2. Authentication Boundary (`get_current_user`)
Located in [auth.py](file:///d:/Gawachabazaar/backend/app/dependencies/auth.py):
- Serves as the architectural boundary for user token extraction, verification, and database user resolution.
- Explicitly documented as a future boundary to be implemented in Phase 8 (Authentication).
- Not wired into active routes in this checkpoint.

### 3. Authorization Boundary (`require_roles`)
Located in [auth.py](file:///d:/Gawachabazaar/backend/app/dependencies/auth.py):
- Higher-order dependency factory enforcing Role-Based Access Control (RBAC).
- To be implemented in Phase 9 (Authorization / RBAC).

---

## 7. Schema Conventions (Pydantic v2)

Located in [base.py](file:///d:/Gawachabazaar/backend/app/schemas/base.py) and `app/schemas/`:

1. **Separation of Concerns**: Pydantic schemas define the API contract; SQLAlchemy models define persistence. Schemas must never inherit from or wrap SQLAlchemy models directly.
2. **Configuration**: All schemas inherit from `BaseSchema` with:
   ```python
   model_config = ConfigDict(
       from_attributes=True,
       populate_by_name=True,
       str_strip_whitespace=True,
   )
   ```
3. **Immutability of Server-Controlled Fields**:
   Client request payloads (`CreateXRequest`, `UpdateXRequest`) must **never** accept:
   - `id`
   - `created_at`
   - `updated_at`
   - `password_hash`
   - or any internally computed status flags.
4. **Standard Schema Naming**:
   - `Create<Entity>Request`: Request body for entity creation.
   - `Update<Entity>Request`: Request body for entity update.
   - `<Entity>Response`: Response body for single entity return.
   - `<Entity>ListResponse`: Response body for lists/paginated collections.

---

## 8. Service Conventions & Transaction Boundaries

Located in [services/__init__.py](file:///d:/Gawachabazaar/backend/app/services/__init__.py):

### Service Design Principles
- Services are plain Python classes or modules focused on a cohesive business capability (e.g. `CheckoutService`, `InventoryService`).
- Services take `db: Session` as an explicit dependency.
- **NO Generic Frameworks**: We deliberately reject `GenericRepository`, `CRUDBase`, `BaseService`, and `UnitOfWork` abstractions. Explicit business logic takes precedence over generic boilerplate.

### Transaction Conventions
1. **Read Operations**: Simple queries execute within the request session without manual transaction wrappers.
2. **Multi-Write Workflows**: Workflows mutating multiple related records (e.g. order creation, inventory deduction, payment attempt) **own their transaction boundary**:
   ```python
   # Example pattern for multi-write business workflow:
   with db.begin():
       order = create_order(...)
       create_order_items(order, ...)
       create_order_address_snapshot(order, ...)
       create_payment(order, ...)
       mark_cart_checked_out(cart, ...)
   ```
3. **Atomic Rollback**: If any operation within `db.begin()` raises an exception, SQLAlchemy automatically executes a database `ROLLBACK`.
4. **No Premature Commits**: Lower-level helpers, repository functions, or utility queries must never invoke `db.commit()` independently. The orchestrating service controls commit timing.

---

## 9. Exception Handling & Predictable Error Contract

Located in [base.py](file:///d:/Gawachabazaar/backend/app/exceptions/base.py) and [handlers.py](file:///d:/Gawachabazaar/backend/app/exceptions/handlers.py):

### Uniform Error Response Shape
Every API error adheres to the exact contract:
```json
{
  "code": "STRING_ERROR_CODE",
  "message": "Human-readable explanation of the issue.",
  "details": null
}
```
Validation errors (`422 Unprocessable Entity`) populate `details` with an array of field-level failure descriptors.

### Exception Hierarchy
- `AppException` (HTTP 500, `INTERNAL_SERVER_ERROR`) — Root application exception.
  - `NotFoundError` (HTTP 404, `NOT_FOUND`) — Entity not found.
  - `AuthenticationError` (HTTP 401, `AUTHENTICATION_ERROR`) — Missing/invalid credentials.
  - `AuthorizationError` (HTTP 403, `AUTHORIZATION_ERROR`) — Insufficient permissions.
  - `ConflictError` (HTTP 409, `CONFLICT_ERROR`) — Resource conflict / state mismatch.
  - `BusinessValidationError` (HTTP 422, `BUSINESS_VALIDATION_ERROR`) — Domain rule violations.

### Error Sanitization & Security
- **No Internal Leakage**: Database connection strings, SQL queries, table names, Argon2 hashes, stack traces, and internal file paths are strictly prevented from reaching the client.
- **Unexpected Exceptions (500)**: Caught by `unhandled_exception_handler`, logged internally with `exc_info=True` using sanitized descriptors, and returned to client as generic `INTERNAL_SERVER_ERROR`.

---

## 10. Request Correlation & Structured Logging

Located in [request_id.py](file:///d:/Gawachabazaar/backend/app/core/request_id.py) and [logging.py](file:///d:/Gawachabazaar/backend/app/core/logging.py):

### Request ID Mechanism
1. **Header**: `X-Request-ID`.
2. **Sanitization**: Incoming header is validated against `^[a-zA-Z0-9_\-]{1,64}$`. If missing, invalid, or exceeding 64 characters, a fresh UUID4 hex is generated.
3. **Context Isolation**: Stored in a Python `contextvars.ContextVar("request_id")`.
4. **Lifecycle Guarantee**: `RequestIDMiddleware` sets the ContextVar token upon request arrival and resets it in a `finally` block, ensuring no context leakage across async tasks.
5. **Header Propagation**: `X-Request-ID` is stamped on every outgoing HTTP response header.

### Structured Logging
- Formatter pattern:
  `%(asctime)s [%(levelname)s] [%(name)s] [%(request_id)s]: %(message)s`
- Out-of-request operations (lifespan, background tasks) display `[-]` as `request_id`.
- Request lifecycle logs:
  `GET /api/v1/ping -> 200 (1.42ms)`
- **Logging Redaction Policy**:
  - **NEVER LOG**: Passwords, password hashes, JWT tokens, OTPs, credit/debit card numbers, CVVs, UPI PINs, payment gateway signatures, or raw SQL queries with parameter bindings.
  - Full request bodies are not dumped by default.

---

## 11. Security Foundations

Located in [security.py](file:///d:/Gawachabazaar/backend/app/core/security.py) and [config.py](file:///d:/Gawachabazaar/backend/app/core/config.py):

- **Argon2id Password Hashing**: Cryptographic password hashing using `argon2-cffi` (`PasswordHasher()`).
- **JWT Cryptography**: Signed access tokens using PyJWT with `HS256` and UTC timestamps (`exp`, `iat`).
- **Environment Isolation**: Configuration driven strictly by `pydantic-settings` reading `.env`. No hardcoded credentials.
- **CORS Policies**: Explicit origin validation (`ALLOWED_ORIGINS`) with fallback for local development.

---

## 12. Approved Domain Boundaries

The 25 frozen tables belong strictly to the following 7 domains:

| Domain | Tables | Responsibility |
|---|---|---|
| **Identity & Access** | `roles`, `users`, `user_roles`, `addresses` | User accounts, credentials, RBAC assignments, customer addresses |
| **Farm & Traceability** | `farms`, `batches`, `quality_checks` | Farm origins, harvest batches, laboratory quality assessments |
| **Catalog & Products** | `categories`, `products`, `product_variants`, `product_images`, `prices` | Product hierarchy, packaging variants, media, pricing rules |
| **Inventory & Stock** | `inventory_locations`, `inventory_lots`, `stock_movements` | Warehouses/cold storage, lot operational balances, immutable stock audit ledger |
| **Packaging & Labeling**| `packaging_operations`, `packaging_inputs`, `packaging_outputs` | Bulk batch conversion to sellable inventory lots with single-batch lineage |
| **Commerce (Cart & Order)**| `carts`, `cart_items`, `orders`, `order_items`, `order_addresses` | Shopping baskets, immutable order snapshots, address snapshots, cart lineage |
| **Payments** | `payments`, `payment_transactions` | Commercial payment records, multi-attempt transaction ledger, UPI/COD status |

---

## 13. Critical Domain Invariants & Business Rules

These approved rules govern future domain services:

### Checkout Invariants
- **Lineage**: `orders.cart_id` (`BIGINT`, `FK -> carts.id`, `ON DELETE RESTRICT`, `UNIQUE`) preserves exact checkout lineage from active cart to finalized order.
- **Commercial Snapshotting**: When an order is placed:
  - Catalog prices are captured immutably in `order_items.unit_price`.
  - Customer shipping/billing address is cloned immutably into `order_addresses`.
  - Future catalog price changes or address edits will **never** alter historical order data.

### Inventory Invariants
- **Operational Balance**: `inventory_lots.quantity` represents current on-hand balance.
- **Audit Ledger**: `stock_movements` represents an immutable audit log.
- **Quantity Sign**: `stock_movements.quantity` is always strictly positive ($> 0$). Movement direction is dictated by `movement_type` (`RECEIPT`, `SHIPMENT`, `ADJUSTMENT`, `PACKAGING_CONSUMPTION`, etc.).

### Packaging & Traceability Invariants
- Packaging operations consume bulk inventory lots and output consumer inventory lots.
- **Single Batch Traceability**: An output inventory lot links to exactly one source harvest batch. Mixing different source batches into a single output lot is strictly forbidden.

### Payments Invariants
- Initial payment methods: `UPI` and `COD`.
- Exactly one `payments` record per order.
- One payment may have multiple `payment_transactions` records (representing distinct payment gateway attempts or retries).
- Sensitive credentials (card numbers, CVV, UPI PIN) are **never** stored.

---

## 14. Future Architecture Concerns (Target vs. Current)

To avoid premature distributed complexity, the following capabilities are explicitly classified as **Future Architecture Concerns** and are **NOT** implemented in this checkpoint:

| Capability | Future Target Design | Current V1 Status |
|---|---|---|
| **Cart Locking** | `SELECT ... FOR UPDATE` row-level locking during checkout to prevent double-ordering | Deferred to Checkout Phase |
| **Inventory Mutex** | Row-level locking (`FOR UPDATE`) on `inventory_lots` during stock movements | Deferred to Inventory Phase |
| **Payment Webhooks**| Webhook processing endpoints with signature verification and idempotency keys | Deferred to Payment Integration Phase |
| **Fulfillment Engine**| Order item allocation to specific lots, route planning, delivery partner app APIs | Deferred to Fulfillment Phase |
| **Distributed Caching**| Redis for session storage, cart caching, and rate limiting | Not implemented (Modular Monolith) |
| **Message Streaming**| Kafka / RabbitMQ for event-driven asynchronous processing | Not implemented (Modular Monolith) |
| **Search Engine** | OpenSearch for full-text catalog discovery | Not implemented (PostgreSQL search sufficient) |
| **Tracing** | OpenTelemetry / Jaeger distributed tracing | Not implemented (Lightweight `X-Request-ID` sufficient) |

---

## 15. Testing Strategy

The test suite validates architectural integrity, database isolation, and application reliability:

1. **Database Isolation**:
   - `tests/conftest.py` strictly mandates the test database: `gawachabazaar_test`.
   - Explicit assertion prevents accidental truncation of the development database (`gawachabazaar`).
   - Tables are truncated between tests in reverse dependency order with `RESTART IDENTITY CASCADE`.
2. **Architecture Test Suite** (`tests/test_architecture.py`):
   - Validates application factory and startup lifecycle.
   - Verifies `/health` and `/health/db` operational responses.
   - Verifies `/api/v1` router registration.
   - Validates `X-Request-ID` generation, propagation, header injection, and ContextVar cleanup.
   - Validates database session dependency acquisition and deterministic cleanup.
   - Asserts that authentication and RBAC dependency boundaries exist without premature active wiring.
3. **Exception Suite** (`tests/test_exceptions.py`):
   - Confirms uniform `{code, message, details}` JSON responses for all domain exceptions.
   - Confirms HTTP 500 error sanitization with no leakage of sensitive trace information.
4. **Model Suite** (`tests/test_phase_[1-7]_models.py`):
   - Validates all 25 database domain tables, foreign keys, and constraints across 344 test cases.
