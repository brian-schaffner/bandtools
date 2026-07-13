"""Hypothesis C — decomposed wild poster: graphics layer + PIL band photo paste."""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from image_providers.reference_compose import (
    CANVAS_BACKGROUND,
    ComposeResult,
    _build_photo_layer,
    parse_output_size,
    protection_zone,
)
from gig_calendar import GigEvent

# Layout palette — western bar flyer
WOOD_DARK = (48, 32, 22)
WOOD_MID = (72, 50, 34)
CREAM = (248, 242, 230)
CREAM_DARK = (228, 210, 185)
INK = (22, 16, 10)
RUST = (140, 38, 28)
GOLD = (186, 158, 108)


def _wood_background(size: tuple[int, int], seed: int = 42) -> Image.Image:
    rng = random.Random(seed)
    w, h = size
    base = Image.new("RGB", size, WOOD_DARK)
    draw = ImageDraw.Draw(base)
    for y in range(0, h, 5):
        shade = 38 + rng.randint(0, 28)
        draw.line([(0, y), (w, y)], fill=(shade, shade - 8, shade - 14), width=5)
    vignette = Image.new("L", size, 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse([-w // 4, -h // 6, w + w // 4, h + h // 6], fill=255)
    dark = Image.new("RGB", size, (0, 0, 0))
    return Image.composite(base, dark, vignette.filter(ImageFilter.GaussianBlur(radius=80)))


def _try_font(size: int, *, bold: bool = True) -> ImageFont.ImageFont:
    names = (
        ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")
        if bold
        else ("DejaVuSans.ttf", "LiberationSans-Regular.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    start_size: int,
    min_size: int,
    max_width: int,
    bold: bool = True,
) -> ImageFont.ImageFont:
    size = start_size
    while size >= min_size:
        font = _try_font(size, bold=bold)
        if _text_width(draw, text, font) <= max_width:
            return font
        size -= 2
    return _try_font(min_size, bold=bold)


def _clean_band_name(title: str, venue: str = "") -> str:
    """Band name only — strip embedded venue suffixes from calendar titles."""
    t = (title or "Live Music").strip()
    if venue:
        suffix = f" at {venue}"
        if t.lower().endswith(suffix.lower()):
            t = t[: -len(suffix)].strip()
    if " at " in t.lower():
        t = re.split(r"\s+at\s+", t, maxsplit=1, flags=re.I)[0].strip()
    if not t.lower().endswith("band"):
        t = f"{t} Band"
    return t.upper()


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> int:
    tw = _text_width(draw, text, font)
    x = max(0, (width - tw) // 2)
    draw.text((x, y), text, fill=fill, font=font)
    bbox = draw.textbbox((x, y), text, font=font)
    return bbox[3] - bbox[1]


def _paste_photo_frame(
    canvas: Image.Image,
    photo_layer: Image.Image,
    photo_bbox: tuple[int, int, int, int],
    *,
    mat_pad: int = 6,
) -> None:
    left, top, right, bottom = photo_bbox
    frame = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(frame)
    outer = (left - mat_pad - 2, top - mat_pad - 2, right + mat_pad + 2, bottom + mat_pad + 2)
    fdraw.rectangle(outer, fill=(*CREAM_DARK, 255))
    fdraw.rectangle(
        [(left - mat_pad, top - mat_pad), (right + mat_pad, bottom + mat_pad)],
        fill=(*CREAM, 255),
        outline=(*GOLD, 255),
        width=2,
    )
    shadow = frame.filter(ImageFilter.GaussianBlur(radius=4))
    canvas.paste(shadow, (3, 5), shadow)
    canvas.paste(frame, (0, 0), frame)

    patch_w, patch_h = right - left, bottom - top
    band_patch = Image.new("RGB", (patch_w, patch_h), CREAM)
    band_patch.paste(photo_layer, (0, 0), photo_layer)
    canvas.paste(band_patch, (left, top))


def render_wild_composite_poster(
    event: GigEvent,
    reference_photo_path: Path,
    output_path: Path,
    *,
    tier: str = "wild_composite",
    seed: int = 42,
) -> dict[str, Any]:
    """Build western-style wild poster with exact PIL-pasted band photo."""
    size = parse_output_size("1024x1536")
    w, h = size
    canvas = _wood_background(size, seed=seed)
    draw = ImageDraw.Draw(canvas)

    venue = (event.venue or "Venue TBA").strip().upper()
    band = _clean_band_name(event.title or "Lindsey Lane Band", event.venue or "")
    date = event.to_dict().get("short_date", event.event_date.strftime("%b %d")).upper()
    time_label = (event.time_label or "7:00 PM").upper()
    margin = 48
    inner_w = w - 2 * margin

    # --- Header plaque ---
    header_top, header_bottom = 36, 168
    draw.rectangle(
        [(margin, header_top), (w - margin, header_bottom)],
        fill=CREAM,
        outline=GOLD,
        width=3,
    )
    draw.line([(margin + 12, header_top + 10), (w - margin - 12, header_top + 10)], fill=GOLD, width=1)
    band_font = _fit_font(
        draw, band, start_size=64, min_size=34, max_width=inner_w - 40, bold=True
    )
    band_h = _draw_centered_text(
        draw, band, y=header_top + 36, width=w, font=band_font, fill=INK
    )

    # --- Band photo (exact pixels) ---
    photo_layer, photo_bbox = _build_photo_layer(
        reference_photo_path,
        size,
        tier=tier,
        apply_treatment=False,
    )
    _paste_photo_frame(canvas, photo_layer, photo_bbox)
    draw = ImageDraw.Draw(canvas)
    _, _, _, photo_bottom = photo_bbox

    # --- Event info card (fills space below photo) ---
    footer_h = 40
    bottom_pad = 24
    gap = 24
    card_top = photo_bottom + gap
    card_bottom = h - bottom_pad - footer_h
    card_h = max(150, card_bottom - card_top)
    draw.rectangle(
        [(margin, card_top), (w - margin, card_bottom)],
        fill=CREAM,
        outline=GOLD,
        width=2,
    )

    pad_x = margin + 32
    max_text_w = inner_w - 64

    venue_line = f"LIVE AT {venue}"
    venue_font = _fit_font(
        draw, venue_line, start_size=44, min_size=24, max_width=max_text_w, bold=True
    )
    date_time = f"{date}  •  {time_label}"
    dt_font = _fit_font(
        draw, date_time, start_size=48, min_size=28, max_width=max_text_w, bold=True
    )

    # Vertically center the two-line block inside the card
    block_h = 120
    block_top = card_top + max(24, (card_h - block_h) // 2)
    _draw_centered_text(draw, venue_line, y=block_top, width=w, font=venue_font, fill=INK)
    divider_y = block_top + 56
    draw.line([(pad_x, divider_y), (w - pad_x, divider_y)], fill=GOLD, width=2)
    _draw_centered_text(draw, date_time, y=divider_y + 18, width=w, font=dt_font, fill=RUST)

    footer_top = card_bottom + 8
    footer_bottom = h - bottom_pad
    draw.rectangle(
        [(margin, footer_top), (w - margin, footer_bottom)],
        fill=WOOD_MID,
        outline=GOLD,
        width=1,
    )
    tag_font = _try_font(18, bold=True)
    _draw_centered_text(
        draw, "LIVE MUSIC • NO COVER", y=footer_top + 10, width=w, font=tag_font, fill=CREAM
    )

    with __import__("tempfile").TemporaryDirectory(prefix="wild-compose-") as tmp:
        work_dir = Path(tmp)
        left, top, _, _ = photo_bbox
        work_canvas = Image.new("RGBA", size, (*CREAM, 255))
        work_canvas.paste(photo_layer, (left, top), photo_layer)
        canvas_path = work_dir / "compose_canvas.png"
        work_canvas.convert("RGB").save(canvas_path, format="PNG")
        compose = ComposeResult(
            canvas_path=canvas_path,
            mask_path=None,
            photo_bbox=photo_bbox,
            protection_bbox=protection_zone(photo_bbox, size),
            photo_layer=photo_layer,
            canvas_size=size,
            tier=tier,
            reference_path=reference_photo_path,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return {
        "compose": compose,
        "photo_bbox": compose.photo_bbox,
        "mode": "wild_pil_composite",
    }
