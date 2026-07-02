"""Tests for shell pass 2 edit mask."""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from shell_asset_integrate import ShellPass2Compose
from shell_pass2_mask import build_personalize_mask, enforce_shell_design, text_edit_zones
from shell_text_slots import typography_text_zones
from shell_references import get_shell

ROOT = Path(__file__).resolve().parents[1]


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
        headliner = typography_text_zones(size, shell)[0]
        hx = (headliner[0] + headliner[2]) // 2
        hy = (headliner[1] + headliner[3]) // 2
        self.assertLess(alpha.getpixel((hx, hy)), 32)

    def test_typography_slots_avoid_illustration_band(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        zones = typography_text_zones((1024, 1536), shell)
        mid = 768
        for x1, y1, x2, y2 in zones:
            covers_mid = y1 < mid < y2
            self.assertFalse(covers_mid, f"zone {y1}-{y2} covers illustration at y={mid}")
        self.assertEqual(len(zones), 5)

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

    def test_enforce_shell_design_restores_pass1_pixels(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        size = (400, 600)
        photo_clear = (50, 180, 350, 420)
        logo = (280, 300, 360, 360)
        zones = tuple(text_edit_zones(size, photo_clear, shell))
        pass1 = Image.new("RGBA", size, (255, 220, 0, 255))
        draw = ImageDraw.Draw(pass1)
        draw.rectangle([50, 180, 350, 420], fill=(0, 0, 0, 255))
        model = pass1.copy()
        draw_model = ImageDraw.Draw(model)
        draw_model.rectangle([0, 0, 400, 600], fill=(240, 235, 220, 255))
        out_path = ROOT / "output" / ".test_design_restore.png"
        model.convert("RGB").save(out_path)
        compose = ShellPass2Compose(
            photo_bbox=(60, 190, 340, 410),
            photo_clear_bbox=photo_clear,
            photo_layer=Image.new("RGBA", (280, 220), (100, 100, 100, 255)),
            logo_bbox=logo,
            logo_layer=Image.new("RGBA", (80, 60), (0, 0, 0, 0)),
            shell_layer=pass1,
            text_edit_zones=zones,
            canvas_size=size,
            asset_mode="photo_hero",
        )
        enforce_shell_design(out_path, compose)
        restored = Image.open(out_path).convert("RGB")
        self.assertGreater(restored.getpixel((200, 100))[0], 200)
        self.assertLess(restored.getpixel((200, 300))[0], 40)
        out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
