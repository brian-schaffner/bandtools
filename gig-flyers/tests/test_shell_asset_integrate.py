"""Tests for shell photo/logo integration."""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from shell_asset_integrate import (
    integrate_band_photo,
    integrate_band_logo,
    knockout_studio_background,
    shell_palette_rgb,
)
from shell_references import get_shell


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"


class ShellAssetIntegrateTest(unittest.TestCase):
    def test_knockout_creates_transparency(self) -> None:
        if not DEFAULT_PHOTO.is_file():
            self.skipTest("band photo missing")
        photo = Image.open(DEFAULT_PHOTO)
        out = knockout_studio_background(photo, target=(60, 30, 80), threshold=220)
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


if __name__ == "__main__":
    unittest.main()
