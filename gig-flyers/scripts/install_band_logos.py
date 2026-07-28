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

SLUG = "lindsey-lane-band"


def _key_to_alpha(img: Image.Image, key: tuple[int, int, int], *, tolerance: int = 28) -> Image.Image:
    """Make solid background (near key color) transparent."""
    rgba = img.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (*key, 255))
    diff = ImageChops.difference(rgba, bg).convert("L")
    mask = diff.point(lambda v: 0 if v < tolerance else 255)
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), mask))
    return rgba


def _save_stack_set(stack_white: Path, stack_black: Path) -> None:
    on_white = Image.open(stack_white).convert("RGBA")
    on_black = Image.open(stack_black).convert("RGBA")

    dark = _key_to_alpha(on_white, (255, 255, 255))
    light = _key_to_alpha(on_black, (0, 0, 0))

    dark.save(OUT / f"{SLUG}-dark.png")
    dark.save(OUT / f"{SLUG}.png")
    light.save(OUT / f"{SLUG}-light.png")
    on_white.save(OUT / f"{SLUG}-on-white.png")
    on_black.save(OUT / f"{SLUG}-on-black.png")


def _install_from_source_dir() -> bool:
    stack_white = SOURCE / "stack-on-white.png"
    stack_black = SOURCE / "stack-on-black.png"
    if not stack_white.is_file() or not stack_black.is_file():
        return False
    OUT.mkdir(parents=True, exist_ok=True)
    _save_stack_set(stack_white, stack_black)
    circle = SOURCE / "circle-on-black.png"
    if circle.is_file():
        Image.open(circle).convert("RGBA").save(OUT / f"{SLUG}-circle.png")
        Image.open(circle).convert("RGBA").save(OUT / f"{SLUG}-badge.png")
    print(f"Installed stack logos from {SOURCE}")
    return True


def _install_legacy_root() -> bool:
    dark_path = REPO / "IMG_8016.png"
    white_path = REPO / "IMG_8015.png"
    if not dark_path.is_file() or not white_path.is_file():
        return False
    OUT.mkdir(parents=True, exist_ok=True)
    dark = Image.open(dark_path).convert("RGBA")
    on_white = Image.open(white_path).convert("RGBA")
    dark.save(OUT / f"{SLUG}-dark.png")
    dark.save(OUT / f"{SLUG}.png")
    on_white.save(OUT / f"{SLUG}-on-white.png")
    r, g, b, a = dark.split()
    light = Image.merge("RGBA", (ImageOps.invert(r), ImageOps.invert(g), ImageOps.invert(b), a))
    light.save(OUT / f"{SLUG}-light.png")
    on_black = ImageOps.invert(on_white.convert("RGB")).convert("RGBA")
    on_black.save(OUT / f"{SLUG}-on-black.png")
    print(f"Installed legacy nested-L logos from repo root into {OUT}")
    return True


def main() -> None:
    if _install_from_source_dir():
        return
    if _install_legacy_root():
        return
    print(
        "No logo sources found. Add stack-on-white.png + stack-on-black.png under "
        f"{SOURCE}, or IMG_8015.png + IMG_8016.png at repo root.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
