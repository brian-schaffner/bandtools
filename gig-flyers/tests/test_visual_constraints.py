"""Tests for visual constraints, evaluation card, and AI predict pipeline."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from evaluation_card import build_evaluation_card  # noqa: E402
from visual_constraints import (  # noqa: E402
    HATCH_CONSTRAINTS,
    hatch_predict_prompt_block,
    validate_layout_constraints,
)


def _event(**kwargs) -> GigEvent:
    defaults = dict(
        event_date=date(2026, 7, 4),
        time_label="6:30 PM",
        title="Live Music",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )
    defaults.update(kwargs)
    return GigEvent(**defaults)


class VisualConstraintsTest(unittest.TestCase):
    def test_hatch_constraints_defined(self) -> None:
        self.assertEqual(HATCH_CONSTRAINTS.study_id, "hatch_hank_williams_1953")
        self.assertEqual(HATCH_CONSTRAINTS.medium_variant, "hatch_stack")
        self.assertIn("venue", HATCH_CONSTRAINTS.stack_order)
        self.assertIn("band", HATCH_CONSTRAINTS.stack_order)

    def test_hatch_stack_passes_constraints(self) -> None:
        from structured_layout.fixed_templates import create_handbill_layout
        from structured_layout.tier_archetypes import load_tier_archetype

        event = _event()
        arch = load_tier_archetype("medium", event=event, research={"venue_type": "member_club"})
        layout = create_handbill_layout(
            event.venue,
            "Lindsey Lane Band",
            "Saturday, July 4, 2026",
            "6:30 PM",
            event=event,
            archetype=arch,
            rng=__import__("random").Random(7),
            medium_variant="hatch_stack",
        )
        report = validate_layout_constraints(
            layout,
            HATCH_CONSTRAINTS,
            venue=event.venue,
            band="Lindsey Lane Band",
        )
        failed = [c for c in report.checks if not c.passed]
        self.assertTrue(
            report.passed,
            msg=f"Failed checks: {[f'{c.id}: {c.detail}' for c in failed]}",
        )

    def test_predict_prompt_includes_facts(self) -> None:
        block = hatch_predict_prompt_block(
            venue="American Legion Post 15",
            date="Saturday, July 4, 2026",
            time="6:30 PM",
            band="Lindsey Lane Band",
        )
        self.assertIn("American Legion Post 15", block)
        self.assertIn("LINDSEY LANE BAND", block.upper())
        self.assertIn("Hatch Show Print", block)


class EvaluationCardTest(unittest.TestCase):
    def test_builds_three_panel_card(self) -> None:
        study_img = ROOT / "cache" / "visual_studies" / "hank_hatch.jpg"
        if not study_img.is_file():
            self.skipTest("reference image not cached")

        with tempfile.TemporaryDirectory() as tmp:
            gen = Path(tmp) / "gen.png"
            Image.new("RGB", (1024, 1536), (245, 235, 220)).save(gen)
            out = Path(tmp) / "card.png"
            meta = build_evaluation_card(
                reference_path=study_img,
                generated_path=gen,
                output_path=out,
                study_title="Hatch test",
                method="test",
                constraint_report=None,
            )
            self.assertTrue(out.is_file())
            self.assertEqual(meta["width"], 1024 * 3)


class VisualPredictFlyerTest(unittest.TestCase):
    def test_dry_run_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "output"
            study_img = ROOT / "cache" / "visual_studies" / "hank_hatch.jpg"
            if not study_img.is_file():
                self.skipTest("reference image not cached")

            with patch("visual_predict_flyer.gig_output_dir", return_value=out_root / "gig"):
                with patch("output_paths.get_output_dir", return_value=out_root):
                    with patch("visual_predict_flyer.research_gig", return_value={"venue_type": "member_club"}):
                        with patch("visual_predict_flyer.resolve_gig_event", return_value=_event()):
                            with patch(
                                "visual_predict_flyer.select_band_photo",
                                return_value={"path": "bandphotos/x.jpg"},
                            ):
                                with patch("visual_predict_flyer.ROOT", ROOT):
                                    from visual_predict_flyer import predict_visual_flyer

                                    manifest = predict_visual_flyer(
                                        "2026-07-04_american-legion-post-15",
                                        dry_run=True,
                                    )
        self.assertEqual(manifest["method"], "ai_visual_predict")
        self.assertIn("evaluation_card_rel", manifest)
        self.assertTrue(manifest["path_rel"].startswith("output/"))


if __name__ == "__main__":
    unittest.main()
