"""Tests for shell pass 2 edit mask."""

from __future__ import annotations

import unittest

from shell_pass2_mask import build_personalize_mask, text_edit_zones
from shell_references import get_shell


class ShellPass2MaskTest(unittest.TestCase):
    def test_mask_protects_photo_and_allows_header_edit(self) -> None:
        size = (1024, 1536)
        shell = get_shell("new_orleans_jazz_club")
        assert shell is not None
        photo_clear = (112, 399, 912, 1075)
        logo = (650, 799, 950, 950)
        mask = build_personalize_mask(
            size, photo_clear_bbox=photo_clear, logo_bbox=logo, shell=shell,
        )
        alpha = mask.split()[3]
        cx, cy = (photo_clear[0] + photo_clear[2]) // 2, (photo_clear[1] + photo_clear[3]) // 2
        self.assertGreater(alpha.getpixel((cx, cy)), 200)
        self.assertLess(alpha.getpixel((512, 40)), 32)

    def test_text_zones_sit_outside_photo_clear(self) -> None:
        shell = get_shell("harvest_time_blues")
        assert shell is not None
        photo_clear = (112, 399, 912, 1075)
        zones = text_edit_zones((1024, 1536), photo_clear, shell)
        self.assertGreaterEqual(len(zones), 2)
        for x1, y1, x2, y2 in zones:
            overlaps = not (y2 <= photo_clear[1] or y1 >= photo_clear[3])
            if overlaps:
                self.assertLessEqual(y2 - y1, 120)


if __name__ == "__main__":
    unittest.main()
