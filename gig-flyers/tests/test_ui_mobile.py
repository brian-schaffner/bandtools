#!/usr/bin/env python3
"""Mobile-first HTML smoke tests for bridge UI."""

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

from bridge.interactive import build_picker_data, render_home_page, render_picker_page  # noqa: E402
from bridge.review import build_review_data, render_job_progress_page, render_review_page  # noqa: E402


class MobileHtmlTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "output" / "2026-07-14_stevie-ray-s-blues-bar").mkdir(parents=True)
        img = self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r1.png"
        img.write_bytes(b"x" * 1024)
        manifest = {
            "gig_id": "2026-07-14_stevie-ray-s-blues-bar",
            "round": 1,
            "event": {"venue": "Stevie Ray's Blues Bar", "short_date": "Jul 14", "band": "Lindsey Lane Band"},
            "options": {"A": "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r1.png"},
        }
        (self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar/manifest_r1.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (self.tmp_path / "state.json").write_text(
            json.dumps(
                {
                    "gigs": {
                        "2026-07-14_stevie-ray-s-blues-bar": {
                            "status": "pending_review",
                            "round": 1,
                            "options": manifest["options"],
                            "event": manifest["event"],
                            "feedback_history": [],
                        }
                    },
                    "last_poll_rowid": 0,
                }
            ),
            encoding="utf-8",
        )

        self.patches = [
            patch("state.ROOT", self.tmp_path),
            patch("state.STATE_PATH", self.tmp_path / "state.json"),
            patch("bridge.review.ROOT", self.tmp_path),
            patch("bridge.review.OUTPUT_DIR", self.tmp_path / "output"),
            patch.dict("os.environ", {"BRIDGE_PUBLIC_URL": "http://test.local/flyers"}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def _assert_mobile_shell(self, html_text: str) -> None:
        self.assertIn('name="viewport"', html_text)
        self.assertIn("viewport-fit=cover", html_text)
        self.assertIn("site-header", html_text)
        self.assertIn("Band Tools", html_text)
        self.assertIn("Pick gig", html_text)
        self.assertIn("page-shell", html_text)
        self.assertIn("@media", html_text)
        self.assertIn("safe-area-inset", html_text)
        self.assertIn("--tap-min", html_text)

    def test_home_page_mobile_shell(self) -> None:
        self._assert_mobile_shell(render_home_page())
        self.assertIn("Mode 1", render_home_page())
        self.assertIn("Mode 2", render_home_page())

    def test_picker_page_mobile_shell(self) -> None:
        with patch("bridge.interactive.get_future_gigs", return_value=[]):
            with patch("bridge.interactive.get_local_today", return_value=date(2026, 6, 23)):
                html_text = render_picker_page(build_picker_data())
        self._assert_mobile_shell(html_text)
        self.assertIn("gig-card", html_text)

    def test_review_page_mobile_shell(self) -> None:
        html_text = render_review_page(build_review_data("2026-07-14_stevie-ray-s-blues-bar"))
        self._assert_mobile_shell(html_text)
        self.assertIn("options-grid", html_text)
        self.assertIn("collapsible-section", html_text)
        self.assertIn("Iteration history", html_text)
        self.assertIn("btn-block", html_text)

    def test_progress_page_mobile_shell(self) -> None:
        html_text = render_job_progress_page(
            "gig-1",
            {"venue": "Test Venue", "short_date": "Jul 1"},
            heading="Generating…",
        )
        self._assert_mobile_shell(html_text)
        self.assertIn("options-grid", html_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
