#!/usr/bin/env python3
"""Backtest performance-day logistics against the schedules the band actually used, then predict ahead."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gig_calendar  # noqa: E402
from logistics.actuals import parse_actual  # noqa: E402
from logistics.backtest import FIXTURES, load_backtest_gigs, run_backtest  # noqa: E402
from logistics.render import render_markdown  # noqa: E402
from logistics.weekly import next_week_window, plan_window, weekend_window  # noqa: E402

NO_MAPS_ENV = {"GOOGLE_MAPS_API_KEY": "", "BAND_HOME_ADDRESS": ""}


def _dt(day: str, clock: str) -> datetime:
    return datetime.strptime(f"{day} {clock}", "%Y-%m-%d %I:%M %p")


def _snapshot_events() -> list[gig_calendar.GigEvent]:
    html = (FIXTURES / "calendar_2026-11-05.html").read_text(encoding="utf-8")
    return gig_calendar._parse_events(html)


class ActualScheduleParsingTests(unittest.TestCase):
    def test_every_actual_parses_core_milestones(self) -> None:
        for row in load_backtest_gigs():
            with self.subTest(actual=row["actual"]):
                actual = parse_actual((FIXTURES / "actuals" / row["actual"]).read_text(encoding="utf-8"))
                self.assertEqual(actual.event_date, date.fromisoformat(row["date"]))
                for name in ("pull_out", "arrival", "dead_stage", "gig_start", "gig_end"):
                    self.assertIn(name, actual.milestones)
                self.assertEqual(actual.revised, bool(row.get("revised")))

    def test_rowdys_values(self) -> None:
        actual = parse_actual((FIXTURES / "actuals" / "2026-10-16_rowdys.md").read_text(encoding="utf-8"))
        m = actual.milestones
        self.assertEqual(m["pull_out"], _dt("2026-10-16", "2:30 PM"))
        self.assertEqual(m["arrival"], _dt("2026-10-16", "3:45 PM"))
        self.assertEqual(m["soundcheck_start"], _dt("2026-10-16", "5:15 PM"))
        self.assertEqual(m["dead_stage"], _dt("2026-10-16", "5:30 PM"))
        self.assertEqual(m["gig_end"], _dt("2026-10-16", "10:00 PM"))
        self.assertEqual(actual.travel_minutes, 75)

    def test_after_midnight_times_roll_to_next_day(self) -> None:
        actual = parse_actual((FIXTURES / "actuals" / "2026-10-10_volt-lounge-caesars.md").read_text(encoding="utf-8"))
        m = actual.milestones
        self.assertEqual(m["gig_start"], _dt("2026-10-10", "10:00 PM"))
        self.assertEqual(m["gig_end"], _dt("2026-10-11", "1:30 AM"))
        self.assertEqual(m["teardown_end"], _dt("2026-10-11", "2:30 AM"))
        self.assertEqual(m["home"], _dt("2026-10-11", "3:15 AM"))


@patch.dict(os.environ, NO_MAPS_ENV)
class CalibratedBacktestTests(unittest.TestCase):
    """With venue profiles, published inputs must reproduce every milestone the band actually used."""

    def test_all_milestones_match_actuals(self) -> None:
        results = run_backtest("profiles")
        self.assertEqual(len(results), len(load_backtest_gigs()))
        for result in results:
            for diff in result.diffs:
                with self.subTest(gig=result.label, milestone=diff.name):
                    self.assertEqual(diff.delta_minutes, 0, f"actual {diff.actual}, predicted {diff.predicted}")

    def test_travel_allowance_matches(self) -> None:
        for result in run_backtest("profiles"):
            if result.travel_actual is not None:
                with self.subTest(gig=result.label):
                    self.assertEqual(result.travel_predicted, result.travel_actual)

    def test_revised_alibi_shifts_whole_day_by_start_change(self) -> None:
        by_label = {r.label: r.schedule for r in run_backtest("profiles")}
        original = by_label["2026-10-17_the-alibi"]
        revised = by_label["2026-10-17_the-alibi_revised"]
        for name, when in original.milestones.items():
            self.assertEqual((revised.milestones[name] - when).total_seconds(), 3600, name)
        self.assertTrue(render_markdown(revised).startswith("Revised\n"))

    def test_rendered_schedule_round_trips_through_actual_parser(self) -> None:
        for result in run_backtest("profiles"):
            with self.subTest(gig=result.label):
                reparsed = parse_actual(render_markdown(result.schedule))
                for name, when in reparsed.milestones.items():
                    self.assertEqual(when, result.schedule.milestones[name], name)
                self.assertEqual(reparsed.travel_minutes, result.schedule.travel_minutes)


@patch.dict(os.environ, NO_MAPS_ENV)
class ColdStartBacktestTests(unittest.TestCase):
    """Standard timing for a never-seen venue (drive time known): never late, never far off."""

    def test_fixed_anchors_are_exact(self) -> None:
        for result in run_backtest("defaults"):
            with self.subTest(gig=result.label):
                for name in ("dead_stage", "gig_start"):
                    self.assertEqual(result.delta(name), 0, name)

    def test_regular_venues_arrive_on_time_or_early_within_30_minutes(self) -> None:
        for result in run_backtest("defaults"):
            if result.label.startswith("2026-10-10_volt-lounge"):
                continue  # casino-run timeline; needs its venue profile
            with self.subTest(gig=result.label):
                for name in ("pull_out", "arrival"):
                    delta = result.delta(name)
                    self.assertIsNotNone(delta)
                    self.assertLessEqual(delta, 0, f"{name} would be late")
                    self.assertGreaterEqual(delta, -30, f"{name} more than 30 min early")


@patch.dict(os.environ, NO_MAPS_ENV)
class PredictionTests(unittest.TestCase):
    """Predictions from the published calendar as captured on Thu Nov 5, 2026."""

    def test_windows(self) -> None:
        thursday = date(2026, 11, 5)
        self.assertEqual(weekend_window(thursday), (date(2026, 11, 6), date(2026, 11, 8)))
        self.assertEqual(weekend_window(date(2026, 11, 8)), (date(2026, 11, 6), date(2026, 11, 8)))
        self.assertEqual(next_week_window(thursday), (date(2026, 11, 9), date(2026, 11, 15)))
        self.assertEqual(next_week_window(date(2026, 11, 8)), (date(2026, 11, 9), date(2026, 11, 15)))

    def test_calendar_snapshot_carries_address_and_end_time(self) -> None:
        events = {e.event_date: e for e in _snapshot_events()}
        self.assertEqual(events[date(2026, 11, 7)].address, "9702 Old Bardstown Rd, Louisville, KY 40291")
        self.assertEqual(events[date(2026, 11, 7)].end_time_label, "")
        self.assertEqual(events[date(2026, 12, 6)].end_time_label, "2:15 pm")

    def test_this_weekend_two_lane_tavern(self) -> None:
        plan = plan_window(date(2026, 11, 6), date(2026, 11, 8), events=_snapshot_events())
        self.assertEqual(len(plan.schedules), 1)
        schedule = plan.schedules[0]
        m = schedule.milestones
        day = "2026-11-07"
        self.assertEqual(m["gig_start"], _dt(day, "8:00 PM"))
        self.assertEqual(m["gig_end"], _dt("2026-11-08", "12:00 AM"))
        self.assertEqual(m["dead_stage"], _dt(day, "7:30 PM"))
        self.assertEqual(m["soundcheck_start"], _dt(day, "7:00 PM"))
        self.assertEqual(m["arrival"], _dt(day, "5:15 PM"))
        self.assertEqual(m["pull_out"], _dt(day, "4:15 PM"))
        self.assertEqual(m["teardown_end"], _dt("2026-11-08", "1:00 AM"))
        text = render_markdown(schedule)
        self.assertIn("Two Lane Tavern — Louisville, KY", text)
        self.assertIn("NEEDS CONFIRMATION", text)
        self.assertIn("assuming a 4-hour gig", text)
        self.assertIn("Drive time is an estimate", text)

    def test_next_week_excludes_jam_and_dedupes(self) -> None:
        plan = plan_window(date(2026, 11, 9), date(2026, 11, 15), events=_snapshot_events() * 2)
        self.assertEqual([s.gig.event_date for s in plan.schedules], [date(2026, 11, 14)])
        self.assertEqual(plan.schedules[0].milestones["pull_out"], _dt("2026-11-14", "3:15 PM"))
        self.assertEqual([e.event_date for e in plan.excluded], [date(2026, 11, 10)])

    def test_google_maps_drive_time_replaces_estimate(self) -> None:
        from logistics.schedule import GigInput, build_schedule

        event = next(e for e in _snapshot_events() if e.event_date == date(2026, 11, 7))
        calls = []

        def fake_lookup(origin, destination, departure):
            calls.append(destination)
            return 25

        schedule = build_schedule(GigInput.from_event(event), drive_lookup=fake_lookup)
        self.assertEqual(calls, ["9702 Old Bardstown Rd, Louisville, KY 40291"])
        self.assertEqual(schedule.milestones["pull_out"], _dt("2026-11-07", "4:35 PM"))
        self.assertTrue(schedule.drive.confirmed)
        self.assertIn("25-minute drive (Google Maps)", render_markdown(schedule))
        self.assertFalse(any("Drive time" in w for w in schedule.warnings))


if __name__ == "__main__":
    unittest.main()
