# Rollback

> **Status:** Partially verified (derived from the deployment files; **no rollback was performed or rehearsed**). **Last verified:** 2026-10-14. No rollback procedure is written in the repository; this document assembles what each mechanism allows, with the constraints that matter. Always confirm which deployment is live first ([DEPLOYMENT](DEPLOYMENT.md)).

## Decision order

1. Is it a **code** problem (revert/redeploy an earlier build), a **configuration** problem (revert the variable), a **data/migration** problem (hardest), or a **mobile JS update** problem?
2. Take a backup before anything that touches data ([BACKUP_AND_RECOVERY](BACKUP_AND_RECOVERY.md)).
3. Prefer rolling **forward** with a small fix when a migration has already run and cannot be reversed.

## Backend

| Deployment | How to roll back | Notes / risks |
|---|---|---|
| **EKS (CI)** | `kubectl -n gawachabazaar rollout undo deployment/gawachabazaar-backend` (or `set image …:<previous SHA>`; images are tagged with the commit SHA and kept in Docker Hub) | Deployments keep revision history by default; the workflow adds the pull secret by patch. **The image runs `alembic upgrade head` on start**, so rolling back code does **not** roll back the schema; old code against a newer schema may break. Re-deploying a commit by pushing a revert to `main` re-runs the whole pipeline (no gates) |
| **VPS compose** | `git checkout <previous-good commit>` then `deploy/scripts/deploy.sh` (rebuilds and restarts); images are tagged `latest` locally, so there is no stored previous image — rebuild from git | If a migration fails during an update the **old backend keeps running** (the `migrate` gate). A successful but bad migration needs a restore or a forward fix |
| **AWS** | Dashboard: redeploy a previous deploy/commit (not in the repository) | Same schema caveat; `start.sh` migrates on boot |
| **Config-only issue** | Restore the previous value of the environment variable and redeploy/restart | Example: removing a bad `FIREBASE_SERVICE_ACCOUNT_JSON` restored sign-in on 2026-10-14 |

## Database migrations

- Check what the offending revision does ([MIGRATIONS](../04-database/MIGRATIONS.md)). `alembic downgrade -1` is possible for most revisions but **not** for: the Firebase identity revision (`c5f1a7e3d9b2`: refuses once Firebase-only users exist), the verification-table drop (`efae4c4402ba`: recreates empty tables), and data-seeding revisions (offers/home slides: downgrade deletes only untouched seeds).
- Never downgrade production without a fresh verified backup; prefer **restore** from a dump for anything involving data loss, and **forward fix** for additive changes.
- Because every container start runs `alembic upgrade head`, an old image started after a downgrade will upgrade the schema again to its own head — pin the image and the schema together.

## Admin panel and website

Redeploy the previous image tag (EKS/compose) or the previous Vercel deployment (promote an earlier one in the dashboard). `NEXT_PUBLIC_*` values are baked into each build, so a rollback also restores the environment of that build.

## Mobile app

| What shipped | How to undo |
|---|---|
| **OTA update** (`eas update`) | Publish the previous good commit to the **same channel**, or `eas update:republish`/rollback to an earlier update group (EAS CLI; not exercised here). Installed apps pick it up on the next launch(es) (`ON_LOAD`, 3 s cache fallback). A broken JS bundle can prevent the app from starting, in which case the app falls back to the embedded bundle only if the new update fails to load — verify on a device before relying on this |
| **Native build** (APK/AAB) | Cannot be recalled from devices; ship a corrected build with a higher version code; users on sideloaded APKs must reinstall |
| Backend contract change | Keep old app versions working: do not remove or rename API fields the installed app uses; the app and API are deployed independently |

## Payments, data and external side effects (cannot be rolled back by redeploying)

Razorpay captures/refunds, push notifications sent, Firebase user changes and Cloudinary uploads are external. After any rollback or restore, reconcile payments against Razorpay and run the diagnostic queries in [INCIDENT_RESPONSE](INCIDENT_RESPONSE.md) §3.

## Gaps

No rehearsed rollback, no stored "last known good" image reference for the VPS stack, no automatic rollback on failed health checks beyond Kubernetes' own rollout behaviour, no feature flags, and no schema/version compatibility policy between releases.
