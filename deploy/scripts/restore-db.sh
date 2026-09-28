#!/usr/bin/env bash
# Restore a pg_dump (-Fc) backup into the production database.
#
#   deploy/scripts/restore-db.sh backups/gawachabazaar-20260101T020000Z.dump
#
# DESTRUCTIVE: drops and recreates every object in the dump. Stops the
# backend first so nothing writes mid-restore, and takes a fresh safety
# backup before touching anything.
set -euo pipefail

cd "$(dirname "$0")/../.."
DUMP="${1:?usage: restore-db.sh <path-to-.dump>}"
[ -f "$DUMP" ] || { echo "No such file: $DUMP" >&2; exit 1; }

COMPOSE=(docker compose --env-file .env.production -f docker-compose.prod.yml)

read -r -p "Restore $DUMP over the LIVE production database? Type 'restore' to continue: " answer
[ "$answer" = "restore" ] || { echo "Aborted."; exit 1; }

echo "==> Safety backup of current state"
"${COMPOSE[@]}" exec -T db-backup /bin/sh /usr/local/bin/backup-db.sh

echo "==> Stopping backend"
"${COMPOSE[@]}" stop backend

echo "==> Restoring"
"${COMPOSE[@]}" exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$DUMP"

echo "==> Starting backend (migrations run first)"
"${COMPOSE[@]}" up -d migrate backend
echo "Done."
