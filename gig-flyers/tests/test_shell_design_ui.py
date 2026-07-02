#!/usr/bin/env python3
"""Tests for shell design web UI."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402


class ShellDesignUiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))

        self.patches = [
            patch("state.ROOT", self.tmp_path),
            patch("state.STATE_PATH", self.tmp_path / "state.json"),
            patch("state.APPROVED_DIR", self.tmp_path / "output/approved"),
            patch("bridge.review.OUTPUT_DIR", self.tmp_path / "output"),
            patch("bridge.interactive.get_future_gigs", return_value=[]),
            patch.dict("os.environ", {"BRIDGE_PUBLIC_URL": "http://test.local/flyers"}),
        ]
        for p in self.patches:
            p.start()

        from bridge.server import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        from bridge.server import _shell_in_flight

        _shell_in_flight.clear()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_shell_studio_page_renders(self) -> None:
        resp = self.client.get("/shell")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Shell Design Studio", resp.text)
        self.assertIn("woodstock_festival_1969", resp.text)
        self.assertIn("/flyers/shell/", resp.text)

    def test_shell_detail_page_renders(self) -> None:
        resp = self.client.get("/shell/woodstock_festival_1969")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Woodstock", resp.text)
        self.assertIn("Start two-pass generation", resp.text)

    def test_shell_reference_image(self) -> None:
        from shell_references import get_shell

        shell = get_shell("woodstock_festival_1969")
        assert shell is not None
        if not shell.has_image():
            self.skipTest("Woodstock reference image not cached")
        resp = self.client.get("/shell/ref/woodstock_festival_1969")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.headers.get("content-type", ""), ("image/jpeg", "image/png"))

    def test_home_page_links_shell_studio(self) -> None:
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Shell Design Studio", resp.text)
        self.assertIn("/flyers/shell", resp.text)

    def test_shell_progress_page_has_stepper(self) -> None:
        from bridge.shell_design import render_shell_generating_page

        page = render_shell_generating_page(
            "shell-test123",
            shell_title="Jimi Hendrix at Sicks Stadium (1970)",
            venue="Two Lane Tavern",
        )
        self.assertIn("Pass 1 — Design shell", page)
        self.assertIn("Pass 2 — Personalize", page)
        self.assertIn("id=\"step-pass1\"", page)
        self.assertIn("Elapsed:", page)


if __name__ == "__main__":
    unittest.main()
