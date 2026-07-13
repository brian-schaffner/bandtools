"""Hypothesis C — decomposed wild poster: graphics layer + PIL band photo paste."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from image_providers.reference_compose import (
    CANVAS_BACKGROUND,
    ComposeResult,
    _build_photo_layer,
    parse_output_size,
    prepare_canvas_with_photo,
    protection_zone,
)
from gig_calendar import GigEvent


def _wood_background(size: tuple[int, int], seed: int = 42) -> Image.Image:
  rng = random.Random(seed)
  w, h = size
  base = Image.new("RGB", size, (62, 42, 28))
  draw = ImageDraw.Draw(base)
  for y in range(0, h, 6):
    shade = 45 + rng.randint(0, 35)
    draw.line([(0, y), (w, y)], fill=(shade, shade - 10, shade - 18), width=6)
  return base.filter(ImageFilter.GaussianBlur(radius=0.6))


def _try_font(size: int) -> ImageFont.ImageFont:
  for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
    try:
      return ImageFont.truetype(name, size=size)
    except OSError:
      continue
  return ImageFont.load_default()


def render_wild_composite_poster(
    event: GigEvent,
    reference_photo_path: Path,
    output_path: Path,
    *,
    tier: str = "creative",
    seed: int = 42,
) -> dict[str, Any]:
    """Build western-style wild poster with exact PIL-pasted band photo."""
    size = parse_output_size("1024x1536")
    canvas = _wood_background(size, seed=seed)
    draw = ImageDraw.Draw(canvas)

    band = (event.title or "Lindsey Lane Band").upper()
    venue = (event.venue or "Venue").upper()
    date = event.to_dict().get("short_date", event.event_date.strftime("%b %d")).upper()
    time_label = (event.time_label or "7:00 PM").upper()

    title_font = _try_font(72)
    sub_font = _try_font(36)
    small_font = _try_font(28)

    draw.rectangle([(30, 30), (size[0] - 30, 130)], outline=(180, 160, 120), width=3)
    draw.text((50, 45), band.replace(" BAND", ""), fill=(20, 15, 10), font=title_font)
    draw.text((50, 105), "BAND", fill=(20, 15, 10), font=sub_font)

    # Barbed wire accents
    for x in range(40, size[0] - 40, 80):
      draw.arc([x, size[1] - 180, x + 60, size[1] - 120], 0, 180, fill=(120, 110, 100), width=2)

    with __import__("tempfile").TemporaryDirectory(prefix="wild-compose-") as tmp:
      work_dir = Path(tmp)
      # Untreated photo — maximum face fidelity for wild D
      photo_layer, photo_bbox = _build_photo_layer(
        reference_photo_path,
        size,
        tier=tier,
        apply_treatment=False,
      )
      left, top, right, bottom = photo_bbox
      mat_pad = 10
      draw.rectangle(
        [(left - mat_pad, top - mat_pad), (right + mat_pad, bottom + mat_pad)],
        fill=CANVAS_BACKGROUND,
        outline=(180, 160, 120),
        width=2,
      )
      patch_w, patch_h = right - left, bottom - top
      band_patch = Image.new("RGB", (patch_w, patch_h), CANVAS_BACKGROUND)
      band_patch.paste(photo_layer, (0, 0), photo_layer)
      canvas.paste(band_patch, (left, top))

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

      # Torn-paper labels below photo
      label_y = bottom + 24
      draw.rectangle([(80, label_y), (size[0] - 80, label_y + 52)], fill=(245, 240, 230))
      draw.text((100, label_y + 8), f"LIVE AT {venue}", fill=(15, 10, 5), font=sub_font)
      draw.rectangle([(120, label_y + 64), (360, label_y + 120)], outline=(160, 40, 30), width=4)
      draw.text((140, label_y + 78), date, fill=(120, 20, 10), font=title_font)
      draw.text((380, label_y + 86), time_label, fill=(15, 10, 5), font=small_font)

      footer = f"{venue} • {band}"
      draw.rectangle([(60, size[1] - 70), (size[0] - 60, size[1] - 30)], fill=(210, 180, 140))
      draw.text((80, size[1] - 62), footer, fill=(30, 20, 10), font=small_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return {
      "compose": compose,
      "photo_bbox": compose.photo_bbox,
      "mode": "wild_pil_composite",
    }
