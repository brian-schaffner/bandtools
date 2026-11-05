"""Predict performance-day logistics schedules from the band's published calendar.

    python3 -m logistics.weekly                      # next Monday–Sunday
    python3 -m logistics.weekly --weekend            # this coming Friday–Sunday
    python3 -m logistics.weekly --from 2026-11-06 --to 2026-11-08 --out /tmp/schedules
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent, get_all_events, get_local_today  # noqa: E402
from logistics.profiles import LogisticsConfig, load_config  # noqa: E402
from logistics.render import render_markdown  # noqa: E402
from logistics.schedule import GigInput, LogisticsSchedule, build_schedule  # noqa: E402


@dataclass
class WeekPlan:
    start: date
    end: date
    schedules: list[LogisticsSchedule]
    excluded: list[GigEvent]


def next_week_window(today: date) -> tuple[date, date]:
    monday = today + timedelta(days=7 - today.weekday())
    return monday, monday + timedelta(days=6)


def weekend_window(today: date) -> tuple[date, date]:
    friday = today + timedelta(days=4 - today.weekday())
    return friday, friday + timedelta(days=2)


def select_gigs(
    events: Iterable[GigEvent], start: date, end: date, config: LogisticsConfig
) -> tuple[list[GigEvent], list[GigEvent]]:
    chosen: list[GigEvent] = []
    excluded: list[GigEvent] = []
    seen: set[tuple[date, str, str]] = set()
    for event in sorted(events, key=lambda e: (e.event_date, e.time_label)):
        if not (start <= event.event_date <= end):
            continue
        key = (event.event_date, event.time_label.lower(), event.venue.lower())
        if key in seen:
            continue
        seen.add(key)
        (excluded if config.is_excluded(event.title) else chosen).append(event)
    return chosen, excluded


def plan_window(
    start: date,
    end: date,
    *,
    events: Optional[list[GigEvent]] = None,
    config: Optional[LogisticsConfig] = None,
) -> WeekPlan:
    config = config or load_config()
    if events is None:
        events = get_all_events(force_refresh=True, allow_stale=True)
    chosen, excluded = select_gigs(events, start, end, config)
    schedules = [build_schedule(GigInput.from_event(e), config=config) for e in chosen]
    return WeekPlan(start=start, end=end, schedules=schedules, excluded=excluded)


def format_plan(plan: WeekPlan) -> str:
    header = f"# Performance-day schedules: {plan.start:%a %b %d} – {plan.end:%a %b %d, %Y}"
    parts = [header, ""]
    if not plan.schedules:
        parts.append("No gigs on the published schedule for this window.\n")
    for schedule in plan.schedules:
        parts.append(render_markdown(schedule))
    if plan.excluded:
        parts.append("Excluded: " + "; ".join(f"{e.event_date:%a %b %d} {e.title}" for e in plan.excluded))
    return "\n".join(parts).rstrip() + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="start", type=date.fromisoformat)
    parser.add_argument("--to", dest="end", type=date.fromisoformat)
    parser.add_argument("--weekend", action="store_true", help="This coming Friday–Sunday")
    parser.add_argument("--out", type=Path, help="Also write one markdown file per gig here")
    args = parser.parse_args(argv)

    today = get_local_today()
    if args.start:
        start, end = args.start, args.end or args.start + timedelta(days=6)
    elif args.weekend:
        start, end = weekend_window(today)
    else:
        start, end = next_week_window(today)

    plan = plan_window(start, end)
    print(format_plan(plan))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for schedule in plan.schedules:
            (args.out / f"{schedule.gig.gig_id}.md").write_text(render_markdown(schedule), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
