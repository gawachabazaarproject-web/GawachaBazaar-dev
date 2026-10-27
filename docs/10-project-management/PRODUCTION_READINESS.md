# Production Readiness

> **Status:** Partially verified. **Last verified:** 2026-10-14. This is an **evidence checklist, not a certification**. It deliberately does not say the system "is" or "is not" production-ready: it lists, per area, what the repository shows, what was verified by running something, and what is unknown. Items that block *relying on the system for real money and customers* in my assessment are marked **Blocker?** — the owner decides.
> Result vocabulary: **Evidence** = verified by a run or unambiguous code · **Partial** · **Gap** · **Unknown** (cannot be decided from the repository).
> Sources: every linked domain/ops document; [`docs/testing/`](../testing); the `deploy/README.md` go-live checklist (its boxes are unchecked in the file; actual state unknown).

## 1. Summary

| Area | Result | Headline |
|---|---|---|
| Core flows (catalogue, cart, checkout, COD, fulfilment, cancel/refund) | Evidence (backend) | Large, passing, concurrency-aware suite — **but 7 tests currently fail** because of an unfinished fee change |
| Online payments | Partial | Verified only against a fake gateway; **PAY-001 open**; no live sandbox run; no reconciliation job/alerts |
| Authentication/authorization | Evidence (backend), Partial (live) | Golden role matrix passes; live Firebase behaviour untested; a bad server setting caused a platform-wide sign-in outage on 2026-10-14 |
| Security hygiene | **Gap** | A live-looking key is committed (`.mcp.json`); no scanning; weak defaults; CI deploys ungated |
| Deployment | **Gap / Unknown** | Three conflicting deployment descriptions; the Docker/CI Admin build cannot sign in; no rollback rehearsed |
| Observability | **Gap** | Logs only; no metrics, alerts, error tracking or uptime monitoring |
| Backup/recovery | **Gap** | Daily on-host dumps (compose stack only), no restore drill, no off-site/encryption; unknown elsewhere |
| Performance/scale | Partial | Exploratory single-worker numbers; a pool-starvation cliff at ≈ 100 users; single-process design vs HPA 1→3 |
| Frontend quality | **Gap** | No automated tests for the app, Admin or website; only `tsc` runs by hand |
| Privacy/compliance | **Gap** | No retention or deletion policy, PRIV-1 phone exposure, no privacy notice found, placeholder support contacts |
| Mobile release | Partial | Sideloaded Android APK signed with a new EAS key; OTA path works for JS changes; push credentials unknown |

## 2. Checklist with evidence

### Functional
| Check | Result | Evidence |
|---|---|---|
| Backend automated tests pass | **Gap (7 failing)** | 891 passed / 7 failed / 1 xfailed on 2026-10-14; all failures = base-fee default change ([TESTING_GUIDE](../07-testing/TESTING_GUIDE.md)) |
| Money integrity under concurrency | Evidence | double-spend, replay, last-unit, refund races tested; PAY-001 is the known exception |
| Fresh database migrates to head and the app boots | Evidence | verified on a disposable DB ([LOCAL_SETUP](../06-development/LOCAL_SETUP.md)) |
| Model/migration drift | Evidence | `alembic check` clean |
| Delivery fee correct and configured | Partial | Logic tested; base fee is **Rs 20** (owner decision 2026-10-27, code default and deploy files); verify the live host does not override it with an old value; routing uses the public OSRM demo by default |
| Admin pages complete | Gap | Reports, Reviews, Audit Log are placeholders |

### Payments
| Check | Result | Evidence |
|---|---|---|
| Live Razorpay keys, auto-capture, webhook configured, ₹1 test paid and refunded | Unknown | `deploy/README.md` checklist (unchecked); not verifiable here |
| Webhook authenticity, dedup, amount match | Evidence (fake) | [WEBHOOKS](../03-api/WEBHOOKS.md) |
| Reconciliation of captures that match nothing; alerts on failures | **Gap** | [PAYMENTS](../05-domains/PAYMENTS.md) |
| Refund path including lost responses | Partial | G-REF-1 |

### Security and privacy
| Check | Result | Evidence |
|---|---|---|
| No secrets in the repository | **Gap — Blocker?** | SECR-1 `.mcp.json` |
| Production start-up validation | Partial | covers Firebase/Razorpay only; CFG-1 |
| Authorization snapshot | Evidence | `test_authz_matrix.py` |
| Rate limiting / abuse | Partial | two routes only; per-process; XFF issue |
| Token revocation | Partial | skipped without the service account (REV-1) |
| Customer data minimisation, retention, deletion | **Gap** | [PRIVACY](../08-security/PRIVACY.md), [DATA_RETENTION](../04-database/DATA_RETENTION.md) |
| Dependency / container / secret scanning | **Gap** | none configured |

### Deployment and operations
| Check | Result | Evidence |
|---|---|---|
| One authoritative production environment, documented | **Gap — Blocker?** | [DEPLOYMENT](../09-deployment-operations/DEPLOYMENT.md) |
| CI gate before production deploy | **Gap — Blocker?** | CI-001 |
| Admin build can sign in (Firebase config injected) | **Gap** for Docker/CI builds; Unknown for Vercel | ADM-1 |
| Rollback procedure rehearsed | Gap | [ROLLBACK](../09-deployment-operations/ROLLBACK.md) |
| Backups restorable, off-site, monitored | **Gap — Blocker?** | [BACKUP_AND_RECOVERY](../09-deployment-operations/BACKUP_AND_RECOVERY.md) |
| Monitoring and alerting; incident process; support contact | **Gap** | [MONITORING_AND_LOGGING](../09-deployment-operations/MONITORING_AND_LOGGING.md), [INCIDENT_RESPONSE](../09-deployment-operations/INCIDENT_RESPONSE.md) |
| Health checks | Partial | `/health`, `/health/db`; no DB-aware readiness |
| Cold-start behaviour (Render free tier) | Partial | ≈ 44 s; app retries/loader (uncommitted) |
| Single-process constraint respected | **Gap** | HPA 1→3 contradicts it |

### Customer-facing readiness
| Check | Result | Evidence |
|---|---|---|
| Real support email/phone in the app | **Gap** | placeholders in `support.tsx` |
| No misleading UI (slot picker, Bazaar+ benefits, test-mode warning) | Gap | UI-2, BAZ-1 |
| Sign-in works on the shipped build (email, Google, phone) | Partial | email and Google observed working on one device after fixes; phone OTP not verified here |
| Push notifications deliver | Unknown | FCM credentials for the current EAS project unknown |
| OTA update path works | Partial | channel/runtime verified from the installed APK; no update published or observed in this audit |
| Store/release signing and listing | Unknown | – |

## 3. Suggested order to close the largest risks (recommendation)

1. Rotate the committed key; confirm Render's production settings (O-1, O-3).
2. Fix the 7 failing tests, then PAY-001, then add the CI gate (E-1, E-2, E-3).
3. Decide the production topology and fix the Admin build/config path (O-2, E-5, E-6).
4. Do a restore drill and set up off-site backups (O-9).
5. Add alerts for the reconciliation markers and an uptime check (E-8).
6. Real support contact; remove misleading UI; privacy policy and deletion path (O-4, O-7).

Details, evidence and effort estimates: [TASKS](TASKS.md), [KNOWN_ISSUES](KNOWN_ISSUES.md).
