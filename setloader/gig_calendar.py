#!/usr/bin/env python3
"""Fetch and parse Lindsey Lane Band gig calendar for output naming."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from typing import List, Optional
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sbp_naming import (
    DEFAULT_GIG_NAME_MAX,
    DEFAULT_VENUE_MAX,
    RECOMMENDED_SBP_SET_NAME_MAX,
    build_gig_suggested_name,
    shorten_venue,
    truncate_name,
)

DEFAULT_CALENDAR_URL = "https://www.lindseylane.com/dates/"
DEFAULT_TIMEZONE = "America/Kentucky/Louisville"
CACHE_TTL_SECONDS = 3600

_cache: dict[str, object] = {"fetched_at": 0.0, "events": [], "url": None}


@dataclass
class GigEvent:
    event_date: date
    time_label: str
    title: str
    venue: str
    suggested_name: str


def _sanitize_output_name(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w\s\-']", "", name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len] if cleaned else "Set"


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

    # Venue before street number, e.g. "Two Lane Tavern 9702 Old Bardstown Rd"
    match = re.match(r"^(.+?)\s+\d+\s+", title)
    if match:
        return match.group(1).strip()

    # Drop trailing address after comma when present
    if "," in title:
        return title.split(",", 1)[0].strip()

    return title


def _format_short_date(event_date: date) -> str:
    """Format as abbreviated month + 2-digit day, e.g. Jun 26."""
    return event_date.strftime("%b %d")


def _build_suggested_name(event_date: date, venue: str) -> str:
    return build_gig_suggested_name(_format_short_date(event_date), venue)


def _fetch_calendar_html(url: str) -> str:
    request = Request(
        url,
        headers={"User-Agent": "SetLoader/1.0 (+https://github.com/setloader)"},
    )
    with urlopen(request, timeout=20) as response:
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
                suggested_name=_build_suggested_name(event_date, venue),
            )
        )

    events.sort(key=lambda e: (e.event_date, e.time_label))
    return events


def get_all_events(force_refresh: bool = False, calendar_url: Optional[str] = None) -> List[GigEvent]:
    url = calendar_url or os.getenv("GIG_CALENDAR_URL", DEFAULT_CALENDAR_URL)
    now = time.time()
    if (
        not force_refresh
        and _cache.get("events")
        and now - float(_cache.get("fetched_at", 0.0)) < CACHE_TTL_SECONDS
        and _cache.get("url") == url
    ):
        return list(_cache["events"])  # type: ignore[arg-type]

    html = _fetch_calendar_html(url)
    events = _parse_events(html)
    _cache["events"] = events
    _cache["fetched_at"] = now
    _cache["url"] = url
    return events


def get_local_today(timezone: Optional[str] = None) -> date:
    tz_name = timezone or os.getenv("GIG_CALENDAR_TIMEZONE", DEFAULT_TIMEZONE)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    return datetime.now(tz).date()


def get_gig_suggestions(
    target_date: Optional[date] = None,
    calendar_url: Optional[str] = None,
    timezone: Optional[str] = None,
) -> dict:
    target = target_date or get_local_today(timezone)
    events = get_all_events(calendar_url=calendar_url)
    same_day = [e for e in events if e.event_date == target]

    primary = same_day[0].suggested_name if same_day else None
    note = None
    if not same_day:
        upcoming = [e for e in events if e.event_date >= target][:5]
        if upcoming:
            primary = upcoming[0].suggested_name
            note = f"No gig on {target.isoformat()}; showing next upcoming show"
        else:
            note = f"No upcoming gigs found on calendar for {target.isoformat()}"

    def serialize(event: GigEvent) -> dict:
        return {
            "date": event.event_date.isoformat(),
            "short_date": _format_short_date(event.event_date),
            "time": event.time_label,
            "title": event.title,
            "venue": event.venue,
            "suggested_name": event.suggested_name,
        }

    return {
        "target_date": target.isoformat(),
        "band": os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band"),
        "source": calendar_url or os.getenv("GIG_CALENDAR_URL", DEFAULT_CALENDAR_URL),
        "events": [serialize(e) for e in same_day],
        "upcoming": [serialize(e) for e in events if e.event_date >= target][:8],
        "primary_suggestion": primary,
        "note": note,
        "naming": {
            "recommended_max_chars": RECOMMENDED_SBP_SET_NAME_MAX,
            "suggestion_max_chars": DEFAULT_GIG_NAME_MAX,
            "venue_max_chars": DEFAULT_VENUE_MAX,
            "note": (
                "Song Book Pro has no documented set-name limit, but 25–40 characters "
                "display best on phone/tablet set lists."
            ),
        },
    }
