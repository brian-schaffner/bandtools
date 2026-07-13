#!/usr/bin/env python3
"""Tests for Flyer Agent v2 MVP modules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_agent.intent import parse_chat_intent  # noqa: E402
from flyer_agent.llm_chat import _intent_from_llm, resolve_chat_intent  # noqa: E402
from flyer_agent.revision_brief import RevisionBrief, RevisionVariant, build_revision_brief  # noqa: E402
from structured_layout.feedback_tweaks import apply_revision_feedback  # noqa: E402
from structured_layout.layout_spec import LayoutSpec  # noqa: E402


class LlmChatIntentTest(unittest.TestCase):
    def test_llm_revise_intent(self) -> None:
        detail = {
            "can_revise": True,
            "flyers": [{"option": "A"}],
        }
        data = {
            "action": "revise",
            "option": "A",
            "feedback": "pastel colors",
            "reply": "Making three pastel variants of A.",
        }
        intent = _intent_from_llm(data, detail=detail)
        self.assertEqual(intent.kind, "revise")
        self.assertEqual(intent.option, "A")

    def test_llm_approve_intent(self) -> None:
        detail = {"flyers": [{"option": "A"}]}
        intent = _intent_from_llm(
            {"action": "approve", "option": "B", "reply": "Approving B."},
            detail=detail,
        )
        self.assertEqual(intent.kind, "approve")
        self.assertEqual(intent.option, "B")

    def test_rules_fallback_when_llm_disabled(self) -> None:
        detail = {
            "can_revise": True,
            "flyers": [{"option": "A"}],
            "event": {"venue": "Test"},
        }
        with patch.dict("os.environ", {"FLYER_AGENT_LLM_CHAT": "0"}, clear=False):
            intent, reply, source = resolve_chat_intent(
                "I like option A, but make it pastel",
                detail=detail,
            )
        self.assertEqual(source, "rules")
        self.assertEqual(intent.kind, "revise")


class RevisionBriefTest(unittest.TestCase):
    def test_keyword_fallback_pastel(self) -> None:
        brief = build_revision_brief("make it pastel", base_option="A")
        self.assertEqual(len(brief.variants), 3)
        self.assertIn("pastel", brief.summary.lower())

    def test_brief_applied_to_layout(self) -> None:
        brief = RevisionBrief(
            summary="pastel",
            font_scale=1.0,
            variants=[
                RevisionVariant("one", "#FADADD", "#7A5C6A"),
                RevisionVariant("two", "#D4E4F7", "#4A5F7A"),
                RevisionVariant("three", "#D8F3DC", "#4A6B55"),
            ],
        )
        layout = LayoutSpec()
        a = apply_revision_feedback(layout, "pastel", variant_index=0, revision_brief=brief)
        b = apply_revision_feedback(layout, "pastel", variant_index=1, revision_brief=brief)
        self.assertNotEqual(a.background.color.hex, b.background.color.hex)


class ApproveIntentRulesTest(unittest.TestCase):
    def test_approve_option_a(self) -> None:
        detail = {"flyers": [{"option": "A"}, {"option": "B"}]}
        intent = parse_chat_intent("approve A", detail=detail)
        self.assertEqual(intent.kind, "approve")
        self.assertEqual(intent.option, "A")


if __name__ == "__main__":
    unittest.main()
