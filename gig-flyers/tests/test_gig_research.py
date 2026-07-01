#!/usr/bin/env python3
"""Tests for gig research and band photo selection."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from gig_research import detect_holiday_context, research_gig  # noqa: E402
from photo_selector import bandphotos_dir, list_band_photos, select_band_photo  # noqa: E402


class GigResearchTest(unittest.TestCase):
    def test_july_fourth_holiday(self) -> None:
        ctx = detect_holiday_context(date(2026, 7, 4))
        self.assertEqual(ctx["holiday"], "Independence Day")
        self.assertTrue(ctx["is_holiday_weekend"])

    def test_stevie_rays_blues_bar_research(self) -> None:
        event = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="7:30 pm",
            title="Hosting Stevie Ray's World Famous Tuesday Jam",
            venue="Stevie Ray's Tuesday Jam",
            suggested_name="Jul 14 Stevie Ray's Tuesday Jam",
        )
        research = research_gig(event, use_llm=False)
        self.assertEqual(research["venue_type"], "blues_bar")
        self.assertEqual(research["design_language"], "blues_club_handbill")
        self.assertIn("blues", " ".join(research["design_notes"]).lower())

    def test_vfw_venue_type(self) -> None:
        event = GigEvent(
            event_date=date(2026, 7, 18),
            time_label="7:30 pm",
            title="Lindsey Lane Band at VFW Post 1170",
            venue="VFW Post 1170",
            suggested_name="Jul 18 VFW Post 1170",
        )
        research = research_gig(event, use_llm=False)
        self.assertEqual(research["venue_type"], "member_club")


class PhotoSelectorTest(unittest.TestCase):
    def test_bandphotos_dir(self) -> None:
        self.assertEqual(bandphotos_dir(), ROOT / "bandphotos")

    def test_lists_three_photos(self) -> None:
        photos = list_band_photos()
        self.assertEqual(len(photos), 3)
        ids = {p.id for p in photos}
        self.assertEqual(ids, {"instruments", "group_standing", "group_energetic"})

    def test_stevie_rays_picks_instruments(self) -> None:
        event = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="7:30 pm",
            title="Hosting Stevie Ray's World Famous Tuesday Jam",
            venue="Stevie Ray's Tuesday Jam",
            suggested_name="Jul 14 Stevie Ray's Tuesday Jam",
        )
        research = research_gig(event, use_llm=False)
        selected = select_band_photo(event, research)
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "instruments")
        self.assertTrue(str(selected["path"]).startswith("bandphotos/"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
