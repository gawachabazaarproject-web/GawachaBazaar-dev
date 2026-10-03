# Deploying Gawacha Bazaar to Contabo

Single-VPS production stack: everything runs under Docker Compose on one
Contabo server, fronted by Caddy with automatic Let's Encrypt HTTPS.

```
internet :80/:443 ─► caddy ─┬─► website:3000   SITE_DOMAIN    (promo site)
                            ├─► admin:3001     ADMIN_DOMAIN   (Admin panel)
                            └─► backend:8000   API_DOMAIN     (FastAPI + /api/v1/ws/events)
                                   │
                                   └─► db:5432 (PostgreSQL 16, never exposed)
db-backup ─► db   nightly pg_dump → ./backups (14-day retention)
migrate   ─► db   `alembic upgrade head`, must succeed before backend starts
```

| File | Purpose |
|---|---|
| `docker-compose.prod.yml` | The production stack |
| `.env.production.example` | Every setting/secret the stack needs (copy → `.env.production`) |
| `deploy/Caddyfile` | TLS, HSTS, compression, upload size cap, www→apex redirect |
| `deploy/scripts/bootstrap-server.sh` | One-time server hardening + Docker install |
| `deploy/scripts/deploy.sh` | Build + (re)start; `--pull` to `git pull` first |
| `deploy/scripts/smoke-test.sh` | Post-deploy checks against the public URLs |
| `deploy/scripts/backup-db.sh` / `restore-db.sh` | Backups (run by `db-backup`) / guarded restore |
| `backend/scripts/create_admin.py` | Creates the first ADMIN on a fresh database |

## Sizing

Any Contabo VPS with **≥ 4 vCPU / 8 GB RAM** is comfortable for launch.
Measured in a local rehearsal, the whole running stack idles at about 250 MB of
RAM (backend ~100 MB, Postgres ~50 MB, each Next.js server ~40 MB, Caddy
~15 MB). The peak is **building** the images (`npm ci` + `next build`), not
running them. The backend intentionally runs **one worker** (rate limiter, WebSocket
registry and reservation sweep are in-process; see `backend/Dockerfile`).
Scaling past one backend process needs Redis for those three first.

## First deploy

**1. DNS.** Create A records pointing at the server's IPv4 for `SITE_DOMAIN`,
`www.SITE_DOMAIN`, `ADMIN_DOMAIN` and `API_DOMAIN`. Caddy can't get
certificates until these resolve.

**2. Server bootstrap** (as root, once):
```bash
bash bootstrap-server.sh deploy
```
Then confirm `ssh deploy@<server-ip>` works with your key. Only after that,
harden SSH by setting `PasswordAuthentication no` and `PermitRootLogin no` in
`/etc/ssh/sshd_config`, then run `systemctl restart ssh`.

**3. Code + config** (as `deploy`):
```bash
git clone <repo-url> /opt/gawachabazaar && cd /opt/gawachabazaar
cp .env.production.example .env.production && chmod 600 .env.production
openssl rand -hex 32   # for POSTGRES_PASSWORD
# FIREBASE_PROJECT_ID + FIREBASE_SERVICE_ACCOUNT_JSON: see deploy/FIREBASE_AUTH.md
nano .env.production
```

**4. Deploy:**
```bash
deploy/scripts/deploy.sh
```

**5. First admin:**
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml \
  exec backend python scripts/create_admin.py \
  --name "Owner Name" --email owner@example.com --phone 9876543210
```
It asks for the password interactively.

**6. Verify:**
```bash
deploy/scripts/smoke-test.sh
```

## Rehearse locally (Docker Desktop)

The same stack runs on a laptop with `*.localhost` domains. Caddy then issues
certificates from its own local CA instead of Let's Encrypt, so the real
Caddyfile is exercised unchanged. Create an env file outside the repo with
`SITE_DOMAIN=gawacha.localhost`, `ADMIN_DOMAIN=admin.gawacha.localhost`,
`API_DOMAIN=api.gawacha.localhost` plus generated secrets, then:
```bash
C="docker compose -p gawacha --env-file <that-file> -f docker-compose.prod.yml"
$C up -d --build
$C exec caddy cat /data/caddy/pki/authorities/local/root.crt > caddy-root.crt
CURL_OPTS="--cacert caddy-root.crt --resolve api.gawacha.localhost:443:127.0.0.1 ..." \
  deploy/scripts/smoke-test.sh <that-file>
```
On Windows, Git Bash's curl also needs `--ssl-no-revoke` in `CURL_OPTS`,
because the local CA has no revocation endpoint. Chromium-based browsers
resolve `*.localhost` by themselves but will warn about the local CA.

## Updating

```bash
cd /opt/gawachabazaar && deploy/scripts/deploy.sh --pull
```
Migrations run automatically before the new backend starts. If a migration
fails, the old backend keeps running. Check it with:
`docker compose --env-file .env.production -f docker-compose.prod.yml logs migrate`

## Mobile app

Production builds have no Metro dev server, so the app uses
`EXPO_PUBLIC_API_BASE_URL` (see `mobile/src/api/client.ts`). Set it when
building (EAS or local):
```
EXPO_PUBLIC_API_BASE_URL=https://<API_DOMAIN>/api/v1
```
The realtime socket derives `wss://<API_DOMAIN>/api/v1/ws/events` from it.

## Payments

**Cash on Delivery** needs no setup. The COD payment is marked **PAID** when the
delivery partner confirms delivery (confirming delivery = cash collected), and a
transaction row records who collected it.

**Online payments (Razorpay)** accept UPI, cards, netbanking and wallets through
Razorpay Checkout. With `RAZORPAY_KEY_ID` empty the app runs COD-only: the
mobile app's "Pay online" returns a clear "not available" message.

1. **Keys:** Razorpay Dashboard → Account & Settings → API Keys. Use
   `rzp_test_…` keys first. The backend logs a startup warning if test keys
   are used in production.
2. **Auto-capture:** Account & Settings → Payment capture → **Automatic**.
   An *authorized*-but-uncaptured payment is money on hold, and the platform
   only confirms orders on *captured*.
3. **Webhook:** Account & Settings → Webhooks → Add:
   - URL `https://<API_DOMAIN>/api/v1/payments/webhooks/razorpay`
   - Secret: any long random string (`openssl rand -hex 32`), which you then
     put in `RAZORPAY_WEBHOOK_SECRET`
   - Events: `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`, `refund.failed`
4. Put the three values in `.env.production` and run `deploy/scripts/deploy.sh`.
5. **Test:** place an order with "Pay online". In test mode, pay with UPI
   `success@razorpay` or any Razorpay test card. The order should show PAID and
   CONFIRMED, and the Admin panel's Payments page shows the Razorpay IDs.

How it's protected: the amount always comes from the server. The checkout
signature is verified, the order is re-checked with Razorpay before it's marked
PAID, and webhooks are signature-checked and de-duplicated. Refunds on cancelled
paid orders go back through Razorpay from the Admin panel (Payments → Refunds).
Razorpay often reports a new refund as *pending*. The `refund.processed` /
`refund.failed` webhook then moves it to Refunded or Failed automatically; if a
refund stays "Processing", press **Check status** in the refund queue.

## Cloud services

**Cloudinary** stores product and category images uploaded from the Admin
panel. Without it, uploads fail with `503 UPLOADS_NOT_CONFIGURED`, and the
backend logs a startup warning in production. The Free plan is enough to
launch; watch credits under Dashboard → Usage.

**No email or SMS is sent by the platform.** Login is email-or-phone +
password only. A customer who forgets their password contacts support, and an
ADMIN sets a new one from the Admin panel (Customers → customer → Account
information), which signs the customer out of every device. Email/phone
changes are made there too. Both actions are recorded in the audit log.

## Operations

```bash
C="docker compose --env-file .env.production -f docker-compose.prod.yml"
$C ps                              # status + health
$C logs -f backend                 # backend logs (rotated: 5 × 10 MB)
$C exec db psql -U gawacha gawachabazaar
$C exec db-backup /bin/sh /usr/local/bin/backup-db.sh    # backup now
deploy/scripts/restore-db.sh backups/<file>.dump         # guarded restore
```

**Off-server backups:** `./backups` lives on the same disk as the database.
Enable Contabo snapshots and/or `rsync` the `backups/` directory to another
machine on a schedule.

## Before going live: checklist

- [ ] DNS for all four hostnames resolves to the server
- [ ] `.env.production` has no `CHANGE_ME` (deploy.sh refuses otherwise), and is `chmod 600`
- [ ] Cloudinary keys set (image uploads in the Admin panel)
- [ ] Razorpay: live keys, automatic capture on, webhook created (see Payments); one real ₹1 test order paid and refunded
- [ ] Real support email/phone in the mobile app's Support screen (`mobile/app/account/support.tsx` still has placeholders). Customers who forget their password are told to contact support
- [ ] First ADMIN created; log in at `https://ADMIN_DOMAIN`
- [ ] `smoke-test.sh` passes
- [ ] Off-server backup copy configured
- [ ] SSH password login and root login disabled
- [ ] Mobile production build points `EXPO_PUBLIC_API_BASE_URL` at `https://API_DOMAIN/api/v1`

## Known limits (deliberate, documented in code)

- **Single backend process**, as described under Sizing.
