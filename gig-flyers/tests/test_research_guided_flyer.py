"""Tests for flyer design research corpus and guided generator."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_design_research import (  # noqa: E402
    build_design_brief,
    corpus_summary,
    recommend_styles,
    sample_count,
)
from gig_calendar import GigEvent  # noqa: E402


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


class FlyerDesignResearchTest(unittest.TestCase):
    def test_corpus_size_in_range(self) -> None:
        count = sample_count()
        self.assertGreaterEqual(count, 10)
        self.assertLessEqual(count, 50)

    def test_legion_venue_prefers_handbill_or_minimal(self) -> None:
        research = {
            "venue_type": "member_club",
            "design_language": "legion_community",
        }
        styles = recommend_styles(research, limit=3)
        self.assertIn(styles[0], {"letterpress_handbill", "minimalist_swiss", "type_only"})

    def test_brief_includes_references(self) -> None:
        brief = build_design_brief(_event(), {"venue_type": "regional_bar"})
        self.assertTrue(brief.reference_ids)
        self.assertIn(brief.option_letter, {"A", "B", "C"})
        self.assertTrue(brief.hierarchy_notes)

    def test_corpus_summary(self) -> None:
        summary = corpus_summary()
        self.assertGreaterEqual(summary["principle_count"], 10)
        self.assertGreaterEqual(summary["sample_count"], 10)


class ResearchGuidedFlyerTest(unittest.TestCase):
    def test_dry_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "output"
            with patch("research_guided_flyer.gig_output_dir", return_value=out_root / "gig"):
                with patch("output_paths.get_output_dir", return_value=out_root):
                    with patch("research_guided_flyer.research_gig", return_value={"venue_type": "member_club"}):
                        with patch("research_guided_flyer.resolve_gig_event", return_value=_event()):
                            with patch("research_guided_flyer.select_band_photo", return_value=None):
                                from research_guided_flyer import generate_research_guided_flyer

                                manifest = generate_research_guided_flyer(
                                    "2026-07-04_american-legion-post-15",
                                    dry_run=True,
                                )
        self.assertIn("brief", manifest)
        self.assertIn("path_rel", manifest)
        self.assertTrue(manifest["path_rel"].startswith("output/"))


if __name__ == "__main__":
    unittest.main()
