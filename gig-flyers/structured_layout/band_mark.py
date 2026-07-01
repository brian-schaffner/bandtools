"""Band logo / name mark — asset files + archetype-aware placement."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

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


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def find_band_logo(band: str, *, paper: tuple[int, int, int] | None = None) -> Path | None:
    """Return logo PNG for band — light or dark variant matched to background."""
    slug = band_slug(band)
    if paper is not None and _luminance(paper) < 128:
        for name in (f"{slug}-light.png", f"{slug}-light.webp", "lindsey-lane-band-light.png"):
            path = LOGO_DIR / name
            if path.is_file():
                return path
    for stem in (slug, slug.replace("-band", "")):
        for suffix in ("", "-dark"):
            for ext in (".png", ".webp"):
                path = LOGO_DIR / f"{stem}{suffix}{ext}"
                if path.is_file():
                    return path
    return None


def band_initials(band: str) -> str:
    skip = {"the", "band", "at", "featuring", "feat", "presents"}
    words = [w for w in re.split(r"\s+", band.strip()) if w.lower() not in skip]
    return "".join(w[0].upper() for w in words[:3]) or "?"


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
    """Place real logo asset or procedural fallback."""
    logo = find_band_logo(band, paper=paper)
    if logo is not None:
        _paste_logo_mark(canvas, logo, style=style, seed=seed, paper=paper, accent=accent)
        return
    _draw_monogram(canvas, band, ink=ink, accent=accent, paper=paper)


def _load_logo_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _tint_logo(logo: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """Recolor opaque logo pixels (keeps alpha)."""
    gray = logo.convert("L")
    tinted = Image.new("RGBA", logo.size, (*color, 255))
    tinted.putalpha(logo.split()[3])
    return tinted


def _placement(style: str, seed: int, nw: int, nh: int, paper: tuple[int, int, int]) -> tuple[int, int, float, float]:
    """Return x, y, scale, opacity for archetype."""
    dark_field = _luminance(paper) < 100
    placements: dict[str, tuple[float, float, float, float]] = {
        "xerox_punk": (0.06, 0.04, 0.42, 0.92),
        "duotone_modern": (0.52, 0.03, 0.48, 1.0),
        "psychedelic": (0.28, 0.02, 0.44, 0.88),
        "boutique": (0.22, 0.05, 0.38, 0.95),
        "neon_bar": (0.08, 0.05, 0.52, 1.0),
        "pasteup_zine": (0.05, 0.06, 0.40, 0.90),
        "broadside": (0.06, 0.52, 0.36, 0.95),
        "country_fair": (0.30, 0.12, 0.40, 1.0),
    }
    px, py, scale, opacity = placements.get(style, (0.06, 0.04, 0.40, 0.95))
    if seed % 3 == 0 and style not in ("broadside", "neon_bar"):
        px = 1.0 - px - (nw * scale / CANVAS[0])
    return int(CANVAS[0] * px), int(CANVAS[1] * py), scale, opacity


def _paste_logo_mark(
    canvas: Image.Image,
    logo_path: Path,
    *,
    style: str,
    seed: int,
    paper: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> None:
    logo = _load_logo_rgba(logo_path)
    max_w = 420 if style in ("neon_bar", "broadside", "country_fair") else 340
    ratio = min(max_w / logo.width, 130 / logo.height)
    nw, nh = max(1, int(logo.width * ratio)), max(1, int(logo.height * ratio))
    logo = logo.resize((nw, nh), Image.Resampling.LANCZOS)

    if style == "xerox_punk":
        logo = _to_grayscale_logo(logo)
    elif style == "neon_bar":
        logo = _tint_logo(logo, accent)
        glow = logo.filter(ImageFilter.GaussianBlur(radius=3))
        logo = Image.alpha_composite(glow, logo)
    elif style == "duotone_modern" and _luminance(paper) > 128:
        logo = _tint_logo(logo, (15, 15, 15))

    x, y, scale, opacity = _placement(style, seed, nw, nh, paper)
    if scale != 1.0:
        nw2, nh2 = int(nw * scale), int(nh * scale)
        logo = logo.resize((nw2, nh2), Image.Resampling.LANCZOS)
        nw, nh = nw2, nh2

    if style == "xerox_punk":
        # Watermark behind content — large, centered upper
        nw, nh = int(nw * 1.15), int(nh * 1.15)
        logo = logo.resize((nw, nh), Image.Resampling.LANCZOS)
        x = (CANVAS[0] - nw) // 2
        y = 200
        opacity = 0.18

    if opacity < 1.0:
        r, g, b, a = logo.split()
        a = a.point(lambda v: int(v * opacity))
        logo = Image.merge("RGBA", (r, g, b, a))

    if style == "pasteup_zine":
        logo = logo.rotate(-4, expand=True, resample=Image.Resampling.BICUBIC)

    canvas.alpha_composite(logo, (x, y))


def _to_grayscale_logo(logo: Image.Image) -> Image.Image:
    gray = ImageEnhance.Contrast(logo.convert("L")).enhance(1.4)
    return Image.merge("RGBA", (gray, gray, gray, logo.split()[3]))


def draw_band_logo_badge(
    canvas: Image.Image,
    band: str,
    *,
    box: tuple[int, int, int, int],
    paper: tuple[int, int, int],
) -> bool:
    """Option B — compact logo in a layout region. Returns True if placed."""
    logo_path = find_band_logo(band, paper=paper)
    if logo_path is None:
        return False
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    logo = _load_logo_rgba(logo_path)
    ratio = min(bw / logo.width, bh / logo.height)
    nw, nh = max(1, int(logo.width * ratio)), max(1, int(logo.height * ratio))
    logo = logo.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = x1 + (bw - nw) // 2
    oy = y1 + (bh - nh) // 2
    canvas.alpha_composite(logo, (ox, oy))
    return True


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
    draw_stroked_text_layer(
        layer, (cx, cy), initials, font, (*ink, 255),
        stroke=(*accent, 255), stroke_width=2, anchor="mm",
    )
    canvas.alpha_composite(layer)
