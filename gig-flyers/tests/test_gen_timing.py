#!/usr/bin/env python3
"""Tests for bucketed generation timing estimates."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gen_timing import (  # noqa: E402
    DEFAULT_GENERATE_SECONDS,
    MIN_GENERATE_ESTIMATE_SECONDS,
    MIN_RECORD_GENERATE_SECONDS,
    get_generate_estimate,
    quality_for_tier,
    record_generate_timing,
    record_option_timing,
    reset_timing_cache,
    tier_for_option,
)


class GenTimingBucketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.timing_path = Path(self.tmp.name) / "gen_timing.json"
        self.path_patch = patch("gen_timing.TIMING_PATH", self.timing_path)
        self.path_patch.start()
        reset_timing_cache()

    def tearDown(self) -> None:
        self.path_patch.stop()
        self.tmp.cleanup()

    def test_tier_and_quality_mapping(self) -> None:
        self.assertEqual(tier_for_option("A"), "conservative")
        self.assertEqual(tier_for_option("C"), "creative")
        self.assertEqual(quality_for_tier("creative"), "high")
        self.assertEqual(quality_for_tier("medium", use_reference=False), "medium")

    def test_exact_bucket_used_with_single_sample(self) -> None:
        record_generate_timing(
            188.0,
            provider="openai",
            quality="high",
            tier="conservative",
        )
        estimate = get_generate_estimate("openai", "high", "conservative")
        self.assertAlmostEqual(estimate, 188.0)

    def test_exact_bucket_used_after_three_samples(self) -> None:
        for seconds in (20.0, 24.0, 28.0, 32.0):
            record_generate_timing(
                seconds,
                provider="openai",
                quality="medium",
                tier="conservative",
            )
        estimate = get_generate_estimate("openai", "medium", "conservative")
        self.assertGreaterEqual(estimate, 24.0)
        self.assertLessEqual(estimate, 32.0)

    def test_fallback_to_provider_quality(self) -> None:
        for seconds in (18.0, 22.0, 26.0):
            record_generate_timing(
                seconds,
                provider="openai",
                quality="medium",
                tier="medium",
            )
        estimate = get_generate_estimate("openai", "medium", "conservative")
        self.assertGreater(estimate, DEFAULT_GENERATE_SECONDS / 2)

    def test_fallback_to_provider(self) -> None:
        for seconds in (40.0, 44.0, 48.0):
            record_generate_timing(
                seconds,
                provider="openai",
                quality="high",
                tier="creative",
            )
        estimate = get_generate_estimate("openai", "low", "unknown")
        self.assertGreaterEqual(estimate, 40.0)

    def test_global_default_without_samples(self) -> None:
        estimate = get_generate_estimate("gemini", "medium", "medium")
        self.assertAlmostEqual(estimate, DEFAULT_GENERATE_SECONDS)

    def test_record_option_timing_backward_compat(self) -> None:
        record_option_timing(30.0, 10.0)
        estimate = get_generate_estimate("openai", "medium", "medium")
        self.assertGreater(estimate, 20.0)

    def test_low_samples_not_recorded(self) -> None:
        record_generate_timing(
            1.0,
            provider="openai",
            quality="medium",
            tier="conservative",
        )
        estimate = get_generate_estimate("openai", "medium", "conservative")
        self.assertAlmostEqual(estimate, DEFAULT_GENERATE_SECONDS)

    def test_polluted_cache_uses_floor(self) -> None:
        for _ in range(5):
            record_generate_timing(
                MIN_RECORD_GENERATE_SECONDS - 1,
                provider="openai",
                quality="medium",
                tier="medium",
            )
        estimate = get_generate_estimate("openai", "medium", "medium")
        self.assertGreaterEqual(estimate, MIN_GENERATE_ESTIMATE_SECONDS)

    def test_estimate_never_below_floor(self) -> None:
        for seconds in (16.0, 17.0, 18.0):
            record_generate_timing(
                seconds,
                provider="openai",
                quality="high",
                tier="creative",
            )
        estimate = get_generate_estimate("openai", "high", "creative")
        self.assertGreaterEqual(estimate, MIN_GENERATE_ESTIMATE_SECONDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
