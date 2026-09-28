#!/bin/sh
# PostgreSQL backup for the db-backup service in docker-compose.prod.yml.
#
#   backup-db.sh          take one backup now, prune old ones, exit
#   backup-db.sh --loop   do that every BACKUP_INTERVAL_SECONDS (default 1 day)
#
# Connection comes from the standard libpq env vars (PGHOST, PGUSER,
# PGPASSWORD, PGDATABASE). Dumps are custom-format (-Fc): compressed, and
# restorable with pg_restore (see restore-db.sh). They land in /backups,
# which the compose file bind-mounts to ./backups on the host - copy that
# directory off the server too (Contabo snapshots or rsync), a backup on
# the same disk as the database is not a disaster-recovery plan by itself.
set -eu

BACKUP_DIR=/backups
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

backup_once() {
	stamp=$(date -u +%Y%m%dT%H%M%SZ)
	target="$BACKUP_DIR/${PGDATABASE}-${stamp}.dump"
	tmp="$target.partial"
	if pg_dump -Fc --no-owner --no-privileges -f "$tmp"; then
		mv "$tmp" "$target"
		echo "[backup] ok: $target ($(du -h "$target" | cut -f1))"
	else
		rm -f "$tmp"
		echo "[backup] FAILED at $stamp" >&2
		return 1
	fi
	find "$BACKUP_DIR" -name "${PGDATABASE}-*.dump" -type f -mtime +"$RETENTION_DAYS" -print -delete |
		sed 's/^/[backup] pruned: /'
}

mkdir -p "$BACKUP_DIR"

if [ "${1:-}" = "--loop" ]; then
	echo "[backup] every ${INTERVAL}s, keeping ${RETENTION_DAYS} days"
	while true; do
		backup_once || true
		sleep "$INTERVAL"
	done
else
	backup_once
fi
