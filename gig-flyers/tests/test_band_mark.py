"""Tests for band mark / logo resolution."""

from __future__ import annotations

import unittest

from PIL import Image, ImageChops

from structured_layout.band_mark import (
    HERO_BOXES,
    band_initials,
    band_slug,
    draw_band_hero,
    find_band_logo,
)
from structured_layout.graphic_primitives import CANVAS


class BandMarkTest(unittest.TestCase):
    def test_band_slug(self) -> None:
        self.assertEqual(band_slug("Lindsey Lane Band"), "lindsey-lane-band")

    def test_band_initials(self) -> None:
        self.assertEqual(band_initials("Lindsey Lane Band"), "LL")

    def test_find_band_logo_missing(self) -> None:
        self.assertIsNone(find_band_logo("Nonexistent Band Name"))

    def test_find_lindsey_lane_logo(self) -> None:
        path = find_band_logo("Lindsey Lane Band", paper=(240, 235, 225))
        self.assertIsNotNone(path)
        self.assertTrue(path.name.endswith(".png"))

    def test_hero_logo_replaces_header_cramp(self) -> None:
        """Logo belongs in band zone, not squeezed beside venue header."""
        paper = (220, 50, 45)
        base = Image.new("RGBA", CANVAS, (*paper, 255))
        canvas = base.copy()
        placed = draw_band_hero(
            canvas,
            "Lindsey Lane Band",
            style="duotone_modern",
            paper=paper,
            accent=(255, 248, 235),
            ink=(255, 248, 235),
        )
        self.assertTrue(placed)
        diff = ImageChops.difference(base, canvas).convert("L")
        header_change = sum(diff.crop((0, 0, CANVAS[0], 160)).get_flattened_data())
        x1, y1, x2, y2 = HERO_BOXES["duotone_modern"]
        hero_change = sum(diff.crop((x1, y1, x2, y2)).get_flattened_data())
        self.assertGreater(hero_change, header_change * 4)


if __name__ == "__main__":
    unittest.main()
