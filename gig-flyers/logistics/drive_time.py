"""One-way drive time from home to a venue: venue profile, then Google Maps, then a flagged estimate."""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from logistics.profiles import VenueProfile

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DriveEstimate:
    minutes: int
    source: str
    confirmed: bool


def maps_api_key() -> str:
    return os.getenv("GOOGLE_MAPS_API_KEY", "").strip()


def home_address() -> str:
    return os.getenv("BAND_HOME_ADDRESS", "").strip()


def round_up_to_5(seconds: float) -> int:
    return int(math.ceil(seconds / 60 / 5) * 5)


def _http_get_json(url: str) -> dict:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class MapsLookup:
    minutes: Optional[int]
    status: str
    error_message: str = ""


_CACHE_TTL_SECONDS = 6 * 3600
_cache: dict[tuple[str, str, str], tuple[float, int]] = {}


def query_distance_matrix(
    origin: str,
    destination: str,
    departure: Optional[datetime] = None,
    *,
    api_key: Optional[str] = None,
    http_get: Callable[[str], dict] = _http_get_json,
) -> MapsLookup:
    """One Distance Matrix request, reporting Google's status so setup problems are visible."""
    key = api_key if api_key is not None else maps_api_key()
    if not key:
        return MapsLookup(None, "NO_API_KEY")
    if not origin:
        return MapsLookup(None, "NO_HOME_ADDRESS")
    if not destination:
        return MapsLookup(None, "NO_DESTINATION")
    params = {"origins": origin, "destinations": destination, "mode": "driving", "units": "imperial", "key": key}
    if departure is not None and departure.timestamp() > datetime.now().timestamp():
        params["departure_time"] = str(int(departure.timestamp()))
    try:
        payload = http_get(f"{DISTANCE_MATRIX_URL}?{urlencode(params)}")
    except Exception as exc:  # noqa: BLE001
        return MapsLookup(None, "HTTP_ERROR", type(exc).__name__)
    status = str(payload.get("status", "UNKNOWN"))
    if status != "OK":
        return MapsLookup(None, status, str(payload.get("error_message", "")))
    try:
        element = payload["rows"][0]["elements"][0]
    except (KeyError, IndexError, TypeError):
        return MapsLookup(None, "NO_ROUTE")
    element_status = str(element.get("status", "UNKNOWN"))
    if element_status != "OK":
        return MapsLookup(None, element_status)
    seconds = (element.get("duration_in_traffic") or element["duration"])["value"]
    return MapsLookup(round_up_to_5(seconds), "OK")


def google_drive_minutes(
    origin: str,
    destination: str,
    departure: Optional[datetime] = None,
    *,
    api_key: Optional[str] = None,
    http_get: Callable[[str], dict] = _http_get_json,
) -> Optional[int]:
    """Traffic-aware drive time in minutes (rounded up to 5), or None if Maps can't answer."""
    cache_key = (origin, destination, departure.strftime("%Y-%m-%d %H") if departure else "")
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    result = query_distance_matrix(origin, destination, departure, api_key=api_key, http_get=http_get)
    if result.minutes is None:
        if result.status not in {"NO_API_KEY", "NO_HOME_ADDRESS", "NO_DESTINATION"}:
            logger.warning("Google Maps drive time unavailable for %s: %s %s", destination, result.status, result.error_message)
        return None
    _cache[cache_key] = (time.time(), result.minutes)
    return result.minutes


def resolve_drive(
    profile: VenueProfile,
    destination: str,
    departure: Optional[datetime] = None,
    *,
    lookup: Callable[..., Optional[int]] = google_drive_minutes,
) -> DriveEstimate:
    if profile.drive_minutes is not None:
        return DriveEstimate(profile.drive_minutes, profile.drive_source or "venue profile", True)
    minutes = lookup(home_address(), destination, departure)
    if minutes is not None:
        return DriveEstimate(minutes, "Google Maps", True)
    return DriveEstimate(profile.minutes("unknown_drive_minutes"), "estimate", False)
