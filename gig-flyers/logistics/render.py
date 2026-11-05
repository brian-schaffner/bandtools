"""Render a logistics schedule in the band's GIG DEPARTURE & SETUP SCHEDULE format."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from logistics.schedule import LogisticsSchedule

DEFAULT_SETUP_BULLETS = (
    "Unload equipment",
    "Set up stage, instruments, PA and monitors",
    "Complete equipment connections",
)
DEFAULT_SOUNDCHECK_BULLETS = (
    "Check vocals and instruments",
    "Adjust monitor and house mixes",
)
_PAREN_DRIVE_SOURCES = {"google maps", "apple maps", "venue profile", "estimate"}
_STATE_ABBREVIATIONS = {"kentucky": "KY", "indiana": "IN", "ohio": "OH", "tennessee": "TN"}


def fmt_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def fmt_range(start: datetime, end: Optional[datetime]) -> str:
    if end is None:
        return fmt_time(start)
    if start.strftime("%p") == end.strftime("%p") and end - start < timedelta(hours=12):
        return f"{start.strftime('%I:%M').lstrip('0')}–{fmt_time(end)}"
    return f"{fmt_time(start)}–{fmt_time(end)}"


def fmt_long_date(schedule: LogisticsSchedule) -> str:
    d = schedule.gig.event_date
    return f"{d.strftime('%A, %B')} {d.day}, {d.year}"


def city_state(address: str) -> str:
    parts = [p.strip() for p in (address or "").split(",") if p.strip()]
    if len(parts) < 3:
        return ""
    state = parts[-1].split()[0] if parts[-1].split() else ""
    state = _STATE_ABBREVIATIONS.get(state.lower(), state)
    return f"{parts[-2]}, {state}" if state else parts[-2]


def _drive_line(schedule: LogisticsSchedule) -> str:
    drive = schedule.drive
    source = drive.source
    if source.lower() in _PAREN_DRIVE_SOURCES:
        suffix = "estimate — confirm" if source == "estimate" else source
        return f"• {drive.minutes}-minute drive ({suffix})"
    return f"• {drive.minutes}-minute {source}"


def _warnings_block(schedule: LogisticsSchedule) -> list[str]:
    if not schedule.warnings:
        return []
    return ["⚠️ **NEEDS CONFIRMATION**", *[f"• {w}" for w in schedule.warnings]]


def _travel_block(schedule: LogisticsSchedule) -> list[str]:
    cushion = schedule.travel_minutes - schedule.drive.minutes
    return [
        f"Travel allowance: {schedule.travel_minutes} minutes total",
        _drive_line(schedule),
        f"• {cushion}-minute required travel cushion",
        *schedule.profile.notes,
    ]


def _return_block(schedule: LogisticsSchedule, *, bold: bool = True) -> list[str]:
    m = schedule.milestones
    if "depart" not in m:
        return []
    b = "**" if bold else ""
    return [
        f"🚙 {b}{fmt_time(m['depart'])} — DEPART VENUE{b}",
        f"🏠 {b}{fmt_time(m['home'])} — ARRIVE HOME{b}",
    ]


def _render_standard(schedule: LogisticsSchedule) -> list[str]:
    m = schedule.milestones
    profile = schedule.profile
    venue_upper = profile.name.upper()
    location = profile.location or city_state(schedule.address)
    lines = [
        "🎶 **GIG DEPARTURE & SETUP SCHEDULE**",
        fmt_long_date(schedule),
        f"{profile.name} — {location}" if location else profile.name,
    ]
    if schedule.address:
        lines.append(schedule.address)
    lines.append(f"Gig: {fmt_range(m['gig_start'], m['gig_end'])}")
    lines += _warnings_block(schedule)
    lines += [
        f"📍 **GIG ARRIVAL: {fmt_time(m['arrival'])}**",
        f"🚙 **{fmt_time(m['pull_out'])} — PULL OUT FROM HOME**",
        *_travel_block(schedule),
        f"📍 **{fmt_time(m['arrival'])} — ARRIVE AT {venue_upper}**",
        f"🎸 **{fmt_range(m['setup_start'], m['setup_end'])} — {profile.setup_label or 'UNLOAD & SETUP'}**",
        *[f"• {b}" for b in (profile.setup_bullets or DEFAULT_SETUP_BULLETS)],
    ]
    if "soundcheck_start" in m:
        lines.append(f"🎤 **{fmt_range(m['soundcheck_start'], m['soundcheck_end'])} — SOUNDCHECK**")
        lines += [f"• {b}" for b in (profile.soundcheck_bullets or DEFAULT_SOUNDCHECK_BULLETS)]
    adjustments_start = m.get("soundcheck_end") or m["setup_end"]
    if adjustments_start < m["dead_stage"]:
        label = profile.adjustments_label or "FINAL ADJUSTMENTS"
        lines.append(f"⏱️ **{fmt_range(adjustments_start, m['dead_stage'])} — {label}**")
    lines += [
        f"🔇 **{fmt_time(m['dead_stage'])} — DEAD STAGE**",
        f"🎶 **{fmt_range(m['gig_start'], m['gig_end'])} — PERFORMANCE**",
    ]
    if "teardown_start" in m:
        lines.append(f"🚚 **{fmt_range(m['teardown_start'], m.get('teardown_end'))} — TEARDOWN & LOAD OUT**")
    lines += _return_block(schedule)
    lines.append("*All times Eastern.*")
    return lines


def _render_timeline(schedule: LogisticsSchedule) -> list[str]:
    m = schedule.milestones
    profile = schedule.profile
    lines = [
        f"🎶 **{profile.header or profile.name.upper()}**",
        fmt_long_date(schedule),
        profile.location or city_state(schedule.address) or profile.name,
        "All times Eastern",
    ]
    lines += _warnings_block(schedule)
    lines += [
        f"🚙 **{fmt_time(m['pull_out'])} — PULL OUT FROM HOME**",
        *_travel_block(schedule),
        f"📍 **{fmt_time(m['arrival'])} — GIG ARRIVAL**",
    ]
    for step in schedule.timeline:
        prefix = f"{step.emoji} " if step.emoji else ""
        lines.append(f"{prefix}{fmt_range(step.start, step.end)} — {step.label}")
    lines += _return_block(schedule)
    return lines


def render_markdown(schedule: LogisticsSchedule) -> str:
    lines = _render_timeline(schedule) if schedule.profile.timeline else _render_standard(schedule)
    if schedule.revised:
        lines.insert(0, "Revised")
    return "\n".join(lines) + "\n"


def render_text(schedule: LogisticsSchedule) -> str:
    return re.sub(r"\*+", "", render_markdown(schedule))
