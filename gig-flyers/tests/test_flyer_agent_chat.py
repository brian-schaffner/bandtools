#!/usr/bin/env python3
"""Tests for Flyer Agent chat intent parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_agent.chat import agent_chat_reply  # noqa: E402
from flyer_agent.intent import parse_chat_intent  # noqa: E402


def _revise_detail() -> dict:
    return {
        "event": {"venue": "Two Lane Tavern", "short_date": "Jul 04", "time": "7 PM"},
        "can_generate": False,
        "can_regenerate": False,
        "can_revise": True,
        "round": 1,
        "flyers": [{"option": "A"}, {"option": "B"}, {"option": "C"}],
        "research": {},
        "workflow_label": "Pending review",
    }


class ChatIntentParseTest(unittest.TestCase):
    def test_parse_revise_option_with_em_dash(self) -> None:
        intent = parse_chat_intent(
            "revise option A — larger font, more vibrant colors",
            detail=_revise_detail(),
        )
        self.assertEqual(intent.kind, "revise")
        self.assertEqual(intent.option, "A")
        self.assertIn("larger font", intent.feedback or "")

    def test_parse_revise_option_with_colon(self) -> None:
        intent = parse_chat_intent(
            "Revise option B: warmer mustard background",
            detail=_revise_detail(),
        )
        self.assertEqual(intent.kind, "revise")
        self.assertEqual(intent.option, "B")
        self.assertIn("mustard", intent.feedback or "")

    def test_revise_without_option_is_incomplete(self) -> None:
        intent = parse_chat_intent("please revise", detail=_revise_detail())
        self.assertEqual(intent.kind, "revise_incomplete")

    def test_generate_intent(self) -> None:
        detail = {**_revise_detail(), "can_generate": True, "can_revise": False, "flyers": []}
        intent = parse_chat_intent("generate posters", detail=detail)
        self.assertEqual(intent.kind, "generate")

    def test_regenerate_intent(self) -> None:
        detail = {**_revise_detail(), "can_regenerate": True}
        intent = parse_chat_intent("regenerate fresh round", detail=detail)
        self.assertEqual(intent.kind, "regenerate")


class ChatExecutionReplyTest(unittest.TestCase):
    def test_revise_message_returns_execution(self) -> None:
        agent = MagicMock()
        agent.gig_detail.return_value = _revise_detail()
        agent.recommend_action.return_value = {"message": "Ready"}
        result = agent_chat_reply(
            "revise option A — larger font, more vibrant colors",
            gig_id="gig-1",
            agent=agent,
        )
        self.assertIsNotNone(result["execution"])
        self.assertEqual(result["execution"]["type"], "revise")
        self.assertEqual(result["execution"]["option"], "A")
        self.assertIn("new round", result["reply"].lower())
        self.assertIn("three variants", result["reply"].lower())
        self.assertIn("Option A", result["reply"])
        self.assertNotIn("I'll apply that as revision feedback", result["reply"])

    def test_revise_with_en_dash(self) -> None:
        agent = MagicMock()
        agent.gig_detail.return_value = _revise_detail()
        agent.recommend_action.return_value = {"message": "Ready"}
        result = agent_chat_reply(
            "Revise option A – larger font",
            gig_id="gig-1",
            agent=agent,
        )
        self.assertEqual(result["execution"]["type"], "revise")
        self.assertIn("larger font", result["execution"]["feedback"])

    def test_incomplete_revise_returns_hint_not_execution(self) -> None:
        agent = MagicMock()
        agent.gig_detail.return_value = _revise_detail()
        agent.recommend_action.return_value = {"message": "Ready"}
        result = agent_chat_reply("revise", gig_id="gig-1", agent=agent)
        self.assertIsNone(result["execution"])
        self.assertIn("which option", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
