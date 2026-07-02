"""Tests for gig resolution helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_resolve import is_placeholder_gig_id, load_event_dict, resolve_gig_event  # noqa: E402


class GigResolveTest(unittest.TestCase):
    def test_placeholder_detection(self) -> None:
        self.assertTrue(is_placeholder_gig_id("{gig_id}"))
        self.assertTrue(is_placeholder_gig_id(""))
        self.assertFalse(is_placeholder_gig_id("2026-07-04_two-lane-tavern"))

    def test_resolve_rejects_placeholder(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_gig_event("{gig_id}")
        self.assertIn("Invalid gig link", str(ctx.exception))

    def test_load_event_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output" / "2026-07-04_test-venue"
            out.mkdir(parents=True)
            manifest = {
                "event": {
                    "venue": "Test Venue",
                    "date": "2026-07-04",
                    "short_date": "Jul 04",
                    "band": "Lindsey Lane Band",
                    "time": "7:00 PM",
                }
            }
            (out / "manifest_r1.json").write_text(json.dumps(manifest), encoding="utf-8")
            with patch("gig_resolve.OUTPUT_DIR", Path(tmp) / "output"):
                with patch("gig_resolve.get_gig_state", return_value=None):
                    with patch("gig_resolve.find_gig_by_id", return_value=None):
                        event = load_event_dict("2026-07-04_test-venue")
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual(event["venue"], "Test Venue")


if __name__ == "__main__":
    unittest.main()
