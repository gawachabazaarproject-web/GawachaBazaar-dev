# Phase 17 — Supplier Management + Bulk & Custom Commerce

Two independent domains, documented together because they shipped in the same phase. See
[ARCHITECTURE.md §21c](../architecture/ARCHITECTURE.md) for the full design narrative and the
conflicts it resolves; this document covers only the actually-implemented API surface.

---

## 1. Domain Separation

| Concept | What it is | Login? |
|---|---|---|
| **Supplier** | A business GawachaBazaar buys inventory FROM | No - a business record, not a `User` |
| **Bulk Customer** | A `CUSTOMER` who buys large/custom quantities FROM GawachaBazaar | Yes - the existing customer login |
| **Customer** | A retail buyer | Yes - unchanged from Phase 1/13 |

Supplier ≠ Bulk Customer ≠ Customer. None of the three is represented as any of the others.

## 2. Batch/Supplier Migration Compatibility

`batches.wholesaler_user_id` (Phase 8.1) still exists, is still nullable-and-valid, and every
pre-Phase-17 test fixture that sets it continues to work unmodified. `batches.supplier_id` (Phase
17) is the new, preferred way to record a batch's origin. Exactly one rule ties them together:

```sql
CHECK (wholesaler_user_id IS NOT NULL OR supplier_id IS NOT NULL)
```

A batch may set either, or both (not expected in practice, but not forbidden), but never neither.
Fully retiring `wholesaler_user_id` is a deliberate, undone future stage - Phase 17 does not attempt
it.

New procurement fields on `batches` (all nullable, additive): `purchase_price`,
`purchase_currency`, `received_date`, `receiving_reference`. These answer "what did we pay, when
did we receive it, what's the receiving reference" without a parallel `supplier_purchases` table.

## 3. Supplier API (`/api/v1/suppliers`, internal staff only)

No customer or delivery-partner route exists in this domain - suppliers are never customer-facing.

| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/suppliers` | ADMIN, HUB_STAFF, OPERATIONS | Create a supplier |
| GET | `/suppliers` | ADMIN, HUB_STAFF, OPERATIONS | List suppliers, optional `?status=` |
| GET | `/suppliers/{id}` | ADMIN, HUB_STAFF, OPERATIONS | Get a supplier |
| PATCH | `/suppliers/{id}` | ADMIN, HUB_STAFF, OPERATIONS | Update a supplier |
| POST | `/suppliers/{id}/products` | ADMIN, HUB_STAFF, OPERATIONS | Link a product this supplier can supply |
| GET | `/suppliers/{id}/products` | ADMIN, HUB_STAFF, OPERATIONS | List a supplier's linked products |
| PATCH | `/suppliers/{id}/products/{link_id}` | ADMIN, HUB_STAFF, OPERATIONS | Update a link (e.g. deactivate) |
| POST | `/suppliers/{id}/evaluations` | **ADMIN only** | Record a performance evaluation (append-only) |
| GET | `/suppliers/{id}/evaluations` | **ADMIN only** | Full evaluation history, newest first |
| GET | `/suppliers/{id}/performance` | ADMIN, HUB_STAFF, OPERATIONS | Dashboard aggregation (see below) |

Evaluations are ADMIN-only per the spec ("supplier ratings are internal procurement data") even
though HUB_STAFF/OPERATIONS can manage the supplier record itself and read the performance summary.

### Evaluation scale

All six dimensions (`quality_rating`, `delivery_rating`, `price_rating`, `reliability_rating`,
`responsiveness_rating`, `overall_rating`) share one manual 0.0-5.0 scale, admin-entered, one row
per evaluation event - never collapsed into a single mutable "current score" column on `Supplier`.
A dashboard's "current" rating is the most recent row (or an average), computed at read time.

### Performance response shape

`GET /suppliers/{id}/performance` returns: the supplier record, distinct active product names
supplied, a per-product supply summary (`{product_name, unit, batch_count,
total_quantity_supplied}` - grouped by unit so KG and UNIT quantities are never summed together),
total batches supplied, last supply date, evaluation count, the most recent evaluation, and average
ratings across all six dimensions.

## 4. Bulk & Custom Commerce API (`/api/v1/bulk-orders`)

### Customer-facing (`CUSTOMER` only)

| Method | Path | Description |
|---|---|---|
| PUT | `/bulk-orders/profile` | Create or update the current user's `BulkCustomerProfile` |
| GET | `/bulk-orders/profile` | Get the current user's profile |
| POST | `/bulk-orders/requests` | Submit a request (Mode A: catalog `product_id`; Mode B: `custom_item_name` - exactly one per item) |
| GET | `/bulk-orders/requests` | List the current user's requests |
| GET | `/bulk-orders/requests/{id}` | Get one of the current user's requests |
| POST | `/bulk-orders/requests/{id}/cancel` | Cancel own request (any non-terminal, non-converted status) |
| GET | `/bulk-orders/requests/{id}/quote` | Get the quote (full version history) for own request |
| POST | `/bulk-orders/requests/{id}/accept` | Accept the current `SENT` quote version (server-derived, never client-named); lazily expires it instead if `valid_until` has passed |

### Ops-facing (`ADMIN`, `OPERATIONS` - **not** HUB_STAFF)

| Method | Path | Description |
|---|---|---|
| GET | `/bulk-orders/admin/requests` | List all requests, optional `?status=` |
| GET | `/bulk-orders/admin/requests/{id}` | Get any request (includes `admin_notes`, `customer_user_id`) |
| POST | `/bulk-orders/admin/requests/{id}/review` | REQUESTED → UNDER_REVIEW |
| POST | `/bulk-orders/admin/requests/{id}/status` | → UNDER_REVIEW / REJECTED / CANCELLED / EXPIRED |
| POST | `/bulk-orders/admin/requests/{id}/quote` | Draft a new quote version (`DRAFT` - not yet visible/actionable to the customer) |
| GET | `/bulk-orders/admin/requests/{id}/quote` | Get the quote (full version history) for any request |
| POST | `/bulk-orders/admin/requests/{id}/quote/{version_id}/send` | Send a `DRAFT` version to the customer (`DRAFT → SENT`; supersedes the prior `SENT` version, moves request to `QUOTED`); 409 if `version_id` is not currently `DRAFT` |
| POST | `/bulk-orders/admin/requests/{id}/quote/{version_id}/reject` | Withdraw a live `SENT` version (`SENT → REJECTED`) without rejecting the whole request |
| GET | `/bulk-orders/admin/variants/{variant_id}/availability` | Read-only `{total_quantity, reserved_quantity, available_quantity}` for a variant, to price a quote - never reserves |
| POST | `/bulk-orders/admin/requests/{id}/convert` | CUSTOMER_ACCEPTED → CONVERTED_TO_ORDER; creates a real `Order` |

HUB_STAFF is deliberately excluded from this entire router - bulk/custom pricing and conversion are
commercial decisions, not warehouse-floor operations (contrast with `suppliers.py`, where HUB_STAFF
has full access).

### Request state machine

```
REQUESTED → UNDER_REVIEW → QUOTED → CUSTOMER_ACCEPTED → CONVERTED_TO_ORDER
```
Terminal alternatives `REJECTED` / `CANCELLED` / `EXPIRED` are reachable from any non-terminal
state. Quoting is allowed directly from `REQUESTED` (silently passes through `UNDER_REVIEW`) as
well as from `UNDER_REVIEW`/`QUOTED` (re-quoting).

### Quote versioning: DRAFT → SENT, not immediately active

`Quote` (one per request) → `QuoteVersion` (`DRAFT` / `SENT` / `SUPERSEDED` / `ACCEPTED` /
`REJECTED` / `EXPIRED` / `CANCELLED`, `version_number` strictly increasing) → `QuoteItem` (one row
per priced line, referencing a concrete `product_variants.id`). Creating a quote
(`POST .../quote`) only ever produces a `DRAFT` - the request's status does not move to `QUOTED`
yet, and nothing is visible to the customer as "their" quote. Only the separate
`POST .../quote/{version_id}/send` makes a version live: it supersedes whichever version was
previously `SENT` (if any) and moves the request to `QUOTED`. Re-drafting while a version is
already `SENT` does not touch that live version until the new draft is explicitly sent - nothing
is ever deleted or overwritten, so the full negotiation history (e.g. ₹35/kg → ₹33/kg) is always
queryable via the version list. `send_quote_version` only accepts a `version_id` that is currently
`DRAFT` (409 otherwise) - this also prevents a version from ever superseding itself.

### Quote expiry (lazy, server-time only)

`QuoteVersion.valid_until` is an optional date set at draft/send time. It is checked only when the
customer calls `.../accept`, against the server's own `date.today()` - never a client-supplied
timestamp, and never proactively via a background job. If the currently-`SENT` version has already
passed `valid_until`, accept transitions it to `EXPIRED` (under the same row lock) and returns 409
instead of accepting it - an expired quote can never be resurrected by a later accept attempt.

### Conversion - the only place a request becomes an Order

`convert_to_order`:
1. Verify the request is `CUSTOMER_ACCEPTED` and has a delivery address.
2. Find the `ACCEPTED` quote version and its items.
3. Build `Order`/`OrderItem`/`OrderAddress` using the exact snapshot pattern `OrderService.checkout`
   already uses (same fields, same rounding, same order-number generator).
4. Call the **unmodified** `InventoryReservationService.create_reservation_for_order` - the
   converted order gets the same FIFO allocation and 30-minute unpaid-window expiry as any retail
   order.
5. Set `bulk_order_requests.order_id` and mark the request `CONVERTED_TO_ORDER`.
6. Commit once. If reservation fails (insufficient stock), the whole conversion rolls back and the
   request stays `CUSTOMER_ACCEPTED` for a retry - nothing partial is ever written.

`order_id` (nullable, `UNIQUE`) is a database-level idempotency backstop, not just a Python check:
even if two conversion requests for the same request somehow both passed the in-app status check
(they cannot, given `_lock_request`'s row lock, but this is never relied on alone), only one could
ever successfully set this column - the second hits a UNIQUE VIOLATION and rolls back cleanly. It
also doubles as the retail/bulk traceability signal for admin/analytics (join on `orders.id`); a
separate `order_source` column was deliberately not added since it would duplicate this.

After conversion, the resulting order is paid, reserved, fulfilled, and delivered through the
**exact same** `POST /payments`, fulfillment, and delivery endpoints as any retail order - nothing
bulk-specific exists in any of those flows.

## 5. Security

- Suppliers are never exposed to `CUSTOMER` or `DELIVERY_PARTNER` - the entire `/suppliers` router
  requires ADMIN/HUB_STAFF/OPERATIONS at minimum, evaluations ADMIN-only.
- A customer can only see/cancel/accept their own requests (404 on another customer's, matching
  this codebase's established "don't disclose existence" convention).
- No endpoint accepts a client-supplied request/order status, quote-version id (for accept/convert -
  `send`/`reject` do take one, but only as an explicit admin action on a version the service still
  verifies belongs to this request's own quote), price, or total - all server-derived. The client
  only ever names *what* it wants (items, quantities) or *that* it accepts/cancels/sends/rejects -
  never *what the system's state should become*.

## 6. Testing

`tests/test_phase_17_supplier_bulk_commerce.py` (45 tests) - Batch/supplier migration compatibility
(new path, legacy path, neither-rejected, procurement fields, negative-price rejection), full
supplier CRUD + product links + RBAC, append-only evaluation history, performance dashboard
aggregation, bulk customer profile upsert, Mode A/B request creation (including the
exactly-one-of product/custom-name validation), cross-customer ownership enforcement, the full
request state machine (review, draft, send, re-draft-preserves-sent-version,
send-supersedes-preserving-price-history, reject, accept, cancel, HUB_STAFF exclusion), quote
expiry (lazy expire on accept attempt, sticky once expired), read-only variant availability
(never mutates, never reserves), the `order_id` uniqueness backstop, and conversion (real Order +
reservation created, pays via COD like any retail order, rejected before acceptance,
insufficient-stock rollback, ownership enforcement, missing-address rejection). Six real-PostgreSQL
concurrency tests (`ThreadPoolExecutor`, real row locks, no mocking): concurrent accept attempts on
one quote, duplicate concurrent conversion requests, two bulk orders racing for the same limited
stock, concurrent supplier field updates (no lost update), accept racing an already-past expiry,
and accepting an already-accepted quote.

## 7. Known Limitations

- No supplier portal/login - explicitly out of scope until a real business need for supplier
  self-service is identified (§6 of the spec).
- No automated supplier scoring - all six rating dimensions are manually admin-entered per the
  explicit "do not over-engineer automated scoring yet" instruction.
- No RFQ (request-for-quote broadcast to multiple suppliers), no purchase-order workflow beyond
  `Batch`'s own procurement fields - out of scope per "do not build a full ERP procurement system."
- No refunds, substitutions, or partial fulfillment for converted bulk orders - identical
  limitations to retail orders (Phase 13-16), not reintroduced or worked around here.
- `wholesaler_user_id` is not yet deprecated - stage 1 of a documented multi-stage migration only.
