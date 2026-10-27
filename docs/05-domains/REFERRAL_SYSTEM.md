# Refer & Earn

> **Status (2026-10-27):** implemented and tested on the backend, mobile screen and Admin page exist. **Ships DISABLED** (`REFERRAL_ENABLED=false`). Evidence: `backend/app/models/referral.py`, `services/referral.py`, `api/v1/referrals.py`, `tests/test_referrals.py` (29 tests).

## REQUIRED BUSINESS DECISIONS (not made by engineering)

Every value is a **placeholder** so the code is safe, not company policy. Nothing is awarded until the owner chooses and sets `REFERRAL_ENABLED=true`.

| Setting | Placeholder | Meaning |
|---|---|---|
| `REFERRAL_ENABLED` | `false` | master switch |
| `REFERRAL_REFERRER_REWARD` | Rs 50 | credit to the inviter |
| `REFERRAL_REFERRED_REWARD` | Rs 50 | credit to the new customer |
| `REFERRAL_MIN_ORDER_VALUE` | Rs 199 | items value after discount, delivery fee excluded |
| `REFERRAL_APPLY_WINDOW_DAYS` | 14 | a code can be added this long after sign-up |
| `REFERRAL_QUALIFY_WINDOW_DAYS` | 30 | from applying a code to the qualifying delivered order |
| `REFERRAL_MAX_REWARDS_PER_REFERRER` | 20 (0 = unlimited) | reward cap |

**Open decision: how is a reward spent?** The ledger records credits; there is **no checkout redemption yet** (a balance cannot lower an order total). Until the owner decides (wallet credit at checkout? promo code? cash-out?) rewards are bookkeeping only. Do not enable the program publicly before this is decided.

## Rules

* **Code:** 8 characters from an unambiguous 31-letter/digit alphabet, `secrets.choice`, stored upper-case, UNIQUE, one per user, created on first `GET /referrals/me`. Not derived from any id. Lookups are case-insensitive.
* **Apply** (`POST /referrals/apply`, rate limited 10/min/user): only a CUSTOMER, only once ever (`UNIQUE(referred_user_id)`), only within the apply window, only before any PENDING/CONFIRMED/COMPLETED order. Blocked: own code, same e-mail (case-insensitive) or same phone digits as the referrer, circular referral (A→B then B→A), inactive referrer. Self-referral also has a DB `CHECK`.
* **Qualification:** when the referred user's order becomes **COMPLETED (delivered; COD cash recorded in the same transaction)** and its items value is at least the minimum, the referral becomes QUALIFIED → REWARDED inside the delivery transaction (in a SAVEPOINT: a reward problem is logged and never blocks a delivery). Qualification on "paid" (before delivery) is **not** implemented; delivered is the only trigger (documented choice: it removes the cancel-after-reward window).
* **Ledger:** `referral_reward_ledger` is append-only (DB trigger rejects UPDATE/DELETE), has no balance column (balance = `SUM(amount)`), and `UNIQUE(referral_id, beneficiary_user_id, entry_type)` makes a second reward or second reversal impossible even under concurrency (tested with 6 parallel workers).
* **Reversal:** a REVERSAL row (negative amount) is appended when the qualifying order's refund is completed (`RefundService`, in a savepoint) or an admin reverses (`POST /referrals/admin/{id}/reverse`, audited). Idempotent. A cancelled order can never have qualified (it is not delivered).
* **Expiry:** a PENDING referral past `expires_at` is CANCELLED lazily when its first order is delivered; no background job.
* **Cap:** the referrer's code row is locked while counting REWARDED referrals; beyond the cap the referral stays QUALIFIED with a reason and no money moves.

## Endpoints

| Method / path | Who | Purpose |
|---|---|---|
| `GET /referrals/me` | CUSTOMER | code, share text, program rules (all numbers), stats, whether a code can still be applied and why not |
| `POST /referrals/apply` `{code}` | CUSTOMER | add a friend's code |
| `GET /referrals/history` | CUSTOMER | people I referred (masked first name + initial only) |
| `GET /referrals/rewards` | CUSTOMER | my ledger + balance |
| `GET /referrals/admin`, `GET /referrals/admin/{id}` | `referrals.read` (ADMIN) | list / detail with ledger |
| `POST /referrals/admin/{id}/reverse` `{reason}` | `referrals.manage` (ADMIN) | reverse rewards / cancel |

Customer routes take no user id; the caller is always the subject.

## Abuse analysis

Verified by tests: self-referral (id, e-mail, phone formatting), duplicate/second code, circular, already-ordered, stale account, malformed/unknown codes, mass assignment on apply, concurrent double-apply (exactly one wins), concurrent double-reward (exactly one pair of rows), ledger tamper at the database, cap, expiry, disabled program, IDOR on history/rewards, admin endpoints vs customer/staff roles. **Not covered (residual risk):** multi-account farming with distinct phones/e-mails and real deliveries (mitigated by the delivered-order trigger, minimum order, cap and admin reversal, not eliminated); device fingerprinting is out of scope.
