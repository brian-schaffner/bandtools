"""Tests for wild design option slots and prompts."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from option_slots import (  # noqa: E402
    is_wild_option,
    round_option_letters,
    select_round_variations,
    uses_structured_layout,
    wild_variation,
)
from wild_design.prompt import build_wild_design_prompt  # noqa: E402


class WildDesignSlotsTests(unittest.TestCase):
    def test_classic_round_when_disabled(self) -> None:
        with patch.dict(os.environ, {"WILD_DESIGN_ENABLED": "0"}, clear=False):
            self.assertEqual(round_option_letters(), ("A", "B", "C"))
            self.assertTrue(uses_structured_layout("C"))

    def test_wild_round_when_enabled(self) -> None:
        with patch.dict(
            os.environ,
            {"WILD_DESIGN_ENABLED": "1", "STRUCTURED_LAYOUT_OPTIONS": "A,B"},
            clear=False,
        ):
            self.assertEqual(round_option_letters(), ("A", "B", "D"))
            self.assertTrue(uses_structured_layout("A"))
            self.assertTrue(uses_structured_layout("B"))
            self.assertFalse(uses_structured_layout("D"))
            self.assertTrue(is_wild_option("D"))
            self.assertFalse(is_wild_option("C"))

    def test_select_round_variations_includes_wild(self) -> None:
        style = {
            "variations": [
                {"id": "conservative", "tier": "conservative"},
                {"id": "medium", "tier": "medium"},
                {"id": "creative", "tier": "creative"},
            ]
        }

        def fake_select(style_obj, count, used):
            tiers = style_obj["variations"]
            return tiers[:count]

        with patch.dict(os.environ, {"WILD_DESIGN_ENABLED": "1"}, clear=False):
            vars_ = select_round_variations(style, [], select_variations_fn=fake_select)
        self.assertEqual(len(vars_), 3)
        self.assertEqual(vars_[-1]["tier"], "wild")
        self.assertEqual(vars_[-1]["generation_mode"], "wild_pil_composite")

    def test_wild_composite_mode_from_env(self) -> None:
        from option_slots import wild_d_band_mode, wild_variation

        with patch.dict(os.environ, {"WILD_D_BAND_MODE": "full_canvas"}, clear=False):
            self.assertEqual(wild_d_band_mode(), "full_canvas")
            self.assertEqual(wild_variation()["generation_mode"], "full_canvas_wild")
        with patch.dict(os.environ, {"WILD_D_BAND_MODE": "composite"}, clear=False):
            self.assertEqual(wild_variation()["generation_mode"], "wild_pil_composite")


class WildDesignPromptTests(unittest.TestCase):
    def test_prompt_allows_face_distortion(self) -> None:
        event = GigEvent(
            event_date=__import__("datetime").date(2026, 7, 14),
            time_label="9pm",
            title="Test Band",
            venue="Blues Bar",
            suggested_name="Jul 14 Blues Bar",
        )
        prompt = build_wild_design_prompt({}, event, wild_variation(), 1)
        self.assertIn("Face distortion", prompt)
        self.assertIn("full_canvas_wild", prompt)
        self.assertIn("Blues Bar", prompt)
        self.assertNotIn("match the reference EXACTLY", prompt)


class WildBandReplaceTests(unittest.TestCase):
    def test_should_replace_on_d_fan_out(self) -> None:
        import tempfile
        from wild_design.band_replace import should_wild_band_replace

        with tempfile.NamedTemporaryFile(suffix=".png") as poster, tempfile.NamedTemporaryFile(suffix=".jpg") as band:
            with patch.dict(os.environ, {"WILD_DESIGN_ENABLED": "1", "WILD_BAND_REPLACE_ON_REVISE": "1"}, clear=False):
                self.assertTrue(
                    should_wild_band_replace(
                        fan_out_base="D",
                        prior_poster_path=Path(poster.name),
                        reference_photo_path=Path(band.name),
                    )
                )
                self.assertFalse(
                    should_wild_band_replace(
                        fan_out_base="A",
                        prior_poster_path=Path(poster.name),
                        reference_photo_path=Path(band.name),
                    )
                )

    def test_band_replace_prompt(self) -> None:
        from wild_design.band_replace import build_wild_band_replace_prompt

        event = GigEvent(
            event_date=__import__("datetime").date(2026, 7, 14),
            time_label="9pm",
            title="Test Band",
            venue="Blues Bar",
            suggested_name="Jul 14 Blues Bar",
        )
        prompt = build_wild_band_replace_prompt(event, feedback="more neon accents")
        self.assertIn("wild_band_replace", prompt)
        self.assertIn("IMAGE 1", prompt)
        self.assertIn("Reference band photo", prompt)
        self.assertIn("more neon accents", prompt)


if __name__ == "__main__":
    unittest.main()
