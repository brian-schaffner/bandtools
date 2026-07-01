"""Typography-only pipeline: API sees blank cream canvas; PIL composites photo once at end."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter

from image_providers.reference_compose import (
    CANVAS_BACKGROUND,
    ComposeResult,
    SAFE_MARGIN_PX,
    TIER_TINTS,
    prepare_canvas_with_photo,
    validate_flyer_photo,
)

TYPOGRAPHY_ONLY_PROMPT_PREFIX = (
    "INPUT = BLANK CREAM FLYER CANVAS WITH EMPTY PHOTO SLOT. "
    "A faint rectangle marks where a band photo will be composited later — do NOT draw people, "
    "faces, instruments, or any band imagery anywhere on the canvas. "
    f"Add flyer typography and graphic design ONLY in the cream paper margins "
    f"(keep all text at least {SAFE_MARGIN_PX}px from top and side edges). "
    "Venue name, date, band name, show time, and full address must ALL appear and be clearly readable. "
    "MANDATORY FOOTER: venue name + full street address in the bottom margin — readable text only. "
    "Do NOT add grey bars, brush strokes, or blank decorative placeholder strips below the photo slot. "
    "Keep the photo slot area plain cream — no frames, mats, borders, or decorative edges inside the slot. "
)


def typography_only_enabled() -> bool:
    """Check if two-stage typography-only pipeline is enabled.
    
    The two-stage pipeline:
    - Stage 1: AI generates layout (typography, background, graphics) on blank canvas
    - Stage 2: PIL composites the band photo into the reserved slot
    
    This mode is useful when you want the AI to never see the photo pixels.
    Set OPENAI_IMAGE_PIPELINE=typography_only to enable.
    
    Default is False (existing AI image generation workflow).
    """
    raw = os.getenv("OPENAI_IMAGE_PIPELINE", "").strip().lower()
    return raw in {"typography_only", "typography-only", "h1"}


def apply_photo_preintegration(
    photo_layer: Image.Image,
    *,
    tier: str = "medium",
    vignette_strength: float = 0.35,
) -> Image.Image:
    """H3: soften white studio edges into cream before compositing (PIL only)."""
    layer = photo_layer.convert("RGBA")
    w, h = layer.size
    # Knock out near-white background toward cream
    pixels = layer.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            whiteness = min(r, g, b)
            if whiteness > 230 and abs(r - g) < 12 and abs(g - b) < 12:
                blend = min(1.0, (whiteness - 230) / 25.0)
                cr, cg, cb = CANVAS_BACKGROUND
                pixels[x, y] = (
                    int(r * (1 - blend) + cr * blend),
                    int(g * (1 - blend) + cg * blend),
                    int(b * (1 - blend) + cb * blend),
                    a,
                )
    # Edge vignette toward cream
    vig = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vig)
    margin = max(8, min(w, h) // 16)
    draw.rectangle([margin, margin, w - margin, h - margin], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(radius=max(6, min(w, h) // 24)))
    vig = vig.point(lambda v: int(255 - (255 - v) * vignette_strength))
    base = Image.new("RGBA", (w, h), (*CANVAS_BACKGROUND, 255))
    base.paste(layer, (0, 0), layer)
    base.putalpha(vig)
    tinted = _apply_tier_tint_rgba(base, tier)
    return tinted


def _apply_tier_tint_rgba(photo: Image.Image, tier: str) -> Image.Image:
    factors = TIER_TINTS.get(tier, TIER_TINTS["medium"])
    if factors == (1.0, 1.0, 1.0):
        return photo
    tinted = photo.convert("RGBA")
    r, g, b, a = tinted.split()
    rf, gf, bf = factors

    def _scale(channel: Image.Image, factor: float) -> Image.Image:
        return channel.point(lambda value: min(255, int(value * factor)))

    return Image.merge("RGBA", (_scale(r, rf), _scale(g, gf), _scale(b, bf), a))


def prepare_blank_typography_canvas(
    reference_path: Path,
    output_size: tuple[int, int],
    *,
    tier: str = "medium",
    work_dir: Path,
) -> ComposeResult:
    """Cream canvas with empty photo slot — no band pixels in API input."""
    compose = prepare_canvas_with_photo(
        reference_path,
        output_size,
        tier=tier,
        work_dir=work_dir,
        create_mask=False,
    )
    canvas_w, canvas_h = output_size
    blank = Image.new("RGB", (canvas_w, canvas_h), CANVAS_BACKGROUND)
    left, top, right, bottom = compose.photo_bbox
    draw = ImageDraw.Draw(blank)
    draw.rectangle([left, top, right, bottom], outline=(235, 228, 215), width=2)
    blank_path = work_dir / "typography_canvas.png"
    blank.save(blank_path, format="PNG")
    return ComposeResult(
        canvas_path=blank_path,
        mask_path=None,
        photo_bbox=compose.photo_bbox,
        protection_bbox=compose.protection_bbox,
        photo_layer=compose.photo_layer,
        canvas_size=output_size,
        tier=tier,
        reference_path=reference_path,
    )


def composite_typography_with_photo(
    typography_path: Path,
    compose: ComposeResult,
    output_path: Path,
    *,
    preintegrate: bool = False,
) -> None:
    """Paste photo under model typography — single photo appearance, no API band pixels."""
    typo = Image.open(typography_path).convert("RGBA")
    orig_w, orig_h = compose.canvas_size
    if typo.size != (orig_w, orig_h):
        typo = typo.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    left, top, right, bottom = compose.photo_bbox
    base = Image.new("RGBA", (orig_w, orig_h), (*CANVAS_BACKGROUND, 255))

    photo = compose.photo_layer
    if preintegrate:
        photo = apply_photo_preintegration(photo, tier=compose.tier)
    base.paste(photo, (left, top), photo)

    # Punch transparent hole in typography layer so photo shows through slot
    typo_over = typo.copy()
    hole = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    typo_over.paste(hole, (left, top))
    base.alpha_composite(typo_over)
    base.convert("RGB").save(output_path, format="PNG")


def validate_typography_compose(
    output_path: Path,
    reference_path: Path,
    compose: ComposeResult,
) -> bool:
    result = validate_flyer_photo(output_path, reference_path, compose)
    return result.passed
