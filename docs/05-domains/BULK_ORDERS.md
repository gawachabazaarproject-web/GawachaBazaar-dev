# Bulk and Wholesale Requests, Quotes

> **Status:** Verified for the backend workflow (code + [`test_phase_17_supplier_bulk_commerce.py`](../../backend/tests/test_phase_17_supplier_bulk_commerce.py)); mobile wholesale screens and Admin pages: **Unverified**. **Last verified:** 2026-10-14.
> **Source files:** [`services/bulk_order.py`](../../backend/app/services/bulk_order.py), [`bulk_order_state.py`](../../backend/app/services/bulk_order_state.py), [`quote_state.py`](../../backend/app/services/quote_state.py), [`api/v1/bulk_orders.py`](../../backend/app/api/v1/bulk_orders.py); models `bulk_customer_profile`, `bulk_order_request(_item)`, `quote`, `quote_version`, `quote_item`; mobile `app/bulk/*`, `src/features/bulkOrders`, `src/store/wholesaleStore.ts`.

## What it is

A business buyer asks for quantities (catalogue products or free-text custom items), an admin prices them in a **quote**, the customer accepts, and an admin converts the accepted quote into a normal order. The customer-side role is **`CUSTOMER`** — the `WHOLESALER` role is not used by any route ([USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md)). The app's "wholesale" toggle on Home switches the UI into request mode (draft items are kept in a local Zustand store and submitted as a request).

## Request lifecycle (`bulk_order_state.py`)

```
REQUESTED → UNDER_REVIEW → QUOTED → CUSTOMER_ACCEPTED → CONVERTED_TO_ORDER
   (any non-terminal) → REJECTED | CANCELLED | EXPIRED          (terminal: CONVERTED_TO_ORDER, REJECTED, CANCELLED, EXPIRED)
```

Strict single-step adjacency; drafting a quote directly from `REQUESTED` silently advances through `UNDER_REVIEW`. A new quote revision does **not** move the request out of `QUOTED`.

## Quote versions (`quote_state.py`)

`DRAFT → SENT → {SUPERSEDED, ACCEPTED, REJECTED, EXPIRED}`; `DRAFT/SENT → CANCELLED`. Rules:

- An admin creates a **DRAFT** version (private work in progress, priced `quote_items` per variant); only **sending** makes it the customer's operative offer. Sending **supersedes** (never deletes) the previously `SENT` version and moves the request to `QUOTED`. Only a `DRAFT` can be sent (re-sending a sent version is rejected).
- Versions are immutable once sent/accepted — a renegotiation creates a new `DRAFT`.
- Quote line totals are quantized ROUND_HALF_UP; quote currency and `valid_until` live on the version.
- **Acceptance** (`POST /bulk-orders/requests/{id}/accept`, customer): the client never names a version — the server accepts whatever is `SENT`. **Lazy expiry:** if `valid_until` has passed, the version becomes `EXPIRED` and the accept is rejected, so accept-vs-expiry has one deterministic outcome.
- An admin can reject (withdraw) a `SENT` version.

## Conversion to an order (`POST /bulk-orders/admin/requests/{id}/convert`, roles ADMIN/OPERATIONS)

In **one transaction**: requires status `CUSTOMER_ACCEPTED`, a delivery address on the request, an `ACCEPTED` version with priced items; creates an `Order` (`PENDING`, `cart_id` NULL, totals = sum of quote lines, **`delivery_fee` left at the default 0, no promotion**), `order_items` snapshots, and runs the standard FIFO **reservation** (30-minute window). If stock is insufficient the whole conversion rolls back and the request stays `CUSTOMER_ACCEPTED` for a retry. The customer then pays through the order-first payment path (`POST /payments`, COD or online — [PAYMENTS](PAYMENTS.md)) within the reservation window, or the order expires.

## Operations and gates

| Operation | Gate |
|---|---|
| Profile `GET/PUT /bulk-orders/profile` | `CUSTOMER` (business details; upsert) |
| Create/list/get/cancel own request, view quote, accept | `CUSTOMER` (own requests only; 404 otherwise) |
| Admin list/detail, `review`, `status`, create/send/reject quote versions, `convert`, variant availability | roles `ADMIN`/`OPERATIONS` (HUB_STAFF excluded) |

Variant availability for quoting = Σ(`quantity − reserved_quantity`) over ACTIVE lots (`get_variant_availability`, read-only).

## Concurrency and failure

Requests and quote versions are row-locked for every transition (`_lock_request` locks unconditionally by id, so a status-filtered lock cannot hide a competing change); accept-vs-expiry and convert-vs-convert are serialised. Failure modes: insufficient stock at conversion (rolled back, retryable); expired quote (accept rejected); missing address (422).

## Gaps

- Conversion does not add a delivery fee or apply promotions (a bulk order's `delivery_fee` is 0 even for a far address).
- No notification to the customer when a quote is sent (push messages cover order/payment/refund events only — [NOTIFICATIONS](NOTIFICATIONS.md)).
- No automatic request expiry job: `EXPIRED` is reachable only by admin action or lazy quote expiry.
- Quote lines reference catalogue **variants chosen by the admin** (`quote_items.variant_id`, each must exist), so a customer's free-text item is only represented in an order if an admin maps it to a variant while drafting the quote; nothing links a request item to its quote line (the quote line carries the `request_item_id`, but free-text items have no product).
- `valid_until` is an optional **date**; with none, a quote never expires.
