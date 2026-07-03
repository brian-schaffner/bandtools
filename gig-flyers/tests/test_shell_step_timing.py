#!/usr/bin/env python3
"""Tests for shell step timing."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_step_timing import ShellStepTiming  # noqa: E402


class ShellStepTimingTest(unittest.TestCase):
    def test_measure_and_export(self) -> None:
        timing = ShellStepTiming()
        timing.start("pass1")
        time.sleep(0.01)
        timing.stop("pass1")
        timing.mark_cache("pass1", True)
        timing.add_openai_calls(2)
        data = timing.to_dict()
        self.assertGreaterEqual(data["timings_ms"]["pass1"], 5)
        self.assertTrue(data["cache_hits"]["pass1"])
        self.assertEqual(data["openai_calls"], 2)


if __name__ == "__main__":
    unittest.main()
