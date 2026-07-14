"""Post-render correction for AI yellow/cream/sepia casts on wild full-canvas flyers."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

# Minimum average warmth before we bother correcting option C (already neutral).
_C_SKIP_WARMTH_THRESHOLD = 18.0

_STRENGTH_BY_LETTER: dict[str, float] = {
    "A": 1.0,
    "B": 0.85,
    "C": 0.4,
}


def wild_color_correct_enabled() -> bool:
    return os.getenv("WILD_COLOR_CORRECT", "1").strip().lower() in {"1", "true", "yes", "on"}


def correction_strength_for_letter(letter: str) -> float:
    key = (letter or "A").strip().upper()
    return _STRENGTH_BY_LETTER.get(key, 0.9)


def _is_red_accent(r: int, g: int, b: int) -> bool:
    return r >= 140 and r > g + 30 and r > b + 18


def _is_cool_pixel(r: int, g: int, b: int) -> bool:
    return b > r + 12 and b >= g


def _pixel_warmth(r: int, g: int, b: int) -> float:
    return ((r + g) / 2.0) - b


def estimate_image_warmth(img: Image.Image, *, sample_stride: int = 8) -> float:
    """Average yellow-cream warmth over a sampled grid (higher = more yellow cast)."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    warmths: list[float] = []
    step = max(1, sample_stride)
    for y in range(0, height, step):
        for x in range(0, width, step):
            r, g, b = pixels[x, y]
            if max(r, g, b) < 40:
                continue
            if _is_red_accent(r, g, b) or _is_cool_pixel(r, g, b):
                continue
            warmth = _pixel_warmth(r, g, b)
            if warmth > 8:
                warmths.append(warmth)
    if not warmths:
        return 0.0
    return sum(warmths) / len(warmths)


def _correct_pixel(r: int, g: int, b: int, strength: float) -> tuple[int, int, int]:
    if max(r, g, b) < 35:
        return r, g, b
    if _is_red_accent(r, g, b) or _is_cool_pixel(r, g, b):
        return r, g, b

    warmth = _pixel_warmth(r, g, b)
    if warmth < 10:
        return r, g, b

    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    blend = strength * min(1.0, warmth / 70.0)
    if luminance > 150:
        blend *= 1.0 + min(0.75, (luminance - 150) / 100.0)

    correction = warmth * blend * 0.58
    nr = int(max(0, min(255, r - correction * 0.42)))
    ng = int(max(0, min(255, g - correction * 0.78)))
    nb = int(max(0, min(255, b + correction * 0.38)))
    return nr, ng, nb


def correct_yellow_cast(img: Image.Image, *, strength: float) -> Image.Image:
    """Return a copy with yellow/cream pixels shifted toward neutral white/gray."""
    strength = max(0.0, min(1.0, strength))
    if strength <= 0:
        return img.copy()

    had_alpha = img.mode in {"RGBA", "LA"} or "A" in img.getbands()
    if had_alpha:
        rgba = img.convert("RGBA")
        alpha = rgba.getchannel("A")
        rgb = rgba.convert("RGB")
    else:
        alpha = None
        rgb = img.convert("RGB")

    pixels = rgb.load()
    width, height = rgb.size

    for y in range(height):
        for x in range(width):
            pixels[x, y] = _correct_pixel(*pixels[x, y], strength)

    if alpha is not None:
        out = rgb.convert("RGBA")
        out.putalpha(alpha)
        return out
    return rgb


def correct_wild_flyer_colors(path: Path, letter: str) -> bool:
    """Apply tiered yellow correction to a saved wild flyer PNG. Returns True if applied."""
    if not wild_color_correct_enabled():
        return False
    if not path.is_file():
        return False

    letter_key = (letter or "A").strip().upper()
    strength = correction_strength_for_letter(letter_key)
    if strength <= 0:
        return False

    img = Image.open(path)
    if letter_key == "C":
        warmth = estimate_image_warmth(img)
        if warmth < _C_SKIP_WARMTH_THRESHOLD:
            return False

    corrected = correct_yellow_cast(img, strength=strength)
    path.parent.mkdir(parents=True, exist_ok=True)
    if corrected.mode == "RGBA":
        corrected.convert("RGB").save(path, format="PNG")
    else:
        corrected.save(path, format="PNG")
    return True
