#!/usr/bin/env python3
"""Tests for authoritative shell render registry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_asset_policy import asset_mode_for_shell, suggest_final_route  # noqa: E402
from shell_render_registry import get_render_spec  # noqa: E402
from shell_references import get_shell  # noqa: E402


class ShellRenderRegistryTest(unittest.TestCase):
    def test_fillmore_is_none_photo_style(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        spec = get_render_spec(shell)
        self.assertEqual(spec.photo_style, "none")
        self.assertEqual(spec.text_engine, "hybrid")
        self.assertEqual(asset_mode_for_shell(shell), "typography_only")
        self.assertEqual(suggest_final_route(shell), "text_only")

    def test_hendrix_is_hero_illustration(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        spec = get_render_spec(shell)
        self.assertEqual(spec.photo_style, "hero_illustration")
        self.assertEqual(spec.logo_policy, "none")
        self.assertIn("threshold", spec.photo_processing)
        self.assertIn("halftone", spec.photo_processing)
        self.assertEqual(suggest_final_route(shell), "photo_logo")

    def test_hybrid_openai_slots_headliner_only(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        spec = get_render_spec(shell)
        self.assertEqual(spec.openai_text_slots(), ("HEADLINER",))

    def test_arena_editable_regions_count(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        spec = get_render_spec(shell)
        self.assertEqual(len(spec.editable_regions), 5)

    def test_arena_preserves_photo_slot(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        spec = get_render_spec(shell)
        self.assertEqual(len(spec.preserve_regions), 1)
        self.assertEqual(spec.preserve_regions[0], spec.photo_slot)


if __name__ == "__main__":
    unittest.main()
