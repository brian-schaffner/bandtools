#!/usr/bin/env python3
"""Tests for Flyer Agent workspace UI and chat."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_agent.chat import agent_chat_reply  # noqa: E402
from flyer_agent.ui import render_agent_workspace  # noqa: E402


class AgentWorkspaceUiTest(unittest.TestCase):
    def test_workspace_layout_regions(self) -> None:
        html = render_agent_workspace(
            user={"name": "Brian", "email": "b@example.com"},
            board={"gigs": [], "count": 0, "today": "2026-07-03"},
            selected_gig_id=None,
            detail=None,
        )
        self.assertIn("agent-sidebar", html)
        self.assertIn("agent-gig-meta", html)
        self.assertIn("agent-posters-panel", html)
        self.assertIn("agent-chat-panel", html)
        self.assertIn("agent-chat-log", html)

    def test_workspace_shows_selected_gig(self) -> None:
        detail = {
            "gig_id": "2026-07-04_test-venue",
            "event": {"venue": "Test Venue", "short_date": "Jul 04", "time": "7 PM", "title": "Gig"},
            "generation_source": "none",
            "generation_source_label": "No flyers yet",
            "workflow_label": "New",
            "round": 0,
            "flyers": [],
            "research": {},
            "can_generate": True,
        }
        html = render_agent_workspace(
            user={"name": "Brian"},
            board={
                "gigs": [{"gig_id": "2026-07-04_test-venue", "venue": "Test Venue", "short_date": "Jul 04",
                          "generation_source": "none", "generation_source_label": "No flyers yet",
                          "workflow_label": "New"}],
                "count": 1,
                "today": "2026-07-03",
            },
            selected_gig_id="2026-07-04_test-venue",
            detail=detail,
            recommendation={"message": "Generate options"},
        )
        self.assertIn("Test Venue", html)
        self.assertIn('class="active"', html)
        self.assertIn("Generate 3 options", html)


class AgentChatTest(unittest.TestCase):
    def test_chat_without_gig(self) -> None:
        result = agent_chat_reply("hello")
        self.assertIn("sidebar", result["reply"].lower())

    def test_chat_generate_intent(self) -> None:
        agent = MagicMock()
        agent.gig_detail.return_value = {
            "event": {"venue": "Two Lane Tavern"},
            "can_generate": True,
            "can_regenerate": False,
            "can_revise": False,
            "flyers": [],
            "research": {},
        }
        agent.recommend_action.return_value = {"message": "Ready"}
        result = agent_chat_reply("please generate posters", gig_id="gig-1", agent=agent)
        self.assertEqual(result["execution"]["type"], "generate")
        self.assertIn("generating", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
