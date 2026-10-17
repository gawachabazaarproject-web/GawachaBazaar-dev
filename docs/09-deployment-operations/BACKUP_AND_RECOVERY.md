# Backup and Recovery

> **Status:** Partially verified. **Last verified:** 2026-10-14. Backup/restore scripts exist for the **VPS Docker Compose stack only**; they were read, **not executed** (no restore drill is recorded anywhere). Backup arrangements for the Render and EKS databases are outside the repository and unknown.
> **Evidence:** [`deploy/scripts/backup-db.sh`](../../deploy/scripts/backup-db.sh), [`restore-db.sh`](../../deploy/scripts/restore-db.sh), [`docker-compose.prod.yml`](../../docker-compose.prod.yml) (`db-backup`, volumes), [`deploy/README.md`](../../deploy/README.md) (Operations, checklist), [RISK_REGISTER](../testing/RISK_REGISTER.md) R-19.

## What is backed up (compose stack)

| Item | Mechanism | Frequency / retention | Where |
|---|---|---|---|
| PostgreSQL (all application data, including personal data and audit rows) | `db-backup` container loops `pg_dump -Fc --no-owner --no-privileges` | every `BACKUP_INTERVAL_SECONDS` (default **86 400 s = daily**); files older than `BACKUP_RETENTION_DAYS` (default **14**) are deleted after each run | `./backups/<db>-<UTC stamp>.dump` on the **same host/disk** as the database (bind mount) |
| Caddy certificates/config | Docker volumes `caddy_data`, `caddy_config` | not backed up | re-issued automatically if lost (needs DNS to resolve) |
| Environment / secrets (`.env.production`) | none | – | must be stored securely elsewhere |
| Images / Cloudinary assets | not backed up by this stack | – | product images live at Cloudinary; the database stores URLs only |
| Firebase accounts | Firebase-managed | – | no export/backup procedure in the repository |

Backups are written to a `.partial` file and moved into place only on success (a failed dump leaves no half file); failures are printed as `[backup] FAILED` and the loop continues. **There is no alert on a failed or missing backup.**

The deploy README itself states: *"`./backups` lives on the same disk as the database. Enable Contabo snapshots and/or `rsync` the `backups/` directory to another machine on a schedule"* and lists "Off-server backup copy configured" as an **unchecked** go-live item. Backups are **not encrypted** by the script.

## Taking a manual backup

```bash
C="docker compose --env-file .env.production -f docker-compose.prod.yml"
$C exec db-backup /bin/sh /usr/local/bin/backup-db.sh     # one backup now (also prunes old ones)
ls -lh backups/ | tail
```

For a quick check that a dump is readable: `pg_restore --list backups/<file>.dump | head` (read-only).

## Restoring (`deploy/scripts/restore-db.sh`) — **destructive, never run casually**

```bash
deploy/scripts/restore-db.sh backups/gawachabazaar-<stamp>.dump
```
Behaviour (from the script): asks you to type `restore`; takes a **fresh safety backup first**; stops the `backend`; runs `pg_restore --clean --if-exists --no-owner --no-privileges` into the production database; starts `migrate` and `backend` (so migrations apply to the restored schema). It restores **into the live database**; practise on a copy first.

After any restore: run the smoke test, check `alembic current` equals the code's head, run the diagnostic queries in [INCIDENT_RESPONSE](INCIDENT_RESPONSE.md) §3 (especially Q4/Q5 for reservations and Q7 for paid-but-unconfirmed orders), and reconcile payments against Razorpay for the window of lost data — Razorpay is not rolled back.

## Recovery considerations specific to this system

- **Money is external:** a restore to an earlier point can lose orders/payments that Razorpay already captured. Pay-first completion and `verify` can rebuild orders from Razorpay state only for sessions that still exist in the restored database; reconcile manually for the gap. Webhooks Razorpay delivered during the gap were acknowledged and are gone.
- **Reservations and stock:** a restore also rewinds `reserved_quantity` and reservations; the sweep will expire overdue holds within about two minutes.
- **Migrations are partly one-way** (Firebase migration downgrade refuses once Firebase-only users exist; dropped verification tables return empty) — restore from a dump, do not `alembic downgrade`, to go back across those revisions ([MIGRATIONS](../04-database/MIGRATIONS.md)).
- **Identity:** Firebase holds credentials; a restored `users` table keeps `firebase_uid`, so sign-in continues to map. Customers created in Firebase after the backup are re-created (as new `CUSTOMER` rows, losing their order history in the lost window) on their next `/auth/sync`. **Staff** created after the backup would exist in Firebase with no database row, and `POST /staff` cannot re-create them (it returns 409 because the Firebase email already exists); they would have to be re-linked by hand or have their Firebase user deleted first ([AUTHENTICATION](../05-domains/AUTHENTICATION.md)).
- **No point-in-time recovery:** `pg_dump` is a daily snapshot, so RPO is up to 24 hours (default) for the compose stack; no WAL archiving is configured.

## Unknowns and gaps

- Backup, retention, PITR and restore capabilities of the **Render PostgreSQL** and any **AWS** database are not documented in the repository (the earlier audit could not tell which databases exist or are live).
- **No restore drill** has been performed or recorded; backup validity is unproven (R-19).
- No off-site copy, no encryption, no backup monitoring or alerting; no documented RPO/RTO.
- Disposable test containers (`gb-qa-test-db`, tmpfs) are **not** backups and must never hold real data.
