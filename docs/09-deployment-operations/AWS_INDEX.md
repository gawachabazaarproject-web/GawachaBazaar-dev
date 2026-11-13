# AWS deployment — index

> **Status (as of the repo docs, 2026-10-27): preparation only. Nothing has been deployed to AWS** ([KNOWN_ISSUES](../10-project-management/KNOWN_ISSUES.md) DEL-17). Every file below was written without an AWS account; the workflows and the restore drill are unrun. Targeted shape: one EC2 (`t4g.medium`, Elastic IP) running Docker Compose + private RDS PostgreSQL 16, region `ap-south-1`.
>
> This page only points to material; the linked files are the source of truth. If one disagrees with the code, trust the code and log it in KNOWN_ISSUES.

**New to AWS? Start with [AWS_DEPLOYMENT_GUIDE_BEGINNER](AWS_DEPLOYMENT_GUIDE_BEGINNER.md)** (also as a PDF in this folder) - a self-contained step-by-step walkthrough.

## 1. Read in this order

| # | Step | Document |
|---|---|---|
| 1 | Architecture decision, capacity, cost, security groups | [AWS_PRODUCTION_PLAN](AWS_PRODUCTION_PLAN.md) §1–5 |
| 2 | Accounts, secrets and settings you must supply | [AWS_CREDENTIALS_CHECKLIST](AWS_CREDENTIALS_CHECKLIST.md) |
| 3 | Measured behaviour (local, **not AWS**) | [AWS_PRODUCTION_PLAN](AWS_PRODUCTION_PLAN.md) §6 |
| 4 | Build the routing data | [AWS_PRODUCTION_PLAN](AWS_PRODUCTION_PLAN.md) §7, [`deploy/osrm/build.sh`](../../deploy/osrm/build.sh) |
| 5 | Database, Redis, compose hardening | [AWS_PRODUCTION_PLAN](AWS_PRODUCTION_PLAN.md) §8–10 |
| 6 | Staging plan (exact order) and acceptance test | [AWS_PRODUCTION_PLAN](AWS_PRODUCTION_PLAN.md) §14–15 |
| 7 | Blockers, then the go-live checklist | [AWS_PRODUCTION_PLAN](AWS_PRODUCTION_PLAN.md) §16, §18 |
| 8 | Operate: monitoring, backups, rollback, incidents | see §3 below |

## 2. Repository files

| What | File |
|---|---|
| AWS compose stack (Caddy, backend, Redis, private OSRM; RDS external) | [`docker-compose.aws.yml`](../../docker-compose.aws.yml) |
| Environment template (names only — never commit values) | [`.env.aws.example`](../../.env.aws.example) |
| CI workflow | [`.forgejo/workflows/ci.yml`](../../.forgejo/workflows/ci.yml) |
| AWS deploy workflow (manual `workflow_dispatch`, unrun) | [`.forgejo/workflows/deploy-aws.yml`](../../.forgejo/workflows/deploy-aws.yml) |
| Server bootstrap, deploy, smoke test | [`deploy/scripts/`](../../deploy/scripts) (`bootstrap-server.sh`, `deploy.sh`, `smoke-test.sh`) |
| DB backup / restore scripts (VPS-era; RDS snapshots replace them on AWS) | `backup-db.sh`, `restore-db.sh` in the same folder |
| Caddy reverse proxy / TLS | [`deploy/Caddyfile`](../../deploy/Caddyfile) |
| Firebase auth setup | [`deploy/FIREBASE_AUTH.md`](../../deploy/FIREBASE_AUTH.md) |
| Load tests | `backend/scripts/loadtest_{api,osrm,server}.py` |
| Health / readiness endpoints | `/health`, `/readiness` ([`backend/app/main.py`](../../backend/app/main.py)) |
| Legacy: EKS manifests (`k8s/`, overlay `k8s/overlays/aws`) and Contabo VPS compose | [DEPLOYMENT](DEPLOYMENT.md) §1–2 |

## 3. Operations

- [MONITORING_AND_LOGGING](MONITORING_AND_LOGGING.md) — CloudWatch agent, alarms (plan §12)
- [BACKUP_AND_RECOVERY](BACKUP_AND_RECOVERY.md) — RDS backups, restore drill (plan §13)
- [ROLLBACK](ROLLBACK.md) — previous image tag + `deploy.sh`, RDS snapshot before migrations
- [INCIDENT_RESPONSE](INCIDENT_RESPONSE.md)

## 4. Related context

- [DEPLOYMENT](DEPLOYMENT.md) — all deployment descriptions and their inconsistencies; owner decisions pending
- [ENVIRONMENT_VARIABLES](../06-development/ENVIRONMENT_VARIABLES.md), [SECRETS_MANAGEMENT](../08-security/SECRETS_MANAGEMENT.md)
- [MIGRATIONS](../04-database/MIGRATIONS.md) — never run against a shared/production DB casually; snapshot first
- [THIRD_PARTY_SERVICES](../11-integrations/THIRD_PARTY_SERVICES.md) — Firebase, Razorpay, Cloudinary stay external to AWS
- [DELIVERY](../05-domains/DELIVERY.md) — OSRM routing and pricing
- [AI_STATUS](../00-overview/AI_STATUS.md), [PRODUCTION_READINESS](../10-project-management/PRODUCTION_READINESS.md)

## 5. Open blockers (from plan §16)

1. No AWS account/credentials — nothing created or tested on AWS.
2. Mobile not yet run against an AWS staging backend; payment failure/duplicate cases untested on device.
3. Real warehouse coordinates (`PACKING_POINT_*`) not supplied.
4. Graviton per-core throughput unmeasured.
5. Restore drill, CloudWatch alarms and CI/CD workflows unrun.
6. Single host, single worker, single-AZ DB (accepted for month one).
7. Committed key rotation (SECR-1) and production variable confirmation (CFG-1) — see AI_STATUS.

## 6. Hard invariants when deploying

- **One backend worker only** (in-process rate limiter, WebSocket hub, reservation sweep).
- No public port except Caddy 80/443; no SSH (use SSM); RDS private with `sslmode=require`.
- Migrations run via `alembic upgrade head` on start — never rewrite a deployed revision; take an RDS snapshot first.
- Pushing to `main` triggers the legacy EKS/production workflows with no checks — see KNOWN_ISSUES CI-001.
