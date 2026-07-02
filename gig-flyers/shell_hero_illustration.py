"""Convert band photos into printed-poster artwork (hero_illustration mode)."""

from __future__ import annotations

import random

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from shell_asset_integrate import (
    blend_duotone_photo,
    knockout_studio_background,
    shell_palette_rgb,
    soften_photo_edges,
    _pick_roles,
)
from shell_references import ShellReference
from shell_render_spec import ShellRenderSpec


def _high_contrast_threshold(layer: Image.Image, *, cutoff: int = 148) -> Image.Image:
    gray = ImageOps.grayscale(layer.convert("RGBA"))
    bw = gray.point(lambda p: 255 if p > cutoff else 0, mode="L")
    rgba = layer.convert("RGBA")
    r, g, b, _ = rgba.split()
    _, _, _, orig_a = rgba.split()
    merged_a = Image.composite(orig_a, Image.new("L", layer.size, 0), bw)
    return Image.merge("RGBA", (r, g, b, merged_a))


def _halftone_dots(layer: Image.Image, *, dot: int = 5) -> Image.Image:
    gray = ImageOps.grayscale(layer.convert("RGBA"))
    w, h = gray.size
    small = gray.resize((max(1, w // dot), max(1, h // dot)), Image.Resampling.BILINEAR)
    small = small.resize((w, h), Image.Resampling.NEAREST)
    rgba = layer.convert("RGBA")
    r, g, b, a = rgba.split()
    mask = small.point(lambda p: int(255 * (p / 255) ** 1.2), mode="L")
    return Image.merge("RGBA", (r, g, b, Image.composite(a, Image.new("L", layer.size, 0), mask)))


def _distress_edges(layer: Image.Image, *, seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    del rng
    rgba = layer.convert("RGBA")
    noise = Image.effect_noise(rgba.size, 28).convert("L")
    noise = noise.point(lambda p: min(255, int(p * 0.35)))
    r, g, b, a = rgba.split()
    a = ImageChops.subtract(a, noise)
    return Image.merge("RGBA", (r, g, b, a))


def _matte_print(layer: Image.Image, *, ink: tuple[int, int, int]) -> Image.Image:
    del ink
    rgba = layer.convert("RGBA")
    w, h = rgba.size
    vignette = Image.new("L", (w, h), 255)
    if w > 4 and h > 4:
        draw = ImageDraw.Draw(vignette)
        draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=max(2, min(w, h) // 80))
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=max(2, min(w, h) // 120)))
    r, g, b, a = rgba.split()
    a = Image.composite(a, Image.new("L", (w, h), 0), vignette)
    return Image.merge("RGBA", (r, g, b, a))


def process_hero_illustration(
    photo: Image.Image,
    shell: ShellReference,
    spec: ShellRenderSpec,
    *,
    backdrop: tuple[int, int, int],
) -> Image.Image:
    """Band photo → high-contrast printed artwork blended into the poster palette."""
    processing = spec.photo_processing
    roles = _pick_roles(shell_palette_rgb(shell))
    layer = photo.convert("RGBA")

    if "remove_background" in processing:
        layer = knockout_studio_background(layer, target=backdrop, threshold=235)

    layer = ImageEnhance.Contrast(layer).enhance(1.18)
    layer = ImageEnhance.Color(layer).enhance(0.35)

    if "threshold" in processing:
        layer = _high_contrast_threshold(layer)

    if "duotone" in processing:
        layer = blend_duotone_photo(
            layer,
            shadow=roles["shadow"],
            highlight=roles["highlight"],
            strength=0.88,
        )

    if "halftone" in processing:
        layer = _halftone_dots(layer)

    if "distress" in processing:
        layer = _distress_edges(layer)

    if "matte" in processing:
        layer = _matte_print(layer, ink=roles["ink"])

    if "feather" in processing:
        layer = soften_photo_edges(layer, radius=8)

    return layer


def process_photo_for_spec(
    photo: Image.Image,
    shell: ShellReference,
    spec: ShellRenderSpec,
    *,
    backdrop: tuple[int, int, int],
    hero: bool = False,
) -> Image.Image:
    """Route photo processing by authoritative photo_style — no decorative frames."""
    if spec.photo_style == "hero_illustration":
        return process_hero_illustration(photo, shell, spec, backdrop=backdrop)

    layer = knockout_studio_background(photo, target=backdrop)
    roles = _pick_roles(shell_palette_rgb(shell))
    layer = ImageEnhance.Contrast(layer).enhance(1.04 if not hero else 1.02)
    if "duotone" in spec.photo_processing:
        layer = blend_duotone_photo(
            layer,
            shadow=roles["shadow"],
            highlight=roles["highlight"],
            strength=0.62 if hero else 0.72,
        )
    if "threshold" in spec.photo_processing:
        layer = _high_contrast_threshold(layer, cutoff=160)
    if "feather" in spec.photo_processing:
        layer = soften_photo_edges(layer, radius=5 if hero else 7)
    return layer
