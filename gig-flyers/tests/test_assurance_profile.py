#!/usr/bin/env python3
"""Tests for staging-wild profile and assurance helpers."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.profiles import apply_gig_flyers_profile, profile_env  # noqa: E402
from assurance.fact_locks import build_fact_lock_prompt_block  # noqa: E402
from gig_calendar import GigEvent  # noqa: E402


class ProfileTests(unittest.TestCase):
    def test_staging_wild_bundle(self) -> None:
        env = profile_env("staging-wild")
        self.assertEqual(env["WILD_ROUND_LAYOUT"], "three_canvas")
        self.assertEqual(env["WILD_COLOR_CORRECT"], "1")
        self.assertEqual(env["ASSURANCE_ENABLED"], "1")

    def test_apply_profile_sets_defaults(self) -> None:
        with patch.dict(os.environ, {"GIG_FLYERS_PROFILE": "staging-wild"}, clear=False):
            os.environ.pop("WILD_DESIGN_ENABLED", None)
            apply_gig_flyers_profile()
            self.assertEqual(os.environ.get("WILD_DESIGN_ENABLED"), "1")


class FactLockTests(unittest.TestCase):
    def test_fact_lock_block_includes_band_name(self) -> None:
        event = GigEvent(
            event_date=__import__("datetime").date(2026, 6, 28),
            time_label="7:00 PM",
            title="Lindsey Lane Band",
            venue="Two Lane Tavern",
            suggested_name="Jun 28",
        )
        with patch.dict(os.environ, {"WILD_FACT_LOCKS": "1"}, clear=False):
            block = build_fact_lock_prompt_block(event, band="Lindsey Lane Band")
        self.assertIn("FACT LOCKS", block)
        self.assertIn("Lindsey Lane Band", block)
        self.assertIn("LINDSELY", block)

    def test_wild_prompt_includes_fact_locks(self) -> None:
        from option_slots import wild_variation_for_letter
        from wild_design.prompt import build_wild_design_prompt

        event = GigEvent(
            event_date=__import__("datetime").date(2026, 6, 28),
            time_label="7:00 PM",
            title="Lindsey Lane Band",
            venue="Two Lane Tavern",
            suggested_name="Jun 28",
        )
        with patch.dict(os.environ, {"WILD_FACT_LOCKS": "1"}, clear=False):
            prompt = build_wild_design_prompt(
                {},
                event,
                wild_variation_for_letter("A"),
                1,
                option_letter="A",
            )
        self.assertIn("FACT LOCKS", prompt)
        self.assertIn("Two Lane Tavern", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
