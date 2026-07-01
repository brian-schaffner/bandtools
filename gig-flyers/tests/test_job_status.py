#!/usr/bin/env python3
"""Tests for generation job status endpoint."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.job_status import clear_all_jobs, report_progress, start_job  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class JobStatusEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_all_jobs()
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))

        self.patches = [
            patch("state.STATE_PATH", self.tmp_path / "state.json"),
            patch.dict("os.environ", {"BRIDGE_PUBLIC_URL": "http://test.local/flyers"}),
        ]
        for p in self.patches:
            p.start()

        from bridge.server import app

        self.client = TestClient(app)
        self.gig_id = "2026-07-14_test-gig"

    def tearDown(self) -> None:
        from bridge.server import _generate_in_flight, _revise_in_flight

        _generate_in_flight.clear()
        _revise_in_flight.clear()
        clear_all_jobs()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_status_idle_when_no_job(self) -> None:
        resp = self.client.get(f"/review/{self.gig_id}/status")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("no-store", resp.headers.get("cache-control", ""))
        data = resp.json()
        self.assertEqual(data["status"], "idle")
        self.assertEqual(data["progress"], 0)
        self.assertIn("options", data)
        self.assertEqual(data["options"]["A"]["phase"], "pending")
        self.assertEqual(data["log"], [])
        self.assertEqual(data["substep"], "")

    def test_status_expanded_payload(self) -> None:
        start_job(self.gig_id, "generate", title="Jul 14 @ Test")
        report_progress(
            self.gig_id,
            step="research",
            substep="venue_detected",
            message="Detected: blues_bar",
            detail="blues_club_handbill",
            progress=7,
        )
        report_progress(
            self.gig_id,
            step="generate",
            substep="prompt",
            message="Building prompt for vertical handbill layout…",
            progress=22,
            option="A",
        )
        report_progress(
            self.gig_id,
            step="review",
            substep="verdict",
            message="Score 7/10 — face cropped at top",
            detail="face cropped awkwardly",
            progress=28,
            option="A",
            attempt=1,
        )
        resp = self.client.get(f"/review/{self.gig_id}/status")
        data = resp.json()
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["step"], "review")
        self.assertEqual(data["substep"], "verdict")
        self.assertEqual(data["option"], "A")
        self.assertEqual(data["attempt"], 1)
        self.assertIn("face cropped", data["message"])
        self.assertGreaterEqual(len(data["log"]), 3)
        self.assertIn("text", data["log"][-1])
        self.assertIn("at", data["log"][-1])

    def test_log_ring_buffer(self) -> None:
        start_job(self.gig_id, "generate")
        for i in range(20):
            report_progress(self.gig_id, step="generate", substep="tick", message=f"step {i}", progress=i)
        data = self.client.get(f"/review/{self.gig_id}/status").json()
        self.assertLessEqual(len(data["log"]), 8)
        self.assertIn("step 19", data["log"][-1]["text"])
        self.assertGreaterEqual(data["log_revision"], 20)

    def test_log_revision_increments_on_each_entry(self) -> None:
        start_job(self.gig_id, "generate")
        first = self.client.get(f"/review/{self.gig_id}/status").json()
        self.assertEqual(first["log_revision"], 1)
        report_progress(self.gig_id, step="research", substep="venue", message="Analyzing venue…", progress=5)
        second = self.client.get(f"/review/{self.gig_id}/status").json()
        self.assertEqual(second["log_revision"], 2)
        self.assertEqual(len(second["log"]), 2)

    def test_log_revision_updates_when_ring_buffer_full(self) -> None:
        start_job(self.gig_id, "generate")
        for i in range(16):
            report_progress(self.gig_id, step="generate", substep="tick", message=f"step {i}", progress=i)
        data = self.client.get(f"/review/{self.gig_id}/status").json()
        self.assertEqual(len(data["log"]), 8)
        self.assertEqual(data["log_revision"], 17)
        self.assertIn("step 15", data["log"][-1]["text"])

    def test_progress_page_uses_log_revision(self) -> None:
        from bridge.review import render_job_progress_page

        html = render_job_progress_page(
            self.gig_id,
            {"venue": "Test Venue", "short_date": "Jul 14"},
            heading="Generating…",
        )
        self.assertIn("lastLogRevision", html)
        self.assertIn("lastOptionsRevision", html)

    def test_progress_page_includes_vessel_grid(self) -> None:
        from bridge.review import render_job_progress_page

        html = render_job_progress_page(
            self.gig_id,
            {"venue": "Test Venue", "short_date": "Jul 14"},
            heading="Generating…",
        )
        self.assertIn("options-grid", html)
        self.assertIn("vessel-fill", html)
        self.assertIn("pollMs = 1000", html)
        self.assertIn("streamUrl", html)
        self.assertIn("EventSource", html)
        self.assertIn("renderOptions", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
