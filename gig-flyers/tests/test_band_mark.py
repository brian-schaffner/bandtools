"""Tests for band mark / logo resolution."""

from __future__ import annotations

import unittest

from structured_layout.band_mark import band_initials, band_slug, find_band_logo


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


if __name__ == "__main__":
    unittest.main()
