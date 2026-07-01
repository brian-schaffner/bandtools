#!/usr/bin/env python3
"""Tests for prompt diversity across options and revision rounds."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_generator import (  # noqa: E402
    _image_quality_for_tier,
    _variation_seed,
    build_prompt,
    generate_for_gig,
    load_style,
)
from gig_calendar import GigEvent


def _sample_event() -> GigEvent:
    return GigEvent(
        event_date=date(2026, 7, 14),
        time_label="8:00 pm",
        title="Lindsey Lane Band at Stevie Ray's Blues Bar",
        venue="Stevie Ray's Blues Bar",
        suggested_name="Jul 14 Stevie Ray's Blues Bar",
    )


def _sample_research() -> dict:
    return {
        "venue_type": "blues_bar",
        "design_language": "blues_club_handbill",
        "demographics": ["blues_fans", "30_to_60"],
        "design_notes": ["moody_but_readable", "no_neon_cliches"],
        "venue_bias": ["venue_first"],
    }


def _word_set(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-z0-9']+", text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


class PromptDiversityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.style = load_style()
        self.event = _sample_event()
        self.research = _sample_research()
        self.variations = self.style["variations"][:3]
        self.tiers = [v["tier"] for v in self.variations]

    def _prompts_for_round(
        self,
        feedback: Optional[str] = None,
        prior: Optional[str] = None,
        *,
        selected_photo: Optional[dict] = None,
    ) -> dict[str, str]:
        photo = selected_photo or {
            "member_count": 4,
            "description": "Four-piece band group photo",
            "filename": "band.jpg",
        }
        prompts: dict[str, str] = {}
        for letter, variation in zip(("A", "B", "C"), self.variations):
            prompts[letter] = build_prompt(
                self.style,
                self.event,
                variation,
                round_num=2,
                feedback=feedback,
                prior_prompt=prior if letter == "B" else None,
                sibling_variations=self.variations,
                research=self.research,
                selected_photo=photo,
                option_letter=letter,
            )
        return prompts

    def test_variations_are_creativity_spectrum(self) -> None:
        self.assertEqual(self.tiers, ["conservative", "medium", "creative"])
        ids = [v["id"] for v in self.variations]
        self.assertEqual(ids, ["conservative", "medium", "creative"])

    def test_variation_prompts_include_creativity_blocks(self) -> None:
        prompts = self._prompts_for_round()
        for letter, variation in zip(("A", "B", "C"), self.variations):
            prompt = prompts[letter]
            self.assertIn("CREATIVITY TIER", prompt)
            self.assertIn("Creative freedom level", prompt)
            self.assertIn(variation["label"], prompt)
            self.assertIn("Creative freedom level", prompt)
            self.assertIn("LAYOUT STRUCTURE", prompt)
            self.assertIn("NEGATIVE CONSTRAINTS", prompt)

    def test_creative_freedom_scales_across_abc(self) -> None:
        prompts = self._prompts_for_round()
        self.assertIn("Creative freedom level: low", prompts["A"])
        self.assertIn("Creative freedom level: medium", prompts["B"])
        self.assertIn("Creative freedom level: high", prompts["C"])
        self.assertIn("Risk-taking: minimal", prompts["A"])
        self.assertIn("Risk-taking: higher", prompts["C"])

    def test_tier_specific_layout_keywords(self) -> None:
        prompts = self._prompts_for_round()
        self.assertRegex(prompts["A"].lower(), r"black-and-white|one ink")
        self.assertIn("single column", prompts["A"].lower())
        self.assertIn("accent", prompts["B"].lower())
        self.assertRegex(prompts["B"].lower(), r"asymmetr|paste-up|offset")
        self.assertRegex(prompts["C"].lower(), r"ticket|torn|diagonal|collage")

    def test_all_tiers_include_band_photo_fidelity(self) -> None:
        prompts = self._prompts_for_round()
        for letter in ("A", "B", "C"):
            prompt = prompts[letter]
            self.assertIn("BAND PHOTO FIDELITY", prompt, letter)
            self.assertIn("PHOTO-ON-CANVAS INPUT MODE", prompt, letter)
            self.assertIn("already on the canvas", prompt.lower(), letter)
            self.assertIn("no warping", prompt.lower(), letter)
            self.assertNotIn("slight inset crop", prompt.lower(), letter)
            self.assertNotIn("tighter dynamic crop", prompt.lower(), letter)

    def test_creative_does_not_allow_photo_crop(self) -> None:
        prompt = self._prompts_for_round()["C"]
        self.assertNotIn("photo_crop", prompt.lower())
        self.assertIn("never redraw or regenerate the reference photo", prompt.lower())

    def test_variation_seed_unique_per_option(self) -> None:
        prompts = self._prompts_for_round()
        seeds = [line for line in prompts["A"].splitlines() if line.startswith("Variation seed:")]
        self.assertEqual(len(seeds), 1)
        self.assertNotEqual(
            _variation_seed(self.event.gig_id, "A", 2),
            _variation_seed(self.event.gig_id, "B", 2),
        )
        for letter in ("A", "B", "C"):
            expected = _variation_seed(self.event.gig_id, letter, 2)
            self.assertIn(f"Variation seed: {expected}", prompts[letter])

    def test_abc_prompts_are_distinct(self) -> None:
        prompts = self._prompts_for_round()
        pairs = [("A", "B"), ("A", "C"), ("B", "C")]
        for left, right in pairs:
            overlap = _jaccard(_word_set(prompts[left]), _word_set(prompts[right]))
            self.assertLess(
                overlap,
                0.90,
                f"Prompts {left}/{right} too similar (Jaccard={overlap:.3f})",
            )
        self.assertNotEqual(prompts["A"], prompts["B"])
        self.assertNotEqual(prompts["B"], prompts["C"])

    def test_sibling_differentiation_reflects_spectrum(self) -> None:
        prompt = self._prompts_for_round()["A"]
        self.assertIn("SIBLING OPTIONS IN THIS ROUND", prompt)
        self.assertIn("must look distinctly different", prompt.lower())
        self.assertIn("Option B", prompt)
        self.assertIn("Option C", prompt)

    def test_tier_image_quality_defaults(self) -> None:
        self.assertEqual(_image_quality_for_tier("conservative"), "medium")
        self.assertEqual(_image_quality_for_tier("creative"), "high")
        self.assertEqual(_image_quality_for_tier("conservative", use_reference=True), "high")

    def test_revision_puts_feedback_first(self) -> None:
        feedback = "make it pink and purple like a concert ticket stub"
        prior = self._prompts_for_round()["B"]
        revised = build_prompt(
            self.style,
            self.event,
            self.variations[1],
            round_num=3,
            feedback=feedback,
            prior_prompt=prior,
            sibling_variations=self.variations,
            research=self.research,
            option_letter="B",
        )
        self.assertTrue(revised.startswith("=== PRIMARY DIRECTIVE"))
        self.assertLess(revised.index(feedback), revised.index("EVENT DETAILS"))
        self.assertIn("Dramatically redesign", revised)
        self.assertIn("ANTI-REPETITION", revised)

    def test_revision_feedback_overrides_style_conflict_note(self) -> None:
        revised = build_prompt(
            self.style,
            self.event,
            self.variations[0],
            round_num=3,
            feedback="make it pink and purple",
            prior_prompt="old prompt with layout",
            sibling_variations=self.variations,
            research=self.research,
            option_letter="A",
        )
        self.assertIn("PRIMARY DIRECTIVE", revised)
        self.assertIn("conflicts with default style rules", revised)

    def test_manifest_includes_full_prompts(self) -> None:
        event = _sample_event()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("flyer_generator.find_gig_by_id", return_value=event):
                with patch("flyer_generator.ROOT", tmp_path):
                    with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                        with patch("state.STATE_PATH", tmp_path / "state.json"):
                            with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                                manifest = generate_for_gig(
                                    event.gig_id,
                                    count=3,
                                    dry_run=True,
                                    feedback="concert ticket stub",
                                    base_option="B",
                                )
            self.assertIn("prompts", manifest)
            self.assertEqual(len(manifest["prompts"]), 3)
            for letter, prompt in manifest["prompts"].items():
                self.assertIn("PRIMARY DIRECTIVE", prompt, letter)
                self.assertIn("CREATIVITY TIER", prompt, letter)
                self.assertIn("LAYOUT STRUCTURE", prompt, letter)
                self.assertGreater(len(prompt), 500, letter)
            manifest_path = tmp_path / manifest["output_dir"] / f"manifest_r{manifest['round']}.json"
            saved = manifest_path.read_text(encoding="utf-8")
            self.assertIn('"prompts"', saved)
            self.assertIn("concert ticket stub", saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
