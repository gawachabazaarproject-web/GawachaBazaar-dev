# Architecture and Flow Map

Status: derived from code reading in Phase 1; flows marked **traced** were followed in code, **not executed**.

## 1. Runtime topology (as configured)

```
 Expo mobile app ─┐                     ┌─ PostgreSQL 16
 website (Next)  ─┼─ HTTPS ─ ingress ─ FastAPI (uvicorn, 1 worker/pod, HPA 1..3)
 Admin (Next)    ─┘                     ├─ Firebase Admin SDK (verify ID tokens)
                                        ├─ Razorpay REST + webhook (inbound)
                                        ├─ Cloudinary (image upload)
                                        ├─ Google Distance Matrix / OSRM (delivery distance)
                                        └─ in-process: slowapi limiter, WebSocket hub, reservation sweep task
 Firebase Auth ← clients sign in directly; backend never sees passwords (except legacy-migrate)
```
No Redis/queue. Single-process state: rate-limit counters, realtime connections, sweep loop.

## 2. Trust boundaries and who owns each invariant

| Data | Origin | Authoritative owner | Notes |
|---|---|---|---|
| Identity | Firebase ID token | `AuthService.resolve_current_user` (UID → users row, must be ACTIVE, email verified for password sign-ins) | client never supplies user id |
| Role / permission | `user_roles` table | `require_roles` / `require_permission` per request | live DB read, no JWT claims |
| Prices | `prices` table | `services/pricing.py`, `cart.py`, `order.py` | needs test: order must snapshot price at checkout |
| Delivery fee | server config + address GPS + routing API | `services/delivery.py` | falls back to straight-line × 1.4 if routing fails |
| Stock | `inventory_lots` / shared pool | `inventory*.py`, `stock_pool.py` | row-locked |
| Payment truth | Razorpay | `PaymentService` (webhook + server-side status query) | client "success" must not be trusted |
| Promotion limits | `promotions`, `promotion_redemptions` | `promotion.py` | usage-limit race to test |

## 3. Critical flows (traced in code)

### 3.1 Online checkout (pay-first)
1. App → `POST /payments/checkout` (customer role) → `CheckoutSessionService` (locks cart, snapshots totals server-side, creates Razorpay order via gateway; echo-checks amount/currency).
2. App opens Razorpay Checkout with `key_id` + gateway order id.
3. Success path A: app → `POST /payments/checkout/{id}/confirm` with `razorpay_payment_id` + signature → `verify_checkout_signature` (HMAC, constant-time) then server asks Razorpay for status.
4. Success path B: Razorpay → `POST /payments/webhooks/{gateway_slug}` (no JWT) → `verify_webhook_signature` → parse → insert `payment_webhook_events` (UNIQUE gateway+event_id) → resolve transaction → lock payment+order → validate amount → state transition → confirm order + reserve/commit inventory → single commit → realtime push after commit.
5. Order created only after payment confirmation for this flow (commit `183319c` "pay-first").
**Test focus**: A and B racing; replay of B; B with wrong amount; B for unknown reference (recorded as FAILED, 200?); confirm with another user's payment id; expiry vs late success.

### 3.2 COD checkout
Cart → `POST /cart/checkout` → order PENDING/CONFIRMED per `_confirm_cod`, reservation created, stock committed per reservation rules. **Test focus**: double-submit, last-unit race, price changed between add and checkout.

### 3.3 Cancellation / refund
Order cancel (`order_state`: PENDING→CANCELLED, CONFIRMED→CANCELLED) → `RefundService` (Razorpay refund + `query_refund`, async outcome via refund webhook events) → reservation release/stock restore. **Test focus**: duplicate cancel, refund retry duplication, refund > paid, refund for COD.

### 3.4 Inventory
Admin lot create/adjust/remove → locks lot rows (`FOR UPDATE`) → `stock_movements`. Customer availability = shared pool minus reservations (`stock_pool.available_packs_by_variant`). Reservation expiry via sweep (120 s) *and* lazily. **Test focus**: oversell invariant, deadlock on multi-lot ordering, sweep on multiple replicas.

### 3.5 Admin authorization
Router-level `dependencies=[Depends(require_roles(...))]` or per-route `require_permission`. 12 operations have no security scheme (public by design?): `auth/legacy-migrate`, catalog GETs (4), `payments/webhooks/{slug}`, `ads`, `home-slides`, `offers`, `ping`, `health`, `health/db`. **Test focus**: every other operation returns 401 without a token and 403 for a wrong role (can be generated from OpenAPI + role matrix).

## 4. Data integrity levers present
FKs and UNIQUE constraints listed in BASELINE_AUDIT §2; `Decimal` used for money in settings and paise conversion; webhook dedup unique key; `payments.order_id` unique; reservation unique per order. Check constraints (non-negative stock/amount) — **to be verified against the migrated schema, not model files**.

## 5. Deployment flow
Push to `main` → Forgejo runner builds 3 images → pushes to Docker Hub tagged with SHA → `aws eks update-kubeconfig` → kubectl apply (kustomize overlay) → `rollout status`. No gates, no staging step, no automatic rollback logic seen. Migrations execute inside each backend container at start.
