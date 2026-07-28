#!/usr/bin/env python3
"""Install official band logos into assets/logos/ for PIL overlay + structured layouts."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / "assets" / "logos"
SOURCE = OUT / "source"
UPLOADS = ROOT / "logos"

SLUG = "lindsey-lane-band"

# GitHub uploads in gig-flyers/logos/ (2026 lockup)
GITHUB_STACK_DARK = UPLOADS / "Lindset Lane Band Logo 2026 - Black and Transparent.png"
GITHUB_STACK_LIGHT = UPLOADS / "Lindsey Lane Band New Logo 2026.png"
GITHUB_CIRCLE = UPLOADS / "Lindsey Lane Logo for FB Profile Picture.png"


def _key_to_alpha(img: Image.Image, key: tuple[int, int, int], *, tolerance: int = 28) -> Image.Image:
    rgba = img.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (*key, 255))
    diff = ImageChops.difference(rgba, bg).convert("L")
    mask = diff.point(lambda v: 0 if v < tolerance else 255)
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), mask))
    return rgba


def _write_outputs(
    *,
    dark: Image.Image,
    light: Image.Image,
    on_white: Image.Image | None = None,
    on_black: Image.Image | None = None,
    circle: Image.Image | None = None,
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dark.save(OUT / f"{SLUG}-dark.png")
    dark.save(OUT / f"{SLUG}.png")
    light.save(OUT / f"{SLUG}-light.png")
    if on_white is not None:
        on_white.save(OUT / f"{SLUG}-on-white.png")
    if on_black is not None:
        on_black.save(OUT / f"{SLUG}-on-black.png")
    if circle is not None:
        circle.save(OUT / f"{SLUG}-circle.png")
        circle.save(OUT / f"{SLUG}-badge.png")


def _install_from_github_logos_folder() -> bool:
    if not GITHUB_STACK_DARK.is_file() or not GITHUB_STACK_LIGHT.is_file():
        return False

    dark_raw = Image.open(GITHUB_STACK_DARK).convert("RGBA")
    light_raw = Image.open(GITHUB_STACK_LIGHT).convert("RGBA")

    # Dark ink lockup: file may already be transparent; else knock out white.
    if dark_raw.getchannel("A").getextrema()[1] < 250:
        dark = dark_raw
        on_white = dark_raw.copy()
    else:
        dark = _key_to_alpha(dark_raw, (255, 255, 255), tolerance=32)
        on_white = dark_raw

    light = _key_to_alpha(light_raw, (0, 0, 0), tolerance=32)
    on_black = light_raw

    circle_img = None
    if GITHUB_CIRCLE.is_file():
        circle_img = Image.open(GITHUB_CIRCLE).convert("RGBA")

    _write_outputs(dark=dark, light=light, on_white=on_white, on_black=on_black, circle=circle_img)
    print(f"Installed 2026 lockup from {UPLOADS}")
    return True


def _install_from_source_dir() -> bool:
    stack_white = SOURCE / "stack-on-white.png"
    stack_black = SOURCE / "stack-on-black.png"
    if not stack_white.is_file() or not stack_black.is_file():
        return False
    dark = _key_to_alpha(Image.open(stack_white).convert("RGBA"), (255, 255, 255))
    light = _key_to_alpha(Image.open(stack_black).convert("RGBA"), (0, 0, 0))
    circle_img = None
    circle = SOURCE / "circle-on-black.png"
    if circle.is_file():
        circle_img = Image.open(circle).convert("RGBA")
    _write_outputs(
        dark=dark,
        light=light,
        on_white=Image.open(stack_white).convert("RGBA"),
        on_black=Image.open(stack_black).convert("RGBA"),
        circle=circle_img,
    )
    print(f"Installed stack logos from {SOURCE}")
    return True


def _install_legacy_root() -> bool:
    dark_path = REPO / "IMG_8016.png"
    white_path = REPO / "IMG_8015.png"
    if not dark_path.is_file() or not white_path.is_file():
        return False
    dark = Image.open(dark_path).convert("RGBA")
    on_white = Image.open(white_path).convert("RGBA")
    r, g, b, a = dark.split()
    light = Image.merge("RGBA", (ImageOps.invert(r), ImageOps.invert(g), ImageOps.invert(b), a))
    on_black = ImageOps.invert(on_white.convert("RGB")).convert("RGBA")
    _write_outputs(dark=dark, light=light, on_white=on_white, on_black=on_black)
    print(f"Installed legacy nested-L logos from repo root into {OUT}")
    return True


def main() -> None:
    if _install_from_github_logos_folder():
        return
    if _install_from_source_dir():
        return
    if _install_legacy_root():
        return
    print(
        "No logo sources found. Add files under gig-flyers/logos/ (2026 lockup), "
        f"{SOURCE}, or IMG_8015/8016 at repo root.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
