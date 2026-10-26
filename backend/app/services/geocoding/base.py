"""Geocoding provider interface (address text -> coordinates)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class GeocodingError(Exception):
    """The geocoder is unavailable or returned something unusable."""


@dataclass(frozen=True)
class GeocodeResult:
    display_name: str
    latitude: float
    longitude: float
    provider: str
    provider_id: str | None


class GeocodingProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        """Raises GeocodingError. An empty list means 'no match'."""
