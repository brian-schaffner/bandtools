#!/usr/bin/env python3
"""Fetch and parse Lindsey Lane Band gig calendar."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import List, Optional
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

DEFAULT_CALENDAR_URL = "https://www.lindseylane.com/dates/"
DEFAULT_TIMEZONE = "America/Kentucky/Louisville"
DEFAULT_BAND = "Lindsey Lane Band"
MEMORY_CACHE_TTL_SECONDS = 300
ROOT = Path(__file__).resolve().parent
DEFAULT_MOCK_GIGS_PATH = ROOT / "fixtures" / "mock_gigs.json"
DEFAULT_DISK_CACHE_PATH = ROOT / "cache" / "calendar.json"

logger = logging.getLogger(__name__)

_cache: dict[str, object] = {"fetched_at": 0.0, "events": [], "url": None}
_test_mode_override: Optional[bool] = None
_refresh_lock = threading.Lock()
_refresh_scheduled = False


@dataclass(frozen=True)
class CalendarCacheInfo:
    fetched_at: Optional[str]
    is_stale: bool
    source: str
    age_seconds: Optional[float]


_last_cache_info = CalendarCacheInfo(fetched_at=None, is_stale=False, source="none", age_seconds=None)


class CalendarUnavailableError(OSError):
    """Raised when no live data and no disk cache exists."""


def is_test_mode() -> bool:
    if _test_mode_override is not None:
        return _test_mode_override
    return os.getenv("GIG_FLYERS_TEST_MODE", "").strip().lower() in {"1", "true", "yes"}


def set_test_mode(enabled: bool) -> None:
    global _test_mode_override
    _test_mode_override = enabled


def disk_cache_path() -> Path:
    custom = os.getenv("GIG_CALENDAR_CACHE_PATH", "").strip()
    return Path(custom) if custom else DEFAULT_DISK_CACHE_PATH


def cache_ttl_seconds() -> int:
    return int(os.getenv("GIG_CALENDAR_CACHE_TTL_SECONDS", "21600"))


def fetch_timeout_seconds() -> int:
    return int(os.getenv("GIG_CALENDAR_FETCH_TIMEOUT_SECONDS", "45"))


def get_cache_info() -> CalendarCacheInfo:
    return _last_cache_info


def mock_gigs_path() -> Path:
    custom = os.getenv("GIG_FLYERS_MOCK_PATH", "").strip()
    return Path(custom) if custom else DEFAULT_MOCK_GIGS_PATH


def load_mock_data() -> dict:
    path = mock_gigs_path()
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _set_cache_info(
    fetched_at_unix: Optional[float],
    source: str,
    is_stale: bool,
) -> None:
    global _last_cache_info
    if fetched_at_unix is None:
        _last_cache_info = CalendarCacheInfo(
            fetched_at=None,
            is_stale=is_stale,
            source=source,
            age_seconds=None,
        )
        return
    fetched_at = datetime.fromtimestamp(fetched_at_unix, tz=timezone.utc).isoformat()
    _last_cache_info = CalendarCacheInfo(
        fetched_at=fetched_at,
        is_stale=is_stale,
        source=source,
        age_seconds=max(0.0, time.time() - fetched_at_unix),
    )


def _events_from_mock() -> List[GigEvent]:
    data = load_mock_data()
    events: List[GigEvent] = []
    for row in data.get("gigs", []):
        event_date = date.fromisoformat(row["date"])
        title = row.get("title", "")
        venue = row.get("venue") or _extract_venue(title)
        time_label = row.get("time", "")
        events.append(
            GigEvent(
                event_date=event_date,
                time_label=time_label,
                title=title,
                venue=venue,
                suggested_name=build_suggested_name(event_date, venue),
            )
        )
    events.sort(key=lambda e: (e.event_date, e.time_label))
    return _dedupe_events(events)


@dataclass
class GigEvent:
    event_date: date
    time_label: str
    title: str
    venue: str
    suggested_name: str

    @property
    def gig_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.venue.lower()).strip("-")
        return f"{self.event_date.isoformat()}_{slug}"

    def to_dict(self) -> dict:
        return {
            "gig_id": self.gig_id,
            "date": self.event_date.isoformat(),
            "short_date": format_short_date(self.event_date),
            "time": self.time_label,
            "title": self.title,
            "venue": self.venue,
            "suggested_name": self.suggested_name,
            "band": os.getenv("GIG_CALENDAR_BAND", DEFAULT_BAND),
        }


def format_short_date(event_date: date) -> str:
    return event_date.strftime("%b %d")


def build_suggested_name(event_date: date, venue: str) -> str:
    return f"{format_short_date(event_date)} {venue}"


def _parse_event_date(label: str) -> Optional[date]:
    label = (label or "").strip()
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(label, fmt).date()
        except ValueError:
            continue
    return None


def _extract_venue(title: str) -> str:
    title = unescape((title or "").strip())
    title = re.sub(r"^Hosting\s+", "", title, flags=re.I)
    title = title.replace("World Famous ", "")

    if " at " in title:
        return title.split(" at ", 1)[-1].strip()

    match = re.match(r"^(.+?)\s+\d+\s+", title)
    if match:
        return match.group(1).strip()

    if "," in title:
        return title.split(",", 1)[0].strip()

    return title


def _dedupe_events(events: List[GigEvent]) -> List[GigEvent]:
    seen: set[tuple[date, str, str]] = set()
    result: List[GigEvent] = []
    for event in events:
        key = (event.event_date, event.venue.lower(), event.title.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def _fetch_calendar_html(url: str) -> str:
    request = Request(
        url,
        headers={"User-Agent": "GigFlyers/1.0 (+https://github.com/gig-flyers)"},
    )
    with urlopen(request, timeout=fetch_timeout_seconds()) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_events(html: str) -> List[GigEvent]:
    events: List[GigEvent] = []
    articles = re.findall(
        r'<article[^>]*class="[^"]*mec-event-article[^"]*"[^>]*>(.*?)</article>',
        html,
        re.S,
    )

    for article in articles:
        date_match = re.search(r'mec-start-date-label">([^<]+)', article)
        title_match = re.search(r'mec-event-title[^>]*>.*?<a[^>]*>([^<]+)', article, re.S)
        time_match = re.search(r'mec-start-time">([^<]+)', article)
        if not date_match or not title_match:
            continue

        event_date = _parse_event_date(date_match.group(1).strip())
        if not event_date:
            continue

        title = unescape(title_match.group(1).strip())
        venue = _extract_venue(title)
        events.append(
            GigEvent(
                event_date=event_date,
                time_label=time_match.group(1).strip() if time_match else "",
                title=title,
                venue=venue,
                suggested_name=build_suggested_name(event_date, venue),
            )
        )

    events.sort(key=lambda e: (e.event_date, e.time_label))
    return _dedupe_events(events)


def _load_disk_cache(url: str) -> Optional[tuple[float, List[GigEvent]]]:
    path = disk_cache_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read calendar disk cache: %s", exc)
        return None
    if payload.get("url") != url:
        return None
    fetched_at = float(payload.get("fetched_at_unix", 0.0))
    rows = payload.get("events", [])
    if not rows or not fetched_at:
        return None
    events = [_event_from_cache_row(row) for row in rows]
    return fetched_at, events


def _save_disk_cache(url: str, events: List[GigEvent], fetched_at: float) -> None:
    path = disk_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.fromtimestamp(fetched_at, tz=timezone.utc).isoformat(),
        "fetched_at_unix": fetched_at,
        "url": url,
        "event_count": len(events),
        "events": [event.to_dict() for event in events],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _event_from_cache_row(row: dict) -> GigEvent:
    event_date = date.fromisoformat(row["date"])
    venue = row.get("venue", "")
    return GigEvent(
        event_date=event_date,
        time_label=row.get("time", ""),
        title=row.get("title", ""),
        venue=venue,
        suggested_name=row.get("suggested_name") or build_suggested_name(event_date, venue),
    )


def _memory_cache_valid(url: str, now: float, force_refresh: bool) -> bool:
    if force_refresh:
        return False
    return (
        bool(_cache.get("events"))
        and now - float(_cache.get("fetched_at", 0.0)) < MEMORY_CACHE_TTL_SECONDS
        and _cache.get("url") == url
    )


def _apply_memory_cache(url: str, events: List[GigEvent], fetched_at: float, source: str, is_stale: bool) -> List[GigEvent]:
    _cache["events"] = events
    _cache["fetched_at"] = fetched_at
    _cache["url"] = url
    _set_cache_info(fetched_at, source, is_stale)
    return list(events)


def _schedule_background_refresh(url: str) -> None:
    global _refresh_scheduled

    def _worker() -> None:
        global _refresh_scheduled
        try:
            get_all_events(force_refresh=True, calendar_url=url, allow_stale=True, background_refresh=False)
        except OSError as exc:
            logger.warning("Background calendar refresh failed: %s", exc)
        finally:
            with _refresh_lock:
                _refresh_scheduled = False

    with _refresh_lock:
        if _refresh_scheduled:
            return
        _refresh_scheduled = True
    threading.Thread(target=_worker, name="calendar-refresh", daemon=True).start()


def _fetch_live_events(url: str) -> List[GigEvent]:
    html = _fetch_calendar_html(url)
    return _parse_events(html)


def get_all_events(
    force_refresh: bool = False,
    calendar_url: Optional[str] = None,
    allow_stale: bool = True,
    background_refresh: bool = False,
) -> List[GigEvent]:
    if is_test_mode():
        cache_key = f"mock:{mock_gigs_path()}"
        now = time.time()
        if _memory_cache_valid(cache_key, now, force_refresh):
            _set_cache_info(float(_cache["fetched_at"]), "memory", False)  # type: ignore[arg-type]
            return list(_cache["events"])  # type: ignore[arg-type]

        events = _events_from_mock()
        return _apply_memory_cache(cache_key, events, now, "mock", False)

    url = calendar_url or os.getenv("GIG_CALENDAR_URL", DEFAULT_CALENDAR_URL)
    now = time.time()
    ttl = cache_ttl_seconds()

    if _memory_cache_valid(url, now, force_refresh):
        _set_cache_info(float(_cache["fetched_at"]), "memory", False)  # type: ignore[arg-type]
        return list(_cache["events"])  # type: ignore[arg-type]

    disk_entry = _load_disk_cache(url)
    disk_fresh = bool(disk_entry and now - disk_entry[0] < ttl)

    if not force_refresh and disk_fresh and disk_entry:
        fetched_at, events = disk_entry
        logger.info("Calendar cache hit (disk, fresh, age %.0fs)", now - fetched_at)
        if background_refresh:
            _schedule_background_refresh(url)
        return _apply_memory_cache(url, events, fetched_at, "disk", False)

    if not force_refresh and background_refresh and disk_entry and allow_stale:
        fetched_at, events = disk_entry
        is_stale = now - fetched_at >= ttl
        logger.info(
            "Serving calendar from disk cache (age %.0fs); background refresh scheduled",
            now - fetched_at,
        )
        _schedule_background_refresh(url)
        return _apply_memory_cache(url, events, fetched_at, "stale_disk" if is_stale else "disk", is_stale)

    try:
        events = _fetch_live_events(url)
        fetched_at = time.time()
        _save_disk_cache(url, events, fetched_at)
        logger.info("Calendar fetched live (%d events)", len(events))
        return _apply_memory_cache(url, events, fetched_at, "live", False)
    except OSError as exc:
        logger.warning("Live calendar fetch failed: %s", exc)
        if allow_stale and disk_entry:
            fetched_at, events = disk_entry
            age = now - fetched_at
            logger.warning("Using stale disk cache (age %.0fs) after fetch failure", age)
            return _apply_memory_cache(url, events, fetched_at, "stale_disk", True)
        if is_test_mode():
            events = _events_from_mock()
            return _apply_memory_cache(url, events, now, "mock", False)
        raise CalendarUnavailableError(
            "Could not fetch band calendar and no cached copy exists. "
            "Try again later or set GIG_FLYERS_TEST_MODE=1 for offline fixtures."
        ) from exc


def get_local_today(timezone: Optional[str] = None) -> date:
    if is_test_mode():
        ref = load_mock_data().get("reference_today")
        if ref:
            return date.fromisoformat(ref)

    tz_name = timezone or os.getenv("GIG_CALENDAR_TIMEZONE", DEFAULT_TIMEZONE)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    return datetime.now(tz).date()


def _events_in_day_window(
    events: List[GigEvent],
    today: date,
    min_days: int,
    max_days: int,
) -> List[GigEvent]:
    seen: set[tuple[date, str]] = set()
    result: List[GigEvent] = []

    for event in events:
        days_out = (event.event_date - today).days
        if not (min_days <= days_out <= max_days):
            continue
        key = (event.event_date, event.venue.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(event)

    return result


def get_upcoming_gigs(
    min_days: int = 21,
    max_days: int = 28,
    calendar_url: Optional[str] = None,
    timezone: Optional[str] = None,
) -> List[GigEvent]:
    today = get_local_today(timezone)
    events = get_all_events(force_refresh=True, calendar_url=calendar_url, allow_stale=True)
    return _events_in_day_window(events, today, min_days, max_days)


def get_future_gigs(
    min_days: int = 0,
    max_days: int = 60,
    calendar_url: Optional[str] = None,
    timezone: Optional[str] = None,
    background_refresh: bool = True,
) -> List[GigEvent]:
    """Upcoming gigs within a day range (default: next 60 days)."""
    today = get_local_today(timezone)
    events = get_all_events(
        force_refresh=False,
        calendar_url=calendar_url,
        allow_stale=True,
        background_refresh=background_refresh,
    )
    return _events_in_day_window(events, today, min_days, max_days)


def event_from_dict(data: dict, gig_id: Optional[str] = None) -> GigEvent:
    date_str = data.get("date")
    if not date_str and gig_id:
        date_str = gig_id.split("_", 1)[0]
    if not date_str:
        raise ValueError("event data missing date")
    event_date = date.fromisoformat(date_str)
    venue = data.get("venue", "")
    return GigEvent(
        event_date=event_date,
        time_label=data.get("time", ""),
        title=data.get("title", ""),
        venue=venue,
        suggested_name=data.get("suggested_name") or build_suggested_name(event_date, venue),
    )


def find_gig_by_id(gig_id: str, calendar_url: Optional[str] = None) -> Optional[GigEvent]:
    try:
        for event in get_all_events(
            force_refresh=False,
            calendar_url=calendar_url,
            allow_stale=True,
            background_refresh=False,
        ):
            if event.gig_id == gig_id:
                return event
    except OSError:
        if is_test_mode():
            for event in _events_from_mock():
                if event.gig_id == gig_id:
                    return event
    return None
