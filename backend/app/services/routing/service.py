"""RoutingService: cached road distance between two points.

OSRM only answers "how far by road"; pricing lives in delivery_pricing.py.
The cache key is derived from the (rounded, ~11 m) coordinates and the
provider, so an edited address can never read a stale route and no
invalidation is needed. A per-key lock stops concurrent identical requests
(stampede) from all calling the router; this is correct for the current
single-worker deployment.
"""

import logging
import threading
import time

from app.core.config import settings
from app.services.routing.base import RouteResult, RoutingProvider, validate_coordinates
from app.services.routing.cache import RouteCache, route_cache
from app.services.routing.osrm import OSRMProvider

logger = logging.getLogger(__name__)

_LOCK_WAIT_SECONDS = 5.0
_key_locks: dict[str, threading.Lock] = {}
_key_locks_guard = threading.Lock()


def get_routing_provider() -> RoutingProvider:
    # Only "osrm" exists; add new providers here keyed by settings.ROUTING_PROVIDER.
    return OSRMProvider()


def _lock_for(key: str) -> threading.Lock:
    with _key_locks_guard:
        if len(_key_locks) > 2048:
            _key_locks.clear()
        return _key_locks.setdefault(key, threading.Lock())


def _from_cache(cached: dict) -> RouteResult:
    return RouteResult(cached["distance_meters"], cached["duration_seconds"], cached["provider"])


class RoutingService:
    def __init__(
        self, provider: RoutingProvider | None = None, cache: RouteCache | None = None
    ) -> None:
        self.provider = provider or get_routing_provider()
        self.cache = cache or route_cache

    def _key(self, o_lat: float, o_lng: float, d_lat: float, d_lng: float) -> str:
        return (
            f"route:v1:{self.provider.cache_namespace}:"
            f"{o_lat:.4f},{o_lng:.4f}:{d_lat:.4f},{d_lng:.4f}"
        )

    def get_route(self, o_lat: float, o_lng: float, d_lat: float, d_lng: float) -> RouteResult:
        """Raises RoutingError / NoRouteError; never returns a guess."""
        validate_coordinates(o_lat, o_lng)
        validate_coordinates(d_lat, d_lng)
        key = self._key(o_lat, o_lng, d_lat, d_lng)

        cached = self.cache.get(key)
        if cached:
            logger.info("routing cache=hit provider=%s", self.provider.name)
            return _from_cache(cached)

        with _lock_for(key):
            cached = self.cache.get(key)  # another request may have filled it
            if cached:
                logger.info("routing cache=hit provider=%s", self.provider.name)
                return _from_cache(cached)
            token = self.cache.try_lock(key)
            if token is None:
                # Another worker is already asking the router: wait for its answer.
                deadline = time.monotonic() + _LOCK_WAIT_SECONDS
                while time.monotonic() < deadline:
                    time.sleep(0.05)
                    cached = self.cache.get(key)
                    if cached:
                        logger.info("routing cache=hit provider=%s waited=true", self.provider.name)
                        return _from_cache(cached)
                logger.warning("routing lock_wait_timeout provider=%s", self.provider.name)
                token = ""  # fail open: ask the router ourselves
            started = time.monotonic()
            try:
                # Route with the same rounded coordinates the key uses.
                result = self.provider.calculate_route(
                    round(o_lat, 4), round(o_lng, 4), round(d_lat, 4), round(d_lng, 4)
                )
            except Exception as exc:
                self.cache.release_lock(key, token)
                logger.warning(
                    "routing cache=miss provider=%s status=failed error=%s latency_ms=%d",
                    self.provider.name,
                    type(exc).__name__,
                    (time.monotonic() - started) * 1000,
                )
                raise
            logger.info(
                "routing cache=miss provider=%s status=ok distance_m=%d latency_ms=%d",
                self.provider.name,
                result.distance_meters,
                (time.monotonic() - started) * 1000,
            )
            self.cache.set(
                key,
                {
                    "distance_meters": result.distance_meters,
                    "distance_km": result.distance_km,
                    "duration_seconds": result.duration_seconds,
                    "provider": result.provider,
                },
                settings.ROUTE_CACHE_TTL_SECONDS,
            )
            self.cache.release_lock(key, token)
            return result
