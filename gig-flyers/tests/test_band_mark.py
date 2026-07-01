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


if __name__ == "__main__":
    unittest.main()
