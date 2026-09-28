#!/usr/bin/env bash
# Build and (re)start the production stack on the server.
#
#   deploy/scripts/deploy.sh            deploy the current checkout
#   deploy/scripts/deploy.sh --pull     git pull --ff-only first
#
# Migrations run automatically (the `migrate` service must finish
# successfully before `backend` starts), so a failed migration leaves the
# previous backend container running instead of starting new code against
# a half-migrated schema.
set -euo pipefail

cd "$(dirname "$0")/../.."
ENV_FILE=.env.production
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE - copy .env.production.example and fill it in." >&2; exit 1; }
if grep -q "CHANGE_ME" "$ENV_FILE"; then
	echo "$ENV_FILE still contains CHANGE_ME placeholders:" >&2
	grep -n "CHANGE_ME" "$ENV_FILE" >&2
	exit 1
fi

if [ "${1:-}" = "--pull" ]; then
	echo "==> git pull"
	git pull --ff-only
fi

echo "==> Validating compose config"
"${COMPOSE[@]}" config --quiet

echo "==> Building images"
"${COMPOSE[@]}" build --pull

echo "==> Starting stack"
"${COMPOSE[@]}" up -d --remove-orphans

echo "==> Status"
"${COMPOSE[@]}" ps

echo "==> Pruning dangling images"
docker image prune -f >/dev/null

echo
echo "Deployed. Run deploy/scripts/smoke-test.sh to verify the public endpoints."
