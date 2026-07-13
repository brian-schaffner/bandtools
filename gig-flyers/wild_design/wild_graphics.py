"""Procedural western/outlaw graphics for wild D PIL composite (outside photo bbox)."""

from __future__ import annotations

import math
import random
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


def grain_overlay(base: Image.Image, *, seed: int = 0, strength: float = 0.12) -> Image.Image:
    del seed
    noise = Image.effect_noise(base.size, 24).convert("L")
    grain = Image.merge("RGB", (noise, noise, noise))
    return ImageChops.blend(base, grain, min(0.35, strength))


def rust_stains(draw: ImageDraw.ImageDraw, size: tuple[int, int], *, seed: int) -> None:
    rng = random.Random(seed + 3)
    w, h = size
    for _ in range(6):
        cx = rng.randint(0, w)
        cy = rng.randint(0, h)
        rw = rng.randint(80, 220)
        rh = rng.randint(40, 120)
        color = (rng.randint(90, 120), rng.randint(30, 50), rng.randint(18, 32))
        draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=color)


def draw_barbed_wire(
    draw: ImageDraw.ImageDraw,
    y: int,
    width: int,
    *,
    margin: int = 40,
    color: tuple[int, int, int] = (160, 145, 120),
) -> None:
    x0, x1 = margin, width - margin
    draw.line([(x0, y), (x1, y)], fill=color, width=2)
    step = 28
    for x in range(x0, x1, step):
        draw.arc([x - 8, y - 10, x + 8, y + 6], 200, 340, fill=color, width=2)
        draw.line([(x, y), (x + 4, y - 14)], fill=color, width=2)


def draw_star_badge(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    *,
    radius: int = 14,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    cx, cy = center
    points: list[tuple[int, int]] = []
    for i in range(10):
        ang = i * 36 - 90
        r = radius if i % 2 == 0 else radius // 2
        rad = math.radians(ang)
        points.append((int(cx + r * math.cos(rad)), int(cy + r * math.sin(rad))))
    draw.polygon(points, fill=fill, outline=outline)


def torn_rectangle_points(
    left: int,
    top: int,
    right: int,
    bottom: int,
    *,
    seed: int,
    jitter: int = 8,
) -> list[tuple[int, int]]:
    rng = random.Random(seed)

    def j(v: int) -> int:
        return v + rng.randint(-jitter, jitter)

    return [
        (j(left), j(top)),
        (j(right), j(top)),
        (j(right), j(bottom)),
        (j(left), j(bottom)),
    ]


def draw_perforation(
    draw: ImageDraw.ImageDraw,
    y: int,
    x0: int,
    x1: int,
    *,
    color: tuple[int, int, int],
) -> None:
    for x in range(x0 + 6, x1 - 6, 14):
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)


def text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    shadow: tuple[int, int, int] = (30, 18, 10),
    offset: int = 3,
) -> None:
    x, y = xy
    draw.text((x + offset, y + offset), text, fill=shadow, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def centered_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    shadow: tuple[int, int, int] = (30, 18, 10),
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = max(0, (width - tw) // 2)
    text_with_shadow(draw, (x, y), text, font=font, fill=fill, shadow=shadow)


def try_serif_font(size: int, *, bold: bool = True) -> ImageFont.ImageFont:
    names = (
        ("DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf")
        if bold
        else ("DejaVuSerif.ttf", "LiberationSerif-Regular.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    for name in ("DejaVuSans-Bold.ttf",):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
