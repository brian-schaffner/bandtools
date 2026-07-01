#!/usr/bin/env python3
"""Tests for flyer text validation and gig-type hierarchy."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from text_validation import (  # noqa: E402
    SAFE_MARGIN_PX,
    featured_act_line,
    footer_prompt_lines,
    halftone_unsafe_for_band_photo,
    is_house_series_gig,
    resolve_venue_address,
    validate_required_footer_text,
)


class TextValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tuesday_jam = GigEvent(
            event_date=date(2026, 6, 30),
            time_label="9:30 pm",
            title="Hosting Stevie Ray's World Famous Tuesday Jam",
            venue="Stevie Ray's Tuesday Jam",
            suggested_name="Jun 30 Stevie Ray's Tuesday Jam",
        )
        self.headliner = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="8:00 pm",
            title="Lindsey Lane Band at Test Venue",
            venue="Test Venue",
            suggested_name="Jul 14 Test Venue",
        )

    def test_safe_margin_constant(self) -> None:
        self.assertEqual(SAFE_MARGIN_PX, 48)

    def test_resolve_stevie_ray_address(self) -> None:
        address = resolve_venue_address(self.tuesday_jam)
        self.assertIn("40202", address)
        self.assertIn("Main Street", address)

    def test_house_series_gig_detection(self) -> None:
        self.assertTrue(is_house_series_gig(self.tuesday_jam))
        self.assertFalse(is_house_series_gig(self.headliner))

    def test_footer_validation_passes_with_address(self) -> None:
        text = (
            "Stevie Ray's Tuesday Jam Tuesday June 30 2026 "
            "Featuring Lindsey Lane Band 9:30 pm "
            "230 East Main Street, Louisville, KY 40202"
        )
        issues = validate_required_footer_text(text, self.tuesday_jam, band="Lindsey Lane Band")
        self.assertEqual(issues, [])

    def test_footer_validation_fails_without_address(self) -> None:
        text = "Stevie Ray's Tuesday Jam Lindsey Lane Band June 30 2026"
        issues = validate_required_footer_text(text, self.tuesday_jam, band="Lindsey Lane Band")
        self.assertTrue(any("address" in issue.lower() for issue in issues))

    def test_footer_prompt_includes_address(self) -> None:
        lines = footer_prompt_lines(self.tuesday_jam, band="Lindsey Lane Band")
        joined = "\n".join(lines)
        self.assertIn("40202", joined)
        self.assertIn("grey", joined.lower())

    def test_halftone_unsafe_for_band_photo(self) -> None:
        from text_validation import halftone_unsafe_for_band_photo  # noqa: E402

        class Frame:
            halftone = True

        self.assertTrue(halftone_unsafe_for_band_photo(Frame()))
        self.assertFalse(halftone_unsafe_for_band_photo(type("F", (), {"halftone": False})()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
