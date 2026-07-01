"""Band logo / name mark for Option C — asset file or procedural lockup."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from structured_layout.graphic_primitives import (
    CANVAS,
    draw_stroked_text_layer,
    load_font,
    text_size,
)

ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "assets" / "logos"


def band_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def find_band_logo(band: str) -> Path | None:
    """Return bundled logo PNG/WebP if present under assets/logos/."""
    slug = band_slug(band)
    for stem in (slug, slug.replace("-band", "")):
        for ext in (".png", ".webp", ".jpg"):
            path = LOGO_DIR / f"{stem}{ext}"
            if path.is_file():
                return path
    return None


def band_initials(band: str) -> str:
    skip = {"the", "band", "at", "featuring", "feat", "presents"}
    words = [w for w in re.split(r"\s+", band.strip()) if w.lower() not in skip]
    return "".join(w[0].upper() for w in words[:3]) or "?"


def _split_band_name(band: str) -> tuple[str, str]:
    """'Lindsey Lane Band' → ('LINDSEY LANE', 'BAND')."""
    words = band.strip().split()
    if len(words) >= 3 and words[-1].lower() == "band":
        return " ".join(words[:-1]).upper(), words[-1].upper()
    if len(words) >= 2:
        return " ".join(words[:-1]).upper(), words[-1].upper()
    return band.upper(), ""


def draw_band_mark(
    canvas: Image.Image,
    band: str,
    *,
    style: str,
    ink: tuple[int, int, int],
    accent: tuple[int, int, int],
    paper: tuple[int, int, int],
    seed: int = 0,
) -> None:
    """Graphical band identity — logo file or procedural lockup."""
    logo = find_band_logo(band)
    if logo is not None:
        _paste_logo_mark(canvas, logo, style=style, seed=seed)
        return
    if style in ("monogram", "xerox_punk", "pasteup_zine"):
        _draw_monogram(canvas, band, ink=ink, accent=accent, paper=paper)
    elif style in ("neon_bar", "psychedelic"):
        _draw_neon_lockup(canvas, band, accent=accent, ink=ink)
    elif style in ("boutique", "country_fair", "broadside"):
        _draw_serif_lockup(canvas, band, ink=ink, accent=accent)
    else:
        _draw_display_lockup(canvas, band, ink=ink, accent=accent, paper=paper)


def _paste_logo_mark(canvas: Image.Image, logo_path: Path, *, style: str, seed: int) -> None:
    logo = Image.open(logo_path).convert("RGBA")
    max_w = 280 if style == "neon_bar" else 220
    ratio = min(max_w / logo.width, 120 / logo.height)
    nw, nh = max(1, int(logo.width * ratio)), max(1, int(logo.height * ratio))
    logo = logo.resize((nw, nh), Image.Resampling.LANCZOS)
    x = CANVAS[0] - nw - 48 if seed % 2 else 48
    y = 36 if style != "broadside" else CANVAS[1] - nh - 160
    canvas.alpha_composite(logo, (x, y))


def _draw_monogram(
    canvas: Image.Image,
    band: str,
    *,
    ink: tuple[int, int, int],
    accent: tuple[int, int, int],
    paper: tuple[int, int, int],
) -> None:
    initials = band_initials(band)
    cx, cy, r = CANVAS[0] - 120, 130, 72
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*paper, 240), outline=(*ink, 255), width=4)
    font = load_font(52, "display")
    iw, ih = text_size(initials, font)
    draw_stroked_text_layer(
        layer, (cx, cy), initials, font, (*ink, 255),
        stroke=(*accent, 255), stroke_width=2, anchor="mm",
    )
    canvas.alpha_composite(layer)


def _draw_neon_lockup(
    canvas: Image.Image,
    band: str,
    *,
    accent: tuple[int, int, int],
    ink: tuple[int, int, int],
) -> None:
    line1, line2 = _split_band_name(band)
    font = load_font(36, "display")
    y = 1180
    draw_stroked_text_layer(
        canvas, (48, y), line1, font, (*accent, 255),
        stroke=(255, 255, 255, 60), stroke_width=2,
    )
    if line2:
        draw_stroked_text_layer(
            canvas, (48, y + 44), line2, load_font(28, "display"), (*accent, 200),
            stroke=(0, 0, 0, 180), stroke_width=2,
        )


def _draw_serif_lockup(
    canvas: Image.Image,
    band: str,
    *,
    ink: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> None:
    line1, line2 = _split_band_name(band)
    font = load_font(42, "serif")
    cx = CANVAS[0] - 160
    cy = 150
    draw_stroked_text_layer(canvas, (cx, cy), line1, font, (*ink, 255), anchor="mm")
    if line2:
        draw_stroked_text_layer(
            canvas, (cx, cy + 38), line2, load_font(22, "typewriter"), (*accent, 255), anchor="mm",
        )


def _draw_display_lockup(
    canvas: Image.Image,
    band: str,
    *,
    ink: tuple[int, int, int],
    accent: tuple[int, int, int],
    paper: tuple[int, int, int] = (255, 255, 255),
) -> None:
    words = band.upper().split()
    if len(words) <= 2:
        text = band.upper()
        font = load_font(48, "display")
        draw_stroked_text_layer(
            canvas, (CANVAS[0] - 48, 120), text, font, (*accent, 255),
            stroke=(*ink, 255), stroke_width=2, anchor="rm",
        )
        return
    line1 = " ".join(words[:-1])
    line2 = words[-1]
    draw_stroked_text_layer(
        canvas, (CANVAS[0] - 48, 100), line1, load_font(40, "display"), (*ink, 255),
        stroke=(*paper, 255), stroke_width=1, anchor="rm",
    )
    draw_stroked_text_layer(
        canvas, (CANVAS[0] - 48, 148), line2, load_font(56, "display"), (*accent, 255),
        stroke=(*ink, 255), stroke_width=3, anchor="rm",
    )
