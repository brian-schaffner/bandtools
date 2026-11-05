"""Build a performance-day logistics schedule for one gig."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Optional

from logistics.drive_time import DriveEstimate, resolve_drive
from logistics.profiles import LogisticsConfig, VenueProfile, load_config

MILESTONES = (
    "pull_out",
    "arrival",
    "setup_start",
    "setup_end",
    "soundcheck_start",
    "soundcheck_end",
    "dead_stage",
    "gig_start",
    "gig_end",
    "teardown_start",
    "teardown_end",
    "depart",
    "home",
)

_CLOCK = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\s*$", re.I)


def parse_clock(label: str) -> Optional[time]:
    match = _CLOCK.match(label or "")
    if not match:
        return None
    hour = int(match.group(1)) % 12
    if match.group(3).lower() == "p":
        hour += 12
    return time(hour, int(match.group(2) or 0))


@dataclass(frozen=True)
class GigInput:
    event_date: date
    start: time
    end: Optional[time]
    title: str
    venue: str = ""
    address: str = ""
    gig_id: str = ""

    @classmethod
    def from_event(cls, event: Any) -> "GigInput":
        start = parse_clock(event.time_label)
        if start is None:
            raise ValueError(f"Unparseable start time {event.time_label!r} for {event.title!r}")
        return cls(
            event_date=event.event_date,
            start=start,
            end=parse_clock(getattr(event, "end_time_label", "")),
            title=event.title,
            venue=event.venue,
            address=getattr(event, "address", ""),
            gig_id=event.gig_id,
        )


@dataclass(frozen=True)
class TimelineStep:
    start: datetime
    end: Optional[datetime]
    label: str
    emoji: str = ""


@dataclass
class LogisticsSchedule:
    gig: GigInput
    profile: VenueProfile
    drive: DriveEstimate
    travel_minutes: int
    milestones: dict[str, datetime]
    end_published: bool
    timeline: list[TimelineStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    revised: bool = False

    @property
    def address(self) -> str:
        return self.profile.address or self.gig.address


def _at(base: datetime, minutes: int) -> datetime:
    return base + timedelta(minutes=minutes)


def _gig_window(gig: GigInput, profile: VenueProfile) -> tuple[datetime, datetime, bool]:
    gig_start = datetime.combine(gig.event_date, gig.start)
    if gig.end is None:
        return gig_start, _at(gig_start, profile.minutes("gig_length_minutes")), False
    gig_end = datetime.combine(gig.event_date, gig.end)
    if gig_end <= gig_start:
        gig_end += timedelta(days=1)
    return gig_start, gig_end, True


def _standard_milestones(profile: VenueProfile, gig_start: datetime, gig_end: datetime) -> dict[str, datetime]:
    m: dict[str, datetime] = {"gig_start": gig_start, "gig_end": gig_end}
    m["dead_stage"] = _at(gig_start, -profile.minutes("dead_stage_minutes"))
    adjustments_start = _at(m["dead_stage"], -profile.minutes("final_adjustments_minutes"))
    soundcheck = profile.minutes("soundcheck_minutes")
    if soundcheck:
        m["soundcheck_end"] = adjustments_start
        m["soundcheck_start"] = _at(adjustments_start, -soundcheck)
        m["setup_end"] = m["soundcheck_start"]
    else:
        m["setup_end"] = adjustments_start
    m["setup_start"] = _at(m["setup_end"], -profile.minutes("setup_minutes"))
    m["arrival"] = m["setup_start"]
    teardown = profile.minutes("teardown_minutes")
    if teardown:
        m["teardown_start"] = gig_end
        m["teardown_end"] = _at(gig_end, teardown)
    return m


def _timeline_milestones(profile: VenueProfile, gig_start: datetime) -> tuple[dict[str, datetime], list[TimelineStep]]:
    steps: list[TimelineStep] = []
    m: dict[str, datetime] = {}
    for item in profile.timeline:
        start = _at(gig_start, int(item["at"]))
        end = _at(gig_start, int(item["until"])) if "until" in item else None
        steps.append(TimelineStep(start, end, item["label"], item.get("emoji", "")))
        tag = item.get("milestone")
        if tag == "dead_stage":
            m["dead_stage"] = start
        elif tag in {"setup", "soundcheck", "teardown"}:
            m.setdefault(f"{tag}_start", start)
            if end:
                m[f"{tag}_end"] = end
        elif tag == "performance":
            m.setdefault("gig_start", start)
            if end:
                m["gig_end"] = end
    m["arrival"] = min(s.start for s in steps)
    return m, steps


def build_schedule(
    gig: GigInput,
    *,
    config: Optional[LogisticsConfig] = None,
    profile: Optional[VenueProfile] = None,
    drive: Optional[DriveEstimate] = None,
    drive_lookup: Optional[Callable[..., Optional[int]]] = None,
    revised: bool = False,
) -> LogisticsSchedule:
    config = config or load_config()
    profile = profile or config.profile_for(gig.title, gig.venue, gig.address)
    gig_start, gig_end, end_published = _gig_window(gig, profile)

    timeline: list[TimelineStep] = []
    if profile.timeline:
        milestones, timeline = _timeline_milestones(profile, gig_start)
    else:
        milestones = _standard_milestones(profile, gig_start, gig_end)

    if drive is None:
        destination = gig.address or profile.address or gig.title
        departure = _at(milestones["arrival"], -60)
        kwargs = {"lookup": drive_lookup} if drive_lookup else {}
        drive = resolve_drive(profile, destination, departure, **kwargs)
    travel = drive.minutes + profile.minutes("travel_cushion_minutes")
    milestones["pull_out"] = _at(milestones["arrival"], -travel)

    if profile.include_return:
        depart = milestones.get("teardown_end") or milestones["gig_end"]
        milestones["depart"] = depart
        milestones["home"] = _at(depart, travel)

    warnings: list[str] = []
    if not profile.known:
        warnings.append("No venue profile yet — standard setup timing used.")
    if not end_published and not profile.timeline:
        hours = profile.minutes("gig_length_minutes") / 60
        warnings.append(f"End time not published — assuming a {hours:g}-hour gig.")
    if not drive.confirmed:
        warnings.append(
            f"Drive time is an estimate ({drive.minutes} min). Set GOOGLE_MAPS_API_KEY and "
            "BAND_HOME_ADDRESS, or add drive_minutes to the venue profile."
        )
    if not (gig.address or profile.address):
        warnings.append("No venue address on the published schedule.")

    return LogisticsSchedule(
        gig=gig,
        profile=profile,
        drive=drive,
        travel_minutes=travel,
        milestones={k: milestones[k] for k in MILESTONES if k in milestones},
        end_published=end_published,
        timeline=timeline,
        warnings=warnings,
        revised=revised,
    )
