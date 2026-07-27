#!/usr/bin/env python3
"""Tests for wild post-render yellow/cream color correction."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from wild_design.color_correct import (  # noqa: E402
    correct_wild_flyer_colors,
    correct_yellow_cast,
    estimate_image_warmth,
)


def _cream_rgb(warmth: int = 55) -> tuple[int, int, int]:
    return (220 + warmth // 3, 205 + warmth // 4, 175 - warmth // 6)


class WildColorCorrectTests(unittest.TestCase):
    def test_reduces_yellow_cast_on_cream_field(self) -> None:
        img = Image.new("RGB", (128, 128), _cream_rgb(60))
        before = estimate_image_warmth(img)
        after = estimate_image_warmth(correct_yellow_cast(img, strength=1.0))
        self.assertGreater(before, 40)
        self.assertLess(after, before * 0.65)

    def test_correct_wild_flyer_colors_writes_file(self) -> None:
        img = Image.new("RGB", (80, 120), _cream_rgb(75))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wild-a.png"
            img.save(path)
            with patch.dict(os.environ, {"WILD_COLOR_CORRECT": "1"}, clear=False):
                self.assertTrue(correct_wild_flyer_colors(path, "A"))
            self.assertGreater(path.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
