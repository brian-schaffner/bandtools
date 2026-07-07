#!/usr/bin/env python3
"""Tests for structured layout revision feedback tweaks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from structured_layout.feedback_tweaks import apply_revision_feedback  # noqa: E402
from structured_layout.layout_spec import ColorSpec, LayoutSpec, TextElement  # noqa: E402


class FeedbackTweaksTest(unittest.TestCase):
    def test_larger_font_scales_text(self) -> None:
        layout = LayoutSpec(
            text_elements=[
                TextElement(content="VENUE", x=10, y=10, width=80, font_size=40),
            ]
        )
        updated = apply_revision_feedback(layout, "larger font, more vibrant colors")
        self.assertGreater(updated.text_elements[0].font_size, 40)

    def test_pastel_variants_differ(self) -> None:
        layout = LayoutSpec()
        first = apply_revision_feedback(layout, "pastel colors", variant_index=0, variant_count=3)
        second = apply_revision_feedback(layout, "pastel colors", variant_index=1, variant_count=3)
        self.assertNotEqual(first.background.color.hex, second.background.color.hex)

    def test_like_option_pastel_intent(self) -> None:
        from flyer_agent.intent import parse_chat_intent

        detail = {
            "can_revise": True,
            "can_generate": False,
            "can_regenerate": False,
            "flyers": [{"option": "A"}],
        }
        intent = parse_chat_intent("I like option A, but I want it in pastel", detail=detail)
        self.assertEqual(intent.kind, "revise")
        self.assertEqual(intent.option, "A")
        self.assertIn("pastel", (intent.feedback or "").lower())


if __name__ == "__main__":
    unittest.main()
