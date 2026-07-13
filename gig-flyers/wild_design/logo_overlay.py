"""Post-render band logo badge for full-canvas and structured flyers."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from structured_layout.band_mark import BADGE_BOX_TOP_RIGHT, draw_band_logo_badge

CANVAS_SIZE = (1024, 1536)


def flyer_logo_overlay_enabled() -> bool:
    return os.getenv("FLYER_LOGO_OVERLAY", "1").strip().lower() in {"1", "true", "yes", "on"}


def _sample_paper_color(img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    x1, y1, x2, y2 = box
    region = img.crop((x1, y1, x2, y2)).convert("RGB")
    pixels = list(region.getdata())
    if not pixels:
        return (240, 235, 225)
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)


def overlay_flyer_logo(
    output_path: Path,
    band: str,
    *,
    box: tuple[int, int, int, int] = BADGE_BOX_TOP_RIGHT,
) -> bool:
    """Paste official band logo lockup onto a finished flyer PNG. Returns True if applied."""
    if not flyer_logo_overlay_enabled():
        return False
    if not output_path.is_file():
        return False
    band_name = (band or "").strip()
    if not band_name:
        return False

    img = Image.open(output_path).convert("RGBA")
    if img.size != CANVAS_SIZE:
        scale = min(img.width / CANVAS_SIZE[0], img.height / CANVAS_SIZE[1])
        if scale <= 0:
            return False
        nw = max(1, int(img.width / scale))
        nh = max(1, int(img.height / scale))
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)

    paper = _sample_paper_color(img, box)
    if not draw_band_logo_badge(img, band_name, box=box, paper=paper):
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output_path, format="PNG")
    return True
