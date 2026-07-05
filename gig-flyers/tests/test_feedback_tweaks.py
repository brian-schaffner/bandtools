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

    def test_vibrant_adjusts_background(self) -> None:
        layout = LayoutSpec()
        updated = apply_revision_feedback(layout, "more vibrant colors")
        self.assertNotEqual(updated.background.color.hex, layout.background.color.hex)


if __name__ == "__main__":
    unittest.main()
