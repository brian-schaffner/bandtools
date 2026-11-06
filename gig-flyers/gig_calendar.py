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
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

DEFAULT_CALENDAR_URL = "https://www.lindseylane.com/dates/"
FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v21.0"
FACEBOOK_SOURCE_PREFIX = "facebook:"
FACEBOOK_EVENT_FIELDS = (
    "id,name,start_time,end_time,is_canceled,"
    "place{name,location{street,city,state,zip}},"
    "event_times{start_time,end_time}"
)
FACEBOOK_MAX_PAGES = 10
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
                end_time_label=row.get("end_time", ""),
                address=row.get("address") or extract_address(title),
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
    end_time_label: str = ""
    address: str = ""

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
            "end_time": self.end_time_label,
            "title": self.title,
            "venue": self.venue,
            "address": self.address,
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


_STREET_NUMBER = re.compile(r"(?<![\w-])\d+\s+[A-Za-z]")
_ZIP_TAIL = re.compile(r"^(.*\b\d{5})\b")


def extract_address(title: str) -> str:
    """Street address embedded in a calendar title, e.g. 'Ernie's 104 Taylorsville Rd, Bloomfield, KY 40008'."""
    title = unescape((title or "").strip())
    zip_match = _ZIP_TAIL.match(title)
    if not zip_match:
        return ""
    head = zip_match.group(1)
    before_comma = head.split(",", 1)[0]
    starts = [m.start() for m in _STREET_NUMBER.finditer(before_comma)]
    if not starts:
        return ""
    return re.sub(r"\s+", " ", head[starts[-1]:]).strip()


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
        end_match = re.search(r'mec-end-time">([^<]+)', article)
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
                end_time_label=end_match.group(1).strip() if end_match else "",
                address=extract_address(title),
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
    title = row.get("title", "")
    return GigEvent(
        event_date=event_date,
        time_label=row.get("time", ""),
        title=title,
        venue=venue,
        suggested_name=row.get("suggested_name") or build_suggested_name(event_date, venue),
        end_time_label=row.get("end_time", ""),
        address=row.get("address") or extract_address(title),
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


def calendar_source() -> str:
    """``website`` (default) or ``facebook`` via GIG_CALENDAR_SOURCE."""
    return os.getenv("GIG_CALENDAR_SOURCE", "website").strip().lower() or "website"


def _facebook_credentials() -> Optional[tuple[str, str]]:
    page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    if page_id and token:
        return page_id, token
    return None


def _default_calendar_url() -> str:
    if calendar_source() == "facebook":
        creds = _facebook_credentials()
        if creds:
            return f"{FACEBOOK_SOURCE_PREFIX}{creds[0]}"
        logger.warning(
            "GIG_CALENDAR_SOURCE=facebook but FACEBOOK_PAGE_ID / FACEBOOK_PAGE_ACCESS_TOKEN "
            "are not set; using the website calendar"
        )
    return os.getenv("GIG_CALENDAR_URL", DEFAULT_CALENDAR_URL)


def _fetch_graph_json(url: str) -> dict:
    # Graph URLs carry the access token, so errors are re-raised without the URL or chained HTTPError.
    request = Request(url, headers={"User-Agent": "GigFlyers/1.0"})
    try:
        with urlopen(request, timeout=fetch_timeout_seconds()) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8", errors="replace"))["error"]["message"]
        except Exception:
            pass
        raise OSError(f"Facebook Graph API HTTP {exc.code}: {detail or exc.reason}") from None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise OSError("Facebook Graph API returned invalid JSON") from None


def _fetch_facebook_rows(page_id: str, token: str) -> List[dict]:
    query = urlencode(
        {
            "fields": FACEBOOK_EVENT_FIELDS,
            "time_filter": "upcoming",
            "limit": 100,
            "access_token": token,
        }
    )
    url: Optional[str] = f"{FACEBOOK_GRAPH_URL}/{page_id}/events?{query}"
    rows: List[dict] = []
    for _ in range(FACEBOOK_MAX_PAGES):
        if not url:
            break
        payload = _fetch_graph_json(url)
        rows.extend(payload.get("data") or [])
        url = (payload.get("paging") or {}).get("next")
    return rows


def _parse_facebook_time(value: str, tz: ZoneInfo) -> Optional[tuple[date, str]]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        moment = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone(tz)
    except ValueError:
        try:
            return date.fromisoformat(value[:10]), ""
        except ValueError:
            return None
    label = f"{moment.hour % 12 or 12}:{moment.minute:02d} {'am' if moment.hour < 12 else 'pm'}"
    return moment.date(), label


def _format_facebook_location(location: dict) -> str:
    state_zip = " ".join(p for p in (location.get("state"), location.get("zip")) if p)
    parts = [location.get("street"), location.get("city"), state_zip]
    return ", ".join(p.strip() for p in parts if p and p.strip())


def _facebook_title_venue(title: str) -> str:
    match = re.match(r"^(.+?)\s+presents\b", title, re.I)
    if match:
        return match.group(1).strip()
    return _extract_venue(title)


def _facebook_venue_and_address(title: str, place: dict) -> tuple[str, str]:
    name = (place.get("name") or "").strip()
    address = _format_facebook_location(place.get("location") or {})
    # Ad-hoc places are often just a typed street address with no venue page behind them.
    if name and not address and _STREET_NUMBER.match(name):
        address, name = name, ""
    return name or _facebook_title_venue(title), address


def _facebook_tz() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("GIG_CALENDAR_TIMEZONE", DEFAULT_TIMEZONE))
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _parse_facebook_events(rows: List[dict]) -> List[GigEvent]:
    tz = _facebook_tz()
    events: List[GigEvent] = []
    for row in rows:
        if row.get("is_canceled"):
            continue
        title = re.sub(r"\s+", " ", unescape(row.get("name") or "")).strip()
        if not title:
            continue
        venue, address = _facebook_venue_and_address(title, row.get("place") or {})
        occurrences = row.get("event_times") or []
        if isinstance(occurrences, dict):
            occurrences = occurrences.get("data") or []
        if not occurrences:
            occurrences = [row]
        for occurrence in occurrences:
            start = _parse_facebook_time(occurrence.get("start_time", ""), tz)
            if not start:
                continue
            end = _parse_facebook_time(occurrence.get("end_time", ""), tz)
            event_date, time_label = start
            events.append(
                GigEvent(
                    event_date=event_date,
                    time_label=time_label,
                    title=title,
                    venue=venue,
                    suggested_name=build_suggested_name(event_date, venue),
                    end_time_label=end[1] if end else "",
                    address=address,
                )
            )
    events.sort(key=lambda e: (e.event_date, e.time_label))
    return _dedupe_events(events)


def _fetch_facebook_events() -> List[GigEvent]:
    creds = _facebook_credentials()
    if not creds:
        raise OSError("FACEBOOK_PAGE_ID / FACEBOOK_PAGE_ACCESS_TOKEN are not set")
    return _parse_facebook_events(_fetch_facebook_rows(*creds))


def _fetch_live_events(url: str) -> List[GigEvent]:
    if url.startswith(FACEBOOK_SOURCE_PREFIX):
        return _fetch_facebook_events()
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

    url = calendar_url or _default_calendar_url()
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
    title = data.get("title", "")
    return GigEvent(
        event_date=event_date,
        time_label=data.get("time", ""),
        title=title,
        venue=venue,
        suggested_name=data.get("suggested_name") or build_suggested_name(event_date, venue),
        end_time_label=data.get("end_time", ""),
        address=data.get("address") or extract_address(title),
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
