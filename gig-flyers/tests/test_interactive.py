#!/usr/bin/env python3
"""Tests for interactive picker and home dashboard."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from gig_calendar import GigEvent  # noqa: E402


def _sample_event(gig_id: str = "2026-07-25_king-s-landing") -> GigEvent:
    return GigEvent(
        event_date=date(2026, 7, 25),
        time_label="8:00 pm",
        title="Lindsey Lane Band at King's Landing",
        venue="King's Landing",
        suggested_name="Jul 25 King's Landing",
    )


class InteractiveEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))
        self.event = _sample_event()

        self.patches = [
            patch("state.ROOT", self.tmp_path),
            patch("state.STATE_PATH", self.tmp_path / "state.json"),
            patch("state.APPROVED_DIR", self.tmp_path / "output/approved"),
            patch("bridge.review.ROOT", self.tmp_path),
            patch("bridge.review.OUTPUT_DIR", self.tmp_path / "output"),
            patch("bridge.interactive.get_future_gigs", return_value=[self.event]),
            patch("bridge.interactive.get_local_today", return_value=date(2026, 6, 23)),
            patch.dict("os.environ", {"BRIDGE_PUBLIC_URL": "http://test.local/flyers"}),
        ]
        for p in self.patches:
            p.start()

        from bridge.server import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        from bridge.server import _generate_in_flight, _revise_in_flight

        _generate_in_flight.clear()
        _revise_in_flight.clear()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_home_page_renders(self) -> None:
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Mode 1", resp.text)
        self.assertIn("Mode 2", resp.text)
        self.assertIn("/flyers/pick", resp.text)

    def test_home_page_prefixed_path(self) -> None:
        resp = self.client.get("/flyers/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Gig Flyers", resp.text)

    def test_pick_page_lists_gigs(self) -> None:
        resp = self.client.get("/pick")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("King", resp.text)
        self.assertIn("Generate 3 options", resp.text)

    @patch("bridge.server._run_interactive_generation")
    @patch("bridge.server.find_gig_by_id", return_value=_sample_event())
    def test_pick_generate_starts_background(self, _find, mock_bg) -> None:
        resp = self.client.post(
            f"/pick/{self.event.gig_id}/generate",
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Generating flyer options", resp.text)
        mock_bg.assert_called_once()

    def test_pick_generate_redirects_when_pending(self) -> None:
        state = {
            "gigs": {
                self.event.gig_id: {
                    "status": "pending_review",
                    "round": 1,
                    "options": {"A": "output/x.png"},
                    "event": self.event.to_dict(),
                }
            },
            "last_poll_rowid": 0,
        }
        (self.tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
        resp = self.client.post(
            f"/pick/{self.event.gig_id}/generate",
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 303)
        self.assertIn("/flyers/review/", resp.headers.get("location", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
