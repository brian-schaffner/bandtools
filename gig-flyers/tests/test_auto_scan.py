#!/usr/bin/env python3
"""Tests for auto-scan eligibility and dry-run workflow."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from state import is_eligible_for_auto_generation, upsert_gig  # noqa: E402


class AutoScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))
        self.event = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="7:30 pm",
            title="Hosting Stevie Ray's World Famous Tuesday Jam",
            venue="Stevie Ray's Tuesday Jam",
            suggested_name="Jul 14 Stevie Ray's Tuesday Jam",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_eligible_when_not_in_state(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            self.assertTrue(is_eligible_for_auto_generation(self.event.gig_id))

    def test_not_eligible_when_pending_review(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            upsert_gig(
                self.event.gig_id,
                status="pending_review",
                round=1,
                options={"A": "output/x.png"},
            )
            self.assertFalse(is_eligible_for_auto_generation(self.event.gig_id))

    def test_not_eligible_when_approved(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            upsert_gig(self.event.gig_id, status="approved", round=2, options={"A": "output/x.png"})
            self.assertFalse(is_eligible_for_auto_generation(self.event.gig_id))

    @patch("flyer_generator.post_send_review", return_value={"sent": True})
    @patch("flyer_generator.generate_for_gig")
    @patch("flyer_generator.get_upcoming_gigs", return_value=[])
    def test_auto_scan_dry_run_empty(self, _upcoming, _gen, _send) -> None:
        from flyer_generator import cmd_auto_scan

        with patch("flyer_generator.ROOT", self.tmp_path):
            with patch("state.STATE_PATH", self.tmp_path / "state.json"):
                buf = StringIO()
                with patch("sys.stdout", buf):
                    rc = cmd_auto_scan(21, 28, 3, dry_run=True)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["mode"], "auto")
        self.assertEqual(payload["results"], [])

    @patch("flyer_generator.post_send_review", return_value={"sent": True})
    @patch("flyer_generator.generate_for_gig")
    @patch("flyer_generator.get_upcoming_gigs")
    def test_auto_scan_skips_pending(self, mock_upcoming, mock_gen, _send) -> None:
        from flyer_generator import cmd_auto_scan

        mock_upcoming.return_value = [self.event]
        with patch("flyer_generator.ROOT", self.tmp_path):
            with patch("state.STATE_PATH", self.tmp_path / "state.json"):
                upsert_gig(
                    self.event.gig_id,
                    status="pending_review",
                    round=1,
                    options={"A": "output/x.png"},
                )
                buf = StringIO()
                with patch("sys.stdout", buf):
                    cmd_auto_scan(21, 28, 3, dry_run=True)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["results"][0]["skipped"], "pending_review")
        mock_gen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
