#!/usr/bin/env python3
"""Tests for per-option job status and timing estimates."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_reviewer import max_reviewer_retries  # noqa: E402
from bridge.job_status import (  # noqa: E402
    clear_all_jobs,
    get_job_status,
    report_progress,
    start_job,
    update_option,
)
from bridge.review import public_output_url  # noqa: E402
from gen_timing import (  # noqa: E402
    DEFAULT_GENERATE_SECONDS,
    DEFAULT_OPTION_SECONDS,
    MIN_GENERATE_ESTIMATE_SECONDS,
    get_estimates,
    get_generate_estimate,
    record_generate_timing,
    record_option_timing,
    reset_timing_cache,
    tier_for_option,
)


class OptionStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_all_jobs()
        reset_timing_cache()
        self.gig_id = "2026-07-14_test-gig"

    def tearDown(self) -> None:
        clear_all_jobs()
        reset_timing_cache()

    def test_idle_includes_options_and_estimates(self) -> None:
        data = get_job_status(self.gig_id)
        self.assertEqual(data["status"], "idle")
        self.assertIn("options", data)
        self.assertEqual(set(data["options"].keys()), {"A", "B", "C"})
        self.assertEqual(data["options"]["A"]["phase"], "pending")
        self.assertIn("image_url", data["options"]["A"])
        self.assertAlmostEqual(data["estimated_option_seconds"], DEFAULT_OPTION_SECONDS)

    def test_start_job_sets_per_option_estimates(self) -> None:
        with patch.dict("os.environ", {"GIG_IMAGE_PROVIDER": "openai", "OPENAI_API_KEY": "x"}, clear=False):
            start_job(self.gig_id, "generate")
        data = get_job_status(self.gig_id)
        for letter in ("A", "B", "C"):
            est = data["options"][letter]["estimated_generate_seconds"]
            self.assertGreaterEqual(est, MIN_GENERATE_ESTIMATE_SECONDS)
        self.assertEqual(
            data["estimated_generate_seconds"],
            max(data["options"][l]["estimated_generate_seconds"] for l in ("A", "B", "C")),
        )

    def test_per_tier_estimates_differ_when_buckets_differ(self) -> None:
        for seconds, tier in ((22.0, "conservative"), (30.0, "medium"), (40.0, "creative")):
            for _ in range(3):
                record_generate_timing(seconds, provider="openai", quality="high", tier=tier)
        with patch.dict("os.environ", {"GIG_IMAGE_PROVIDER": "openai", "OPENAI_API_KEY": "x"}, clear=False):
            start_job(self.gig_id, "generate")
        data = get_job_status(self.gig_id)
        est_a = data["options"]["A"]["estimated_generate_seconds"]
        est_c = data["options"]["C"]["estimated_generate_seconds"]
        self.assertGreater(est_c, est_a)

    def test_generating_start_freezes_estimate_and_timestamp(self) -> None:
        start_job(self.gig_id, "generate")
        before = get_job_status(self.gig_id)["options"]["A"]["estimated_generate_seconds"]
        report_progress(
            self.gig_id,
            step="generate",
            substep="start",
            message="Generating A",
            progress=22,
            option="A",
            attempt=1,
        )
        after_start = get_job_status(self.gig_id)
        opt_a = after_start["options"]["A"]
        self.assertEqual(opt_a["phase"], "generating")
        self.assertAlmostEqual(opt_a["estimated_generate_seconds"], before)
        self.assertIsNotNone(opt_a.get("generate_started_at"))

    def test_remake_resets_generate_started_at(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="generate",
            substep="start",
            message="Generating B",
            option="B",
            attempt=1,
        )
        first = get_job_status(self.gig_id)["options"]["B"]["generate_started_at"]
        report_progress(
            self.gig_id,
            step="generate",
            substep="remake",
            message="Remaking B",
            option="B",
            attempt=2,
        )
        second = get_job_status(self.gig_id)["options"]["B"]
        self.assertEqual(second["phase"], "remaking")
        self.assertNotEqual(second["generate_started_at"], first)

    def test_start_job_includes_provider_label(self) -> None:
        with patch.dict("os.environ", {"GIG_IMAGE_PROVIDER": "gemini", "GOOGLE_API_KEY": "x"}, clear=False):
            start_job(self.gig_id, "generate")
        data = get_job_status(self.gig_id)
        self.assertIn("Gemini", data.get("provider_label", ""))
        self.assertEqual(data.get("active_provider"), "gemini")

    def test_start_job_split_sets_per_option_labels(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GIG_IMAGE_PROVIDER_SPLIT": "1",
                "OPENAI_API_KEY": "x",
                "GOOGLE_API_KEY": "y",
            },
            clear=False,
        ):
            start_job(self.gig_id, "generate")
        data = get_job_status(self.gig_id)
        self.assertEqual(data["options"]["A"]["provider_label"], "A: OpenAI")
        self.assertEqual(data["options"]["B"]["provider_label"], "B: Gemini Nano")
        self.assertIn("A: OpenAI", data["provider_label"])

    def test_generating_start_sets_phase_once(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="generate",
            substep="start",
            message="Generating A",
            progress=22,
            option="A",
            attempt=1,
        )
        after_start = get_job_status(self.gig_id)
        rev_after_start = after_start["options_revision"]
        self.assertEqual(after_start["options"]["A"]["phase"], "generating")
        self.assertEqual(after_start["options"]["A"]["progress"], 0)

        report_progress(
            self.gig_id,
            step="generate",
            substep="api_start",
            message="Calling API for A",
            progress=24,
            option="A",
            attempt=1,
        )
        after_api = get_job_status(self.gig_id)
        self.assertEqual(after_api["options"]["A"]["phase"], "generating")
        self.assertEqual(after_api["options_revision"], rev_after_start)

    def test_review_preview_includes_image_url(self) -> None:
        start_job(self.gig_id, "generate")
        url = "/flyers/output/2026-07-14_test/option-A_r1.png"
        report_progress(
            self.gig_id,
            step="review",
            substep="preview",
            message="Ready for review",
            option="A",
            attempt=1,
            option_phase="reviewing",
            option_image_url=url,
        )
        data = get_job_status(self.gig_id)
        self.assertEqual(data["options"]["A"]["phase"], "reviewing")
        self.assertEqual(data["options"]["A"]["image_url"], url)

    def test_review_passed_turns_green(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="review",
            substep="passed",
            message="Option A: Passed",
            option="A",
            attempt=1,
            option_image_url="/flyers/output/x.png",
        )
        data = get_job_status(self.gig_id)
        self.assertEqual(data["options"]["A"]["phase"], "passed")
        self.assertEqual(data["options"]["A"]["progress"], 100)

    def test_fail_exhausted_flag(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="review",
            substep="remake",
            message="Failed",
            detail="bad text",
            option="B",
            attempt=2,
            option_exhausted=True,
            option_image_url="/flyers/output/b.png",
        )
        data = get_job_status(self.gig_id)
        self.assertEqual(data["options"]["B"]["phase"], "failed")
        self.assertTrue(data["options"]["B"]["exhausted"])

    def test_review_fail_then_remake_cycle(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="review",
            substep="remake",
            message="Remake recommended",
            detail="Venue name unreadable",
            option="B",
            attempt=1,
            option_image_url="/flyers/output/b.png",
        )
        failed = get_job_status(self.gig_id)
        self.assertEqual(failed["options"]["B"]["phase"], "failed")
        self.assertFalse(failed["options"]["B"]["exhausted"])

        report_progress(
            self.gig_id,
            step="generate",
            substep="remake",
            message="Remaking B",
            option="B",
            attempt=2,
        )
        remaking = get_job_status(self.gig_id)
        self.assertEqual(remaking["options"]["B"]["phase"], "remaking")
        self.assertEqual(remaking["options"]["B"]["progress"], 0)
        self.assertEqual(remaking["options"]["B"]["image_url"], "")

    def test_generating_substeps_preserve_generate_started_at(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="generate",
            substep="start",
            message="Generating A",
            option="A",
            attempt=1,
        )
        started = get_job_status(self.gig_id)["options"]["A"]["generate_started_at"]
        for substep in ("prompt", "provider", "api_start", "saved", "retry"):
            report_progress(
                self.gig_id,
                step="generate",
                substep=substep,
                message=f"A {substep}",
                option="A",
                attempt=1,
            )
        after = get_job_status(self.gig_id)["options"]["A"]
        self.assertEqual(after["generate_started_at"], started)
        self.assertEqual(after["phase"], "generating")

    def test_heartbeats_do_not_update_option_state(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="generate",
            substep="start",
            message="Generating A",
            option="A",
            attempt=1,
        )
        before = get_job_status(self.gig_id)
        report_progress(
            self.gig_id,
            step="generate",
            substep="heartbeat",
            message="Still generating A…",
            progress=25,
            option="A",
            attempt=1,
            log=False,
            option_phase="generating",
            option_progress=42,
        )
        after = get_job_status(self.gig_id)
        self.assertEqual(after["options"]["A"], before["options"]["A"])
        self.assertEqual(after["options_revision"], before["options_revision"])

    def test_generate_started_at_stable_across_generating_substeps(self) -> None:
        start_job(self.gig_id, "generate")
        report_progress(
            self.gig_id,
            step="generate",
            substep="start",
            message="Generating A",
            option="A",
            attempt=1,
        )
        started = get_job_status(self.gig_id)["options"]["A"]["generate_started_at"]
        estimate = get_job_status(self.gig_id)["options"]["A"]["estimated_generate_seconds"]
        for substep in ("prompt", "provider", "api_start", "saved"):
            report_progress(
                self.gig_id,
                step="generate",
                substep=substep,
                message=f"A {substep}",
                option="A",
                attempt=1,
            )
            opt = get_job_status(self.gig_id)["options"]["A"]
            self.assertEqual(opt["generate_started_at"], started)
            self.assertAlmostEqual(opt["estimated_generate_seconds"], estimate)

    def test_max_reviewer_retries_default(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("AI_REVIEWER_MAX_REMAKES", None)
            self.assertEqual(max_reviewer_retries(), 1)

    def test_public_output_url(self) -> None:
        with patch.dict("os.environ", {"BRIDGE_PUBLIC_URL": "https://x.ts.net/flyers"}, clear=False):
            url = public_output_url("output/2026-07-14_test-venue/option-A_r1.png")
            self.assertIn("/output/", url)
            self.assertIn("option-A_r1.png", url)

    def test_timing_rolling_average(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            timing_path = Path(tmp) / "gen_timing.json"
            with patch("gen_timing.TIMING_PATH", timing_path):
                reset_timing_cache()
                record_option_timing(20.0, 10.0)
                record_option_timing(40.0, 20.0)
                est = get_estimates()
                self.assertGreater(est["generate_seconds"], 20.0)
                self.assertLess(est["generate_seconds"], 40.0)


class OptionProgressPageTest(unittest.TestCase):
    def test_progress_page_has_preview_ui(self) -> None:
        from bridge.review import render_job_progress_page

        html = render_job_progress_page(
            "2026-07-14_test",
            {"venue": "Test Venue", "short_date": "Jul 14"},
            heading="Generating…",
        )
        self.assertIn("option-preview", html)
        self.assertIn("option-thumb", html)
        self.assertIn("startFillTracking", html)
        self.assertIn("computeFillRatio", html)
        self.assertIn("maxProgress", html)
        self.assertIn("generate_started_at", html)
        self.assertIn("provider-label", html)
        self.assertIn("engine-A", html)
        self.assertIn("outline-review", html)
        self.assertIn("failFlash", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
