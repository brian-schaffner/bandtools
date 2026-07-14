#!/usr/bin/env python3
"""Tests for wild post-render yellow/cream color correction."""

from __future__ import annotations

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
    """Synthetic parchment yellow-cream."""
    return (220 + warmth // 3, 205 + warmth // 4, 175 - warmth // 6)


class WildColorCorrectTests(unittest.TestCase):
    def test_reduces_yellow_cast_on_cream_field(self) -> None:
        img = Image.new("RGB", (128, 128), _cream_rgb(60))
        before = estimate_image_warmth(img)
        corrected = correct_yellow_cast(img, strength=1.0)
        after = estimate_image_warmth(corrected)
        self.assertGreater(before, 40)
        self.assertLess(after, before * 0.65)

    def test_preserves_brick_red_blocks(self) -> None:
        img = Image.new("RGB", (64, 64), _cream_rgb(50))
        pixels = img.load()
        for x in range(20, 44):
            for y in range(20, 44):
                pixels[x, y] = (190, 45, 38)
        corrected = correct_yellow_cast(img, strength=1.0)
        cp = corrected.load()
        r, g, b = cp[32, 32]
        self.assertGreaterEqual(r, 170)
        self.assertLess(g, 80)
        self.assertLess(b, 70)

    def test_option_c_skips_when_already_neutral(self) -> None:
        img = Image.new("RGB", (64, 96), (28, 28, 30))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "neutral-c.png"
            img.save(path)
            with patch.dict("os.environ", {"WILD_COLOR_CORRECT": "1"}, clear=False):
                self.assertFalse(correct_wild_flyer_colors(path, "C"))

    def test_option_c_corrects_when_warm(self) -> None:
        img = Image.new("RGB", (96, 128), _cream_rgb(70))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "warm-c.png"
            img.save(path)
            before = estimate_image_warmth(img)
            with patch.dict("os.environ", {"WILD_COLOR_CORRECT": "1"}, clear=False):
                self.assertTrue(correct_wild_flyer_colors(path, "C"))
            after_img = Image.open(path)
            after = estimate_image_warmth(after_img)
            self.assertLess(after, before * 0.8)

    def test_disabled_via_env(self) -> None:
        img = Image.new("RGB", (64, 64), _cream_rgb(80))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cream-a.png"
            img.save(path)
            original = path.read_bytes()
            with patch.dict("os.environ", {"WILD_COLOR_CORRECT": "0"}, clear=False):
                self.assertFalse(correct_wild_flyer_colors(path, "A"))
            self.assertEqual(path.read_bytes(), original)

    def test_option_a_stronger_than_c(self) -> None:
        img = Image.new("RGB", (64, 64), _cream_rgb(65))
        a = correct_yellow_cast(img, strength=1.0)
        c = correct_yellow_cast(img, strength=0.4)
        self.assertLess(estimate_image_warmth(a), estimate_image_warmth(c))

    def test_correct_wild_flyer_colors_writes_file(self) -> None:
        img = Image.new("RGB", (80, 120), _cream_rgb(75))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wild-a.png"
            img.save(path)
            with patch.dict("os.environ", {"WILD_COLOR_CORRECT": "1"}, clear=False):
                self.assertTrue(correct_wild_flyer_colors(path, "A"))
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
