#!/usr/bin/env bash
# Reproducible build of the Nagpur OSRM routing data. Run it ON DEMAND (first
# install, or when you decide to refresh the map) - never at application start.
#
#   ./build.sh                      # download, verify, clip, build into ./data
#   OUT=/srv/osrm ./build.sh
#   PBF_FILE=/path/western-zone.osm.pbf ./build.sh     # skip the download
#
# Output: $OUT/nagpur.osrm* (+ BUILD_INFO.json). docker-compose.prod.yml mounts
# that directory read-only into the `osrm` service.
set -euo pipefail

OUT="${OUT:-$(pwd)/data}"
# Geofabrik "western zone" snapshot (Maharashtra, Gujarat, Goa, ...). The dated
# URL is immutable; to refresh the map pick a newer dated file on
# https://download.geofabrik.de/asia/india.html and update URL + MD5 together.
PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/india/western-zone-261025.osm.pbf}"
PBF_MD5="${PBF_MD5:-fc396c6c2fc048ed0c6fcc5b9182ce6d}"
# Clip: min_lon,min_lat,max_lon,max_lat. ~80 km x 78 km around Nagpur; widen it
# if the delivery radius grows. Delivery beyond the box returns "no route".
BBOX="${BBOX:-78.7,20.8,79.5,21.5}"
# Pinned by digest (OSRM v26.10.0 when this was written).
OSRM_IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend@sha256:55dbfd47d984c2cacd64e32901b4321c86b5ec761438e69aa053dc78698a786f}"
OSMIUM_BASE_IMAGE="${OSMIUM_BASE_IMAGE:-debian:bookworm-slim}"

mkdir -p "$OUT"
cd "$OUT"
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: do not rewrite /data paths
HOST_DIR="$(pwd -W 2>/dev/null || pwd)"

if [ -n "${PBF_FILE:-}" ]; then
  cp -f "$PBF_FILE" source.osm.pbf
else
  curl -fL --retry 3 -o source.osm.pbf "$PBF_URL"
fi
actual_md5="$(md5sum source.osm.pbf | cut -d' ' -f1)"
if [ "$actual_md5" != "$PBF_MD5" ]; then
  echo "MD5 mismatch: expected $PBF_MD5 got $actual_md5" >&2; exit 1
fi

started=$(date +%s)
# 1. clip to the delivery area (official Debian osmium-tool package)
docker run --rm -v "$HOST_DIR:/data" "$OSMIUM_BASE_IMAGE" sh -c \
  "apt-get update -qq && apt-get install -y -qq osmium-tool >/dev/null && \
   osmium extract -b $BBOX --strategy=complete_ways --overwrite -o /data/nagpur.osm.pbf /data/source.osm.pbf"
# 2. OSRM MLD pipeline (car profile)
for step in "osrm-extract -p /opt/car.lua /data/nagpur.osm.pbf" "osrm-partition /data/nagpur.osrm" "osrm-customize /data/nagpur.osrm"; do
  docker run --rm -v "$HOST_DIR:/data" "$OSRM_IMAGE" $step
done
built=$(date +%s)

cat > BUILD_INFO.json <<JSON
{
  "source_url": "$PBF_URL",
  "source_md5": "$actual_md5",
  "source_bytes": $(wc -c < source.osm.pbf),
  "bbox_min_lon_min_lat_max_lon_max_lat": "$BBOX",
  "clipped_bytes": $(wc -c < nagpur.osm.pbf),
  "osrm_image": "$OSRM_IMAGE",
  "profile": "car, algorithm MLD",
  "built_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "build_seconds": $((built - started))
}
JSON
rm -f source.osm.pbf        # keep only the clipped input + built files
echo "OSRM data ready in $OUT"; cat BUILD_INFO.json
