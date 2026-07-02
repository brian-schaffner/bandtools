"""Tests for shell photo/logo integration."""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from shell_asset_integrate import (
    ShellPass2Compose,
    blend_duotone_photo,
    clear_photo_slot,
    enforce_shell_photo,
    integrate_band_photo,
    integrate_band_logo,
    knockout_studio_background,
    photo_slot_for_shell,
    placement_zones,
    shell_palette_rgb,
)
from shell_references import get_shell


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"


class ShellAssetIntegrateTest(unittest.TestCase):
    def test_knockout_creates_transparency(self) -> None:
        img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([40, 40, 160, 160], fill=(120, 80, 60, 255))
        out = knockout_studio_background(img, target=(60, 30, 80))
        alpha = out.split()[3]
        transparent = sum(1 for a in alpha.getdata() if a < 128)
        self.assertGreater(transparent, 500)

    def test_integrate_photo_has_transparency(self) -> None:
        if not DEFAULT_PHOTO.is_file():
            self.skipTest("band photo missing")
        shell = get_shell("circus_victorian_mr_kite_1967")
        assert shell is not None
        photo = Image.open(DEFAULT_PHOTO)
        out = integrate_band_photo(photo, shell, backdrop=(60, 30, 80))
        self.assertEqual(out.mode, "RGBA")
        alpha = out.split()[3]
        self.assertLess(min(alpha.getdata()), 255)

    def test_integrate_logo_returns_badge(self) -> None:
        shell = get_shell("circus_victorian_mr_kite_1967")
        assert shell is not None
        logo_path = ROOT / "assets/logos/lindsey-lane-band-light.png"
        if not logo_path.is_file():
            self.skipTest("logo missing")
        logo = Image.open(logo_path)
        out = integrate_band_logo(logo, shell, zone_color=(40, 20, 60))
        self.assertEqual(out.mode, "RGBA")
        self.assertGreater(out.height, 20)
        self.assertGreater(out.width, 20)

    def test_shell_palette_parses_hex(self) -> None:
        shell = get_shell("woodstock_festival_1969")
        assert shell is not None
        colors = shell_palette_rgb(shell)
        self.assertGreaterEqual(len(colors), 3)
        self.assertTrue(all(len(c) == 3 for c in colors))

    def test_blend_duotone_preserves_color_variation(self) -> None:
        if not DEFAULT_PHOTO.is_file():
            self.skipTest("band photo missing")
        photo = Image.open(DEFAULT_PHOTO).convert("RGBA")
        full = blend_duotone_photo(
            photo, shadow=(20, 20, 20), highlight=(220, 210, 200), strength=1.0,
        )
        partial = blend_duotone_photo(
            photo, shadow=(20, 20, 20), highlight=(220, 210, 200), strength=0.3,
        )
        full_px = list(full.convert("RGB").getdata())
        partial_px = list(partial.convert("RGB").getdata())
        full_spread = max(p[0] for p in full_px) - min(p[0] for p in full_px)
        partial_spread = max(p[0] for p in partial_px) - min(p[0] for p in partial_px)
        self.assertGreater(partial_spread, full_spread * 0.85)

    def test_letterpress_photo_not_full_grayscale(self) -> None:
        if not DEFAULT_PHOTO.is_file():
            self.skipTest("band photo missing")
        shell = get_shell("hatch_hank_williams_1953")
        if shell is None:
            self.skipTest("hatch shell missing")
        photo = Image.open(DEFAULT_PHOTO)
        out = integrate_band_photo(photo, shell, backdrop=(60, 30, 80))
        rgb = out.convert("RGB")
        px = [p for p in rgb.getdata() if sum(p) > 30]
        if len(px) < 100:
            self.skipTest("not enough opaque pixels")
        color_delta = max(abs(p[0] - p[1]) + abs(p[1] - p[2]) for p in px[:5000])
        self.assertGreater(color_delta, 8)

    def test_photo_zone_is_larger_for_hero_shells(self) -> None:
        shell = get_shell("new_orleans_jazz_club")
        assert shell is not None
        zones = placement_zones((1024, 1536), shell)
        photo = zones["photo"]
        w, h = photo[2] - photo[0], photo[3] - photo[1]
        self.assertEqual(photo_slot_for_shell(shell), "center_hero")
        self.assertGreaterEqual(w, 790)
        self.assertGreaterEqual(h, 670)

    def test_clear_photo_slot_erases_placeholder(self) -> None:
        canvas = Image.new("RGBA", (400, 400), (20, 80, 40, 255))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([80, 80, 320, 280], fill=(200, 100, 50, 255))
        zone = (80, 80, 320, 280)
        cleared = clear_photo_slot(canvas, zone, backdrop=(20, 80, 40), pad=12)
        patch = canvas.crop(cleared)
        orange = sum(1 for p in patch.getdata() if p[0] > 150 and p[1] < 130)
        self.assertLess(orange, patch.width * patch.height // 10)

    def test_gritty_shell_uses_lower_left(self) -> None:
        shell = get_shell("altamont_free_concert_1969")
        assert shell is not None
        self.assertEqual(photo_slot_for_shell(shell), "lower_left")
        zones = placement_zones((1024, 1536), shell)
        photo = zones["photo"]
        self.assertLess(photo[0], 200)
        self.assertGreater(photo[1], 800)

    def test_enforce_shell_photo_restores_layer(self) -> None:
        if not DEFAULT_PHOTO.is_file():
            self.skipTest("band photo missing")
        shell = get_shell("circus_victorian_mr_kite_1967")
        assert shell is not None
        photo = integrate_band_photo(
            Image.open(DEFAULT_PHOTO), shell, backdrop=(60, 30, 80),
        )
        canvas = Image.new("RGB", (1024, 1536), (242, 235, 220))
        bbox = (40, 900, 40 + photo.width, 900 + photo.height)
        clear_bbox = (28, 888, 52 + photo.width, 912 + photo.height)
        compose = ShellPass2Compose(
            photo_bbox=bbox,
            photo_clear_bbox=clear_bbox,
            photo_layer=photo,
            canvas_size=(1024, 1536),
            backdrop_rgb=(242, 235, 220),
        )
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.alpha_composite(photo, (40, 900))
        canvas_rgba.convert("RGB").save(tmp := ROOT / "output" / ".test_enforce_in.png")
        degraded = canvas_rgba.copy()
        draw = ImageDraw.Draw(degraded)
        draw.rectangle(bbox, fill=(255, 0, 0, 200))
        out_path = ROOT / "output" / ".test_enforce_out.png"
        degraded.convert("RGB").save(out_path)
        self.assertTrue(enforce_shell_photo(out_path, compose))
        restored = Image.open(out_path).convert("RGB")
        patch = restored.crop(bbox)
        red_pixels = sum(1 for p in patch.getdata() if p[0] > 200 and p[1] < 80)
        self.assertLess(red_pixels, patch.width * patch.height // 4)
        tmp.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
