# Gawacha Bazaar Database Specification: Version 7 — Payments

This document defines the database architecture and technical specifications for **Phase 7: Payments** of the Gawacha Bazaar platform.

---

## 1. Business Context & Domain Architecture

Phase 7 introduces the financial payment domain to Gawacha Bazaar, establishing the database models and constraints for payment obligations and payment transactions:

```text
CUSTOMER (User)
    │
    ▼
PURCHASE ORDER (`orders`)
    │
    │ 1 : 1
    ▼
PAYMENT OBLIGATION (`payments`)
    │
    │ 1 : N
    ▼
PAYMENT TRANSACTION ATTEMPTS (`payment_transactions`)
```

### 1.1 Payment Obligation vs. Payment Transaction Attempts

The domain strictly separates the financial obligation for an order from the physical payment attempts executed against it:

- **`payments` (Payment Obligation)**:
  - Exactly one payment record exists per order (`UNIQUE(order_id)`).
  - Tracks the overall payment lifecycle (`PENDING`, `PROCESSING`, `PAID`, `FAILED`, `CANCELLED`, `EXPIRED`).
  - Represents the gross amount and currency snapshot required to settle the order.
  - Contains `paid_at` which is stamped only when the obligation is fulfilled.

- **`payment_transactions` (Append-Oriented Financial Records)**:
  - Represents individual transaction attempts/events against a payment obligation.
  - A single payment can undergo multiple retry attempts (e.g. UPI transaction fails, customer retries with another UPI app or method).
  - Append-oriented financial records: records are appended, never deleted or overwritten (`ON DELETE RESTRICT` from payments; no `updated_at` column).

---

## 2. Supported Payment Methods & Operational Lifecycles

Day-one support covers two primary payment methods:
1. **UPI (Unified Payments Interface)**
2. **COD (Cash on Delivery)**

### 2.1 UPI Payment Lifecycle
In an online UPI flow, the payment obligation is created in `PENDING` status. Individual transaction attempts are initiated against payment gateways:

```text
ORDER (total = 850.00 INR)
  ↓
PAYMENT (method = UPI, status = PENDING, amount = 850.00)
  ↓
TRANSACTION #1 (INITIATED → FAILED, gateway_name = "provider_name", gateway_transaction_id = "txn_101")
  ↓ [Retry]
TRANSACTION #2 (INITIATED → SUCCESS, gateway_name = "provider_name", gateway_transaction_id = "txn_102")
  ↓
PAYMENT (status = PAID, paid_at = 2026-09-09T03:00:00Z)
```

- If a transaction fails, a new transaction attempt record is appended.
- When a transaction succeeds, the payment status transitions to `PAID` with `paid_at` recorded.
- Gateway reference fields (`gateway_name`, `gateway_transaction_id`, `gateway_response`, `failure_reason`) capture provider context without hard-coding specific gateway implementations (e.g. Razorpay, Stripe).

### 2.2 COD (Cash on Delivery) Lifecycle
COD orders do not require gateway interaction and are not immediately paid at order creation:

```text
ORDER (total = 850.00 INR)
  ↓
PAYMENT (method = COD, status = PENDING, amount = 850.00, paid_at = NULL)
  ↓ [Produce harvested, packed, and delivered to doorstep]
TRANSACTION #1 (INITIATED → SUCCESS, gateway_name = NULL, gateway_transaction_id = NULL)
  ↓
PAYMENT (status = PAID, paid_at = collection_timestamp)
```

- COD orders are initialized with `status = 'PENDING'` and `paid_at = NULL`.
- Gateway fields remain `NULL`.
- Physical cash collection and driver assignment belong to the future delivery/fulfillment domain.

---

## 3. Core Architectural & Domain Invariants

### 3.1 1:1 Order to Payment Guarantee
- An order can have at most one payment record.
- Enforced at the database level via a named unique constraint:
  ```sql
  CONSTRAINT uq_payments_order_id UNIQUE (order_id)
  ```
- Redundant secondary index on `order_id` is omitted because PostgreSQL automatically creates and uses the unique btree index created by `uq_payments_order_id`.

### 3.2 Idempotency for Webhooks and Gateways
- Network retries and duplicate webhooks from payment gateways are handled safely via an idempotency key:
  ```sql
  CONSTRAINT uq_payment_transactions_idempotency_key UNIQUE (idempotency_key)
  ```
- Because `idempotency_key` is nullable (e.g. COD transactions or manual entries), PostgreSQL's standard unique-null semantics apply: multiple `NULL` values are permitted, while non-null strings must be globally unique across all transactions.

### 3.3 Financial Snapshot Independence
- `amount` (`NUMERIC(12, 2)`) and `currency` (`VARCHAR(3)`) are recorded as independent snapshots in `payments` and `payment_transactions`.
- They are not computed dynamically from the `orders` table, preserving an immutable commercial snapshot even if catalog prices or discounts evolve.

### 3.4 Append-Oriented Nature (No Database Triggers)
- `payment_transactions` intentionally omits `updated_at`. Transaction attempts are append-oriented financial records.
- Database-level immutability triggers are avoided in adherence with the core project architecture.
- State transitions (`PENDING -> PAID`, `INITIATED -> SUCCESS`) belong to the application service layer rather than complex PostgreSQL state-machine triggers.

### 3.5 Strict Delete Rules (No Cascading Deletion)
- `orders -> payments`: `ON DELETE RESTRICT`. Deleting an order that has financial payment records is strictly blocked.
- `payments -> payment_transactions`: `ON DELETE RESTRICT`. Deleting a payment that has transaction history is strictly blocked.

### 3.6 Explicit Exclusions from Phase 7
- **No Payment Gateway SDKs / APIs**: No integration with Razorpay, Stripe, Cashfree, or UPI SDKs.
- **No Webhook Handlers**: Webhook endpoints and signature verification are deferred to the application integration phase.
- **No Refunds Implementation**: `transaction_type` is restricted to `'PAYMENT'` in this phase. Refund transaction types and workflows will be introduced in a dedicated refund domain.
- **No Delivery/Driver Assignment**: COD collection personnel tracking (`collected_by_user_id`) is deferred to the delivery domain.
- **No Inventory Changes**: Inventory reservations and stock movements are decoupled from Phase 7.
- **No PostgreSQL ENUM Types**: All statuses and methods use `VARCHAR` with `CHECK` constraints.

---

## 4. Detailed Table Specifications

### 4.1 `payments`
Represents the overall financial obligation for a purchase order.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `order_id` | `BIGINT` | `NO` | — | FK to `orders.id` (`ON DELETE RESTRICT`), `UNIQUE` |
| `payment_method` | `VARCHAR(30)` | `NO` | — | Method (`UPI`, `COD`) |
| `status` | `VARCHAR(30)` | `NO` | — | Status (`PENDING`, `PROCESSING`, `PAID`, `FAILED`, `CANCELLED`, `EXPIRED`) |
| `amount` | `NUMERIC(12, 2)` | `NO` | — | Amount to be paid (`> 0`) |
| `currency` | `VARCHAR(3)` | `NO` | — | Currency code (e.g. `INR`) |
| `paid_at` | `TIMESTAMPTZ` | `YES` | `NULL` | Timestamp when payment was completed |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record update timestamp |

**Constraints & Indexes**:
- `pk_payments`: PRIMARY KEY (`id`)
- `fk_payments_order_id_orders`: FOREIGN KEY (`order_id`) REFERENCES `orders(id)` ON DELETE RESTRICT
- `uq_payments_order_id`: UNIQUE (`order_id`)
- `ck_payments_payment_method`: CHECK (`payment_method IN ('UPI', 'COD')`)
- `ck_payments_status`: CHECK (`status IN ('PENDING', 'PROCESSING', 'PAID', 'FAILED', 'CANCELLED', 'EXPIRED')`)
- `ck_payments_amount`: CHECK (`amount > 0`)
- `ix_payments_status`: INDEX (`status`)
- `ix_payments_payment_method`: INDEX (`payment_method`)

---

### 4.2 `payment_transactions`
Append-oriented record of an individual transaction attempt or event.

| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `NO` | `GENERATED BY DEFAULT AS IDENTITY` | Primary key |
| `payment_id` | `BIGINT` | `NO` | — | FK to `payments.id` (`ON DELETE RESTRICT`) |
| `transaction_type` | `VARCHAR(30)` | `NO` | — | Transaction type (`PAYMENT`) |
| `status` | `VARCHAR(30)` | `NO` | — | Status (`INITIATED`, `PROCESSING`, `SUCCESS`, `FAILED`, `CANCELLED`, `EXPIRED`) |
| `amount` | `NUMERIC(12, 2)` | `NO` | — | Transaction amount (`> 0`) |
| `currency` | `VARCHAR(3)` | `NO` | — | Currency code (e.g. `INR`) |
| `gateway_name` | `VARCHAR(50)` | `YES` | `NULL` | Gateway or processor name (e.g. provider identifier) |
| `gateway_transaction_id` | `VARCHAR(150)` | `YES` | `NULL` | Processor's reference/transaction ID |
| `idempotency_key` | `VARCHAR(150)` | `YES` | `NULL` | Unique idempotency key (allows multiple NULLs) |
| `gateway_response` | `TEXT` | `YES` | `NULL` | Raw or structured response payload |
| `failure_reason` | `TEXT` | `YES` | `NULL` | Error description if transaction failed |
| `initiated_at` | `TIMESTAMPTZ` | `NO` | — | When transaction attempt was initiated |
| `completed_at` | `TIMESTAMPTZ` | `YES` | `NULL` | When transaction finished (success/failure) |
| `created_at` | `TIMESTAMPTZ` | `NO` | `now()` | Record creation timestamp |

**Constraints & Indexes**:
- `pk_payment_transactions`: PRIMARY KEY (`id`)
- `fk_payment_transactions_payment_id_payments`: FOREIGN KEY (`payment_id`) REFERENCES `payments(id)` ON DELETE RESTRICT
- `uq_payment_transactions_idempotency_key`: UNIQUE (`idempotency_key`)
- `ck_payment_transactions_transaction_type`: CHECK (`transaction_type IN ('PAYMENT')`)
- `ck_payment_transactions_status`: CHECK (`status IN ('INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')`)
- `ck_payment_transactions_amount`: CHECK (`amount > 0`)
- `ix_payment_transactions_payment_id`: INDEX (`payment_id`)
- `ix_payment_transactions_status`: INDEX (`status`)
- `ix_payment_transactions_gateway_transaction_id`: INDEX (`gateway_transaction_id`)

---

## 5. SQLAlchemy Model Mapping & Navigation

```text
User
  │
  └── 1:N ──> Order (back_populates="user")
                │
                └── 1:1 (uselist=False) ──> Payment (back_populates="order")
                                              │
                                              └── 1:N ──> PaymentTransaction (back_populates="payment")
```

- Direct relationship between `User` and `Payment` is intentionally omitted; payments are navigated through `Order.payment`.
