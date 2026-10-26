"""Nominatim (OpenStreetMap) geocoder.

Usage policy of the public server: max ~1 request/second, a real identifying
User-Agent, no autocomplete / search-as-you-type, cache results. This
provider spaces calls >= 1 s apart and the API route is user-triggered
(search button), never per keystroke. For real traffic self-host Nominatim
or switch NOMINATIM_BASE_URL to a hosted provider.
"""

import logging
import threading
import time

import httpx

from app.core.config import settings
from app.services.geocoding.base import GeocodeResult, GeocodingError, GeocodingProvider

logger = logging.getLogger(__name__)

_MIN_INTERVAL = 1.0
_throttle_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    with _throttle_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


class NominatimProvider(GeocodingProvider):
    name = "nominatim"

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.NOMINATIM_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.GEOCODING_TIMEOUT_SECONDS

    def search(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        _throttle()
        try:
            resp = httpx.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": max(1, min(limit, 10)),
                    "countrycodes": "in",
                },
                headers={"User-Agent": settings.NOMINATIM_USER_AGENT},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("geocoding provider=nominatim status=failed error=%s", type(exc).__name__)
            raise GeocodingError("Address search is unavailable right now.") from exc
        if not isinstance(rows, list):
            raise GeocodingError("Address search returned an unexpected response.")

        results: list[GeocodeResult] = []
        for row in rows:
            try:
                lat, lng = float(row["lat"]), float(row["lon"])
                if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    continue
                results.append(
                    GeocodeResult(
                        display_name=str(row["display_name"]),
                        latitude=lat,
                        longitude=lng,
                        provider=self.name,
                        provider_id=str(row["place_id"]) if "place_id" in row else None,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        logger.info("geocoding provider=nominatim status=ok results=%d", len(results))
        return results


def get_geocoding_provider() -> GeocodingProvider:
    # Only "nominatim" exists; add providers here keyed by settings.GEOCODING_PROVIDER.
    return NominatimProvider()
