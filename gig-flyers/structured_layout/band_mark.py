"""Band logo placement — hero lockup in band zone, never cramped in headers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from structured_layout.graphic_primitives import (
    CANVAS,
    draw_stroked_text_layer,
    load_font,
)

ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "assets" / "logos"

# Generic badge zones for post-render logo overlay (wild + structured flyers).
BADGE_BOX_TOP_RIGHT = (744, 28, 1000, 132)
BADGE_BOX_FOOTER_LEFT = (48, 1420, 360, 1500)

# Band-name zone per Option C archetype (x1, y1, x2, y2) — logo replaces text here.
HERO_BOXES: dict[str, tuple[int, int, int, int]] = {
    "duotone_modern": (48, 688, 620, 808),
    "neon_bar": (48, 848, 976, 948),
    "pasteup_zine": (72, 808, 976, 908),
    "broadside": (48, 762, 560, 862),
    "country_fair": (96, 742, 928, 842),
    "boutique": (96, 48, 928, 168),
    "psychedelic": (96, 88, 928, 208),
    "xerox_punk": (48, 728, 976, 828),
}


@dataclass(frozen=True)
class LogoStyle:
    tint: tuple[int, int, int] | None = None
    opacity: float = 1.0
    glow: bool = False
    rotate: float = 0.0


def band_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def find_band_logo(band: str, *, paper: tuple[int, int, int] | None = None) -> Path | None:
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


def _crop_to_content(logo: Image.Image) -> Image.Image:
    bbox = logo.getbbox()
    if bbox:
        return logo.crop(bbox)
    return logo


def _load_logo(path: Path) -> Image.Image:
    return _crop_to_content(Image.open(path).convert("RGBA"))


def _style_for_archetype(style: str, paper: tuple[int, int, int], accent: tuple[int, int, int]) -> LogoStyle:
    if style == "xerox_punk":
        return LogoStyle(opacity=1.0)
    if style == "neon_bar":
        return LogoStyle(tint=accent, glow=True)
    if style == "pasteup_zine":
        return LogoStyle(rotate=-3.0)
    if style == "duotone_modern" and _luminance(paper) < 128:
        return LogoStyle(tint=accent)
    if _luminance(paper) < 128:
        return LogoStyle()  # light logo file already
    return LogoStyle()


def _tint_logo(logo: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    tinted = Image.new("RGBA", logo.size, (*color, 255))
    tinted.putalpha(logo.split()[3])
    return tinted


def _to_grayscale_logo(logo: Image.Image) -> Image.Image:
    gray = ImageEnhance.Contrast(logo.convert("L")).enhance(1.35)
    return Image.merge("RGBA", (gray, gray, gray, logo.split()[3]))


def _fit_logo_in_box(logo: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = box
    max_w, max_h = x2 - x1, y2 - y1
    ratio = min(max_w / logo.width, max_h / logo.height)
    nw = max(1, int(logo.width * ratio))
    nh = max(1, int(logo.height * ratio))
    return logo.resize((nw, nh), Image.Resampling.LANCZOS)


def _paste_in_box(
    canvas: Image.Image,
    logo: Image.Image,
    box: tuple[int, int, int, int],
    *,
    logo_style: LogoStyle,
) -> None:
    x1, y1, x2, y2 = box
    fitted = _fit_logo_in_box(logo, box)
    if logo_style.tint:
        fitted = _tint_logo(fitted, logo_style.tint)
    if logo_style.glow:
        glow = fitted.filter(ImageFilter.GaussianBlur(radius=4))
        ox = x1 + (x2 - x1 - fitted.width) // 2
        oy = y1 + (y2 - y1 - fitted.height) // 2
        canvas.alpha_composite(glow, (ox, oy))
    if logo_style.rotate:
        fitted = fitted.rotate(
            logo_style.rotate, expand=True, resample=Image.Resampling.BICUBIC,
        )
    if logo_style.opacity < 1.0:
        r, g, b, a = fitted.split()
        a = a.point(lambda v: int(v * logo_style.opacity))
        fitted = Image.merge("RGBA", (r, g, b, a))
    ox = x1 + (x2 - x1 - fitted.width) // 2
    oy = y1 + (y2 - y1 - fitted.height) // 2
    canvas.alpha_composite(fitted, (ox, oy))


def draw_band_hero(
    canvas: Image.Image,
    band: str,
    *,
    style: str,
    paper: tuple[int, int, int],
    accent: tuple[int, int, int],
    ink: tuple[int, int, int],
) -> bool:
    """Place logo in the archetype band-name zone. Returns True if logo replaced text."""
    logo_path = find_band_logo(band, paper=paper)
    box = HERO_BOXES.get(style)
    if logo_path is None or box is None:
        return False
    logo = _load_logo(logo_path)
    if style == "xerox_punk":
        logo = _to_grayscale_logo(logo)
    logo_style = _style_for_archetype(style, paper, accent)
    _paste_in_box(canvas, logo, box, logo_style=logo_style)
    return True


def draw_band_watermark(
    canvas: Image.Image,
    band: str,
    *,
    paper: tuple[int, int, int],
    seed: int = 0,
) -> None:
    """Large faint centered watermark — xerox only, behind content."""
    logo_path = find_band_logo(band, paper=paper)
    if logo_path is None:
        return
    logo = _to_grayscale_logo(_load_logo(logo_path))
    box = (120, 280, CANVAS[0] - 120, 680)
    _paste_in_box(
        canvas, logo, box,
        logo_style=LogoStyle(opacity=0.14),
    )


def draw_band_logo_badge(
    canvas: Image.Image,
    band: str,
    *,
    box: tuple[int, int, int, int],
    paper: tuple[int, int, int],
) -> bool:
    logo_path = find_band_logo(band, paper=paper)
    if logo_path is None:
        return False
    _paste_in_box(canvas, _load_logo(logo_path), box, logo_style=LogoStyle())
    return True


# Backward compat — redirects to hero placement
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
    if style == "xerox_punk":
        draw_band_watermark(canvas, band, paper=paper, seed=seed)
    else:
        draw_band_hero(canvas, band, style=style, paper=paper, accent=accent, ink=ink)
