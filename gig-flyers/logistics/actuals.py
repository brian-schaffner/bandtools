"""Extract milestone times from a hand-written (actual) logistics schedule."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

_TIME = r"(\d{1,2}):(\d{2})\s*([AP]M)?"
_RANGE = re.compile(_TIME + r"\s*[–—-]\s*" + _TIME)
_SINGLE = re.compile(_TIME)
_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})"
)
_TRAVEL = re.compile(r"travel allowance:\s*(\d+)\s*min", re.I)
# Early-morning clock times belong to the night after the gig date.
_NEXT_DAY_BEFORE_HOUR = 6


@dataclass
class ActualSchedule:
    event_date: date
    milestones: dict[str, datetime] = field(default_factory=dict)
    travel_minutes: Optional[int] = None
    revised: bool = False


def _clean(line: str) -> str:
    return re.sub(r"[*#]", "", line).strip()


def _to_minutes(hour: str, minute: str, meridiem: str) -> int:
    h = int(hour) % 12 + (12 if meridiem == "PM" else 0)
    return h * 60 + int(minute)


def _times_in(line: str) -> tuple[Optional[int], Optional[int]]:
    rng = _RANGE.search(line)
    if rng:
        h1, m1, ap1, h2, m2, ap2 = rng.groups()
        ap2 = ap2 or ap1 or "PM"
        ap1 = ap1 or ap2
        return _to_minutes(h1, m1, ap1), _to_minutes(h2, m2, ap2)
    single = _SINGLE.search(line)
    if single:
        h, m, ap = single.groups()
        return _to_minutes(h, m, ap or "PM"), None
    return None, None


def _anchor(event_date: date, minutes: int) -> datetime:
    when = datetime.combine(event_date, datetime.min.time()) + timedelta(minutes=minutes)
    if minutes < _NEXT_DAY_BEFORE_HOUR * 60:
        when += timedelta(days=1)
    return when


def parse_actual(text: str) -> ActualSchedule:
    lines = [_clean(l) for l in text.splitlines() if _clean(l)]
    date_match = next((_DATE.search(l) for l in lines if _DATE.search(l)), None)
    if not date_match:
        raise ValueError("No gig date found in schedule")
    event_date = datetime.strptime(" ".join(date_match.groups()), "%B %d %Y").date()
    result = ActualSchedule(event_date=event_date, revised=any(l.lower() == "revised" for l in lines))

    raw: dict[str, int] = {}
    set_starts: list[int] = []
    set_ends: list[int] = []
    teardown_ends: list[int] = []

    def put(key: str, value: Optional[int]) -> None:
        if value is not None and key not in raw:
            raw[key] = value

    for line in lines:
        travel = _TRAVEL.search(line)
        if travel and result.travel_minutes is None:
            result.travel_minutes = int(travel.group(1))
        start, end = _times_in(line)
        if start is None:
            continue
        upper = line.upper().replace("-", " ")
        if upper.startswith("GIG:"):
            put("gig_start", start)
            put("gig_end", end)
        elif "PULL OUT" in upper:
            put("pull_out", start)
        elif "ARRIVE HOME" in upper or "ARRIVAL HOME" in upper:
            put("home", start)
        elif "GIG ARRIVAL" in upper or "ARRIVE AT" in upper:
            put("arrival", start)
        elif "DEAD STAGE" in upper:
            put("dead_stage", start)
        elif re.search(r"\bUNLOAD\b|\bSETUP\b", upper):
            put("setup_start", start)
            put("setup_end", end)
        elif "SOUNDCHECK" in upper or "SOUND CHECK" in upper:
            put("soundcheck_start", start)
            put("soundcheck_end", end)
        elif "TEARDOWN" in upper:
            put("teardown_start", start)
            if end is not None:
                teardown_ends.append(end)
        elif "DEPART" in upper:
            put("depart", start)
        elif "BAND SET" in upper:
            set_starts.append(start)
            if end is not None:
                set_ends.append(end)

    if set_starts:
        put("gig_start", set_starts[0])
    if set_ends:
        put("gig_end", set_ends[-1])
    if teardown_ends:
        raw["teardown_end"] = teardown_ends[-1]

    result.milestones = {k: _anchor(event_date, v) for k, v in raw.items()}
    return result
