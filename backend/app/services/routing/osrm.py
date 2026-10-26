"""OSRM `/route/v1/driving` provider (OpenStreetMap data)."""

import hashlib

import httpx

from app.core.config import settings
from app.services.routing.base import (
    NoRouteError,
    RouteResult,
    RoutingError,
    RoutingProvider,
    validate_coordinates,
)

# A delivery pin farther than this from any road cannot be routed reliably.
MAX_SNAP_METERS = 2000


class OSRMProvider(RoutingProvider):
    name = "osrm"

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.ROUTING_TIMEOUT_SECONDS

    @property
    def cache_namespace(self) -> str:
        # Endpoint hash: moving from the public demo server to a self-hosted
        # OSRM (different map data) automatically starts a fresh cache.
        return f"osrm:driving:{hashlib.sha1(self.base_url.encode()).hexdigest()[:8]}"

    def calculate_route(
        self, origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float
    ) -> RouteResult:
        validate_coordinates(origin_lat, origin_lng)
        validate_coordinates(destination_lat, destination_lng)
        # OSRM wants longitude,latitude - the reverse of how we store them.
        coords = f"{origin_lng},{origin_lat};{destination_lng},{destination_lat}"
        try:
            resp = httpx.get(
                f"{self.base_url}/route/v1/driving/{coords}",
                params={"overview": "false", "alternatives": "false", "steps": "false"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise RoutingError(f"OSRM unreachable: {type(exc).__name__}") from exc

        try:
            data = resp.json()
        except ValueError:
            data = None
        # OSRM reports "NoRoute"/"NoSegment" with HTTP 400 and a JSON body.
        if isinstance(data, dict) and data.get("code") in ("NoRoute", "NoSegment"):
            raise NoRouteError(f"OSRM: {data['code']}")
        if resp.status_code != 200:
            raise RoutingError(f"OSRM HTTP {resp.status_code}")
        try:
            if data["code"] != "Ok":
                raise RoutingError(f"OSRM code {data['code']}")
            route = data["routes"][0]
            meters = float(route["distance"])
            seconds = float(route["duration"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RoutingError("OSRM returned a malformed response") from exc
        if meters < 0 or seconds < 0:
            raise RoutingError("OSRM returned a negative distance")
        # OSRM snaps each point to the nearest road and still answers "Ok" when
        # that road is far away (e.g. a pin in the sea, or swapped lat/lng gave
        # a distance of 0 in testing). Such a distance is not trustworthy.
        for wp in data.get("waypoints") or []:
            snap = wp.get("distance") if isinstance(wp, dict) else None
            if isinstance(snap, (int, float)) and snap > MAX_SNAP_METERS:
                raise NoRouteError(f"OSRM: point is {round(snap)} m from the nearest road")
        return RouteResult(round(meters), round(seconds), self.name)
