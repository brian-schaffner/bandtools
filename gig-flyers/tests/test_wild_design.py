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
            {
                "WILD_DESIGN_ENABLED": "1",
                "WILD_ROUND_LAYOUT": "safe_plus_wild",
                "STRUCTURED_LAYOUT_OPTIONS": "A,B",
            },
            clear=False,
        ):
            self.assertEqual(round_option_letters(), ("A", "B", "D"))
            self.assertTrue(uses_structured_layout("A"))
            self.assertTrue(uses_structured_layout("B"))
            self.assertFalse(uses_structured_layout("D"))
            self.assertTrue(is_wild_option("D"))
            self.assertFalse(is_wild_option("C"))

    def test_three_canvas_round(self) -> None:
        from option_slots import wild_variation_for_letter, wild_variations

        with patch.dict(
            os.environ,
            {"WILD_DESIGN_ENABLED": "1", "WILD_ROUND_LAYOUT": "three_canvas"},
            clear=False,
        ):
            self.assertEqual(round_option_letters(), ("A", "B", "C"))
            self.assertFalse(uses_structured_layout("A"))
            self.assertTrue(is_wild_option("A"))
            self.assertTrue(is_wild_option("B"))
            self.assertTrue(is_wild_option("C"))
            tiers = [v["tier"] for v in wild_variations()]
            self.assertEqual(tiers, ["wild", "wild_medium", "wild_subtle"])
            self.assertEqual(wild_variation_for_letter("B")["generation_mode"], "full_canvas_wild_balanced")

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

        with patch.dict(
            os.environ,
            {"WILD_DESIGN_ENABLED": "1", "WILD_ROUND_LAYOUT": "safe_plus_wild"},
            clear=False,
        ):
            vars_ = select_round_variations(style, [], select_variations_fn=fake_select)
        self.assertEqual(len(vars_), 3)
        self.assertEqual(vars_[-1]["tier"], "wild")
        self.assertEqual(vars_[-1]["generation_mode"], "full_canvas_wild")

    def test_wild_composite_mode_from_env(self) -> None:
        from option_slots import wild_d_band_mode, wild_variation

        with patch.dict(os.environ, {"WILD_D_BAND_MODE": "composite"}, clear=False):
            self.assertEqual(wild_d_band_mode(), "composite")
            self.assertEqual(wild_variation()["generation_mode"], "wild_pil_composite")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WILD_D_BAND_MODE", None)
            self.assertEqual(wild_d_band_mode(), "full_canvas")
            self.assertEqual(wild_variation()["generation_mode"], "full_canvas_wild")


class WildDesignPromptTests(unittest.TestCase):
    def test_prompt_allows_face_distortion(self) -> None:
        event = GigEvent(
            event_date=__import__("datetime").date(2026, 7, 14),
            time_label="9pm",
            title="Test Band",
            venue="Blues Bar",
            suggested_name="Jul 14 Blues Bar",
        )
        prompt = build_wild_design_prompt({}, event, wild_variation(), 1, option_letter="A")
        self.assertIn("Face distortion", prompt)
        self.assertIn("full_canvas_wild", prompt)
        self.assertIn("COLOR LOCK", prompt)
        self.assertIn("FORBIDDEN: yellow", prompt)
        self.assertIn("Blues Bar", prompt)
        self.assertNotIn("match the reference EXACTLY", prompt)

    def test_prompt_palette_differs_by_option(self) -> None:
        from option_slots import wild_variation_for_letter

        event = GigEvent(
            event_date=__import__("datetime").date(2026, 7, 14),
            time_label="9pm",
            title="Test Band",
            venue="Two Lane Tavern",
            suggested_name="Jul 14",
        )
        a = build_wild_design_prompt({}, event, wild_variation_for_letter("A"), 1, option_letter="A")
        b = build_wild_design_prompt({}, event, wild_variation_for_letter("B"), 1, option_letter="B")
        self.assertIn("walnut", a.lower())
        self.assertIn("denim-blue", b.lower())
        self.assertNotEqual(a, b)

    def test_sanitize_research_drops_yellow_notes(self) -> None:
        from wild_design.palette import sanitize_research_notes

        notes = sanitize_research_notes(
            [
                "Legion hall utilitarian layout",
                "Warm mustard and cream paper tones",
            ]
        )
        self.assertEqual(notes, ["Legion hall utilitarian layout"])

    def test_prompt_intensity_tiers(self) -> None:
        from option_slots import wild_variation_for_letter

        event = GigEvent(
            event_date=__import__("datetime").date(2026, 7, 14),
            time_label="9pm",
            title="Test Band",
            venue="Blues Bar",
            suggested_name="Jul 14 Blues Bar",
        )
        bold = build_wild_design_prompt({}, event, wild_variation_for_letter("A"), 1, option_letter="A")
        refined = build_wild_design_prompt({}, event, wild_variation_for_letter("C"), 1, option_letter="C")
        self.assertIn("BOLD", bold)
        self.assertIn("REFINED", refined)
        self.assertIn("full_canvas_wild_refined", refined)
        self.assertIn("top-right corner", bold.lower())


class LogoOverlayTests(unittest.TestCase):
    def test_overlay_applies_logo(self) -> None:
        import tempfile
        from PIL import Image

        from wild_design.logo_overlay import overlay_flyer_logo

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flyer.png"
            Image.new("RGB", (1024, 1536), color=(40, 30, 20)).save(path)
            with patch.dict(os.environ, {"FLYER_LOGO_OVERLAY": "1"}, clear=False):
                self.assertTrue(overlay_flyer_logo(path, "Lindsey Lane Band"))
            before = Image.open(path).convert("RGB")
            # Logo overlay should change pixels in the badge zone
            region = before.crop((744, 28, 1000, 132))
            self.assertTrue(any(p != (40, 30, 20) for p in region.getdata()))


class WildBandReplaceTests(unittest.TestCase):
    def test_should_replace_on_d_fan_out(self) -> None:
        import tempfile
        from wild_design.band_replace import should_wild_band_replace

        with tempfile.NamedTemporaryFile(suffix=".png") as poster, tempfile.NamedTemporaryFile(suffix=".jpg") as band:
            with patch.dict(
                os.environ,
                {
                    "WILD_DESIGN_ENABLED": "1",
                    "WILD_ROUND_LAYOUT": "safe_plus_wild",
                    "WILD_BAND_REPLACE_ON_REVISE": "1",
                },
                clear=False,
            ):
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

    def test_band_replace_provider_defaults_openai(self) -> None:
        from wild_design.band_replace import resolve_band_replace_provider

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GIG_IMAGE_PROVIDER_D_BAND_REPLACE", None)
            os.environ.pop("GIG_IMAGE_PROVIDER_BAND_REPLACE", None)
            self.assertEqual(resolve_band_replace_provider("D"), "openai")

    def test_band_replace_provider_override(self) -> None:
        from wild_design.band_replace import resolve_band_replace_provider

        with patch.dict(
            os.environ,
            {"GIG_IMAGE_PROVIDER_D_BAND_REPLACE": "gemini"},
            clear=False,
        ):
            self.assertEqual(resolve_band_replace_provider("D"), "gemini")

    def test_auto_band_replace_after_gen(self) -> None:
        import tempfile
        from wild_design.band_replace import should_auto_wild_band_replace

        with tempfile.NamedTemporaryFile(suffix=".jpg") as band:
            env = {
                "WILD_DESIGN_ENABLED": "1",
                "WILD_ROUND_LAYOUT": "safe_plus_wild",
                "WILD_D_BAND_MODE": "full_canvas",
                "WILD_BAND_REPLACE_AFTER_GEN": "1",
                "STRUCTURED_LAYOUT_OPTIONS": "A,B",
            }
            with patch.dict(os.environ, env, clear=False):
                self.assertTrue(
                    should_auto_wild_band_replace(
                        letter="D",
                        reference_photo_path=Path(band.name),
                        fan_out_base=None,
                    )
                )
                self.assertFalse(
                    should_auto_wild_band_replace(
                        letter="D",
                        reference_photo_path=Path(band.name),
                        fan_out_base="D",
                    )
                )
                self.assertFalse(
                    should_auto_wild_band_replace(
                        letter="A",
                        reference_photo_path=Path(band.name),
                        fan_out_base=None,
                    )
                )

    def test_should_band_convert(self) -> None:
        import tempfile
        from wild_design.band_replace import should_wild_band_convert

        with tempfile.NamedTemporaryFile(suffix=".png") as poster, tempfile.NamedTemporaryFile(suffix=".jpg") as band:
            with patch.dict(
                os.environ,
                {"WILD_DESIGN_ENABLED": "1", "WILD_ROUND_LAYOUT": "three_canvas", "WILD_BAND_CONVERT_ENABLED": "1"},
                clear=False,
            ):
                self.assertTrue(
                    should_wild_band_convert(
                        letter="B",
                        prior_poster_path=Path(poster.name),
                        reference_photo_path=Path(band.name),
                    )
                )
                self.assertFalse(
                    should_wild_band_convert(
                        letter="B",
                        prior_poster_path=Path(poster.name),
                        reference_photo_path=None,
                    )
                )


if __name__ == "__main__":
    unittest.main()
