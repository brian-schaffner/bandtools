"""Tests for shell pass-2 asset mode policy."""

from __future__ import annotations

import unittest

from shell_asset_policy import (
    asset_mode_for_route,
    asset_mode_for_shell,
    asset_mode_label,
    final_route_label,
    suggest_final_route,
    uses_band_photo,
)
from shell_references import get_shell


class ShellAssetPolicyTest(unittest.TestCase):
    def test_fillmore_is_typography_only(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        self.assertEqual(asset_mode_for_shell(shell), "typography_only")
        self.assertFalse(uses_band_photo("typography_only"))

    def test_avalon_is_typography_only(self) -> None:
        shell = get_shell("avalon_mantra_rock_1967")
        assert shell is not None
        self.assertEqual(asset_mode_for_shell(shell), "typography_only")

    def test_woodstock_uses_footer_inset_photo(self) -> None:
        shell = get_shell("woodstock_festival_1969")
        assert shell is not None
        self.assertEqual(asset_mode_for_shell(shell), "photo_inset")
        self.assertTrue(uses_band_photo("photo_inset"))

    def test_arena_shell_uses_hero_photo(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        self.assertEqual(asset_mode_for_shell(shell), "photo_hero")

    def test_asset_mode_label(self) -> None:
        self.assertIn("no photo", asset_mode_label("typography_only").lower())

    def test_suggest_final_route_fillmore_text_only(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        self.assertEqual(suggest_final_route(shell), "text_only")

    def test_suggest_final_route_arena_photo_logo(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        self.assertEqual(suggest_final_route(shell), "photo_logo")

    def test_asset_mode_for_route_text_only(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        self.assertEqual(asset_mode_for_route(shell, "text_only"), "typography_only")

    def test_asset_mode_for_route_photo_on_typography_shell_uses_inset(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        self.assertEqual(asset_mode_for_route(shell, "photo_logo"), "photo_inset")

    def test_hendrix_suggest_photo_logo(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        self.assertEqual(suggest_final_route(shell), "photo_logo")

    def test_final_route_label(self) -> None:
        self.assertIn("text-only", final_route_label("text_only").lower())


if __name__ == "__main__":
    unittest.main()
