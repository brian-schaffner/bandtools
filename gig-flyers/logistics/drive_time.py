"""One-way drive time from home to a venue: venue profile, then Google Maps, then a flagged estimate."""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from logistics.profiles import VenueProfile

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
ROUTES_FIELD_MASK = "routes.duration,routes.staticDuration"

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


def _band_timezone() -> ZoneInfo:
    """Schedule times are naive local times in the band's zone; the server clock may be UTC."""
    try:
        return ZoneInfo(os.getenv("GIG_CALENDAR_TIMEZONE", "America/Kentucky/Louisville"))
    except Exception:  # noqa: BLE001
        return ZoneInfo("America/New_York")


def round_up_to_5(seconds: float) -> int:
    return int(math.ceil(seconds / 60 / 5) * 5)


def _http_post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        # Google returns its error details as a JSON body on 4xx/5xx.
        try:
            return json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            return {"error": {"status": f"HTTP_{exc.code}", "message": str(exc.reason)}}


@dataclass(frozen=True)
class MapsLookup:
    minutes: Optional[int]
    status: str
    error_message: str = ""


_CACHE_TTL_SECONDS = 6 * 3600
_cache: dict[tuple[str, str, str], tuple[float, int]] = {}


def _parse_duration_seconds(value: str) -> Optional[float]:
    if not isinstance(value, str) or not value.endswith("s"):
        return None
    try:
        return float(value[:-1])
    except ValueError:
        return None


def query_routes(
    origin: str,
    destination: str,
    departure: Optional[datetime] = None,
    *,
    api_key: Optional[str] = None,
    http_post: Callable[[str, dict, dict[str, str]], dict] = _http_post_json,
) -> MapsLookup:
    """One Google Routes API request, reporting Google's status so setup problems are visible."""
    key = api_key if api_key is not None else maps_api_key()
    if not key:
        return MapsLookup(None, "NO_API_KEY")
    if not origin:
        return MapsLookup(None, "NO_HOME_ADDRESS")
    if not destination:
        return MapsLookup(None, "NO_DESTINATION")
    body: dict = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    if departure is not None:
        aware = departure if departure.tzinfo else departure.replace(tzinfo=_band_timezone())
        if aware.timestamp() > time.time():
            body["departureTime"] = aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": ROUTES_FIELD_MASK}
    try:
        payload = http_post(ROUTES_URL, body, headers)
    except Exception as exc:  # noqa: BLE001
        return MapsLookup(None, "HTTP_ERROR", type(exc).__name__)
    error = payload.get("error")
    if error:
        return MapsLookup(None, str(error.get("status") or error.get("code") or "ERROR"), str(error.get("message", "")))
    routes = payload.get("routes") or []
    if not routes:
        return MapsLookup(None, "NO_ROUTE")
    seconds = _parse_duration_seconds(routes[0].get("duration")) or _parse_duration_seconds(routes[0].get("staticDuration"))
    if seconds is None:
        return MapsLookup(None, "NO_ROUTE")
    return MapsLookup(round_up_to_5(seconds), "OK")


def google_drive_minutes(
    origin: str,
    destination: str,
    departure: Optional[datetime] = None,
    *,
    api_key: Optional[str] = None,
    http_post: Callable[[str, dict, dict[str, str]], dict] = _http_post_json,
) -> Optional[int]:
    """Traffic-aware drive time in minutes (rounded up to 5), or None if Maps can't answer."""
    cache_key = (origin, destination, departure.strftime("%Y-%m-%d %H") if departure else "")
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    result = query_routes(origin, destination, departure, api_key=api_key, http_post=http_post)
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
