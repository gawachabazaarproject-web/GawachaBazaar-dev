# Phase 13 — Cart, Checkout & Orders API

Turns the existing Phase 6 commerce schema (`carts`, `cart_items`, `orders`,
`order_items`, `order_addresses`) into a production customer commerce
workflow. No schema migration was required or created - the tables already
had the correct shape, including `orders.cart_id UNIQUE`, which is the
database-level backbone of checkout's retry safety (see below).
**CUSTOMER-only** throughout - there is no B2B wholesaler cart.

Implementation: [`app/api/v1/cart.py`](../../app/api/v1/cart.py) +
[`app/api/v1/orders.py`](../../app/api/v1/orders.py) (routes) →
[`app/services/cart.py`](../../app/services/cart.py) (`CartService`) /
[`app/services/order.py`](../../app/services/order.py) (`OrderService`,
owns checkout orchestration) → [`app/schemas/cart.py`](../../app/schemas/cart.py) /
[`app/schemas/order.py`](../../app/schemas/order.py) → existing models.
Both services reuse [`app/services/pricing.py`](../../app/services/pricing.py)
(extracted this phase from `CatalogService` - see "Pricing" below) rather
than each re-implementing the current-price rule.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/cart` | Current active cart. **Never creates one as a side effect.** |
| POST | `/cart` | Ensure and return an active cart (idempotent get-or-create). |
| POST | `/cart/items` | Add an item - merges quantity if the variant is already in the cart. |
| PATCH | `/cart/items/{item_id}` | Set a cart item's quantity to an absolute value. |
| DELETE | `/cart/items/{item_id}` | Remove one item. |
| DELETE | `/cart/items` | Clear all items - the cart itself stays `ACTIVE`. |
| POST | `/cart/checkout` | The atomic checkout transaction. Lives under `/cart` but is orchestrated by `OrderService`, not `CartService`. |
| GET | `/orders` | Paginated list, always scoped to the caller. |
| GET | `/orders/{order_id}` | Full order detail (items + address snapshot), always scoped to the caller. |

## Authorization

Every route requires `CUSTOMER` (`require_roles(CUSTOMER)` at the router
level, on both `cart.py` and `orders.py`). Every other role (`ADMIN`,
`HUB_STAFF`, `OPERATIONS`, `WHOLESALER`, `DELIVERY_PARTNER`) gets 403.
Unauthenticated requests get 401. Reuses Phase 9's
`get_current_user`/`require_roles` unchanged.

## Cart Lifecycle

```
(no row)  ──POST /cart or POST /cart/items──>  ACTIVE  ──checkout──>  CHECKED_OUT
```

There is no API path that sets a cart to `ABANDONED` in this phase (that
would be a future scheduled process); checkout still handles the case
defensively (409) since the database allows it. A user has at most one
`ACTIVE` cart (`uq_carts_user_active` partial unique index) - enforced by
the database, with the service self-healing the creation race rather than
surfacing it to the client (see Concurrency below).

## Pricing

Extracted this phase into `app/services/pricing.get_current_prices_for_variants`,
reused by `CatalogService` (Phase 10 display), `CartService` (cart display),
and `OrderService` (checkout snapshotting) - one rule, three call sites,
not three implementations. Eligible: `is_active AND valid_from <= now AND
(valid_to IS NULL OR valid_to >= now)`. Tie-break: most recent `valid_from`
wins; **if multiple eligible rows share the exact same `valid_from`, the
highest `id` wins** - `ORDER BY variant_id, valid_from DESC, id DESC`.

**A genuine determinism gap was found and fixed during this extraction**:
the original Phase 10 implementation ordered only by `valid_from DESC`,
with no secondary `id` tie-break. Two price rows sharing an identical
`valid_from` would resolve to whichever PostgreSQL happened to return
first - not guaranteed deterministic. Phase 13 explicitly requires a
deterministic id tie-break (checkout can't tolerate an ambiguous price),
so the shared function now sorts by `id DESC` as a secondary key. This also
silently fixes the same latent gap in Phase 10's public catalog display -
verified via full Phase 10 regression (13/13 passing) after the change.

Cart display and checkout use the same rule but react differently to a
missing price: the cart shows `unit_price: null` / `line_total: null` for
that item and lets the user keep browsing/editing; checkout hard-rejects
(409) - pricing correctness is only a hard gate at the point of an actual
purchase commitment.

## Currency

All items in one order must resolve to the same currency; checkout compares
the *set* of currencies among resolved prices and rejects (409) if more
than one is present. No conversion is performed or planned. Cart display
does not enforce this - it's a best-effort read (see Pricing above);
mixed-currency carts can be *viewed*, they just can't be *checked out*.

## Checkout: The Atomic Transaction

`OrderService.checkout` (only path that creates an `Order`):

```
1.  SELECT carts WHERE user_id = :uid ORDER BY id DESC LIMIT 1 FOR UPDATE
2.  branch on cart.status:
      CHECKED_OUT -> find Order WHERE cart_id = cart.id, return it (created=False)
      ABANDONED   -> 409
      (no cart)   -> 404
      ACTIVE      -> continue
3.  load cart_items; empty -> 409
4.  SELECT product_variants WHERE id IN (...) ORDER BY id FOR UPDATE
5.  revalidate: variant exists + ACTIVE, product exists + ACTIVE  -> 404/409 otherwise
6.  resolve current price per variant (shared pricing rule)       -> 409 if any missing
7.  verify single currency across all resolved prices             -> 409 otherwise
8.  verify address.user_id == current user                        -> 404 otherwise
9.  compute each line: (quantity * unit_price).quantize(0.01, ROUND_HALF_UP)
10. total_amount = sum of the already-rounded line totals (never sum-then-round)
11. INSERT Order (status=PENDING, cart_id=cart.id, order_number=<generated>)
12. INSERT OrderItem per line (immutable snapshot)
13. INSERT exactly one OrderAddress (immutable snapshot)
14. cart.status = CHECKED_OUT
15. db.commit()  -- exactly once; any prior failure raises before this line
```

Because step 10 sums the *already-quantized* per-line totals rather than
rounding a separately-computed sum, `order.total_amount ==
SUM(order_items.total_price)` holds by construction, not by a secondary
check.

### Why No `db.begin()`

Same rule as every prior phase's atomic transaction (Inventory's
`create_movement`, Packaging's `complete_operation`): every route here is
protected by `require_roles`, which composes `get_current_user`, which
always issues its own reads against the shared session first - autobegin-ing
the transaction before `checkout()` runs. Calling `db.begin()` here would
either raise or silently degrade into a no-op nested savepoint (the exact
bug found in Phase 10's image primary-swap logic). `checkout` performs
every step directly against the already-open transaction and commits once.

## Checkout Retry Safety (Duplicate / Concurrent Checkout)

**The single most important design detail in this phase**: step 1's locking
query finds the cart by `user_id ORDER BY id DESC` - deliberately **not**
filtered by `status = 'ACTIVE'`.

Under PostgreSQL READ COMMITTED, a `SELECT ... FOR UPDATE` that blocks on a
row later modified by the transaction holding the lock re-evaluates its
WHERE clause once unblocked - and if the row *no longer matches* (e.g.
`status` changed from `'ACTIVE'` to `'CHECKED_OUT'` by the transaction that
just committed), **the row is silently excluded from the result**, not
returned with its new values. A locking query filtered on
`status = 'ACTIVE'` would therefore make a second concurrent request see
"no cart" after the first one wins - not the `CHECKED_OUT` cart it needs to
find the existing order via step 2. Locking unconditionally on `user_id`
and branching on `status` only *after* the lock is granted is what makes
"the second request returns the existing order" actually work, rather than
just being aspirational in a comment.

This, combined with `orders.cart_id UNIQUE`, gives checkout domain-level
retry safety without any generic idempotency-key infrastructure - exactly
as directed. Verified by `test_31` (sequential retry) and
`test_32_33_34_concurrent_checkout_exactly_one_order` (genuine concurrent
threads via `ThreadPoolExecutor`, real PostgreSQL locking): exactly one
`Order` row, both requests resolve to the identical order id.

## Locking Order

`cart` row, then `product_variant` rows in ascending id order - matching the
given algorithm exactly. No locks are taken on prices, categories,
inventory, or users. `CartService`'s own mutation methods (add/update/remove/clear)
also lock the cart row first (`_get_locked_active_cart`), which is what
makes the cart-vs-checkout concurrency guarantee bidirectional - see next
section.

## Cart Mutation vs. Checkout Concurrency

Every `CartService` mutation locks the cart row before touching
`cart_items`. If checkout is mid-transaction holding that lock, a
concurrent add/update/remove/clear call blocks until checkout finishes,
then re-checks `cart.status` - if it's now `CHECKED_OUT`, the mutation is
rejected (409) rather than silently applying a stale-intent change (e.g.
"quantity 2 was checked out, then a queued mutation changes it to 5")
after the order snapshot was already taken. Verified by `test_35`.

## Address Handling

`checkout` accepts only `address_id`. `address.user_id` is verified against
the authenticated user; a non-owned or nonexistent address both return 404
(never distinguished, to avoid cross-user resource disclosure). Address
fields are copied into `order_addresses` at checkout time - the order never
references the mutable `addresses` row, so a later address edit or deletion
cannot alter a historical order.

## Snapshots

`order_items` capture `product_name`, `variant_name`, `sku`, `unit`,
`quantity`, `unit_price`, `total_price` at the moment of checkout -
independent of later catalog changes. `order_addresses` captures the full
address at checkout time - independent of later address edits. Neither
snapshot has an FK back to the mutable source row beyond `variant_id`
(needed for future domains, e.g. a future fulfillment/delivery phase) -
the *values* are what make the order historically accurate, not a live
join.

## Order Number

Server-generated only, never client-trusted: date prefix + `secrets.token_hex(4)`
(32 bits of randomness) - not timestamp-only. `orders.order_number UNIQUE`
is the final database-level safety boundary; a collision is astronomically
unlikely and, if it ever happened, surfaces as a clean 409 (via the existing
`IntegrityError` → `ConflictError` translation already used throughout this
codebase) rather than a raw database error.

## Explicit Boundaries (Not Built This Phase)

- **No inventory effect.** Checkout never imports or calls
  `InventoryService`; no `InventoryLot`/`StockMovement` rows are created,
  reserved, or modified. Verified by `test_29` (both tables empty after a
  successful checkout).
- **No payment processing.** No gateway call, no UPI/COD logic. Every order
  ends at `status = PENDING` - Phase 7's `payments`/`payment_transactions`
  tables are untouched.
- **No delivery/fulfillment.** No delivery record, no fulfillment status.
- **No coupons/promotions/discounts.** `total_amount` is a pure sum of
  snapshotted line totals.
- **No generic idempotency framework.** Retry safety here comes entirely
  from cart identity + row locking + `UNIQUE(cart_id)`, as directed - not a
  reusable idempotency-key table. A future domain that can't reduce its
  retry-safety needs to "find the same parent row" the way checkout does
  here would need its own design, not an assumption that this pattern
  generalizes for free.

## Known Limitations

- **No customer-initiated cancellation** - not built this phase, per
  explicit instruction.
- **No order status transitions beyond creation** - orders are created
  `PENDING` and nothing in this phase moves them further; that's a future
  payment/fulfillment phase's responsibility.
- **Cart display's mixed-currency handling is best-effort** - see Currency
  above; only checkout is a hard gate.
- **`ABANDONED` cart status has no producer yet** - the checkout code path
  handles it defensively, but nothing in the current codebase ever sets it.

## Focused Validation Performed

`tests/test_phase_13_cart_orders.py`, 39 tests covering all 44 required
scenarios (some combined where one test naturally proves multiple points,
e.g. the concurrent-checkout test covers #32/#33/#34 together), against
real PostgreSQL - cart CRUD and merge semantics, catalog-active revalidation,
all six pricing rules including the id tie-break, address ownership
verification, full checkout happy-path with database re-verification of
total/snapshots/inventory-untouched/cart-order linkage, sequential and
genuinely-concurrent (`ThreadPoolExecutor`) checkout retry safety,
concurrent-mutation-vs-checkout, and two fault-injection rollback tests
(monkeypatched `OrderItem`/`OrderAddress` construction to force a mid-transaction
failure, verifying no `Order`/`OrderItem`/`OrderAddress` row survives and
the cart remains `ACTIVE` - not inferred from the HTTP 500 alone). Also
re-ran Phase 10 catalog (13/13), auth (12/12), and Phase 9 RBAC (8/8, run
in isolation per that suite's own documented requirement) as regression
after the `pricing.py` extraction - all pass.
