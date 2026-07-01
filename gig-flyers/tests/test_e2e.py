#!/usr/bin/env python3
"""Offline end-to-end test using fixture calendar HTML."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURE_HTML = """
<article class="mec-event-article mec-clear">
  <span class="mec-start-date-label">Jul 18 2026</span>
  <h3 class="mec-event-title"><a href="#">Lindsey Lane Band at Stevie Ray's Blues Bar</a></h3>
  <span class="mec-start-time">8:00 pm</span>
</article>
"""


class GigFlyerE2ETest(unittest.TestCase):
    def test_calendar_parse(self) -> None:
        from gig_calendar import _parse_events

        events = _parse_events(FIXTURE_HTML)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].venue, "Stevie Ray's Blues Bar")
        self.assertEqual(events[0].time_label, "8:00 pm")

    def test_upcoming_window(self) -> None:
        from gig_calendar import GigEvent, get_upcoming_gigs

        target = date(2026, 6, 23)
        fake_event = GigEvent(
            event_date=date(2026, 7, 18),
            time_label="8:00 pm",
            title="Lindsey Lane Band at Stevie Ray's Blues Bar",
            venue="Stevie Ray's Blues Bar",
            suggested_name="Jul 18 Stevie Ray's Blues Bar",
        )
        with patch("gig_calendar.get_all_events", return_value=[fake_event]):
            with patch("gig_calendar.get_local_today", return_value=target):
                gigs = get_upcoming_gigs(min_days=21, max_days=28)
        self.assertEqual(len(gigs), 1)
        self.assertEqual(gigs[0].gig_id, fake_event.gig_id)

    def test_dry_run_generation(self) -> None:
        from gig_calendar import GigEvent
        from flyer_generator import generate_for_gig

        event = GigEvent(
            event_date=date(2026, 7, 18),
            time_label="8:00 pm",
            title="Lindsey Lane Band at Stevie Ray's Blues Bar",
            venue="Stevie Ray's Blues Bar",
            suggested_name="Jul 18 Stevie Ray's Blues Bar",
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("flyer_generator.find_gig_by_id", return_value=event):
                with patch("flyer_generator.ROOT", tmp_path):
                    with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                        with patch("state.STATE_PATH", tmp_path / "state.json"):
                            with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                                manifest = generate_for_gig(event.gig_id, count=3, dry_run=True)
            self.assertEqual(len(manifest["options"]), 3)
            for rel in manifest["options"].values():
                self.assertTrue((tmp_path / rel).exists(), rel)

    def test_reply_parser(self) -> None:
        from bridge.imessage import parse_reply

        self.assertEqual(parse_reply("APPROVE B").action, "approve")
        self.assertEqual(parse_reply("REVISE A: darker background").action, "revise")
        self.assertEqual(parse_reply("REVISE A: darker background").feedback, "darker background")
        self.assertEqual(parse_reply("maybe later").action, "unknown")

    def test_mode_loads_mock_gigs(self) -> None:
        from gig_calendar import find_gig_by_id, get_all_events, get_upcoming_gigs, set_test_mode

        set_test_mode(True)
        try:
            events = get_all_events(force_refresh=True)
            self.assertGreaterEqual(len(events), 6)
            self.assertEqual(events[0].event_date.isoformat(), "2026-06-28")

            upcoming = get_upcoming_gigs(min_days=21, max_days=28)
            self.assertEqual(len(upcoming), 3)
            gig_ids = {g.gig_id for g in upcoming}
            self.assertIn("2026-07-14_stevie-ray-s-blues-bar", gig_ids)
            self.assertIn("2026-07-18_vfw-post-1170", gig_ids)
            self.assertIn("2026-07-21_the-waters-club", gig_ids)

            found = find_gig_by_id("2026-07-14_stevie-ray-s-blues-bar")
            self.assertIsNotNone(found)
            self.assertEqual(found.venue, "Stevie Ray's Blues Bar")
        finally:
            set_test_mode(False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
