"""Routing provider interface. Business code depends on this, never on OSRM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class RoutingError(Exception):
    """The provider could not answer (timeout, HTTP error, malformed reply)."""


class NoRouteError(RoutingError):
    """The provider answered, but there is no drivable route."""


@dataclass(frozen=True)
class RouteResult:
    distance_meters: int
    duration_seconds: int
    provider: str

    @property
    def distance_km(self) -> float:
        return round(self.distance_meters / 1000.0, 3)


def validate_coordinates(lat: float, lng: float) -> None:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("Coordinates out of range.")


class RoutingProvider(ABC):
    name: str

    @property
    def cache_namespace(self) -> str:
        """Part of the cache key: provider + routing profile + endpoint, so
        switching provider/endpoint/profile never reads another's routes."""
        return self.name

    @abstractmethod
    def calculate_route(
        self, origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float
    ) -> RouteResult:
        """Driving distance/duration. Raises RoutingError / NoRouteError."""
