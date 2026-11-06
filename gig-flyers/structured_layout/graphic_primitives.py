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


def draw_corner_strip(
    canvas: Image.Image,
    *,
    corner: str,
    size: tuple[int, int],
    color: tuple[int, int, int, int],
) -> None:
    w, h = size
    cw, ch = canvas.size
    anchors = {
        "top_left": (0, 0),
        "top_right": (cw - w, 0),
        "bottom_left": (0, ch - h),
        "bottom_right": (cw - w, ch - h),
    }
    x, y = anchors.get(corner, (0, 0))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if corner == "top_left":
        points = [(x, y), (x + w, y), (x, y + h)]
    elif corner == "top_right":
        points = [(x + w, y), (x + w, y + h), (x, y)]
    elif corner == "bottom_left":
        points = [(x, y + h), (x, y), (x + w, y + h)]
    else:
        points = [(x + w, y + h), (x, y + h), (x + w, y)]
    draw.polygon(points, fill=color)
    canvas.alpha_composite(layer)


def draw_ticket_stub(
    canvas: Image.Image,
    *,
    box: tuple[int, int, int, int],
    edge: str = "right",
    perforations: int = 14,
    color: tuple[int, int, int, int] = (80, 80, 80, 180),
) -> None:
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rectangle([x1, y1, x2, y2], fill=(*color[:3], min(40, color[3])))
    draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
    edge_x = x2 if edge == "right" else x1
    step = max(4, (y2 - y1) // max(1, perforations))
    for i in range(perforations):
        py = y1 + i * step
        if py > y2:
            break
        draw.ellipse([edge_x - 2, py, edge_x + 2, py + 4], fill=color)
    draw.line([edge_x, y1, edge_x, y2], fill=color, width=1)
    canvas.alpha_composite(layer)


def draw_double_rule(
    canvas: Image.Image,
    *,
    y: int,
    x1: int = 48,
    x2: int | None = None,
    color: tuple[int, int, int, int],
    gap: int = 6,
) -> None:
    if x2 is None:
        x2 = canvas.width - 48
    draw = ImageDraw.Draw(canvas)
    draw.line([(x1, y), (x2, y)], fill=color, width=2)
    draw.line([(x1, y + gap), (x2, y + gap)], fill=(*color[:3], max(80, color[3] // 2)), width=1)


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


def draw_bubbly_stacked_text(
    canvas: Image.Image,
    origin: tuple[int, int],
    lines: list[str],
    *,
    font_size: int = 52,
    fill: tuple[int, int, int, int],
    stroke: tuple[int, int, int, int] = (17, 17, 17, 255),
    stroke_width: int = 5,
    line_gap: int = 8,
    anchor: str = "rm",
) -> None:
    """Thick stroked display lines — festival poster hook typography."""
    font = load_font(font_size, "display")
    x, y = origin
    for line in lines:
        draw_stroked_text_layer(
            canvas, (x, y), line.upper(), font, fill,
            stroke=stroke, stroke_width=stroke_width, anchor=anchor,
        )
        y += font_size + line_gap


def draw_psychedelic_swirls(
    canvas: Image.Image,
    bbox: tuple[int, int, int, int],
    *,
    colors: tuple[tuple[int, int, int], tuple[int, int, int]],
    seed: int = 0,
) -> None:
    """Floral/teardrop swirls behind festival hero art."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    for _ in range(14):
        color = colors[rng.randint(0, 1)]
        rx = rng.randint(40, max(41, (x2 - x1) // 2))
        ry = rng.randint(30, max(31, (y2 - y1) // 2))
        ox = rng.randint(x1 + 20, max(x1 + 21, x2 - 20))
        oy = rng.randint(y1 + 20, max(y1 + 21, y2 - 20))
        draw.ellipse([ox - rx, oy - ry, ox + rx, oy + ry], outline=(*color, 220), width=rng.randint(3, 6))
        draw.pieslice([ox - rx, oy - ry, ox + rx, oy + ry], start=rng.randint(0, 180), end=rng.randint(181, 360), fill=(*color, 90))
    for _ in range(8):
        color = colors[rng.randint(0, 1)]
        px, py = rng.randint(x1, x2), rng.randint(y1, y2)
        r = rng.randint(8, 18)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(*color, 200))
    layer.putalpha(layer.split()[3].point(lambda a: int(a * 0.85)))
    canvas.alpha_composite(layer)


def draw_festival_bird_guitar(
    canvas: Image.Image,
    bbox: tuple[int, int, int, int],
    *,
    cream: tuple[int, int, int] = (255, 248, 235),
    blue: tuple[int, int, int] = (21, 101, 192),
    yellow: tuple[int, int, int] = (245, 196, 0),
    seed: int = 0,
) -> None:
    """Original symbolic hero — bird on guitar neck (Woodstock-inspired, not a copy)."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = bbox
    gx = x1 + int((x2 - x1) * 0.08)
    gy = y1 + int((y2 - y1) * 0.42)
    neck_w = int((x2 - x1) * 0.72)
    neck_h = max(18, int((y2 - y1) * 0.07))
    draw.rounded_rectangle([gx, gy, gx + neck_w, gy + neck_h], radius=neck_h // 2, fill=(*blue, 255))

    bx = gx + int(neck_w * 0.18)
    by = gy - int((y2 - y1) * 0.22)
    bw, bh = int((x2 - x1) * 0.28), int((y2 - y1) * 0.18)
    draw.ellipse([bx, by, bx + bw, by + bh], fill=(*cream, 255))
    draw.polygon(
        [(bx + bw, by + bh // 2), (bx + bw + bw // 4, by + bh // 2 - 6), (bx + bw + bw // 4, by + bh // 2 + 6)],
        fill=(*cream, 255),
    )
    draw.ellipse([bx + bw // 6, by + bh // 4, bx + bw // 6 + 10, by + bh // 4 + 10], fill=(211, 47, 47, 255))
    draw.line([(bx + bw // 3, by + bh), (bx + bw // 3, gy - 4)], fill=(*yellow, 255), width=3)

    hx = gx + int(neck_w * 0.04)
    hy = gy + neck_h + 8
    for i in range(4):
        fw = int(neck_w * 0.14)
        fh = int((y2 - y1) * 0.11)
        fx = hx + i * int(fw * 0.72) + rng.randint(-4, 4)
        draw.rounded_rectangle([fx, hy, fx + fw, hy + fh], radius=12, fill=(*yellow, 255))

    head_x = gx + neck_w + 8
    head_y = gy - neck_h
    draw.rounded_rectangle(
        [head_x, head_y, head_x + int(neck_w * 0.22), gy + neck_h * 2],
        radius=10,
        fill=(46, 125, 50, 255),
    )
    for i in range(3):
        px = head_x + 12 + i * 14
        draw.ellipse([px, head_y + 8, px + 8, head_y + 24], fill=(*blue, 255))
    canvas.alpha_composite(layer)


def draw_three_column_footer(
    canvas: Image.Image,
    *,
    y_top: int,
    columns: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    colors: tuple[tuple[int, int, int, int], tuple[int, int, int, int], tuple[int, int, int, int]],
    fonts: tuple[int, int, int] = (20, 24, 28),
) -> None:
    """Festival bill footer — lineup | logistics | headliner hints."""
    w = canvas.width
    col_w = (w - 96) // 3
    xs = (48, 48 + col_w + 12, 48 + 2 * (col_w + 12))
    for col_idx, (lines, color, size) in enumerate(zip(columns, colors, fonts)):
        font = load_font(size, "display" if col_idx == 2 else "body")
        y = y_top
        for line in lines:
            if not line:
                continue
            draw_stroked_text_layer(canvas, (xs[col_idx], y), line.upper(), font, color)
            y += size + 10


def save_rgb(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path)
