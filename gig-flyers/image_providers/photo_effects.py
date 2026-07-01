"""Tier-aware band photo grain/vignette via ideamaxfx with PIL fallback."""

from __future__ import annotations

import os
import random
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFilter

_BACKEND = os.getenv("PHOTO_EFFECTS_BACKEND", "ideamaxfx").strip().lower()
_IDEAMAXFX_PIPELINE: Any = None
_IDEAMAXFX_IMPORT_FAILED = False


def _use_ideamaxfx() -> bool:
    """True when ideamaxfx backend is enabled and importable."""
    global _IDEAMAXFX_PIPELINE, _IDEAMAXFX_IMPORT_FAILED
    if _BACKEND in {"", "pil", "0", "false", "no", "off"}:
        return False
    if _IDEAMAXFX_IMPORT_FAILED:
        return False
    if _IDEAMAXFX_PIPELINE is not None:
        return True
    try:
        from ideamaxfx import EffectsPipeline

        _IDEAMAXFX_PIPELINE = EffectsPipeline
        return True
    except ImportError:
        _IDEAMAXFX_IMPORT_FAILED = True
        return False


def _tier_treatment(tier: str) -> dict[str, Any]:
    from image_providers.reference_compose import TIER_PHOTO_TREATMENT

    return TIER_PHOTO_TREATMENT.get(tier, TIER_PHOTO_TREATMENT["medium"])


def _canvas_background() -> tuple[int, int, int]:
    from image_providers.reference_compose import CANVAS_BACKGROUND

    return CANVAS_BACKGROUND


def _preserve_alpha(original: Image.Image, processed: Image.Image) -> Image.Image:
    orig = original.convert("RGBA")
    rgb = processed.convert("RGB")
    r, g, b = rgb.split()
    _, _, _, alpha = orig.split()
    return Image.merge("RGBA", (r, g, b, alpha))


def _apply_grain_pil(photo: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return photo
    result = photo.convert("RGBA")
    pixels = result.load()
    w, h = result.size
    grain_range = int(255 * strength)
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            noise = random.randint(-grain_range, grain_range)
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
                a,
            )
    return result


def _apply_cream_vignette_pil(photo: Image.Image, strength: float) -> Image.Image:
    """Soft cream-edge vignette for paper integration (not in ideamaxfx API)."""
    if strength <= 0:
        return photo

    result = photo.convert("RGBA")
    w, h = result.size
    vig = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vig)
    margin = max(8, min(w, h) // 16)
    draw.rectangle([margin, margin, w - margin, h - margin], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(radius=max(6, min(w, h) // 24)))
    vig = vig.point(lambda value: int(255 - (255 - value) * strength))

    cream = Image.new("RGBA", (w, h), (*_canvas_background(), 255))
    cream.putalpha(vig)
    return Image.alpha_composite(result, cream)


def _apply_vignette_pil(photo: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return photo

    result = photo.convert("RGBA")
    w, h = result.size
    vignette_mask = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vignette_mask)
    center_x, center_y = w // 2, h // 2
    max_dist = ((w / 2) ** 2 + (h / 2) ** 2) ** 0.5
    for y in range(h):
        for x in range(w):
            dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            factor = dist / max_dist
            darkness = int(255 * (1 - factor * strength))
            vignette_mask.putpixel((x, y), darkness)

    vignette_mask = vignette_mask.filter(ImageFilter.GaussianBlur(radius=max(w, h) // 8))
    r, g, b, a = result.split()
    r = Image.composite(r, Image.new("L", (w, h), 0), vignette_mask)
    g = Image.composite(g, Image.new("L", (w, h), 0), vignette_mask)
    b = Image.composite(b, Image.new("L", (w, h), 0), vignette_mask)
    return Image.merge("RGBA", (r, g, b, a))


def _apply_grain(photo: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return photo
    if _use_ideamaxfx():
        rgb = photo.convert("RGBA")
        r, g, b, _a = rgb.split()
        base = Image.merge("RGB", (r, g, b))
        result = _IDEAMAXFX_PIPELINE(base).grain(strength).image
        return _preserve_alpha(photo, result)
    return _apply_grain_pil(photo, strength)


def _apply_dark_vignette(photo: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return photo
    if _use_ideamaxfx():
        rgb = photo.convert("RGBA")
        r, g, b, _a = rgb.split()
        base = Image.merge("RGB", (r, g, b))
        result = _IDEAMAXFX_PIPELINE(base).vignette(strength).image
        return _preserve_alpha(photo, result)
    return _apply_vignette_pil(photo, strength)


def apply_tier_photo_effects(
    photo: Image.Image,
    tier: str,
    *,
    apply_grain: bool = True,
    apply_vignette: bool = True,
) -> Image.Image:
    """Apply tier-aware grain and vignette effects (safe for band photos)."""
    treatment = _tier_treatment(tier)
    result = photo.convert("RGBA")

    if apply_grain:
        grain_strength = treatment.get("film_grain", 0.0)
        if grain_strength > 0:
            result = _apply_grain(result, grain_strength)

    cream_strength = treatment.get("cream_vignette", 0.0)
    if cream_strength > 0:
        result = _apply_cream_vignette_pil(result, cream_strength)

    if apply_vignette:
        vignette_strength = treatment.get("vignette", 0.0)
        if vignette_strength > 0:
            result = _apply_dark_vignette(result, vignette_strength)

    return result


def apply_frame_photo_effects(
    photo: Image.Image,
    *,
    film_grain: float,
    cream_vignette: float = 0.0,
    tier: str = "medium",
) -> Image.Image:
    """Structured-layout photo frame: light grain only (no cream vignette by default)."""
    if cream_vignette is None:
        cream_vignette = 0.0

    result = photo.convert("RGBA")
    if film_grain > 0:
        result = _apply_grain(result, film_grain)
    if cream_vignette > 0:
        result = _apply_cream_vignette_pil(result, cream_vignette)
    return result
