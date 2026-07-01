#!/usr/bin/env python3
"""Install official band logos from repo-root uploads into assets/logos/."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / "assets" / "logos"

# User uploads at repo root (GitHub "Add files via upload")
SOURCES = (
    ("IMG_8016.png", "dark"),   # black ink, transparent
    ("IMG_8015.png", "on_white"),  # black on white canvas
)


def main() -> None:
    dark_path = REPO / "IMG_8016.png"
    white_path = REPO / "IMG_8015.png"
    if not dark_path.is_file() or not white_path.is_file():
        print("Missing IMG_8015.png or IMG_8016.png at repo root", file=sys.stderr)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    dark = Image.open(dark_path).convert("RGBA")
    on_white = Image.open(white_path).convert("RGBA")

    dark.save(OUT / "lindsey-lane-band-dark.png")
    dark.save(OUT / "lindsey-lane-band.png")
    on_white.save(OUT / "lindsey-lane-band-on-white.png")

    r, g, b, a = dark.split()
    light = Image.merge("RGBA", (ImageOps.invert(r), ImageOps.invert(g), ImageOps.invert(b), a))
    light.save(OUT / "lindsey-lane-band-light.png")

    on_black = ImageOps.invert(on_white.convert("RGB")).convert("RGBA")
    on_black.save(OUT / "lindsey-lane-band-on-black.png")

    print(f"Installed Lindsey Lane Band logos into {OUT}")


if __name__ == "__main__":
    main()
