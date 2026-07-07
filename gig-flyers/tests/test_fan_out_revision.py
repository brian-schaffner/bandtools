#!/usr/bin/env python3
"""Tests for fan-out revision generation (3 variants of base option)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_generator import (  # noqa: E402
    _fan_out_revision,
    _variations_for_base_option,
    load_style,
)


class FanOutRevisionTest(unittest.TestCase):
    def test_fan_out_when_base_and_feedback(self) -> None:
        self.assertTrue(_fan_out_revision("A", "pastel colors"))
        self.assertFalse(_fan_out_revision("A", ""))
        self.assertFalse(_fan_out_revision(None, "pastel"))

    def test_variations_repeat_base_tier(self) -> None:
        style = load_style()
        vars_a = _variations_for_base_option(style, 3, "A")
        self.assertEqual(len(vars_a), 3)
        self.assertEqual(vars_a[0]["tier"], vars_a[1]["tier"])
        self.assertEqual(vars_a[0]["tier"], "conservative")

        vars_c = _variations_for_base_option(style, 3, "C")
        self.assertEqual(vars_c[0]["tier"], "creative")


if __name__ == "__main__":
    unittest.main()
