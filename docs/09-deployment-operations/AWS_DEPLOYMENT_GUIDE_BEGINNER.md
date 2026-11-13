# Gawacha Bazaar - AWS Deployment Guide for Beginners

**A complete, step-by-step guide to putting the backend, Admin panel and website on AWS, and pointing the mobile app at it.**

> **Read this first - honest status.** This guide is built from the real files in the repository (`docker-compose.aws.yml`, `.env.aws.example`, `deploy/scripts/*`, `deploy/Caddyfile`, `deploy/osrm/build.sh`, the backend code). **Nobody has yet run this on a real AWS account** - the project docs say the AWS path is "preparation only" (KNOWN_ISSUES DEL-17). So every AWS console click below is written from general AWS knowledge and **console screens/labels may differ slightly**. Where something is a guess or unverified, it is marked **[UNVERIFIED]**. Do the whole thing once as *staging* (a throwaway copy) before you do production.
>
> **Never paste real passwords, keys or the contents of `.env.aws` into chat, e-mail, tickets or Git.**

---

## Part 1 - Understand what you are building

### 1.1 In one paragraph

You will rent **one small Linux server** (AWS EC2) and **one managed database** (AWS RDS PostgreSQL). On the server, Docker runs six small programs ("containers"): a web gateway (Caddy), the API (FastAPI backend), the Admin website, the public website, a map-routing engine (OSRM) and a small cache (Redis). Customers' phones and the Admin panel talk to the server over HTTPS. Login, payments and product images stay with outside companies (Firebase, Razorpay, Cloudinary) - you only need their keys.

### 1.2 Architecture picture

```
        OUTSIDE COMPANIES (not on AWS - you only need their keys)
   Firebase (login)     Razorpay (payments)     Cloudinary (images)
          ^                    ^                       ^
          |                    |                       |   (the server calls out on port 443)
  Phones / browsers ---HTTPS--->  [ EC2 SERVER  t4g.medium, Elastic (fixed) IP ]
  (mobile app, Admin)            |
                                 |  Caddy        ports 80 + 443  (the ONLY open doors)
                                 |    api.yourdomain   -> backend  (FastAPI, port 8000)
                                 |    admin.yourdomain -> admin    (Next.js, port 3001)
                                 |    yourdomain       -> website  (Next.js, port 3000)
                                 |
                                 |  Hidden inside the server (no outside access):
                                 |    redis  (route cache)      osrm (road-distance engine)
                                 v
                    [ RDS PostgreSQL 16  db.t4g.micro - private, only the server may connect ]
```

### 1.3 What each piece does

| Piece | What it is | Why you need it |
|---|---|---|
| **EC2 server** | A virtual Linux computer in Mumbai (`ap-south-1`) | Runs all the containers |
| **Elastic IP** | A fixed public address for the server | DNS must always point to the same address |
| **RDS PostgreSQL** | Managed database with automatic backups | Holds users, orders, products, stock - everything important |
| **Security groups** | Firewall rules | Only the web (80/443) can reach the server; only the server can reach the database |
| **Docker + Compose** | Runs the containers from `docker-compose.aws.yml` | One command starts everything |
| **Caddy** | Web gateway | Gets free HTTPS certificates (Let's Encrypt) automatically and sends each domain to the right container |
| **backend** | The API (Python / FastAPI), **exactly one worker** | Prices, orders, stock, payments. Never run more than one worker - rate limits, WebSocket events and the reservation-expiry job live in memory |
| **migrate** | One-time job run before the backend starts | Updates the database tables (`alembic upgrade head`); if it fails, the old backend keeps running |
| **admin / website** | Two Next.js sites | The staff panel and the public promo site |
| **osrm** | Self-hosted map routing for Nagpur | Calculates the road distance used for delivery fees |
| **redis** | Small cache (64 MB) | Remembers route distances; if it is down, delivery still works |
| **Route 53 (or your domain registrar's DNS)** | Domain names | `api.`, `admin.`, root and `www.` must point at the Elastic IP |
| **SSM Session Manager** | Browser-based terminal into the server | Lets you manage the server **without opening SSH port 22** |
| **CloudWatch** | AWS monitoring | Alarms when the server or database is unhealthy |

### 1.4 Three rules that must never be broken

1. **One backend worker only.** Do not add `--workers 2` or run two backend containers.
2. **The database is never public.** `Publicly accessible = No`, and only the server's security group may connect.
3. **No secret in Git, ever.** Real values live only in `.env.aws` on the server (permission `600`) and in your password manager.

---

## Part 2 - What you need before you start

### 2.1 Accounts and access

| # | Need | Notes |
|---|---|---|
| 1 | **AWS account** with a payment card | Turn on MFA for the root user immediately |
| 2 | **A domain name** you control | The project uses `gawachabazaar.in` (`api.`, `admin.` sub-domains). You must be able to add DNS records |
| 3 | **Firebase project** (production) | Needs Authentication enabled (phone / Google / e-mail as used by the app) and a *service account key* |
| 4 | **Razorpay account** | `rzp_test_` keys for staging, `rzp_live_` keys only for production |
| 5 | **Cloudinary account** | Cloud name, API key, API secret |
| 6 | **Git access to the repository** from the server | A read-only deploy key or token for your Git host (GitHub / Forgejo) |
| 7 | **The real warehouse latitude/longitude** | Without it per-km delivery pricing is not production-ready |
| 8 | **Expo account** (only for the mobile app build) | `eas login` |
| 9 | A **password manager** | Store the DB password, OTP secret, and all keys here |

### 2.2 What it costs (estimate, USD per month, Mumbai region, on-demand)

Prices come from AWS's public price list as recorded in `AWS_PRODUCTION_PLAN.md` section 4 (downloaded 2026-10-27). GST/taxes, Razorpay fees, Firebase SMS and Cloudinary are **not** included.

| Line | Minimum | Expected | Higher than expected |
|---|---|---|---|
| EC2 server (t4g.small / t4g.medium / t4g.medium) | 8.18 | 16.35 | 16.35 |
| Server disk, gp3 (20 / 30 / 50 GB) | 1.82 | 2.74 | 4.56 |
| Public IPv4 address | 3.65 | 3.65 | 3.65 |
| RDS database instance (single-AZ / single-AZ / Multi-AZ) | 15.33 | 15.33 | 30.66 |
| RDS storage (20 / 20 / 50 GB) | 2.62 | 2.62 | 13.10 |
| CloudWatch alarms | 0.60 | 0.80 | 1.50 |
| CloudWatch custom metrics | 0.00 | 0.90 | 0.90 |
| CloudWatch logs | 0.70 | 2.10 | 7.00 |
| Data transfer out | 0.22 | 0.87 | 5.46 |
| Route 53 hosted zone | 0.50 | 0.50 | 0.50 |
| **Total** | **33.62** | **45.86** | **83.69** |

Things deliberately **not** used because they cost extra and are not needed at this size: NAT Gateway (about $41/month), Application Load Balancer (about $17/month), ElastiCache (about $12/month). **Set a billing budget alarm of about $60** (step 3.1).

### 2.3 How long it takes

A first-time run, with everything prepared: about half a day. DNS and certificate steps can add waiting time. Plan a second, shorter pass for production.

### 2.4 Tools on your own laptop

You only need a web browser (AWS console, SSM terminal), a Git client, and for the mobile app Node.js + `eas-cli`. Everything else runs on the AWS server.

---

## Part 3 - The repository: where everything lives

```
GawachaBazaar-dev/
|-- docker-compose.aws.yml     <- THE AWS stack definition (use this one)
|-- .env.aws.example           <- template for the secrets/settings file (copy to .env.aws)
|-- docker-compose.prod.yml    <- older single-VPS (Contabo) stack - NOT for AWS
|-- docker-compose.yml         <- local development only
|-- backend/                   <- FastAPI API (Dockerfile, start.sh, alembic/ migrations, scripts/)
|   `-- scripts/create_admin.py   <- creates the first Admin login
|-- Admin/                     <- Next.js staff panel (built by compose; Firebase keys baked in at build time)
|-- website/                   <- Next.js public promo site
|-- mobile/                    <- Expo customer app (built separately with EAS; eas.json holds profiles)
|-- deploy/
|   |-- Caddyfile              <- HTTPS gateway rules (domains -> containers)
|   |-- osrm/build.sh          <- builds the Nagpur map-routing data (run once)
|   `-- scripts/
|       |-- bootstrap-server.sh   <- one-time server setup (Docker, firewall, swap, deploy user)
|       |-- deploy.sh             <- build + start/update the stack
|       |-- smoke-test.sh         <- checks the public endpoints after a deploy
|       |-- backup-db.sh / restore-db.sh   <- older VPS-era scripts (RDS snapshots replace them on AWS)
|-- k8s/                       <- older Kubernetes (EKS) files - NOT used for this guide
|-- .forgejo/workflows/        <- ci.yml (checks), deploy-aws.yml (optional automated deploy, never run yet)
`-- docs/                      <- project documentation
```

### 3.1 Where things live on the AWS server

| Path | Contents |
|---|---|
| `/opt/gawachabazaar/` | A clone of this repository (owned by the `deploy` user) |
| `/opt/gawachabazaar/.env.aws` | **All real secrets and settings** (permission `600`, never committed) |
| `/opt/gawachabazaar/osrm-data/` | The prebuilt map data (about 98 MB), mounted read-only into the `osrm` container |
| Docker volumes `gawachabazaar_prod_caddy_data` / `_caddy_config` | Caddy's HTTPS certificates - do not delete them, or certificates are reissued |
| RDS (not on the server) | The database. Nothing important is stored on the server's disk |

Because all real data is in RDS, a lost server can be rebuilt from the repository plus `.env.aws` plus the OSRM build.

### 3.2 Ports

| Port | Who can reach it | What |
|---|---|---|
| 80 (TCP) | Everyone | Caddy: HTTP -> HTTPS redirect and certificate checks |
| 443 (TCP and UDP) | Everyone | Caddy: HTTPS (UDP is HTTP/3) |
| 8000 | Only inside Docker | backend |
| 3001 | Only inside Docker | admin |
| 3000 | Only inside Docker | website |
| 6379 | Only inside Docker | redis |
| 5000 | Only inside Docker | osrm |
| 5432 | Only the server's security group | RDS PostgreSQL |
| 22 | **Nobody** (use SSM) | SSH stays closed |

---

## Part 4 - Step-by-step deployment

Do these in order. Tick each box.

### Step 4.1 - Secure the AWS account  [ ]

1. Sign in as root, **enable MFA** on the root user (IAM -> Security credentials).
2. Create a normal admin user (IAM Identity Center or an IAM user with MFA) and use it from now on; stop using root.
3. Open **Billing -> Budgets** and create a monthly cost budget of about **$60** with an e-mail alert.
4. In the top-right of the console, choose the region **Asia Pacific (Mumbai) `ap-south-1`**. Stay in this region for everything.

### Step 4.2 - Network  [ ]

The plan describes a custom VPC with extra private subnets. **For a beginner the simpler choice is the default VPC** (every region already has one, with a public subnet in each availability zone). This is safe here **as long as** the database has *Publicly accessible = No* and only the security group rule below can reach it. *(This is a simplification of the plan; both are valid. [UNVERIFIED on AWS.])*

### Step 4.3 - Security groups (firewalls)  [ ]

EC2 console -> **Security Groups** -> Create. Create the app group first.

**Group `gb-app`** (for the server)

| Direction | Type | Port | Source | Why |
|---|---|---|---|---|
| Inbound | HTTP | 80 | 0.0.0.0/0 | HTTPS redirect + Let's Encrypt |
| Inbound | HTTPS | 443 | 0.0.0.0/0 | The website/API |
| Inbound | Custom UDP | 443 | 0.0.0.0/0 | Optional HTTP/3 (compose publishes it) |
| Inbound | *(none for 22)* | - | - | **Do not open SSH** |
| Outbound | All | all | 0.0.0.0/0 (default) | The server calls Firebase, Razorpay, Cloudinary, package repos, RDS |

**Group `gb-rds`** (for the database)

| Direction | Type | Port | Source | Why |
|---|---|---|---|---|
| Inbound | PostgreSQL | 5432 | **Security group `gb-app`** (select the group, not an IP range) | Only the server may connect |

### Step 4.4 - Create the database (RDS)  [ ]

RDS console -> **Create database**.

| Setting | Value |
|---|---|
| Creation method | Standard create |
| Engine | **PostgreSQL**, version **16.x** |
| Template | **Dev/Test** (avoids the Production template defaulting to Multi-AZ, which doubles the price). Single-AZ is the month-one decision in the plan |
| DB instance identifier | `gawachabazaar` (or `gawachabazaar-staging`) |
| Master username | e.g. `gbadmin` |
| Master password | Generate a long random one; **save it in your password manager** |
| Instance class | Burstable **`db.t4g.micro`** |
| Storage | gp3, **20 GB** |
| Connectivity -> VPC | default VPC |
| **Public access** | **No** |
| VPC security group | choose **`gb-rds`** (remove `default`) |
| Initial database name (Additional configuration) | `gawachabazaar` |
| Backup retention | **7 days** (PITR comes with it) |
| Encryption | leave on (default) |
| **Deletion protection** | **On** |

Create it (about 10 minutes). When it is "Available", open it and copy the **Endpoint** (looks like `gawachabazaar.xxxxxxxx.ap-south-1.rds.amazonaws.com`). Keep it for step 4.10.

> The recommendation in the docs is to use a dedicated application user rather than the master user. For a first deployment using the master user is acceptable; tighten later [UNVERIFIED how to script this here].

### Step 4.5 - Give the server an identity (IAM role for SSM)  [ ]

IAM -> Roles -> **Create role** -> trusted entity **AWS service -> EC2** -> attach the policy **`AmazonSSMManagedInstanceCore`** -> name it `gb-ec2-role`. This lets you open a terminal in the browser (Session Manager) without SSH.

### Step 4.6 - Launch the server (EC2)  [ ]

EC2 -> **Launch instance**.

| Setting | Value |
|---|---|
| Name | `gawachabazaar-prod` (or `-staging`) |
| AMI | **Ubuntu Server 24.04 LTS, 64-bit (Arm)** |
| Instance type | **`t4g.medium`** (2 vCPU, 4 GB RAM). `t4g.small` (2 GB) fits the measured memory but leaves little room while the two Next.js sites build |
| Key pair | "Proceed without a key pair" (you will use Session Manager) |
| Network | default VPC, a public subnet, **Auto-assign public IP: Enable** |
| Security group | select existing -> **`gb-app`** |
| Storage | **30 GB gp3** |
| Advanced -> IAM instance profile | **`gb-ec2-role`** |

Why Ubuntu: `deploy/scripts/bootstrap-server.sh` uses `apt` and Docker's Ubuntu repository. (The plan text mentions Amazon Linux 2023, but the script would not run on it, so this guide uses Ubuntu.)

> **Arm warning [UNVERIFIED]:** `t4g` servers are Arm (Graviton). The Python base image is multi-architecture, but nobody has yet confirmed that the pinned OSRM image digest in `docker-compose.aws.yml` runs on Arm. If `osrm` fails to start with an "exec format error" or "no matching manifest", the simplest fix is to launch an x86 `t3.medium` instead (about $0.0448/hour versus $0.0224/hour - roughly $16 more per month).

### Step 4.7 - Give the server a fixed address (Elastic IP)  [ ]

EC2 -> **Elastic IPs** -> Allocate -> then **Associate** it with your instance. Write the IP down. (A public IPv4 address costs about $3.65/month; that is included in the estimate.)

### Step 4.8 - Point your domain names at the server (DNS)  [ ]

Create **A records** pointing to the Elastic IP, in Route 53 (create a hosted zone, then copy its four name servers into your domain registrar) or in your registrar's own DNS:

| Record name | Type | Value |
|---|---|---|
| `api.gawachabazaar.in` | A | Elastic IP |
| `admin.gawachabazaar.in` | A | Elastic IP |
| `gawachabazaar.in` (root) | A | Elastic IP |
| `www.gawachabazaar.in` | A | Elastic IP (Caddy redirects `www` to the root and needs a certificate for it) |

**Wait until all four resolve to the Elastic IP before the first start.** Check from your laptop: `nslookup api.gawachabazaar.in`. If DNS is wrong when Caddy starts, certificate issuance fails (it retries, but you waste time and can hit Let's Encrypt rate limits). For staging use different names (for example `api-staging.`, `admin-staging.`, `staging.`).

### Step 4.9 - Open a terminal on the server and prepare it  [ ]

1. EC2 -> select the instance -> **Connect -> Session Manager -> Connect**. (Ubuntu's official AMIs normally include the SSM agent; if the button is greyed out, wait a few minutes and make sure the IAM role is attached **[UNVERIFIED]**. As a fallback you can temporarily open port 22 from *your own IP only* with a key pair, and remove that rule afterwards.)
2. Become root and fetch the repository to a temporary place. Replace `<REPO_URL>` with your repository's clone address (use a read-only deploy key/token; do not paste tokens anywhere else):

```bash
sudo -i
git clone <REPO_URL> /tmp/gb-bootstrap
```

3. Run the one-time setup script. It installs Docker, a firewall (`ufw`), `fail2ban`, automatic security updates, a 4 GB swap file, log rotation, and creates a user called `deploy` with the folder `/opt/gawachabazaar`:

```bash
bash /tmp/gb-bootstrap/deploy/scripts/bootstrap-server.sh deploy
```

4. Switch to the `deploy` user and clone the repository to its real place. The folder already exists and is empty:

```bash
sudo -iu deploy
git clone <REPO_URL> /opt/gawachabazaar
cd /opt/gawachabazaar
git log --oneline -3
```

If you want to deploy a specific release, check out a tag or commit now (for example `git checkout <tag>`). Production should always be a tag you can return to.

### Step 4.10 - Build the map-routing data (once)  [ ]

Still as `deploy`, in `/opt/gawachabazaar`. This downloads a 221 MB map extract, verifies its checksum, clips it to the Nagpur area and builds the routing files. It takes a few minutes and needs the free disk space (the 30 GB disk is plenty):

```bash
cd /opt/gawachabazaar
OUT=/opt/gawachabazaar/osrm-data bash deploy/osrm/build.sh
ls -lh osrm-data
```

Success looks like `OSRM data ready in /opt/gawachabazaar/osrm-data` followed by the contents of `BUILD_INFO.json`, and a folder holding `nagpur.osrm*` files (about 98 MB). The script rejects the download if the checksum does not match. Delivery addresses outside the clipped box (about 80 x 78 km around Nagpur) get "no route". Refresh the map only when you choose to (every 3-6 months or when the delivery area grows).

### Step 4.11 - Create the settings file `.env.aws`  [ ]

```bash
cd /opt/gawachabazaar
cp .env.aws.example .env.aws
chmod 600 .env.aws
nano .env.aws        # Ctrl+O then Enter to save, Ctrl+X to exit
```

Fill in **every** line using the table below. `deploy.sh` refuses to run while any `CHANGE_ME` remains. Values containing spaces or special characters need care (see the notes after the table).

| Variable | What to put | Where to get it |
|---|---|---|
| `API_DOMAIN` | `api.gawachabazaar.in` | your DNS |
| `ADMIN_DOMAIN` | `admin.gawachabazaar.in` | your DNS |
| `SITE_DOMAIN` | `gawachabazaar.in` (no `www`) | your DNS |
| `ACME_EMAIL` | a real e-mail for certificate notices | you |
| `DATABASE_URL` | `postgresql+psycopg://gbadmin:PASSWORD@ENDPOINT:5432/gawachabazaar?sslmode=require` | RDS endpoint + master password. **Keep `?sslmode=require`.** If the password contains `@ : / ? # %` etc., URL-encode those characters (e.g. `@` -> `%40`) or choose a password with letters and digits only |
| `FIREBASE_PROJECT_ID` | project id | Firebase console -> Project settings (**the server refuses to start if empty**) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | the service-account key as **one line** of JSON, wrapped in single quotes | Firebase console -> Project settings -> Service accounts -> Generate new private key. SECRET. Without it no login works. [UNVERIFIED: how Compose parses a long JSON value - after the first start check the backend logs and test a login] |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | web API key | Firebase -> Project settings -> Your apps (web). Public by design |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | `<project>.firebaseapp.com` | same |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | project id | same |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | bucket name | same |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | number | same |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | app id | same |
| `RAZORPAY_KEY_ID` | `rzp_test_...` (staging) or `rzp_live_...` (production) | Razorpay -> API keys. **Leave empty to run Cash-on-Delivery only.** |
| `RAZORPAY_KEY_SECRET` | secret | same. If KEY_ID is set, the backend will not start without this and the webhook secret |
| `RAZORPAY_WEBHOOK_SECRET` | a long random string you choose | You will type the same value into Razorpay's webhook screen (step 4.15) |
| `CLOUDINARY_CLOUD_NAME` / `_API_KEY` / `_API_SECRET` | from Cloudinary | Cloudinary dashboard. Needed for product-image uploads |
| `PACKING_POINT_LATITUDE` / `_LONGITUDE` | real warehouse coordinates | Google/OSM map. (Alternatively set the packing point later in Admin -> Settings) |
| `DELIVERY_BASE_FEE` | `20` | owner decision (Rs 20 base) |
| `DELIVERY_PER_KM` | `10` | owner decision |
| `DELIVERY_MAX_DISTANCE_KM` | `0` (= no limit) | owner decision |
| `DELIVERY_MIN_ORDER_VALUE` | `0` | owner decision |
| `DELIVERY_OTP_ENFORCED` | `true` | keep |
| `DELIVERY_OTP_SECRET` | a new random string of **at least 32 characters** | generate (below). **Never change it after go-live** or already-issued delivery codes stop working |
| `DELIVERY_OTP_EXPIRY_MINUTES`, `_MAX_ATTEMPTS`, `_RESEND_LIMIT`, `_RESEND_WINDOW_MINUTES` | `240`, `5`, `3`, `15` | defaults are fine |
| `OSRM_DATA_DIR` | `/opt/gawachabazaar/osrm-data` | where step 4.10 built the data (the template's `./osrm-data` is the same folder relative to the repo) |
| `NOMINATIM_USER_AGENT` | `GawachaBazaar/1.0 (your-real-email@example.com)` | must contain a real contact e-mail (OpenStreetMap policy) |

Generate the OTP secret on the server (copy the printed text into `.env.aws`; do not share it):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Settings you do **not** need to add (the compose file supplies safe defaults): `APP_ENV=production`, `DEBUG=False`, `ALLOWED_ORIGINS` (built from your Admin and site domains), `OSRM_BASE_URL=http://osrm:5000`, `REDIS_URL=redis://redis:6379/0`, `ROUTING_PROVIDER=osrm`, referral/partner settings (`REFERRAL_ENABLED` defaults to `false`).

Double-check nothing real is committed: `git status` must **not** list `.env.aws` (it is git-ignored).

### Step 4.12 - Deploy  [ ]

```bash
cd /opt/gawachabazaar
ENV_FILE=.env.aws COMPOSE_FILE_NAME=docker-compose.aws.yml deploy/scripts/deploy.sh
```

What it does, in order: refuses to continue if `CHANGE_ME` is still present, validates the compose file, **builds** the backend / Admin / website images (the first build is slow - allow 10-20 minutes; swap helps on the 4 GB server), starts everything, runs database migrations first (the backend only starts after migrations succeed), and prints `docker compose ps`.

Check the containers:

```bash
docker compose --env-file .env.aws -f docker-compose.aws.yml ps
```

You should see `redis`, `osrm`, `backend`, `admin`, `website`, `caddy` running (the `migrate` job shows as exited with code 0 - that is correct). View logs if something is wrong:

```bash
docker compose --env-file .env.aws -f docker-compose.aws.yml logs --tail=100 backend
docker compose --env-file .env.aws -f docker-compose.aws.yml logs --tail=100 caddy
```

The very first start of Caddy contacts Let's Encrypt for four certificates; this needs DNS (step 4.8) and ports 80/443 open (step 4.3).

### Step 4.13 - Create the first Admin login  [ ]

A fresh database has no users. Create the owner account (you will be asked for a password; it is never saved in shell history):

```bash
cd /opt/gawachabazaar
docker compose --env-file .env.aws -f docker-compose.aws.yml run --rm backend \
  python scripts/create_admin.py --name "Owner Name" --email owner@example.com --phone 9876543210
```

Use that e-mail and password to sign in at `https://admin.gawachabazaar.in`.

### Step 4.14 - Smoke test  [ ]

```bash
cd /opt/gawachabazaar
deploy/scripts/smoke-test.sh .env.aws
```

It checks these and prints `ok` or `FAIL` per line:

| Check | Expected |
|---|---|
| `/health`, `/health/db`, `/readiness` on the API | 200 |
| Public catalog `/api/v1/catalog/categories` | 200 |
| `/docs` on the API (must be disabled in production) | 404 |
| `/api/v1/auth/me` without a token | 401 |
| HSTS and `nosniff` headers | present |
| `http://api...` redirects | 308 |
| Admin `/login` | 200, with a frame-deny header |
| Website home | 200; `www` redirect 301 |

All lines must say `ok` and the last line `All smoke checks passed.` Also open the three sites in a browser and confirm a padlock.

### Step 4.15 - Wire up the outside services  [ ]

1. **Admin settings:** sign in to the Admin panel -> **Settings** -> choose the packing point (warehouse) if you did not set the `PACKING_POINT_*` variables.
2. **Firebase authorized domains:** Firebase console -> Authentication -> Settings -> **Authorized domains** -> add `admin.gawachabazaar.in` (and your site domain). Without it Admin sign-in fails.
3. **Razorpay webhook:** Razorpay dashboard -> Webhooks -> add `https://api.gawachabazaar.in/api/v1/payments/webhooks/razorpay`, set the secret to exactly your `RAZORPAY_WEBHOOK_SECRET`, enable payment events. (Staging: use the test-mode dashboard.)
4. **Firebase for the mobile app:** register the release signing key's SHA-1/SHA-256 fingerprints in the Android app in Firebase, or Google sign-in fails.

### Step 4.16 - Point the mobile app at the new API  [ ]

The mobile app is built with Expo EAS; it never connects to AWS directly, only to your API URL. In `mobile/eas.json` the `preview` and `production` profiles already set `EXPO_PUBLIC_API_BASE_URL` to `https://api.gawachabazaar.in/api/v1`; if your domain differs, change it **before** building. Production builds must use the production Firebase project. From your laptop:

```bash
cd mobile
npm install
npx eas login
npx eas build --platform android --profile production
```

JavaScript-only changes later can be shipped as an over-the-air update (`eas update`, with the channel of the installed build); native or dependency changes need a rebuild. Push notifications require the Firebase service-account key to be uploaded to the Expo/EAS project (status for the current project is unverified in the docs). Do not publish to the stores until the acceptance test below passes.

### Step 4.17 - Acceptance test (do this before announcing)  [ ]

Using staging with Razorpay **test** keys and a real Nagpur address, walk through one order and compare what you see in three places:

| Check | API / screen | Database |
|---|---|---|
| Log in with Firebase | login succeeds | user row exists |
| Save 3 real Nagpur addresses with "Find this address on the map" | distance and fee shown | stored values equal the server's |
| Place an order and pay (test payment) | order confirmed | `payments.status = PAID`, one row, one order |
| Order history | order listed | stock reserved/consumed as expected |
| Tamper test (send a fake `delivery_fee`) | ignored | stored values are the server's |
| Second quote for the same place | faster (cache hit) | - |

Only then repeat the whole guide for production with: a **separate RDS**, **separate Firebase project**, **`rzp_live_` keys**, production domains.

---

## Part 5 - Everyday operations

### 5.1 Release a new version

1. **Take a manual RDS snapshot first** (RDS console -> your DB -> Actions -> Take snapshot) whenever the release changes the database.
2. On the server:

```bash
sudo -iu deploy
cd /opt/gawachabazaar
git fetch --tags
git checkout <release-tag>
ENV_FILE=.env.aws COMPOSE_FILE_NAME=docker-compose.aws.yml deploy/scripts/deploy.sh
deploy/scripts/smoke-test.sh .env.aws
```

Migrations run automatically before the new backend starts. Write down the tag you replaced so you can go back.

### 5.2 Roll back

- **Code:** `git checkout <previous-tag>` and run `deploy.sh` again (same command as above).
- **Database:** do **not** use `alembic downgrade` in production. The project uses expand-then-contract migrations, so older code normally still works against a newer schema. If a migration truly went wrong, restore the snapshot you took into a **new** RDS instance and change `DATABASE_URL` to its endpoint, then redeploy.
- **Settings:** restore the previous `.env.aws` (keep a copy as `.env.aws.prev` before changing) and redeploy.
- **Map data:** point `OSRM_DATA_DIR` back to the old folder, restart `osrm`, then flush Redis.

### 5.3 Backups

- RDS automatic backups (retention 7 days) with point-in-time recovery; deletion protection on; a manual snapshot before schema-changing releases.
- **Practise a restore once** (in staging): restore the latest snapshot or a point in time to a *new* instance, connect from the server, compare table row counts and `alembic_version`, run the smoke test against it, then delete the test instance. Until you do this, treat backups as unproven.
- Nothing on the server's disk needs backing up except `.env.aws` (keep a secure copy in your password manager) and, optionally, the `osrm-data` folder (it can be rebuilt).

### 5.4 Monitoring (minimum, in CloudWatch)

| Alarm | Rule |
|---|---|
| Server status check failed | `StatusCheckFailed` > 0 |
| Server CPU | > 80% for 10 minutes |
| Server memory | > 85% (needs the CloudWatch agent) |
| Server disk | > 80% (needs the CloudWatch agent) |
| RDS CPU | > 80% for 10 minutes |
| RDS free storage | < 4 GB |
| RDS connections | > 80 |
| API availability | external uptime check of `https://api.../readiness` (free services exist) |

Logs: the containers keep 5 x 10 MB of logs each (`docker compose ... logs`). Request logs hide the `token=` query value; passwords and payment secrets are not logged.

### 5.5 Renewals and routine care

- HTTPS certificates renew automatically via Caddy; keep ports 80/443 open.
- Ubuntu security updates install automatically (`unattended-upgrades`).
- Refresh OSRM map data every 3-6 months (edit the URL/MD5/box in `build.sh`, build into a **new** folder, change `OSRM_DATA_DIR`, run `docker compose ... up -d osrm`, then flush Redis).
- Rotate any secret that was ever shared in chat or committed (see `SECRETS_MANAGEMENT.md`).

---

## Part 6 - Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `deploy.sh` says "Missing .env.aws" or lists `CHANGE_ME` lines | Settings file not filled | Edit `.env.aws` until no `CHANGE_ME` remains |
| `docker compose` complains "DATABASE_URL ... is required" | A required variable is empty | Fill the named variable |
| Backend container keeps restarting | Missing Firebase project id; Razorpay key id set without secrets; OTP secret shorter than 32 characters | Read `logs backend`; fix the named setting |
| Backend cannot reach the database / times out | Wrong endpoint or password; `gb-rds` does not allow `gb-app`; missing `?sslmode=require`; password characters not URL-encoded | Re-check the URL and the security-group source |
| Browser shows a certificate error | DNS not yet pointing at the Elastic IP, or ports 80/443 blocked | Fix DNS/security group; `logs caddy`; wait a few minutes |
| 502 Bad Gateway | Backend still starting or crashed | `docker compose ps`; `logs backend` |
| Admin login fails | Domain not in Firebase authorized domains; wrong `NEXT_PUBLIC_*` values (they are baked in at build time, so rebuild after changing) | Fix Firebase; edit `.env.aws`; run `deploy.sh` again |
| Nobody can log in | `FIREBASE_SERVICE_ACCOUNT_JSON` missing or mangled | Check how it was written into `.env.aws` |
| Delivery quote fails / 503 for paid-delivery baskets | OSRM down or `osrm-data` missing, or address outside the clipped box | `logs osrm`; rerun step 4.10 |
| `osrm` exits immediately ("exec format error" / "no matching manifest") | Arm server with an image digest that has no Arm build [UNVERIFIED] | Use an x86 `t3.medium` instead |
| Payments not confirmed | Webhook secret mismatch or wrong URL | Compare Razorpay webhook settings with `.env.aws` |
| Out-of-memory during the first build | Small instance | Make sure swap exists (`swapon --show`); use `t4g.medium` |
| 503 `SERVER_BUSY` under heavy load | The backend deliberately sheds load when its in-flight limit is reached | Load test; consider a bigger instance - **do not add workers** |
| Price/fee surprises | An old environment value overriding defaults | Re-read `.env.aws` for `DELIVERY_*` |

Useful commands (run in `/opt/gawachabazaar`, as `deploy`):

```bash
docker compose --env-file .env.aws -f docker-compose.aws.yml ps              # what is running
docker compose --env-file .env.aws -f docker-compose.aws.yml logs --tail=100 backend
docker compose --env-file .env.aws -f docker-compose.aws.yml restart backend
docker compose --env-file .env.aws -f docker-compose.aws.yml up -d --build   # rebuild after changes
docker stats --no-stream                                                      # memory/CPU per container
df -h && free -m                                                              # disk and memory on the server
```

---

## Part 7 - Security checklist (tick before production)

- [ ] Root account has MFA; daily work uses a separate admin user with MFA
- [ ] Budget alarm set (about $60)
- [ ] Port 22 is closed (SSM only); only 80 and 443 are open to the internet
- [ ] RDS is private (`Publicly accessible = No`), SSL required in `DATABASE_URL`, backups 7+ days, deletion protection on
- [ ] `.env.aws` has mode `600`, is not in Git, and a copy is stored only in the password manager
- [ ] Production uses **live** Razorpay keys; staging uses **test** keys; staging and production use separate Firebase projects and databases
- [ ] `FIREBASE_SERVICE_ACCOUNT_JSON` is not in any `NEXT_PUBLIC_` or `EXPO_PUBLIC_` setting
- [ ] `DELIVERY_OTP_ENFORCED=true` and `DELIVERY_OTP_SECRET` is at least 32 characters
- [ ] `/docs` returns 404 on the API (smoke test)
- [ ] Any secret that was ever pasted into chat or committed has been rotated (project note: SECR-1, committed key still to rotate)
- [ ] Tested restore from an RDS snapshot
- [ ] Real warehouse coordinates set; three real addresses priced correctly
- [ ] One real order verified end to end

---

## Part 8 - Complete reference

### 8.1 Containers in `docker-compose.aws.yml`

| Container | Image / build | Memory limit | Network | Role |
|---|---|---|---|---|
| `redis` | `redis:7-alpine`, 64 MB maxmemory, no persistence | 128 MB | backend | Route cache |
| `osrm` | `ghcr.io/project-osrm/osrm-backend` (pinned digest), data mounted read-only | 384 MB, 1 CPU | backend | Road distances |
| `migrate` | built from `./backend` | - | backend | `alembic upgrade head`, runs once and exits |
| `backend` | built from `./backend`, 1 worker | 640 MB | backend | API on port 8000 |
| `admin` | built from `./Admin` (Firebase keys baked in) | none set | web | Staff panel on port 3001 |
| `website` | built from `./website` | none set | web | Promo site on port 3000 |
| `caddy` | `caddy:2-alpine` | - | web + backend | Ports 80/443, HTTPS, redirects, 10 MB request limit on the API |

Measured on a developer laptop (not AWS): backend memory at most 176 MB at 100 concurrent users, OSRM about 90 MB, Redis about 5 MB. Admin/website memory is unmeasured.

### 8.2 Domains and routing (Caddy)

| Domain | Goes to | Notes |
|---|---|---|
| `SITE_DOMAIN` | `website:3000` | |
| `www.SITE_DOMAIN` | permanent redirect to `SITE_DOMAIN` | needs its own DNS record |
| `ADMIN_DOMAIN` | `admin:3001` | |
| `API_DOMAIN` | `backend:8000` | WebSocket upgrades pass through; request bodies capped at 10 MB (image uploads are capped at 8 MB by the app); HSTS header added |

### 8.3 Health endpoints

| URL | Meaning |
|---|---|
| `https://API_DOMAIN/health` | The process is alive (no database check) |
| `https://API_DOMAIN/health/db` | Database reachable (503 if not) |
| `https://API_DOMAIN/readiness` | Ready to serve traffic |

### 8.4 Behaviour that will surprise beginners

- The backend **will not start** when: `FIREBASE_PROJECT_ID` is empty; `RAZORPAY_KEY_ID` is set without both other Razorpay values; `DELIVERY_OTP_SECRET` is under 32 characters while enforcement is on.
- Admin `NEXT_PUBLIC_*` values are **baked into the Admin image at build time** - changing them needs a rebuild/redeploy.
- Empty `RAZORPAY_KEY_ID` = online payments off (Cash on Delivery only).
- If Redis is down delivery still works (just more OSRM calls). If OSRM is down, quotes for baskets that pay per-km delivery return 503 by design.
- Only the backend computes prices, fees, discounts and statuses; the apps cannot override them.

### 8.5 Optional: automated deploys from Forgejo

`.forgejo/workflows/ci.yml` (checks) and `.forgejo/workflows/deploy-aws.yml` (manual "workflow dispatch" with a Git ref: deploy to staging, smoke test, then production after an approval in a protected `production` environment, over SSH as the `deploy` user) are written but **have never been run** and need SSH access, which this guide deliberately keeps closed. Deploy by hand with Step 5.1 until you decide otherwise. The older `deploy.yml` (Kubernetes/EKS) is manual-only and is **not** part of this guide - do not run it.

### 8.6 What is NOT verified (be honest in your own checklist)

1. Nothing in this guide has been executed on a real AWS account.
2. The OSRM container image on Arm (`t4g`) servers.
3. Exact AWS console labels and the SSM Session Manager connection on the Ubuntu AMI.
4. Parsing of a long single-line Firebase JSON in `.env.aws`.
5. RDS restore time, `max_connections`, `rds.force_ssl` on your parameter group.
6. API speed on Graviton hardware under real load (the load tests were run on a laptop).
7. Razorpay sandbox end to end, and push notifications from the current EAS project.

### 8.7 Glossary

| Term | Meaning |
|---|---|
| EC2 | Amazon's rentable virtual servers |
| RDS | Amazon's managed databases |
| VPC / subnet | Your private network inside AWS |
| Security group | Firewall attached to a server or database |
| Elastic IP | A public IP address that stays the same |
| SSM Session Manager | A browser terminal into the server with no open SSH port |
| IAM role | Permissions given to a server or person |
| Docker / container | A packaged program that runs the same everywhere |
| Docker Compose | Starts many containers from one file |
| Caddy | The web gateway that obtains HTTPS certificates |
| OSRM | Open-source road routing engine |
| Alembic migration | A versioned database change |
| PITR | Point-in-time recovery of the database |
| Snapshot | A saved copy of the database at one moment |
| `.env` file | A text file of settings and secrets |
