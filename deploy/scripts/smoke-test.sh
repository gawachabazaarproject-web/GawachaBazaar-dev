#!/usr/bin/env bash
# Post-deploy smoke test against the public HTTPS endpoints.
# Reads the domains from .env.production (or pass an env file path).
#
#   deploy/scripts/smoke-test.sh [.env.production]
#
# CURL_OPTS adds curl flags, e.g. for a local rehearsal behind Caddy's
# internal CA:  CURL_OPTS="--cacert root.crt --resolve api.x.localhost:443:127.0.0.1"
set -uo pipefail

cd "$(dirname "$0")/../.."
ENV_FILE="${1:-.env.production}"
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a
read -r -a EXTRA <<< "${CURL_OPTS:-}"

fail=0
check() {
	local name="$1" url="$2" expect="$3"
	local code
	code=$(curl "${EXTRA[@]}" -s -o /dev/null -w '%{http_code}' --max-time 15 "$url")
	if [ "$code" = "$expect" ]; then
		printf '  ok    %-34s %s\n' "$name" "$code"
	else
		printf '  FAIL  %-34s got %s, want %s  (%s)\n' "$name" "$code" "$expect" "$url"
		fail=1
	fi
}

header_check() {
	local name="$1" url="$2" header="$3"
	if curl "${EXTRA[@]}" -s -D - -o /dev/null --max-time 15 "$url" | grep -qi "^$header"; then
		printf '  ok    %-34s present\n' "$name"
	else
		printf '  FAIL  %-34s missing %s\n' "$name" "$header"
		fail=1
	fi
}

echo "API  https://$API_DOMAIN"
check "health"                    "https://$API_DOMAIN/health" 200
check "health/db"                 "https://$API_DOMAIN/health/db" 200
check "catalog (public)"          "https://$API_DOMAIN/api/v1/catalog/categories" 200
check "docs disabled in prod"     "https://$API_DOMAIN/docs" 404
check "auth required"             "https://$API_DOMAIN/api/v1/auth/me" 401
header_check "HSTS"               "https://$API_DOMAIN/health" "strict-transport-security"
header_check "nosniff"            "https://$API_DOMAIN/health" "x-content-type-options"
check "http -> https redirect"    "http://$API_DOMAIN/health" 308

echo "Admin  https://$ADMIN_DOMAIN"
check "login page"                "https://$ADMIN_DOMAIN/login" 200
header_check "frame deny"         "https://$ADMIN_DOMAIN/login" "x-frame-options"

echo "Website  https://$SITE_DOMAIN"
check "home"                      "https://$SITE_DOMAIN/" 200
check "www redirect"              "https://www.$SITE_DOMAIN/" 301

[ $fail -eq 0 ] && echo "All smoke checks passed." || { echo "Smoke test FAILED."; exit 1; }
