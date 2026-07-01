"""Style DNA renderers — designed archetype templates for Option C (PIL only).

Each archetype is a hand-tuned layout with fixed hierarchy and no text overlap.
Seeded archetype selection per gig/round via pick_creative_archetype().
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from structured_layout.layout_spec import LayoutSpec

CANVAS = (1024, 1536)

CREATIVE_ARCHETYPE_KEYS = (
    "xerox_punk",
    "duotone_modern",
    "psychedelic",
    "boutique",
)

STYLE_DNA_PREFIX = "style dna"


def is_style_dna_layout(layout: LayoutSpec) -> bool:
    return STYLE_DNA_PREFIX in (layout.style_notes or "").lower()


def parse_style_dna_archetype(layout: LayoutSpec) -> str | None:
    notes = (layout.style_notes or "").lower()
    for key in CREATIVE_ARCHETYPE_KEYS:
        if key in notes:
            return key
    return None


def pick_creative_archetype(rng: random.Random) -> str:
    """Deterministic archetype pick for Option C."""
    return CREATIVE_ARCHETYPE_KEYS[rng.randint(0, len(CREATIVE_ARCHETYPE_KEYS) - 1)]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in paths:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _load_photo(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    photo = Image.open(path).convert("RGBA")
    ratio = min(w / photo.width, h / photo.height)
    nw, nh = max(1, int(photo.width * ratio)), max(1, int(photo.height * ratio))
    photo = photo.resize((nw, nh), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(photo, ((w - nw) // 2, (h - nh) // 2), photo)
    return layer


def _threshold_photo(photo: Image.Image, cutoff: int = 140) -> Image.Image:
    gray = photo.convert("L")
    bw = gray.point(lambda x: 255 if x > cutoff else 0)
    rgba = Image.merge("RGBA", (bw, bw, bw, photo.split()[3]))
    return rgba


def _duotone_photo(
    photo: Image.Image, shadow: tuple[int, int, int], highlight: tuple[int, int, int]
) -> Image.Image:
    gray = photo.convert("L")
    out = Image.new("RGBA", photo.size)
    px = out.load()
    gp = gray.load()
    alpha = photo.split()[3].load()
    for y in range(photo.height):
        for x in range(photo.width):
            if alpha[x, y] < 16:
                continue
            t = gp[x, y] / 255.0
            r = int(shadow[0] + (highlight[0] - shadow[0]) * t)
            g = int(shadow[1] + (highlight[1] - shadow[1]) * t)
            b = int(shadow[2] + (highlight[2] - shadow[2]) * t)
            px[x, y] = (r, g, b, alpha[x, y])
    return out


def _grain(img: Image.Image, strength: float = 0.08, seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    rgba = img.convert("RGBA")
    px = rgba.load()
    for y in range(0, rgba.height, 2):
        for x in range(0, rgba.width, 2):
            r, g, b, a = px[x, y]
            if a < 16:
                continue
            n = rng.randint(-int(30 * strength), int(30 * strength))
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
                a,
            )
    return rgba


def _concentric_rings(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    colors: list[tuple[int, int, int]],
    max_r: int,
    step: int,
) -> None:
    for i, r in enumerate(range(max_r, 0, -step)):
        c = colors[i % len(colors)]
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)


def _seed_from_layout(layout: LayoutSpec) -> int:
    match = re.search(r"seed (\d+)", layout.style_notes or "")
    return int(match.group(1)) if match else 42


def _facts_from_layout(layout: LayoutSpec) -> dict[str, str]:
    ordered = [t.content for t in sorted(layout.text_elements, key=lambda t: (t.y, t.x))]
    venue = ordered[0] if len(ordered) > 0 else ""
    band = ordered[1] if len(ordered) > 1 else ""
    date = ordered[2] if len(ordered) > 2 else ""
    time = ordered[3] if len(ordered) > 3 else ""
    address = ordered[4] if len(ordered) > 4 else ""
    return {
        "venue": venue,
        "band": band,
        "date": date,
        "time": time,
        "address": address,
    }


def render_style_dna_xerox(
    *,
    venue: str,
    band: str,
    date: str,
    time: str,
    address: str,
    photo_path: Path,
    out_path: Path,
    seed: int = 7,
) -> None:
    """Xerox / punk — high-threshold photo, black footer, single hierarchy."""
    img = Image.new("RGBA", CANVAS, (235, 228, 210, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([24, 24, CANVAS[0] - 24, CANVAS[1] - 24], outline=(20, 20, 20), width=4)
    draw.text((48, 36), "PRESENTS", font=_font(22), fill=(30, 30, 30))

    photo_box = (80, 120, 944, 720)
    photo = _threshold_photo(_load_photo(photo_path, photo_box))
    img.paste(photo, (photo_box[0], photo_box[1]), photo)

    draw.text((48, 760), band.upper(), font=_font(72), fill=(15, 15, 15))
    draw.line([(48, 850), (976, 850)], fill=(15, 15, 15), width=3)
    draw.text((48, 870), date.upper(), font=_font(36), fill=(15, 15, 15))
    draw.text((48, 920), time.upper(), font=_font(48), fill=(15, 15, 15))

    draw.rectangle([0, 1280, CANVAS[0], CANVAS[1]], fill=(12, 12, 12))
    draw.text((48, 1310), venue.upper(), font=_font(40), fill=(245, 245, 245))
    draw.text((48, 1370), address, font=_font(24, bold=False), fill=(200, 200, 200))

    _grain(img, 0.12, seed=seed).convert("RGB").save(out_path)


def render_style_dna_duotone(
    *,
    venue: str,
    band: str,
    date: str,
    time: str,
    address: str,
    photo_path: Path,
    out_path: Path,
    seed: int = 7,
) -> None:
    """Modern duotone grid — yellow/black panels."""
    yellow = (245, 197, 24)
    black = (12, 12, 12)
    img = Image.new("RGBA", CANVAS, (*yellow, 255))
    draw = ImageDraw.Draw(img)

    for i in range(0, CANVAS[0], 40):
        draw.rectangle([i, 0, i + 28, 18], fill=black)

    draw.text((48, 48), venue.upper(), font=_font(56), fill=black)

    panels = [(48, 200, 320, 680), (352, 200, 624, 680), (656, 200, 928, 680)]
    for box in panels:
        duotone = _duotone_photo(_load_photo(photo_path, box), black, yellow)
        img.paste(duotone, (box[0], box[1]), duotone)

    draw.text((48, 720), band.upper(), font=_font(80), fill=black)
    parts = date.replace(",", "").split()
    day_str = f"{parts[1][:3].upper()} {parts[2]}" if len(parts) >= 3 else date[:12]
    draw.text((48, 820), day_str, font=_font(64), fill=black)
    draw.text((48, 900), time.upper(), font=_font(52), fill=black)

    draw.rectangle([0, 1320, CANVAS[0], CANVAS[1]], fill=black)
    draw.text((48, 1360), address, font=_font(28), fill=yellow)

    _grain(img, 0.06, seed=seed).convert("RGB").save(out_path)


def render_style_dna_psychedelic(
    *,
    venue: str,
    band: str,
    date: str,
    time: str,
    address: str,
    photo_path: Path,
    out_path: Path,
    seed: int = 7,
) -> None:
    """Fillmore-lite — concentric rings, oval photo."""
    _ = seed
    magenta = (199, 21, 133)
    cream = (255, 250, 240)
    black = (10, 10, 10)
    img = Image.new("RGBA", CANVAS, (*cream, 255))
    draw = ImageDraw.Draw(img)

    draw.rectangle([60, 80, CANVAS[0] - 60, CANVAS[1] - 120], fill=magenta)
    draw.rectangle([80, 100, CANVAS[0] - 80, CANVAS[1] - 140], fill=black)

    _concentric_rings(draw, CANVAS[0] // 2, 620, [magenta, black, cream], 380, 36)

    photo_box = (212, 480, 812, 880)
    photo = _load_photo(photo_path, photo_box)
    mask = Image.new("L", (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, mask.width, mask.height], fill=255)
    photo.putalpha(mask)
    img.paste(photo, (photo_box[0], photo_box[1]), photo)

    draw.text((CANVAS[0] // 2 - 280, 160), band.upper(), font=_font(64), fill=cream)
    draw.text((CANVAS[0] // 2 - 200, 980), venue.upper(), font=_font(44), fill=cream)
    draw.text((CANVAS[0] // 2 - 180, 1060), date.upper()[:28], font=_font(28), fill=cream)
    draw.text((CANVAS[0] // 2 - 80, 1120), time.upper(), font=_font(36), fill=magenta)

    draw.text((100, CANVAS[1] - 90), address, font=_font(20, bold=False), fill=black)

    img.convert("RGB").save(out_path)


def render_style_dna_boutique(
    *,
    venue: str,
    band: str,
    date: str,
    time: str,
    address: str,
    photo_path: Path,
    out_path: Path,
    seed: int = 7,
) -> None:
    """Boutique / picnic — designed community template."""
    _ = seed
    cream = (250, 245, 235)
    navy = (25, 42, 86)
    brick = (168, 58, 42)
    img = Image.new("RGBA", CANVAS, (*cream, 255))
    draw = ImageDraw.Draw(img)

    for x in range(40, CANVAS[0] - 40, 70):
        draw.line([(x, 30), (x + 35, 50)], fill=(180, 160, 120), width=2)
        draw.ellipse([x + 30, 46, x + 46, 62], fill=(255, 230, 180))

    band_upper = band.upper()
    draw.text((CANVAS[0] // 2 - min(280, len(band_upper) * 8), 70), band_upper, font=_font(48), fill=navy)

    photo_box = (112, 200, 912, 720)
    photo = _load_photo(photo_path, photo_box)
    img.paste(photo, (photo_box[0], photo_box[1]), photo)

    draw.rounded_rectangle((80, 760, 944, 1080), radius=12, fill=(210, 180, 140), outline=navy, width=3)
    draw.text((120, 790), venue.upper(), font=_font(32), fill=navy)
    draw.text((120, 850), "LIVE MUSIC", font=_font(72), fill=brick)

    parts = date.replace(",", "").split()
    if len(parts) >= 3:
        draw.text((120, 960), f"{parts[1][:3].upper()} {parts[2]}", font=_font(56), fill=navy)
        if len(parts) >= 4:
            draw.text((380, 970), parts[3], font=_font(36), fill=brick)
    draw.text((120, 1030), time.upper(), font=_font(32), fill=navy)

    draw.rectangle([0, 1420, CANVAS[0], CANVAS[1]], fill=navy)
    draw.text(
        (CANVAS[0] // 2 - 280, 1460),
        "Live Music  ·  Good Food  ·  Great Community",
        font=_font(24),
        fill=cream,
    )
    draw.text((120, 1380), address, font=_font(22, bold=False), fill=navy)

    img.convert("RGB").save(out_path)


_RENDERERS: dict[str, Callable[..., None]] = {
    "xerox_punk": render_style_dna_xerox,
    "duotone_modern": render_style_dna_duotone,
    "psychedelic": render_style_dna_psychedelic,
    "boutique": render_style_dna_boutique,
}


def render_style_dna_archetype(
    archetype: str,
    *,
    venue: str,
    band: str,
    date: str,
    time: str,
    address: str,
    photo_path: Path,
    out_path: Path,
    seed: int = 7,
) -> None:
    fn = _RENDERERS.get(archetype)
    if fn is None:
        raise ValueError(f"Unknown Style DNA archetype: {archetype}")
    fn(
        venue=venue,
        band=band,
        date=date,
        time=time,
        address=address,
        photo_path=photo_path,
        out_path=out_path,
        seed=seed,
    )


def render_style_dna_from_layout(
    layout: LayoutSpec,
    photo_path: Path,
    output_path: Path,
) -> None:
    """Render Option C from a Style DNA layout stub."""
    archetype = parse_style_dna_archetype(layout)
    if not archetype:
        raise ValueError(f"Not a Style DNA layout: {layout.style_notes!r}")
    facts = _facts_from_layout(layout)
    render_style_dna_archetype(
        archetype,
        venue=facts["venue"],
        band=facts["band"],
        date=facts["date"],
        time=facts["time"],
        address=facts["address"],
        photo_path=photo_path,
        out_path=output_path,
        seed=_seed_from_layout(layout),
    )
