#!/bin/sh
set -e

# Run database migrations
echo "==> Running database migrations..."
alembic upgrade head

# Start Uvicorn
# Render injects $PORT (usually 10000). Default to 8000 if not set.
PORT="${PORT:-8000}"
echo "==> Starting Uvicorn on port $PORT..."
exec uvicorn app.main:app \
     --host 0.0.0.0 \
     --port "$PORT" \
     --workers 1 \
     --proxy-headers \
     --forwarded-allow-ips "*" \
     --no-access-log \
     --timeout-graceful-shutdown 20
