"""Hypothesis C — decomposed wild poster: graphics layer + PIL band photo paste."""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from image_providers.reference_compose import (
    CANVAS_BACKGROUND,
    ComposeResult,
    _build_photo_layer,
    parse_output_size,
    protection_zone,
)
from gig_calendar import GigEvent
from wild_design.wild_graphics import (
    centered_text_with_shadow,
    draw_barbed_wire,
    draw_perforation,
    draw_star_badge,
    grain_overlay,
    rust_stains,
    torn_rectangle_points,
    try_serif_font,
)

# Outlaw-country palette
WOOD_DARK = (32, 20, 14)
WOOD_MID = (58, 38, 26)
PARCHMENT = (236, 222, 198)
PARCHMENT_LIGHT = (248, 238, 220)
INK = (18, 10, 6)
RUST = (168, 42, 28)
RUST_DARK = (100, 22, 14)
GOLD = (198, 162, 88)
WHISKEY = (140, 88, 38)


def _wood_background(size: tuple[int, int], seed: int = 42) -> Image.Image:
    rng = random.Random(seed)
    w, h = size
    base = Image.new("RGB", size, WOOD_DARK)
    draw = ImageDraw.Draw(base)
    for y in range(0, h, 4):
        shade = 28 + rng.randint(0, 32)
        draw.line([(0, y), (w, y)], fill=(shade, shade - 6, shade - 12), width=4)
    rust_stains(draw, size, seed=seed + 11)
    vignette = Image.new("L", size, 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse([-w // 3, -h // 5, w + w // 3, h + h // 5], fill=255)
    dark = Image.new("RGB", size, (0, 0, 0))
    blended = Image.composite(base, dark, vignette.filter(ImageFilter.GaussianBlur(radius=90)))
    return grain_overlay(blended, seed=seed + 99, strength=0.14)


def _try_font(size: int, *, bold: bool = True, western: bool = False) -> ImageFont.ImageFont:
    if western:
        return try_serif_font(size, bold=bold)
    for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
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
    western: bool = False,
) -> ImageFont.ImageFont:
    size = start_size
    while size >= min_size:
        font = _try_font(size, bold=bold, western=western)
        if _text_width(draw, text, font) <= max_width:
            return font
        size -= 2
    return _try_font(min_size, bold=bold, western=western)


def _clean_band_name(title: str, venue: str = "") -> str:
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


def _paste_photo_frame(
    canvas: Image.Image,
    photo_layer: Image.Image,
    photo_bbox: tuple[int, int, int, int],
    *,
    seed: int,
    mat_pad: int = 8,
) -> None:
    left, top, right, bottom = photo_bbox
    frame = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(frame)

    outer_pts = torn_rectangle_points(
        left - mat_pad - 6, top - mat_pad - 6, right + mat_pad + 6, bottom + mat_pad + 6, seed=seed + 1
    )
    inner_pts = torn_rectangle_points(
        left - mat_pad, top - mat_pad, right + mat_pad, bottom + mat_pad, seed=seed + 2
    )
    fdraw.polygon(outer_pts, fill=(*WHISKEY, 230))
    fdraw.polygon(inner_pts, fill=(*PARCHMENT_LIGHT, 255), outline=(*GOLD, 255))

    # Wanted-poster corner ticks
    tick = 18
    for ox, oy in ((left - mat_pad, top - mat_pad), (right + mat_pad, top - mat_pad)):
        fdraw.line([(ox, oy), (ox + tick, oy)], fill=(*INK, 200), width=3)
        fdraw.line([(ox, oy), (ox, oy + tick)], fill=(*INK, 200), width=3)

    shadow = frame.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.paste(shadow, (4, 6), shadow)
    canvas.paste(frame, (0, 0), frame)

    patch_w, patch_h = right - left, bottom - top
    band_patch = Image.new("RGB", (patch_w, patch_h), PARCHMENT_LIGHT)
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
    """Build outlaw-country wild poster with exact PIL-pasted band photo."""
    size = parse_output_size("1024x1536")
    w, h = size
    canvas = _wood_background(size, seed=seed)
    draw = ImageDraw.Draw(canvas)

    venue = (event.venue or "Venue TBA").strip().upper()
    band = _clean_band_name(event.title or "Lindsey Lane Band", event.venue or "")
    date = event.to_dict().get("short_date", event.event_date.strftime("%b %d")).upper()
    time_label = (event.time_label or "7:00 PM").upper()
    margin = 40
    inner_w = w - 2 * margin

    # Top stamp + barbed wire
    stamp_font = _try_font(22, western=True)
    centered_text_with_shadow(
        draw, "★  LIVE SHOW  ★", y=18, width=w, font=stamp_font, fill=GOLD, shadow=RUST_DARK
    )
    draw_barbed_wire(draw, 48, w, margin=margin)

    # Header — torn wanted-poster plaque
    header_top, header_bottom = 58, 188
    header_pts = torn_rectangle_points(margin, header_top, w - margin, header_bottom, seed=seed + 5)
    draw.polygon(header_pts, fill=PARCHMENT, outline=GOLD)
    draw.polygon(header_pts, outline=RUST, width=2)
    draw_star_badge(draw, (margin + 28, header_top + 28), radius=16, fill=RUST, outline=GOLD)
    draw_star_badge(draw, (w - margin - 28, header_top + 28), radius=16, fill=RUST, outline=GOLD)

    band_font = _fit_font(
        draw, band, start_size=58, min_size=32, max_width=inner_w - 80, bold=True, western=True
    )
    centered_text_with_shadow(
        draw, band, y=header_top + 44, width=w, font=band_font, fill=INK, shadow=RUST_DARK
    )
    sub_font = _try_font(22, western=True)
    centered_text_with_shadow(
        draw, "OUTLAW COUNTRY • LIVE", y=header_bottom - 38, width=w, font=sub_font, fill=RUST, shadow=INK
    )

    draw_barbed_wire(draw, header_bottom + 14, w, margin=margin)

    # Band photo (exact pixels)
    photo_layer, photo_bbox = _build_photo_layer(
        reference_photo_path,
        size,
        tier=tier,
        apply_treatment=False,
    )
    _paste_photo_frame(canvas, photo_layer, photo_bbox, seed=seed)
    draw = ImageDraw.Draw(canvas)
    _, _, _, photo_bottom = photo_bbox

    # Ticket-stub event block
    footer_h = 44
    bottom_pad = 20
    gap = 20
    card_top = photo_bottom + gap
    card_bottom = h - bottom_pad - footer_h
    card_pts = torn_rectangle_points(margin, card_top, w - margin, card_bottom, seed=seed + 9)
    draw.polygon(card_pts, fill=PARCHMENT, outline=GOLD)
    draw.polygon(card_pts, outline=RUST, width=2)
    draw_perforation(draw, card_top + 8, margin + 24, w - margin - 24, color=WOOD_MID)

    max_text_w = inner_w - 48
    venue_line = f"LIVE AT {venue}"
    venue_font = _fit_font(
        draw, venue_line, start_size=46, min_size=26, max_width=max_text_w, bold=True, western=True
    )
    date_time = f"{date}   •   {time_label}"
    dt_font = _fit_font(
        draw, date_time, start_size=50, min_size=28, max_width=max_text_w, bold=True, western=True
    )

    card_h = card_bottom - card_top
    block_top = card_top + max(36, (card_h - 130) // 2)
    centered_text_with_shadow(
        draw, venue_line, y=block_top, width=w, font=venue_font, fill=INK, shadow=RUST_DARK
    )
    divider_y = block_top + 58
    draw.line([(margin + 36, divider_y), (w - margin - 36, divider_y)], fill=RUST, width=3)
    draw.line([(margin + 36, divider_y + 2), (w - margin - 36, divider_y + 2)], fill=GOLD, width=1)
    centered_text_with_shadow(
        draw, date_time, y=divider_y + 16, width=w, font=dt_font, fill=RUST, shadow=INK
    )

    # Bottom whiskey strip
    footer_top = card_bottom + 6
    footer_bottom = h - bottom_pad
    draw.rectangle([(margin, footer_top), (w - margin, footer_bottom)], fill=WOOD_MID, outline=GOLD)
    draw_barbed_wire(draw, footer_top + 10, w, margin=margin + 8, color=GOLD)
    tag_font = _try_font(20, bold=True)
    centered_text_with_shadow(
        draw, "LIVE MUSIC  •  NO COVER  •  TWO STEPS FROM THE BAR",
        y=footer_top + 18,
        width=w,
        font=tag_font,
        fill=PARCHMENT_LIGHT,
        shadow=INK,
    )

    with __import__("tempfile").TemporaryDirectory(prefix="wild-compose-") as tmp:
        work_dir = Path(tmp)
        left, top, _, _ = photo_bbox
        work_canvas = Image.new("RGBA", size, (*CANVAS_BACKGROUND, 255))
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
