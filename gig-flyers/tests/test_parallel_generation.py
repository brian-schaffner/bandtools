#!/usr/bin/env python3
"""Tests for parallel A/B/C generation."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_generator import generate_for_gig  # noqa: E402
from gig_calendar import GigEvent  # noqa: E402


def _sample_event() -> GigEvent:
    from datetime import date

    return GigEvent(
        event_date=date(2026, 7, 14),
        time_label="8:00 pm",
        title="Lindsey Lane Band at Test Venue",
        venue="Test Venue",
        suggested_name="Jul 14 Test Venue",
    )


class ParallelGenerationTest(unittest.TestCase):
    def test_three_options_run_concurrently(self) -> None:
        active = {"count": 0}
        peak = {"value": 0}
        lock = threading.Lock()
        gen_delay = 0.12

        def slow_generate(*args, **kwargs) -> None:
            with lock:
                active["count"] += 1
                peak["value"] = max(peak["value"], active["count"])
            time.sleep(gen_delay)
            output_path = kwargs.get("output_path") or args[1]
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(b"png")
            with lock:
                active["count"] -= 1

        event = _sample_event()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            timing_path = tmp_path / "gen_timing.json"
            (tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))
            with patch("gen_timing.TIMING_PATH", timing_path):
                with patch("flyer_generator.resolve_gig_event", return_value=event):
                    with patch("flyer_generator.research_gig", return_value={}):
                        with patch("flyer_generator.select_band_photo", return_value=None):
                            with patch("flyer_generator.generate_image", side_effect=slow_generate):
                                with patch("flyer_generator.reviewer_enabled", return_value=False):
                                    with patch("flyer_generator.ROOT", tmp_path):
                                        with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                                            with patch("state.STATE_PATH", tmp_path / "state.json"):
                                                with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                                                    start = time.monotonic()
                                                    manifest = generate_for_gig(
                                                        event.gig_id,
                                                        count=3,
                                                        dry_run=False,
                                                    )
                                                    elapsed = time.monotonic() - start

        self.assertEqual(len(manifest["options"]), 3)
        self.assertGreaterEqual(peak["value"], 2, "expected at least 2 concurrent generations")
        sequential_estimate = gen_delay * 3
        self.assertLess(
            elapsed,
            sequential_estimate * 0.75,
            f"parallel {elapsed:.2f}s should beat sequential ~{sequential_estimate:.2f}s",
        )

    def test_parallel_message_emitted(self) -> None:
        messages: list[str] = []

        def capture_progress(**kwargs) -> None:
            msg = kwargs.get("message", "")
            if msg:
                messages.append(msg)

        event = _sample_event()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            timing_path = tmp_path / "gen_timing.json"
            (tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))
            with patch("gen_timing.TIMING_PATH", timing_path):
                with patch("flyer_generator.resolve_gig_event", return_value=event):
                    with patch("flyer_generator.research_gig", return_value={}):
                        with patch("flyer_generator.select_band_photo", return_value=None):
                            with patch("flyer_generator.generate_image"):
                                with patch("flyer_generator.reviewer_enabled", return_value=False):
                                    with patch("flyer_generator.ROOT", tmp_path):
                                        with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                                            with patch("state.STATE_PATH", tmp_path / "state.json"):
                                                with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                                                    generate_for_gig(
                                                        event.gig_id,
                                                        count=3,
                                                        dry_run=False,
                                                        on_progress=capture_progress,
                                                    )

        self.assertTrue(any("parallel" in m.lower() for m in messages))


if __name__ == "__main__":
    unittest.main(verbosity=2)
