# Incident Response

> **Status:** Partially verified. **There is no incident-response process, on-call rota, severity scheme, status page or contact list in the repository.** This document therefore provides (a) **symptom → likely cause → first checks** playbooks *derived from the code and from the one real incident observed on 2026-10-14*, and (b) the read-only SQL I validated against the schema. The playbooks are **not an agreed runbook**; owners must review them. Commands that change production are marked **[changes data]** and need an explicit decision.
> **Evidence:** [`services/`](../../backend/app/services) (behaviour per scenario), [MONITORING_AND_LOGGING](MONITORING_AND_LOGGING.md) (markers), [DEFECT_LOG](../testing/DEFECT_LOG.md), [`deploy/README.md`](../../deploy/README.md). All eight queries in §3 were executed (read-only `SELECT`s) against a disposable database with the real schema on 2026-10-14 to confirm they are valid; they were **not** run against production.

## 1. First five minutes (any incident)

1. **Scope it:** which client (app, Admin, website), which action (sign-in, browse, checkout, payment, delivery), since when, one user or all?
2. **Is the backend up?** `curl -s https://<api>/health` (expect `{"status":"ok",…}`; a sleeping host may take ≈ 45 s to wake) and `/health/db` (expect `"database":"connected"`).
3. **Can tokens be verified?** `curl -s -i -X POST https://<api>/api/v1/auth/sync -H "Authorization: Bearer bad"`: **401** `AUTHENTICATION_ERROR` = token verification works; **503** `AUTH_UNAVAILABLE` = the Firebase integration is broken for everyone (Playbook P1).
4. **Read the logs** around the time for the markers in [MONITORING_AND_LOGGING](MONITORING_AND_LOGGING.md); note the `request_id` from a failing response header `X-Request-ID`.
5. **Do not restart, redeploy or edit data until you know why** — a restart drops WebSockets and in-flight work; several fixes below need data checks first. Record what you did and when.

## 2. Playbooks

### P1 — Nobody can sign in (observed 2026-10-14)
*Symptoms:* mobile shows "Could not validate credentials." or "Sign-in is temporarily unavailable"; Admin shows the 503 message; the `/auth/sync` probe returns 503.
*Cause seen:* `FIREBASE_SERVICE_ACCOUNT_JSON` was set to a file path with no valid file behind it; the code then treats the value as inline JSON, fails ("not valid JSON") and **every** token verification returns 503. Other possible causes: `FIREBASE_PROJECT_ID` empty or wrong (401 "Could not validate credentials" for valid Firebase tokens), certificate fetch failing (`FIREBASE_CERT_FETCH_FAILED`).
*Check:* VPS/AWS environment for `FIREBASE_PROJECT_ID` (must equal the Firebase project of the app: `gawachabazaar-ac900`) and `FIREBASE_SERVICE_ACCOUNT_JSON` (valid one-line JSON, **or** an existing secret file path, **or** unset); logs for `FIREBASE_*` lines.
*Fix **[changes configuration]**:* correct or **remove** `FIREBASE_SERVICE_ACCOUNT_JSON` and redeploy (sign-in then works with only the project id; staff creation, password resets, legacy migration and revocation checks are unavailable until a valid key is restored). Then re-run the probe: expect 401.
*Prevention (proposal):* make service-account loading fail soft; alert on `AUTH_UNAVAILABLE` ([AUTHENTICATION](../05-domains/AUTHENTICATION.md)).

### P2 — Customer paid online but has no order (pay-first)
*Symptoms:* money taken (customer report or Razorpay dashboard shows a captured payment), no order in the app.
*Checks:* (1) run **Q1** (checkout sessions still `PENDING` or `REFUND_FAILED`); (2) in Razorpay find the order id and confirm *captured*; (3) logs for `PAYMENT_WEBHOOK_*` and `CHECKOUT_SESSION_*` with that order id.
*Actions:* ask the customer to reopen checkout/tap "verify" (calls `POST /payments/online/{session_id}/verify`, which asks Razorpay and creates the order); or replay the webhook from Razorpay's dashboard if available. A session in `REFUND_FAILED` means the system could not refund an order it could not place — **refund manually in Razorpay [changes money]** and note it. If the payment matches no session (`PAYMENT_WEBHOOK_UNKNOWN_REFERENCE`), investigate and refund manually. Known defect PAY-001 may attach a payment to an older order instead — compare the order's payment `gateway_order_id` (**Q7**).

### P3 — A refund is stuck in `PROCESSING` (finding G-REF-1)
*Checks:* **Q2** — if `gateway_transaction_id` is NULL on the refund transaction, the gateway response was lost before an id was stored; the Admin "process" and "check status" buttons will refuse. Look the payment up in the Razorpay dashboard: if a refund exists, record it; if not, the refund was never made.
*Actions:* there is no in-app recovery; resolving it requires a deliberate database/dashboard decision by an owner **[changes data/money]** (e.g. after confirming in Razorpay, set the refund/transaction outcome by hand or re-run processing after clearing the failed attempt). Do not click "process" repeatedly.

### P4 — Payment stuck `PROCESSING` or order paid but unconfirmed
*Checks:* **Q3** and **Q7**. `POST /payments/{id}/verify` (customer) or the Admin Payments detail shows the gateway state. `PAYMENT_RESERVATION_MISMATCH` in the logs means the payment is `PAID` but the reservation could not be committed — the order is intentionally **not** auto-confirmed; decide manually (confirm, or cancel and refund).

### P5 — Stock looks wrong (oversold / phantom reservations)
*Checks:* **Q4** (overdue `ACTIVE` reservations — the sweep runs every 120 s and handles 500 per tick; many overdue rows suggest the process is not running the sweep or is overloaded), **Q5** (lots whose `reserved_quantity` differs from the sum of active allocations). The reservation window is 30 minutes. Physical stock only changes at delivery, receipt/adjustment/transfer movements — inspect `stock_movements` for the lot. **Do not** edit `reserved_quantity` by hand without understanding the allocation rows.

### P6 — Backend slow or timing out under load
*Symptoms:* many `QueuePool limit … timed out` errors, requests hang ≈ 30 s, health checks fail. *Cause:* DB pool (5+10) smaller than the 40-thread request pool (PERF-001); recovery took ≈ 6 minutes after load stopped in the experiment. *Actions:* reduce incoming load; a restart clears the queue but drops WebSockets; scaling out does not help the pool and breaks single-process assumptions ([MULTI_REPLICA_ANALYSIS](../testing/MULTI_REPLICA_ANALYSIS.md)). Longer-term fixes are proposals in PERFORMANCE_RESULTS.

### P7 — First request after idle takes ~45 s (AWS)
Expected behaviour of the host; the mobile app pings `/health` early and retries sync with back-off. An external uptime ping every few minutes would avoid it (proposal).

### P8 — Admin does not show new orders / alarm silent
WebSocket events do not cross processes or survive reconnects; refresh the page (REST is authoritative). If it happens on a single process, check the browser console, token expiry (Admin refreshes every 5 min and on focus) and the connection state in `Admin/lib/realtime-context.tsx`. Events are only sent for staff roles other than `DELIVERY_PARTNER`.

### P9 — Suspected credential leak
Rotate first (see [SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md)): the committed `.mcp.json` key (SECR-1), then any secret that appeared in logs/screenshots; revoke Firebase sessions for affected users (`customers.reset_password` / status change); review `admin_action_logs` (read directly in SQL — there is no viewer).

### P10 — A bad deployment
See [ROLLBACK](ROLLBACK.md). Migrations are the hard part; some are one-way.

## 3. Read-only diagnostic queries (validated against the schema; run on a read replica or in a transaction you roll back)

```sql
-- Q1 stuck pay-first checkouts
SELECT id, user_id, cart_id, amount, status, failure_reason, created_at
FROM checkout_sessions WHERE status IN ('PENDING','REFUND_FAILED') ORDER BY id DESC LIMIT 50;

-- Q2 refunds that are open, with the gateway reference (NULL = lost response)
SELECT r.id, r.order_id, r.status, r.requested_at, t.gateway_transaction_id
FROM refunds r LEFT JOIN payment_transactions t ON t.refund_id = r.id AND t.transaction_type = 'REFUND'
WHERE r.status IN ('PENDING_APPROVAL','PROCESSING','FAILED') ORDER BY r.id;

-- Q3 payments stuck in PROCESSING for 30+ minutes
SELECT p.id, p.order_id, p.payment_method, p.status, p.gateway_order_id, p.updated_at
FROM payments p WHERE p.status = 'PROCESSING' AND p.updated_at < now() - interval '30 minutes';

-- Q4 overdue ACTIVE reservations (the sweep should have expired these)
SELECT r.id, r.order_id, r.expires_at FROM inventory_reservations r
WHERE r.status = 'ACTIVE' AND r.expires_at < now();

-- Q5 lots whose reserved quantity disagrees with active/committed allocations
SELECT l.id AS lot_id, l.variant_id, l.reserved_quantity, COALESCE(a.allocated, 0) AS allocated
FROM inventory_lots l
LEFT JOIN (SELECT i.inventory_lot_id, SUM(i.quantity) AS allocated
           FROM inventory_reservation_items i JOIN inventory_reservations r ON r.id = i.reservation_id
           WHERE r.status IN ('ACTIVE','COMMITTED') GROUP BY i.inventory_lot_id) a ON a.inventory_lot_id = l.id
WHERE l.reserved_quantity <> COALESCE(a.allocated, 0);

-- Q6 webhook events that failed to apply
SELECT id, event_type, status, processed_at FROM payment_webhook_events WHERE status = 'FAILED' ORDER BY id DESC LIMIT 50;

-- Q7 orders whose payment is PAID but the order is not confirmed/completed
SELECT o.id, o.order_number, o.status, o.total_amount
FROM orders o JOIN payments p ON p.order_id = o.id
WHERE p.status = 'PAID' AND o.status NOT IN ('CONFIRMED','COMPLETED');

-- Q8 legacy accounts not yet moved to Firebase
SELECT id, name, email, status FROM users WHERE firebase_uid IS NULL AND password_hash IS NOT NULL;
```

Note Q5 is expected to be empty: a row means the reservation bookkeeping and the lot counters have diverged — treat as an integrity incident.

## 4. After an incident

Write down timeline, cause, fix and prevention in the repository (a `docs/incidents/` file is a reasonable home — none exists yet), add the missing marker/alert/test, and update [KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md) and [AI_STATUS](../00-overview/AI_STATUS.md). The 2026-10-14 sign-in outage has no written post-mortem other than this repository's documentation of it.

## 5. Gaps

No owners, escalation path, customer-communication template, severity levels, RTO/RPO, status page, or tested restore ([BACKUP_AND_RECOVERY](BACKUP_AND_RECOVERY.md)).
