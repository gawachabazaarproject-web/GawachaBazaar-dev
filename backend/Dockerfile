# Gawacha Bazaar backend - Python 3.11-slim, non-root.
# Used by both docker-compose.yml (dev: overrides CMD with --reload and
# bind-mounts the source) and docker-compose.prod.yml (runs as built).
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy requirements first for Docker layer caching. Every dependency ships
# a manylinux wheel (psycopg[binary], argon2-cffi, cryptography), so no
# compiler or libpq is needed in the image.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create the non-root user before copying source so ownership is set in
# the same layer as the files themselves (no second chown-everything layer)
RUN useradd --create-home --uid 1000 appuser

COPY --chown=appuser:appuser . .
RUN chmod +x start.sh

USER appuser

EXPOSE 8000

# /health is dependency-free (no DB) - it answers "is the process serving",
# which is what a container restart decision needs. /health/db is checked
# separately by the deploy smoke test.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

# Production command.
# - ONE worker, deliberately: the rate limiter (app/core/rate_limit.py),
#   the realtime WebSocket registry (app/core/realtime.py) and the
#   reservation-expiry sweep (main.py lifespan) are all in-process state.
#   Multiple workers would split WebSocket delivery across processes and
#   run the sweep N times. Sync routes already run on a thread pool.
# - --proxy-headers + --forwarded-allow-ips '*': trust X-Forwarded-For/Proto
#   from the reverse proxy so rate limiting keys on the real client IP and
#   HSTS sees https. Only safe because the prod compose file never
#   publishes port 8000 - the proxy is the only thing that can reach it.
# - --no-access-log: RequestIDMiddleware already logs method/path/status/
#   duration (without query strings), so uvicorn's access log is duplicate
#   noise. The realtime socket's ?token=<JWT> is kept out of uvicorn's
#   WebSocket handshake lines by RedactTokenQueryFilter (app/core/logging.py)
#   - those are logged on uvicorn.error, which this flag does not silence.
# Production entrypoint runs database migrations and starts uvicorn on $PORT
CMD ["./start.sh"]
