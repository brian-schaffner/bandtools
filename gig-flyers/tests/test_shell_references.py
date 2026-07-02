"""Tests for shell reference registry."""

from __future__ import annotations

import unittest

from shell_references import (
    SHELL_REFERENCES,
    get_shell,
    pick_shell_for_research,
    pick_shell_for_venue_type,
    registry_summary,
)


class ShellReferenceRegistryTest(unittest.TestCase):
    def test_registry_has_at_least_23_shells(self) -> None:
        self.assertGreaterEqual(len(SHELL_REFERENCES), 23)

    def test_unique_shell_ids(self) -> None:
        ids = [s.id for s in SHELL_REFERENCES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_festival_routes_woodstock(self) -> None:
        shell = pick_shell_for_research({"venue_type": "festival"})
        self.assertEqual(shell.id, "woodstock_festival_1969")

    def test_blues_bar_routes_altamont(self) -> None:
        shell = pick_shell_for_venue_type("blues_bar")
        self.assertEqual(shell.id, "altamont_free_concert_1969")

    def test_member_club_routes_hatch(self) -> None:
        shell = pick_shell_for_venue_type("member_club")
        self.assertEqual(shell.id, "hatch_hank_williams_1953")

    def test_get_shell_unknown(self) -> None:
        self.assertIsNone(get_shell("not_a_real_shell"))

    def test_legacy_shells_have_images(self) -> None:
        for sid in (
            "hatch_hank_williams_1953",
            "altamont_free_concert_1969",
            "woodstock_festival_1969",
        ):
            shell = get_shell(sid)
            assert shell is not None
            self.assertTrue(shell.has_image(), msg=sid)

    def test_registry_summary_shape(self) -> None:
        summary = registry_summary()
        self.assertIn("count", summary)
        self.assertIn("shells", summary)
        self.assertGreaterEqual(summary["count"], 23)


if __name__ == "__main__":
    unittest.main()
