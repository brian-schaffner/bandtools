"""Tests for typography placeholder slots."""

from __future__ import annotations

import unittest

from shell_references import get_shell
from shell_text_slots import placeholder_values, typography_text_zones


class ShellTextSlotsTest(unittest.TestCase):
    def test_fillmore_headliner_slot_is_top_only(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        zones = typography_text_zones((1024, 1536), shell)
        headliner = zones[0]
        self.assertLess(headliner[3], 400)

    def test_placeholder_values(self) -> None:
        values = placeholder_values(
            band="Lindsey Lane Band",
            venue="Nelson County Fair",
            date="Sunday, July 26, 2026",
            time="5:00 pm",
        )
        self.assertEqual(values["HEADLINER"], "Lindsey Lane Band")
        self.assertEqual(values["SUPPORTING ACTS"], "")


if __name__ == "__main__":
    unittest.main()
