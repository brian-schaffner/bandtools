"""Shared graphic primitives for Option C — display type, textures, accents."""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSET_FONTS = ROOT / "assets" / "fonts"
CANVAS = (1024, 1536)

FONT_DISPLAY = (
    ASSET_FONTS / "BebasNeue-Regular.ttf",
    "/usr/share/fonts/truetype/oswald/Oswald-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
FONT_BODY = (
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
FONT_TYPEWRITER = (
    ASSET_FONTS / "SpecialElite-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
)
FONT_SERIF = (
    ASSET_FONTS / "PlayfairDisplay-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
)


def load_font(size: int, role: str = "display") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = {
        "display": FONT_DISPLAY,
        "body": FONT_BODY,
        "typewriter": FONT_TYPEWRITER,
        "serif": FONT_SERIF,
    }.get(role, FONT_DISPLAY)
    for p in paths:
        path = Path(p)
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def text_size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_stroked_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, ...],
    *,
    stroke: tuple[int, ...] = (0, 0, 0),
    stroke_width: int = 3,
    anchor: str | None = None,
) -> None:
    x, y = xy
    if stroke_width > 0:
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx * dx + dy * dy > stroke_width * stroke_width:
                    continue
                kwargs = {"font": font, "fill": stroke}
                if anchor:
                    kwargs["anchor"] = anchor
                draw.text((x + dx, y + dy), text, **kwargs)
    kwargs = {"font": font, "fill": fill}
    if anchor:
        kwargs["anchor"] = anchor
    draw.text((x, y), text, **kwargs)


def draw_stroked_text_layer(
    canvas: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, ...],
    *,
    stroke: tuple[int, ...] = (0, 0, 0),
    stroke_width: int = 3,
    anchor: str | None = None,
) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_stroked_text(
        ImageDraw.Draw(layer), xy, text, font, fill,
        stroke=stroke, stroke_width=stroke_width, anchor=anchor,
    )
    canvas.alpha_composite(layer)


def grain(img: Image.Image, strength: float = 0.08, seed: int = 7) -> Image.Image:
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


def halftone_dots(
    size: tuple[int, int],
    *,
    bg: tuple[int, int, int],
    dot: tuple[int, int, int],
    spacing: int = 14,
    seed: int = 0,
) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGBA", size, (*bg, 255))
    draw = ImageDraw.Draw(img)
    for y in range(0, size[1], spacing):
        for x in range(0, size[0], spacing):
            jitter = rng.randint(-2, 2)
            r = max(2, spacing // 4 + jitter)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*dot, 180))
    return img


def draw_starburst(
    canvas: Image.Image,
    cx: int,
    cy: int,
    outer_r: int,
    *,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] | None = None,
    spikes: int = 12,
) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    inner_r = max(4, outer_r // 3)
    points: list[tuple[float, float]] = []
    for i in range(spikes * 2):
        angle = math.pi * i / spikes - math.pi / 2
        radius = outer_r if i % 2 == 0 else inner_r
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=fill, outline=outline)
    canvas.alpha_composite(layer)


def draw_tape_strip(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    *,
    color: tuple[int, int, int, int] = (212, 196, 160, 200),
    rotation: float = -4.0,
) -> None:
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle([x1, y1, x2, y2], fill=color)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    layer = layer.rotate(rotation, center=(cx, cy), resample=Image.Resampling.BICUBIC)
    canvas.alpha_composite(layer)


def draw_diagonal_band(
    canvas: Image.Image,
    *,
    color: tuple[int, int, int, int],
    y_center: int,
    height: int = 180,
    angle: float = -8.0,
) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rectangle([0, y_center - height // 2, canvas.width, y_center + height // 2], fill=color)
    layer = layer.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    canvas.alpha_composite(layer)


def load_photo(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    photo = Image.open(path).convert("RGBA")
    ratio = min(w / photo.width, h / photo.height)
    nw, nh = max(1, int(photo.width * ratio)), max(1, int(photo.height * ratio))
    photo = photo.resize((nw, nh), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(photo, ((w - nw) // 2, (h - nh) // 2), photo)
    return layer


def threshold_photo(photo: Image.Image, cutoff: int = 140) -> Image.Image:
    gray = photo.convert("L")
    bw = gray.point(lambda x: 255 if x > cutoff else 0)
    return Image.merge("RGBA", (bw, bw, bw, photo.split()[3]))


def duotone_photo(
    photo: Image.Image,
    shadow: tuple[int, int, int],
    highlight: tuple[int, int, int],
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


def oval_mask_photo(photo: Image.Image) -> Image.Image:
    mask = Image.new("L", photo.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, photo.width, photo.height], fill=255)
    photo = photo.copy()
    photo.putalpha(mask)
    return photo


def torn_paste(canvas: Image.Image, photo: Image.Image, xy: tuple[int, int], *, seed: int) -> None:
    from structured_layout.structured_renderer import _apply_torn_edge_mask

    treated = _apply_torn_edge_mask(photo, seed=seed)
    canvas.paste(treated, xy, treated)


def halftone_photo(photo: Image.Image, dot_size: int = 5) -> Image.Image:
    from structured_layout.structured_renderer import _apply_halftone

    rgb = _apply_halftone(photo.convert("RGB"), dot_size)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(photo.split()[3])
    return rgba


def concentric_rings(
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


def compact_day(date: str) -> str:
    parts = date.replace(",", "").split()
    if len(parts) >= 3:
        return f"{parts[1][:3].upper()} {parts[2]}"
    return date[:12].upper()


def save_rgb(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path)
