#!/usr/bin/env python3
"""Tests for Flyer Agent module."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from flyer_agent.agent import FlyerAgent  # noqa: E402
from flyer_agent.catalog import add_catalog_entry, load_design_catalog  # noqa: E402
from flyer_agent.gig_board import build_agent_gig_board, build_gig_detail  # noqa: E402
from flyer_agent.research_worker import load_design_research, run_design_research  # noqa: E402


def _sample_event() -> GigEvent:
    return GigEvent(
        event_date=date(2026, 7, 4),
        time_label="7:00 PM",
        title="Test Gig",
        venue="Test Venue",
        suggested_name="Test Venue — Jul 4",
    )


class FlyerAgentBoardTest(unittest.TestCase):
    def test_generation_source_labels(self) -> None:
        event = _sample_event()
        with patch("flyer_agent.gig_board.get_future_gigs", return_value=[event]):
            with patch("flyer_agent.gig_board.get_local_today", return_value=date(2026, 6, 23)):
                with patch("flyer_agent.gig_board.get_gig_state") as mock_state:
                    with patch("flyer_agent.gig_board.get_cache_info") as mock_cache:
                        mock_cache.return_value = MagicMock(
                            fetched_at="2026-06-23",
                            is_stale=False,
                            source="live",
                            age_seconds=0,
                        )
                        mock_state.return_value = {
                            "status": "pending_review",
                            "round": 1,
                            "options": {"A": "output/x.png"},
                            "generation_source": "auto",
                        }
                        board = build_agent_gig_board(max_days=60)
                        self.assertEqual(board["count"], 1)
                        gig = board["gigs"][0]
                        self.assertEqual(gig["generation_source"], "background")
                        self.assertEqual(gig["generation_source_label"], "Background generated")

    def test_build_gig_detail_missing(self) -> None:
        with patch("gig_resolve.resolve_gig_event", side_effect=ValueError("missing")):
            self.assertIsNone(build_gig_detail("missing-gig"))


class FlyerAgentCatalogTest(unittest.TestCase):
    def test_catalog_has_defaults(self) -> None:
        entries = load_design_catalog(limit=5)
        self.assertGreaterEqual(len(entries), 1)

    def test_add_catalog_entry(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_path = Path(tmpdir) / "good_designs.json"
            with patch("flyer_agent.catalog.CATALOG_PATH", catalog_path):
                entry = add_catalog_entry(
                    title="Test Design",
                    tags=["test"],
                    notes="A strong handbill layout.",
                )
                self.assertEqual(entry["title"], "Test Design")
                loaded = load_design_catalog(limit=10)
                self.assertTrue(any(e["id"] == entry["id"] for e in loaded))


class FlyerAgentResearchTest(unittest.TestCase):
    def test_research_has_defaults(self) -> None:
        findings = load_design_research(limit=5)
        self.assertGreaterEqual(len(findings), 1)

    def test_run_design_research(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "design_research.json"
            with patch("flyer_agent.research_worker.RESEARCH_CACHE_PATH", cache_path):
                with patch("gig_calendar.get_future_gigs", return_value=[]):
                    result = run_design_research(use_llm=False)
                    self.assertIn("total", result)
                    self.assertGreater(result["total"], 0)


class FlyerAgentRecommendTest(unittest.TestCase):
    def test_recommend_generate_for_new_gig(self) -> None:
        agent = FlyerAgent()
        with patch.object(agent, "gig_detail") as mock_detail:
            mock_detail.return_value = {
                "can_generate": True,
                "can_revise": False,
                "can_regenerate": False,
                "workflow": "new",
            }
            rec = agent.recommend_action("test-gig")
            self.assertEqual(rec["action"], "generate")

    def test_layout_expertise_summary_loads_style_yaml(self) -> None:
        from flyer_agent.context import layout_expertise_summary

        summary = layout_expertise_summary()
        self.assertIsInstance(summary["reference_models"], list)
        self.assertGreater(len(summary["reference_models"]), 0)
        self.assertIsInstance(summary["anti_patterns"], list)


if __name__ == "__main__":
    unittest.main()
