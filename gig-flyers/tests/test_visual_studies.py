"""Tests for visual poster studies and visual-guided generator."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from visual_studies import (  # noqa: E402
    VISUAL_STUDIES,
    get_study,
    pick_study_for_research,
)
from visual_guided_flyer import build_visual_brief  # noqa: E402


def _event(**kwargs) -> GigEvent:
    defaults = dict(
        event_date=date(2026, 7, 4),
        time_label="7:00 PM",
        title="Live Music",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )
    defaults.update(kwargs)
    return GigEvent(**defaults)


class VisualStudiesTest(unittest.TestCase):
    def test_three_real_studies_defined(self) -> None:
        self.assertEqual(len(VISUAL_STUDIES), 3)
        ids = {s.id for s in VISUAL_STUDIES}
        self.assertEqual(
            ids,
            {
                "hatch_hank_williams_1953",
                "altamont_free_concert_1969",
                "woodstock_festival_1969",
            },
        )

    def test_study_has_observations_and_rules(self) -> None:
        hatch = get_study("hatch_hank_williams_1953")
        assert hatch is not None
        self.assertGreaterEqual(len(hatch.observations), 5)
        self.assertGreaterEqual(len(hatch.layout_rules), 4)
        self.assertEqual(hatch.medium_variant, "hatch_stack")

    def test_legion_picks_hatch_study(self) -> None:
        study = pick_study_for_research({"venue_type": "member_club"})
        self.assertEqual(study.id, "hatch_hank_williams_1953")

    def test_blues_bar_picks_altamont(self) -> None:
        study = pick_study_for_research({"venue_type": "blues_bar"})
        self.assertEqual(study.id, "altamont_free_concert_1969")

    def test_festival_picks_woodstock(self) -> None:
        study = pick_study_for_research({"venue_type": "festival"})
        self.assertEqual(study.id, "woodstock_festival_1969")


class VisualDesignBriefTest(unittest.TestCase):
    def test_legion_brief_uses_hatch_stack(self) -> None:
        brief, study = build_visual_brief(_event(), {"venue_type": "member_club"})
        self.assertEqual(brief.study_id, "hatch_hank_williams_1953")
        self.assertEqual(brief.medium_variant, "hatch_stack")
        self.assertEqual(brief.option_letter, "B")
        self.assertIn("venue", brief.guidance[1].lower())

    def test_blues_brief_uses_altamont_sidebar(self) -> None:
        brief, _ = build_visual_brief(
            _event(venue="Stevie Ray's Blues Bar"),
            {"venue_type": "blues_bar"},
        )
        self.assertEqual(brief.medium_variant, "altamont_sidebar")


class VisualStudyLayoutTest(unittest.TestCase):
    def test_hatch_stack_venue_above_band(self) -> None:
        from structured_layout.fixed_templates import create_handbill_layout
        from structured_layout.tier_archetypes import load_tier_archetype

        event = _event()
        arch = load_tier_archetype("medium", event=event, research={"venue_type": "member_club"})
        layout = create_handbill_layout(
            event.venue,
            "Lindsey Lane Band",
            "Friday, July 4, 2026",
            "7:00 PM",
            event=event,
            archetype=arch,
            rng=__import__("random").Random(7),
            medium_variant="hatch_stack",
        )
        self.assertIn("hatch_stack", layout.style_notes.lower())
        venue_el = next(t for t in layout.text_elements if "LEGION" in t.content.upper())
        band_el = next(t for t in layout.text_elements if "LINDSEY" in t.content.upper())
        self.assertLess(venue_el.y, band_el.y, "Hatch study: venue must sit above band name")
        self.assertGreater(band_el.font_size, venue_el.font_size, "Band name should be largest type")

    def test_altamont_sidebar_has_guest_column(self) -> None:
        from structured_layout.fixed_templates import create_handbill_layout
        from structured_layout.tier_archetypes import load_tier_archetype

        event = _event(venue="Stevie Ray's Blues Bar")
        arch = load_tier_archetype("medium", event=event, research={"venue_type": "blues_bar"})
        layout = create_handbill_layout(
            event.venue,
            "Lindsey Lane Band",
            "Tuesday, July 14, 2026",
            "8:00 PM",
            event=event,
            archetype=arch,
            rng=__import__("random").Random(3),
            medium_variant="altamont_sidebar",
        )
        combined = " ".join(t.content for t in layout.text_elements)
        self.assertIn("SPECIAL", combined)
        self.assertIn("GUESTS", combined)
        sidebar = next(t for t in layout.text_elements if "SPECIAL" in t.content)
        headliner = next(t for t in layout.text_elements if "LINDSEY" in t.content.upper())
        self.assertGreater(sidebar.x, headliner.x, "Sidebar should sit right of main column")


class VisualGuidedFlyerTest(unittest.TestCase):
    def test_dry_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "output"
            with patch("visual_guided_flyer.gig_output_dir", return_value=out_root / "gig"):
                with patch("output_paths.get_output_dir", return_value=out_root):
                    with patch("visual_guided_flyer.research_gig", return_value={"venue_type": "member_club"}):
                        with patch("visual_guided_flyer.resolve_gig_event", return_value=_event()):
                            with patch("visual_guided_flyer.select_band_photo", return_value=None):
                                from visual_guided_flyer import generate_visual_guided_flyer

                                manifest = generate_visual_guided_flyer(
                                    "2026-07-04_american-legion-post-15",
                                    dry_run=True,
                                )
        self.assertEqual(manifest["brief"]["study_id"], "hatch_hank_williams_1953")
        self.assertIn("study_guidance", manifest)
        self.assertTrue(manifest["path_rel"].startswith("output/"))


if __name__ == "__main__":
    unittest.main()
