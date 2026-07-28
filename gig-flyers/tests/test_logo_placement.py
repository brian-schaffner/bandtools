#!/usr/bin/env python3
"""Tests for standard wild logo placement slots."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wild_design.logo_placement import (  # noqa: E402
    FOOTER_HERO,
    TOP_BANNER,
    placement_for_option,
)


class LogoPlacementTests(unittest.TestCase):
    def test_per_option_defaults(self) -> None:
        self.assertEqual(placement_for_option("A").key, "footer_hero")
        self.assertEqual(placement_for_option("C").key, "footer_hero")
        self.assertEqual(placement_for_option("B").key, "top_banner")

    def test_footer_box_is_large(self) -> None:
        x1, y1, x2, y2 = FOOTER_HERO.box
        self.assertGreaterEqual(x2 - x1, 800)
        self.assertGreaterEqual(y2 - y1, 200)

    def test_all_footer_mode(self) -> None:
        with patch.dict(os.environ, {"FLY_LOGO_PLACEMENT": "footer_hero"}, clear=False):
            self.assertEqual(placement_for_option("B").key, "footer_hero")

    def test_pass2_prompt_when_enabled(self) -> None:
        from wild_design.logo_placement import band_photo_pass2_prompt_block

        with patch.dict(os.environ, {"WILD_BAND_REPLACE_AFTER_GEN": "1"}, clear=False):
            self.assertIn("PASS 2", band_photo_pass2_prompt_block())


if __name__ == "__main__":
    unittest.main()
