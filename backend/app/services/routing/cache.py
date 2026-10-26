"""Route cache: Redis when REDIS_URL is set, otherwise a small in-process TTL
dict. Every Redis error is swallowed (logged) - caching must never make
delivery unavailable. Only route distances are cached, never fees."""

import json
import logging
import secrets
import threading
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_LOCAL = 4096
_BREAKER_SECONDS = 30


class RouteCache:
    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client
        self._redis_checked = redis_client is not None
        self._down_until = 0.0
        self._local: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def _trip(self, op: str, exc: Exception) -> None:
        """Circuit breaker: after a Redis error, skip Redis for a while (each
        failed call would otherwise cost up to the socket timeout) and serve
        from the per-worker in-process cache. Logged at WARNING."""
        if time.monotonic() >= self._down_until:
            logger.warning(
                "route_cache redis_unavailable op=%s error=%s - using the in-process "
                "cache for %ds", op, type(exc).__name__, _BREAKER_SECONDS,
            )
        self._down_until = time.monotonic() + _BREAKER_SECONDS

    def _client(self) -> Any | None:
        if time.monotonic() < self._down_until:
            return None
        if not self._redis_checked:
            self._redis_checked = True
            if settings.REDIS_URL:
                try:
                    import redis

                    self._redis = redis.Redis.from_url(
                        settings.REDIS_URL, socket_timeout=0.5, socket_connect_timeout=0.5
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("route_cache redis_init_failed error=%s", type(exc).__name__)
        return self._redis

    def get(self, key: str) -> dict | None:
        client = self._client()
        if client is not None:
            try:
                raw = client.get(key)
                return json.loads(raw) if raw else None
            except Exception as exc:  # noqa: BLE001 - Redis down / bad payload = miss
                self._trip("get", exc)
                return None
        with self._lock:
            hit = self._local.get(key)
            if hit and hit[0] > time.monotonic():
                return json.loads(hit[1])
            self._local.pop(key, None)
        return None

    def ping(self) -> bool:
        """True when Redis answers right now (used by /readiness only)."""
        client = self._client()
        if client is None:
            return False
        try:
            return bool(client.ping())
        except Exception as exc:  # noqa: BLE001
            self._trip("ping", exc)
            return False

    @property
    def is_shared(self) -> bool:
        """True when backed by Redis (shared between workers/instances)."""
        return self._client() is not None

    def try_lock(self, key: str, ttl: int = 15) -> str | None:
        """Distributed single-flight lock. Returns a token when acquired, ""
        when there is no (working) Redis so the caller just proceeds, and None
        when another worker holds it."""
        client = self._client()
        if client is None:
            return ""
        token = secrets.token_hex(8)
        try:
            return token if client.set(f"lock:{key}", token, nx=True, ex=ttl) else None
        except Exception as exc:  # noqa: BLE001
            self._trip("lock", exc)
            return ""

    def release_lock(self, key: str, token: str | None) -> None:
        client = self._client()
        if client is None or not token:
            return
        try:
            lock_key = f"lock:{key}"
            if client.get(lock_key) in (token, token.encode()):
                client.delete(lock_key)
        except Exception as exc:  # noqa: BLE001
            self._trip("unlock", exc)

    def set(self, key: str, value: dict, ttl: int) -> None:
        payload = json.dumps(value)
        client = self._client()
        if client is not None:
            try:
                client.set(key, payload, ex=ttl)
            except Exception as exc:  # noqa: BLE001
                self._trip("set", exc)
                client = None
            if client is not None:
                return
        with self._lock:
            if len(self._local) >= _MAX_LOCAL:
                self._local.clear()
            self._local[key] = (time.monotonic() + ttl, payload)


route_cache = RouteCache()
