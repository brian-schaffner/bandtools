#!/usr/bin/env python3
"""Render Lindsey Lane Band logo lockup PNGs (nested L) for assets/logos/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT = ROOT / "assets" / "logos"
FONT_BIG = ROOT / "assets/fonts/BebasNeue-Regular.ttf"
FONT_SMALL = "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"


def _font(path: str | Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def render_lockup(*, fill: tuple[int, int, int], bg: tuple[int, int, int] | None = None) -> Image.Image:
    """Nested-L lockup matching brand: L + indsey / ane Band."""
    big = _font(FONT_BIG, 248)
    mid = _font(FONT_SMALL, 58)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l_box = probe.textbbox((0, 0), "L", font=big)
    l_w, l_h = l_box[2] - l_box[0], l_box[3] - l_box[1]
    line1 = "indsey"
    line2 = "ane Band"
    t1 = probe.textbbox((0, 0), line1, font=mid)
    t2 = probe.textbbox((0, 0), line2, font=mid)
    w = int(l_w + max(t1[2] - t1[0], t2[2] - t2[0]) + 28)
    h = int(l_h + 16)
    img = Image.new("RGBA", (w, h), (*bg, 255) if bg else (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (*fill, 255)
    # Big L anchor
    draw.text((0, -l_box[1]), "L", font=big, fill=color)
    x_text = int(l_w * 0.68)
    draw.text((x_text, 22 - t1[1]), line1, font=mid, fill=color)
    draw.text((x_text, 86 - t2[1]), line2, font=mid, fill=color)
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    render_lockup(fill=(15, 15, 15)).save(OUT / "lindsey-lane-band.png")
    render_lockup(fill=(15, 15, 15)).save(OUT / "lindsey-lane-band-dark.png")
    render_lockup(fill=(245, 245, 245)).save(OUT / "lindsey-lane-band-light.png")
    render_lockup(fill=(245, 245, 245), bg=(15, 15, 15)).save(OUT / "lindsey-lane-band-on-black.png")
    render_lockup(fill=(15, 15, 15), bg=(245, 245, 245)).save(OUT / "lindsey-lane-band-on-white.png")
    print("Wrote logo assets to", OUT)


if __name__ == "__main__":
    main()
