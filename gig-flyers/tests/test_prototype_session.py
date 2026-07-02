"""Tests for rapid prototype iteration loop."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design_explorer import enumerate_explore_specs  # noqa: E402
from preference_model import apply_feedback_text, apply_rankings_to_preferences  # noqa: E402
from prototype_session import (  # noqa: E402
    FEEDBACK_KEYWORDS,
    _base_spec_id,
    default_prototype_session,
    select_prototype_specs,
    submit_prototype_turn,
)


class PrototypeSessionTest(unittest.TestCase):
    def test_select_three_distinct_specs(self) -> None:
        specs = select_prototype_specs(
            "2026-07-04_american-legion",
            round_num=1,
            preferences={},
            used_spec_ids=[],
        )
        self.assertEqual(len(specs), 3)
        ids = {s.spec_id.split("-r")[0] if "-r" in s.spec_id else s.spec_id for s in specs}
        self.assertEqual(len(ids), 3)

    def test_feedback_boosts_duotone(self) -> None:
        weights = {"archetype": {}, "palette": {}, "accent": {}, "family": {}, "medium_variant": {}, "layers": {}}
        boosted = apply_feedback_text(weights, "love the duotone red handbill", FEEDBACK_KEYWORDS)
        self.assertGreater(boosted["archetype"].get("duotone_modern", 0), 0)
        self.assertGreater(boosted["palette"].get("red_cream", 0), 0)
        self.assertGreater(boosted["family"].get("B", 0), 0)

    def test_rankings_update_preferences(self) -> None:
        prefs = apply_rankings_to_preferences(
            {},
            [
                {
                    "rank": 1,
                    "tags": {"archetype": "duotone_modern", "palette": "red_cream", "family": "C"},
                },
                {
                    "rank": 3,
                    "tags": {"archetype": "xerox_punk", "family": "C"},
                },
            ],
        )
        self.assertGreater(
            prefs["global"]["archetype"]["duotone_modern"],
            prefs["global"]["archetype"].get("xerox_punk", 0),
        )

    def test_submit_forfeit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            with patch("state.STATE_PATH", state_path):
                from state import upsert_gig

                upsert_gig(
                    "test-gig",
                    prototype={
                        **default_prototype_session(),
                        "status": "active",
                        "round": 1,
                        "options": {"1": {"path_rel": "output/x.png", "tags": {}}},
                    },
                )
                result = submit_prototype_turn(
                    "test-gig",
                    rankings=[{"slot": "1", "rank": 1}],
                    feedback="not working",
                    action="forfeit",
                )
                self.assertEqual(result["status"], "forfeit")


    def test_rounds_avoid_repeat_signatures(self) -> None:
        history = [
            {
                "round": 1,
                "options": {
                    "1": {"tags": {"family": "C", "archetype": "duotone_modern", "palette": "red_cream", "accent": "starburst"}},
                    "2": {"tags": {"family": "B", "medium_variant": "paste_up", "accent": ""}},
                    "3": {"tags": {"family": "C", "archetype": "xerox_punk", "palette": "cream_black", "accent": "stamp"}},
                },
            }
        ]
        r2 = select_prototype_specs(
            "2026-07-04_american-legion",
            round_num=2,
            preferences={"global": {"archetype": {"duotone_modern": 10}}},
            used_spec_ids=["c-duotone_modern-red_cream", "b-paste_up", "c-xerox_punk-cream_black"],
            round_history=history,
        )
        r2_bases = {_base_spec_id(s.spec_id) for s in r2}
        self.assertNotIn("c-duotone_modern-red_cream", r2_bases)

    def test_pool_is_larger_than_before(self) -> None:
        pool = enumerate_explore_specs("test-gig", max_count=999)
        self.assertGreater(len(pool), 25)


class ExplorePoolTest(unittest.TestCase):
    def test_pool_has_abc_coverage(self) -> None:
        pool = enumerate_explore_specs("test-gig", max_count=999)
        families = {s.family for s in pool}
        self.assertIn("A", families)
        self.assertIn("B", families)
        self.assertIn("C", families)


if __name__ == "__main__":
    unittest.main()
