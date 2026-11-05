"""One-way drive time from home to a venue: venue profile, then Google Maps, then a flagged estimate."""

from __future__ import annotations

import json
import logging
import math
import os
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


def google_drive_minutes(
    origin: str,
    destination: str,
    departure: Optional[datetime] = None,
    *,
    api_key: Optional[str] = None,
    http_get: Callable[[str], dict] = _http_get_json,
) -> Optional[int]:
    """Traffic-aware drive time in minutes (rounded up to 5), or None if Maps can't answer."""
    key = api_key if api_key is not None else maps_api_key()
    if not (key and origin and destination):
        return None
    params = {"origins": origin, "destinations": destination, "mode": "driving", "units": "imperial", "key": key}
    if departure is not None and departure.timestamp() > datetime.now().timestamp():
        params["departure_time"] = str(int(departure.timestamp()))
    try:
        payload = http_get(f"{DISTANCE_MATRIX_URL}?{urlencode(params)}")
        element = payload["rows"][0]["elements"][0]
        if payload.get("status") != "OK" or element.get("status") != "OK":
            logger.warning("Google Maps could not route to %s: %s", destination, element.get("status"))
            return None
        seconds = (element.get("duration_in_traffic") or element["duration"])["value"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Maps drive time lookup failed for %s: %s", destination, exc)
        return None
    return round_up_to_5(seconds)


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
