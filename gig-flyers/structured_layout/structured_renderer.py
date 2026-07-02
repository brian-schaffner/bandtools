"""Deterministic renderer for Structured Layout Mode.

Renders final flyers from a LayoutSpec + band photo using PIL only.
The photo is IMMUTABLE source artwork - only allowed operations are applied.
"""

from __future__ import annotations

import math
import os
import random
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from structured_layout.layout_spec import (
    LayoutSpec,
    TextElement,
    PhotoFrame,
    GraphicElement,
    BackgroundSpec,
    ColorSpec,
    TextAlignment,
    FontWeight,
)
from image_providers.photo_effects import apply_frame_photo_effects
from image_providers.photo_treatment import PHOTO_ALLOWED
from image_providers.reference_compose import SAFE_MARGIN_PX
from structured_layout.layout_geometry import (
    MAX_TEXT_WIDTH_PCT,
    TEXT_MARGIN_X_PCT,
    clamp_text_element,
    validate_layout_bounds,
)
from structured_layout.design_system import PRO_MIN_FONT_PT
from progress_helper import ProgressCallback, emit_progress


class LayoutRenderError(RuntimeError):
    """Raised when layout cannot be rendered within canvas bounds."""


# Photo readability band (mean RGB luminance in photo bbox)
PHOTO_LUMINANCE_MIN = 70
PHOTO_LUMINANCE_MAX = 215
MAX_PHOTO_FILM_GRAIN = 0.012


def photo_region_mean_luminance(
    output_path: Path,
    layout: LayoutSpec,
) -> Optional[float]:
    """Mean RGB luminance inside the layout photo bbox (0–255 scale)."""
    if not output_path.is_file():
        return None

    flyer = Image.open(output_path).convert("RGB")
    w, h = flyer.size
    frame = layout.photo_frame
    left = int(w * frame.x / 100)
    top = int(h * frame.y / 100)
    right = int(w * (frame.x + frame.width) / 100)
    bottom = int(h * (frame.y + frame.height) / 100)
    if right <= left or bottom <= top:
        return None

    region = flyer.crop((left, top, right, bottom))
    pixels = list(region.getdata())
    if not pixels:
        return None
    return sum((r + g + b) / 3 for r, g, b in pixels) / len(pixels)


def assert_photo_readable(
    output_path: Path,
    layout: LayoutSpec,
    *,
    min_luminance: float = PHOTO_LUMINANCE_MIN,
    max_luminance: float = PHOTO_LUMINANCE_MAX,
) -> tuple[bool, str]:
    """Fail when the band photo region is washed out or too dark to read faces."""
    mean = photo_region_mean_luminance(output_path, layout)
    if mean is None:
        return False, "photo region missing or empty"
    if mean < min_luminance:
        return False, f"photo washed out (mean luminance {mean:.1f} < {min_luminance})"
    if mean > max_luminance:
        return False, f"photo overexposed (mean luminance {mean:.1f} > {max_luminance})"
    return True, f"photo readable (mean luminance {mean:.1f})"


def _normalize_photo_frame(frame: PhotoFrame) -> PhotoFrame:
    """One subtle effect max; full opacity; no stacked degradation."""
    frame.opacity = 1.0
    frame.brightness = min(max(frame.brightness, 0.98), 1.05)
    frame.contrast = min(max(frame.contrast, 0.98), 1.20)
    frame.saturation = min(max(frame.saturation, 0.0), 1.0)
    frame.film_grain = min(frame.film_grain, MAX_PHOTO_FILM_GRAIN)

    if frame.film_grain > 0:
        frame.paper_texture = 0.0
        frame.edge_feather = 0.0
    elif frame.edge_feather > 0:
        frame.paper_texture = 0.0
        frame.edge_feather = min(frame.edge_feather, 3.0)
    elif frame.paper_texture > 0:
        frame.paper_texture = min(frame.paper_texture, 0.03)
    else:
        frame.paper_texture = 0.0
        frame.edge_feather = 0.0

    frame.halftone = False
    return frame


_BLACK_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_BOLD_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_REGULAR_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "arial.ttf",
]
_FAMILY_PATHS: dict[str, str] = {
    "Impact": "/System/Library/Fonts/Supplemental/Impact.ttf",
    "Arial Black": "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "American Typewriter": "/System/Library/Fonts/Supplemental/AmericanTypewriter.ttc",
    "Helvetica Bold Condensed": "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
    "Arial": "/System/Library/Fonts/Supplemental/Arial.ttf",
}


def _find_font(family: str, weight: FontWeight) -> Optional[str]:
    """Find a weight-appropriate font file."""
    named = _FAMILY_PATHS.get(family)
    if named and os.path.exists(named):
        return named
    if weight == FontWeight.BLACK:
        candidates = _BLACK_FONT_PATHS + _REGULAR_FONT_PATHS
    elif weight == FontWeight.BOLD:
        candidates = _BOLD_FONT_PATHS + _BLACK_FONT_PATHS + _REGULAR_FONT_PATHS
    else:
        candidates = _REGULAR_FONT_PATHS + _BOLD_FONT_PATHS
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _get_font(family: str, size: int, weight: FontWeight) -> ImageFont.FreeTypeFont:
    """Get a PIL font object."""
    font_path = _find_font(family, weight)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _apply_opacity(rgb: tuple[int, int, int], opacity: float) -> tuple[int, int, int, int]:
    """Convert RGB to RGBA with opacity."""
    return (*rgb, int(255 * opacity))


def _render_background(
    canvas: Image.Image,
    background: BackgroundSpec,
    *,
    photo_bbox: Optional[tuple[int, int, int, int]] = None,
) -> Image.Image:
    """Render the background layer."""
    w, h = canvas.size
    
    bg_color = _hex_to_rgb(background.color.hex)
    bg = Image.new("RGBA", (w, h), (*bg_color, 255))
    
    if background.texture == "paper":
        _apply_paper_texture(bg, background.texture_strength)
    elif background.texture == "photocopy":
        _apply_photocopy_texture(bg, background.texture_strength)
    elif background.texture == "cardboard":
        _apply_cardboard_texture(bg, background.texture_strength)
    
    if background.grain_strength > 0:
        if background.margin_grain_only and photo_bbox:
            _apply_margin_grain(bg, background.grain_strength, photo_bbox)
        else:
            _apply_grain(bg, background.grain_strength)
    
    return bg


def _apply_paper_texture(image: Image.Image, strength: float) -> None:
    """Apply subtle paper texture."""
    if strength <= 0:
        return
    
    w, h = image.size
    pixels = image.load()
    random.seed(42)
    
    noise_range = int(10 * strength)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = pixels[x, y]
            noise = random.randint(-noise_range, noise_range)
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise - 2)),
                a,
            )


def _apply_photocopy_texture(image: Image.Image, strength: float) -> None:
    """Apply photocopy texture (slight contrast, grain, edge artifacts)."""
    if strength <= 0:
        return
    
    enhancer = ImageEnhance.Contrast(image)
    enhanced = enhancer.enhance(1.0 + strength * 0.15)
    image.paste(enhanced)
    
    _apply_grain(image, strength * 0.03)


def _apply_cardboard_texture(image: Image.Image, strength: float) -> None:
    """Apply cardboard/kraft paper texture."""
    if strength <= 0:
        return
    
    w, h = image.size
    pixels = image.load()
    random.seed(123)
    
    for y in range(h):
        streak = random.randint(-5, 5) * strength
        for x in range(w):
            r, g, b, a = pixels[x, y]
            noise = random.randint(-8, 8) * strength + streak
            pixels[x, y] = (
                max(0, min(255, int(r + noise))),
                max(0, min(255, int(g + noise - 2))),
                max(0, min(255, int(b + noise - 5))),
                a,
            )


def _apply_grain(image: Image.Image, strength: float) -> None:
    """Apply film grain effect."""
    if strength <= 0:
        return
    
    w, h = image.size
    pixels = image.load()
    grain_range = int(255 * strength)
    rng = random.Random(42)
    
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            noise = rng.randint(-grain_range, grain_range)
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
                a,
            )


def _apply_margin_grain(
    image: Image.Image,
    strength: float,
    photo_bbox: tuple[int, int, int, int],
) -> None:
    """Apply grain only outside the photo bbox (paper margins)."""
    if strength <= 0:
        return
    left, top, right, bottom = photo_bbox
    w, h = image.size
    grain_layer = image.copy()
    _apply_grain(grain_layer, strength)
    mask = Image.new("L", (w, h), 255)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle([left, top, right, bottom], fill=0)
    image.paste(grain_layer, mask=mask)


def _apply_torn_edge_mask(photo: Image.Image, *, seed: int = 42) -> Image.Image:
    """Irregular torn-paper alpha mask along photo edges."""
    w, h = photo.size
    mask = Image.new("L", (w, h), 255)
    pixels = mask.load()
    rng = random.Random(seed)
    jitter = max(3, min(w, h) // 40)

    for x in range(w):
        tear = rng.randint(0, jitter)
        for y in range(tear):
            pixels[x, y] = 0
        tear = rng.randint(0, jitter)
        for y in range(h - tear, h):
            pixels[x, y] = 0

    for y in range(h):
        tear = rng.randint(0, jitter)
        for x in range(tear):
            pixels[x, y] = 0
        tear = rng.randint(0, jitter)
        for x in range(w - tear, w):
            pixels[x, y] = 0

    r, g, b, a = photo.split()
    combined = Image.composite(
        a,
        Image.new("L", (w, h), 0),
        mask,
    )
    return Image.merge("RGBA", (r, g, b, combined))


def _apply_halftone(image: Image.Image, dot_size: int = 4) -> Image.Image:
    """Halftone dot overlay on the source photo (preserves faces, not silhouettes on white)."""
    rgba = image.convert("RGBA")
    grayscale = rgba.convert("L")
    w, h = rgba.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    step = max(2, dot_size * 2)

    for y in range(0, h, step):
        for x in range(0, w, step):
            sample_x = min(x + dot_size, w - 1)
            sample_y = min(y + dot_size, h - 1)
            brightness = grayscale.getpixel((sample_x, sample_y))
            radius = max(0, int((1 - brightness / 255) * dot_size))
            if radius > 0:
                alpha = min(200, int(120 + (1 - brightness / 255) * 80))
                draw.ellipse(
                    [x - radius, y - radius, x + radius, y + radius],
                    fill=(0, 0, 0, alpha),
                )

    return Image.alpha_composite(rgba, overlay)


def _render_photo(
    photo_path: Path,
    frame: PhotoFrame,
    canvas_size: tuple[int, int],
    *,
    tier: str = "medium",
) -> tuple[Image.Image, tuple[int, int]]:
    """Render the photo with all allowed treatments.
    
    ONLY applies operations from PHOTO_ALLOWED.
    Never modifies the actual content of the photo (faces, poses, etc.).
    """
    canvas_w, canvas_h = canvas_size
    
    frame = _normalize_photo_frame(frame)
    photo = Image.open(photo_path).convert("RGBA")
    orig_w, orig_h = photo.size
    
    crop_left = int(orig_w * frame.crop_left / 100)
    crop_right = int(orig_w * frame.crop_right / 100)
    crop_top = int(orig_h * frame.crop_top / 100)
    crop_bottom = int(orig_h * frame.crop_bottom / 100)
    
    if crop_left + crop_right < orig_w and crop_top + crop_bottom < orig_h:
        photo = photo.crop((
            crop_left,
            crop_top,
            orig_w - crop_right,
            orig_h - crop_bottom,
        ))
    
    target_w = int(canvas_w * frame.width / 100)
    target_h = int(canvas_h * frame.height / 100)
    
    ratio = min(target_w / photo.width, target_h / photo.height)
    new_w = max(1, int(photo.width * ratio))
    new_h = max(1, int(photo.height * ratio))
    photo = photo.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    if frame.brightness != 1.0:
        enhancer = ImageEnhance.Brightness(photo)
        photo = enhancer.enhance(frame.brightness)
    
    if frame.contrast != 1.0:
        enhancer = ImageEnhance.Contrast(photo)
        photo = enhancer.enhance(frame.contrast)
    
    if frame.saturation != 1.0:
        enhancer = ImageEnhance.Color(photo)
        photo = enhancer.enhance(frame.saturation)
    
    if frame.color_tint:
        tint_rgb = _hex_to_rgb(frame.color_tint.hex)
        r, g, b, a = photo.split()
        r = r.point(lambda x: int(x * tint_rgb[0] / 255))
        g = g.point(lambda x: int(x * tint_rgb[1] / 255))
        b = b.point(lambda x: int(x * tint_rgb[2] / 255))
        photo = Image.merge("RGBA", (r, g, b, a))
    
    photo = apply_frame_photo_effects(
        photo, film_grain=frame.film_grain, cream_vignette=0.0, tier=tier
    )
    
    if frame.paper_texture > 0:
        _apply_paper_texture(photo, frame.paper_texture)
    
    if frame.halftone:
        photo = _apply_halftone(photo, frame.halftone_dot_size)
    
    if frame.rotation != 0:
        rotation = max(-2.0, min(2.0, frame.rotation))
        photo = photo.rotate(
            rotation,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=(255, 255, 255, 0),
        )
    
    if frame.edge_feather > 0:
        mask = Image.new("L", photo.size, 255)
        draw = ImageDraw.Draw(mask)
        feather = int(frame.edge_feather)
        draw.rectangle([0, 0, photo.width, feather], fill=0)
        draw.rectangle([0, photo.height - feather, photo.width, photo.height], fill=0)
        draw.rectangle([0, 0, feather, photo.height], fill=0)
        draw.rectangle([photo.width - feather, 0, photo.width, photo.height], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
        photo.putalpha(mask)
    
    if frame.border_width > 0:
        border = int(frame.border_width)
        border_color = _hex_to_rgb(frame.border_color.hex)
        bordered = Image.new("RGBA", (photo.width + border * 2, photo.height + border * 2), (*border_color, 255))
        bordered.paste(photo, (border, border), photo)
        photo = bordered

    if frame.mask_shape == "torn_edge":
        photo = _apply_torn_edge_mask(photo)

    x = int(canvas_w * frame.x / 100)
    y = int(canvas_h * frame.y / 100)
    
    return photo, (x, y)


def _margin_pct(canvas_size: tuple[int, int]) -> tuple[float, float]:
    """Safe margin as percentage of canvas width/height."""
    w, h = canvas_size
    return SAFE_MARGIN_PX / max(w, 1) * 100, SAFE_MARGIN_PX / max(h, 1) * 100


def _clamp_text_element(text: TextElement, canvas_size: tuple[int, int]) -> TextElement:
    """Keep text within safe margins so headers/footers are not clipped."""
    canvas_h = canvas_size[1]
    layout_probe = LayoutSpec(canvas_width=canvas_size[0], canvas_height=canvas_h)
    clamped = clamp_text_element(text, layout_probe)
    margin_y = SAFE_MARGIN_PX / canvas_h * 100
    max_y = 100 - margin_y
    if clamped.y > max_y:
        clamped = TextElement(
            content=clamped.content,
            x=clamped.x,
            y=max_y,
            width=clamped.width,
            font_size=clamped.font_size,
            font_family=clamped.font_family,
            font_weight=clamped.font_weight,
            color=clamped.color,
            alignment=clamped.alignment,
            rotation=clamped.rotation,
            letter_spacing=clamped.letter_spacing,
            line_height=clamped.line_height,
            all_caps=clamped.all_caps,
        )
    return clamped


def _wrap_text_lines(
    draw: ImageDraw.ImageDraw,
    content: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Word-wrap content to fit within max_width."""
    words = content.split()
    if not words:
        return [content]

    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word]) if current else word
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines if lines else [content]


def _fit_text_font(
    draw: ImageDraw.ImageDraw,
    content: str,
    family: str,
    size: int,
    weight: FontWeight,
    max_width: int,
    *,
    min_size: int = PRO_MIN_FONT_PT,
) -> tuple[ImageFont.FreeTypeFont, int]:
    """Shrink font until single-line content fits max_width (down to min_size)."""
    font_size = size
    font = _get_font(family, font_size, weight)
    bbox = draw.textbbox((0, 0), content, font=font)
    while bbox[2] - bbox[0] > max_width and font_size > min_size:
        font_size -= 2
        font = _get_font(family, font_size, weight)
        bbox = draw.textbbox((0, 0), content, font=font)
    return font, font_size


def estimate_text_overflow_issues(layout: LayoutSpec) -> list[str]:
    """Return issues when any text element would exceed its allocated width."""
    canvas_size = (layout.canvas_width, layout.canvas_height)
    probe = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    issues: list[str] = []

    for text in layout.text_elements:
        clamped = _clamp_text_element(text, canvas_size)
        content = clamped.content.upper() if clamped.all_caps else clamped.content
        max_width = int(canvas_size[0] * clamped.width / 100)
        original_size = clamped.font_size
        font, font_size = _fit_text_font(
            draw,
            content,
            clamped.font_family,
            clamped.font_size,
            clamped.font_weight,
            max_width,
        )
        if font_size < max(PRO_MIN_FONT_PT, int(original_size * 0.5)):
            issues.append(
                f"Text overflow: '{clamped.content[:30]}' needs shrink "
                f"({original_size}pt -> {font_size}pt) for {max_width}px width"
            )
            continue
        bbox = draw.textbbox((0, 0), content, font=font)
        if bbox[2] - bbox[0] > max_width:
            lines = _wrap_text_lines(draw, content, font, max_width)
            for line in lines:
                line_bbox = draw.textbbox((0, 0), line, font=font)
                if line_bbox[2] - line_bbox[0] > max_width:
                    issues.append(
                        f"Text overflow: '{clamped.content[:30]}' exceeds {max_width}px width"
                    )
                    break
    return issues


def _render_text(
    draw: ImageDraw.ImageDraw,
    text: TextElement,
    canvas_size: tuple[int, int],
) -> None:
    """Render a text element, auto-shrinking or wrapping when wider than max_width."""
    canvas_w, canvas_h = canvas_size

    content = text.content.upper() if text.all_caps else text.content

    x = int(canvas_w * text.x / 100)
    y = int(canvas_h * text.y / 100)
    max_width = int(canvas_w * text.width / 100)

    color = _apply_opacity(_hex_to_rgb(text.color.hex), text.color.opacity)

    font, font_size = _fit_text_font(
        draw,
        content,
        text.font_family,
        text.font_size,
        text.font_weight,
        max_width,
    )
    bbox = draw.textbbox((0, 0), content, font=font)
    lines = [content]
    if bbox[2] - bbox[0] > max_width:
        lines = _wrap_text_lines(draw, content, font, max_width)

    line_height_px = max(1, int(font_size * text.line_height))
    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = line_bbox[2] - line_bbox[0]
        draw_x = x
        if text.alignment == TextAlignment.CENTER:
            draw_x = x + (max_width - line_width) // 2
        elif text.alignment == TextAlignment.RIGHT:
            draw_x = x + max_width - line_width
        draw.text((draw_x, y + i * line_height_px), line, font=font, fill=color)


def _draw_starburst(
    layer_draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    outer_r: int,
    inner_r: int,
    spikes: int,
    fill: tuple[int, int, int, int],
    outline: Optional[tuple[int, int, int, int]],
    stroke_width: int,
) -> None:
    """Draw a starburst polygon centered at (cx, cy)."""
    points: list[tuple[float, float]] = []
    for i in range(spikes * 2):
        angle = math.pi * i / spikes - math.pi / 2
        radius = outer_r if i % 2 == 0 else inner_r
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    layer_draw.polygon(points, fill=fill, outline=outline)
    if outline and stroke_width > 1:
        layer_draw.polygon(points, outline=outline, width=stroke_width)


def _render_graphic(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    element: GraphicElement,
    canvas_size: tuple[int, int],
) -> None:
    """Render a graphic element."""
    canvas_w, canvas_h = canvas_size
    
    x = int(canvas_w * element.x / 100)
    y = int(canvas_h * element.y / 100)
    w = int(canvas_w * element.width / 100)
    h = int(canvas_h * element.height / 100)
    
    fill = None
    if element.fill_color:
        fill = _apply_opacity(_hex_to_rgb(element.fill_color.hex), element.fill_color.opacity * element.opacity)
    
    outline = None
    if element.stroke_color and element.stroke_width > 0:
        outline = _apply_opacity(_hex_to_rgb(element.stroke_color.hex), element.stroke_color.opacity * element.opacity)
    
    if element.element_type == "box":
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        if element.corner_radius > 0:
            layer_draw.rounded_rectangle(
                [x, y, x + w, y + h],
                radius=int(element.corner_radius),
                fill=fill,
                outline=outline,
                width=int(element.stroke_width),
            )
        else:
            layer_draw.rectangle(
                [x, y, x + w, y + h],
                fill=fill,
                outline=outline,
                width=int(element.stroke_width),
            )
        if element.rotation != 0:
            layer = layer.rotate(element.rotation, center=(x + w // 2, y + h // 2), expand=False)
        canvas.alpha_composite(layer)
    
    elif element.element_type in ("line", "divider"):
        draw.line(
            [x, y, x + w, y],
            fill=outline or fill,
            width=int(element.stroke_width) or 2,
        )
    
    elif element.element_type == "tape":
        tape_color = fill or (212, 196, 160, int(180 * element.opacity))
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        layer_draw.rectangle([x, y, x + w, y + h], fill=tape_color)
        if element.rotation != 0:
            layer = layer.rotate(element.rotation, center=(x + w // 2, y + h // 2), expand=False)
        canvas.alpha_composite(layer)
    
    elif element.element_type == "starburst":
        spikes = int(element.properties.get("spikes", 12))
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        cx, cy = x + w // 2, y + h // 2
        outer_r = max(w, h) // 2
        inner_r = max(4, outer_r // 3)
        burst_fill = fill or (139, 0, 0, int(230 * element.opacity))
        burst_outline = outline or (0, 0, 0, int(255 * element.opacity))
        _draw_starburst(
            layer_draw, cx, cy, outer_r, inner_r, spikes,
            burst_fill, burst_outline, int(element.stroke_width),
        )
        stamp_text = element.properties.get("text", "")
        if stamp_text:
            lines = stamp_text.split("\n")
            font_size = max(12, min(h // 5, w // 6))
            font = _get_font("Helvetica", font_size, FontWeight.BLACK)
            line_h = font_size + 4
            total_h = len(lines) * line_h
            start_y = cy - total_h // 2
            for i, line in enumerate(lines):
                tb = layer_draw.textbbox((0, 0), line, font=font)
                tw = tb[2] - tb[0]
                layer_draw.text(
                    (cx - tw // 2, start_y + i * line_h),
                    line,
                    font=font,
                    fill=(255, 255, 255, 255),
                )
        canvas.alpha_composite(layer)
    
    elif element.element_type == "ticket_stub":
        perf_color = outline or (80, 80, 80, int(180 * element.opacity))
        perf_count = int(element.properties.get("perforations", 12))
        edge_x = x + w // 2
        step = max(4, h // max(1, perf_count))
        for i in range(perf_count):
            py = y + i * step
            if py > y + h:
                break
            draw.ellipse([edge_x - 2, py, edge_x + 2, py + 4], fill=perf_color)
        draw.line([edge_x, y, edge_x, y + h], fill=perf_color, width=1)
    
    elif element.element_type == "stamp":
        stamp_text = element.properties.get("text", "LIVE")
        stamp_color = outline or (139, 0, 0, int(255 * element.opacity))
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        pad = max(4, int(min(w, h) * 0.08))
        layer_draw.ellipse([x + pad, y + pad, x + w - pad, y + h - pad], outline=stamp_color, width=2)
        lines = stamp_text.split("\n")
        font_size = max(11, min(h // (len(lines) + 2), w // 4))
        font = _get_font("Helvetica", font_size, FontWeight.BOLD)
        line_h = font_size + 2
        total_h = len(lines) * line_h
        cx, cy = x + w // 2, y + h // 2
        start_y = cy - total_h // 2
        for i, line in enumerate(lines):
            tb = layer_draw.textbbox((0, 0), line, font=font)
            tw = tb[2] - tb[0]
            layer_draw.text((cx - tw // 2, start_y + i * line_h), line, font=font, fill=stamp_color)
        if element.rotation != 0:
            layer = layer.rotate(
                element.rotation,
                center=(cx, cy),
                expand=True,
                resample=Image.Resampling.BICUBIC,
            )
            # Re-center rotated stamp near original anchor
            ox, oy = cx - layer.width // 2, cy - layer.height // 2
            canvas.alpha_composite(layer, (ox, oy))
        else:
            canvas.alpha_composite(layer)

    elif element.element_type == "corner_strip":
        corner = element.properties.get("corner", "top_left")
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        strip_fill = fill or (139, 0, 0, int(220 * element.opacity))
        if corner == "top_left":
            points = [(x, y), (x + w, y), (x, y + h)]
        elif corner == "top_right":
            points = [(x + w, y), (x + w, y + h), (x, y)]
        elif corner == "bottom_left":
            points = [(x, y + h), (x, y), (x + w, y + h)]
        else:  # bottom_right
            points = [(x + w, y + h), (x, y + h), (x + w, y)]
        layer_draw.polygon(points, fill=strip_fill)
        canvas.alpha_composite(layer)


def _apply_photocopy_effect(image: Image.Image, strength: float) -> Image.Image:
    """Apply overall photocopy effect."""
    if strength <= 0:
        return image
    
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.0 + strength * 0.2)
    
    _apply_grain(image, strength * 0.02)
    
    return image


def _apply_age_effect(image: Image.Image, strength: float) -> Image.Image:
    """Apply aging effect (yellowing, fading)."""
    if strength <= 0:
        return image
    
    r, g, b, a = image.split()
    
    r = r.point(lambda x: min(255, int(x + 10 * strength)))
    g = g.point(lambda x: min(255, int(x + 5 * strength)))
    b = b.point(lambda x: max(0, int(x - 5 * strength)))
    
    image = Image.merge("RGBA", (r, g, b, a))
    
    w, h = image.size
    vignette = Image.new("L", (w, h), 255)
    vignette_draw = ImageDraw.Draw(vignette)
    
    for i in range(10):
        shade = int(255 - (strength * 30 * (10 - i) / 10))
        margin = int(i * min(w, h) / 40)
        vignette_draw.rectangle(
            [margin, margin, w - margin, h - margin],
            outline=shade,
        )
    
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=20))
    
    r, g, b, a = image.split()
    r = Image.composite(r, Image.new("L", (w, h), 240), vignette)
    g = Image.composite(g, Image.new("L", (w, h), 230), vignette)
    b = Image.composite(b, Image.new("L", (w, h), 210), vignette)
    
    return Image.merge("RGBA", (r, g, b, a))


def render_flyer(
    layout: LayoutSpec,
    photo_path: Path,
    output_path: Path,
    on_progress: Optional[ProgressCallback] = None,
    option: str = "",
    tier: str = "medium",
) -> None:
    """Render a flyer from a layout spec and photo.
    
    This is a DETERMINISTIC render - same inputs always produce same output.
    The photo is treated as IMMUTABLE source artwork.
    
    Args:
        layout: The layout specification
        photo_path: Path to the band photo
        output_path: Where to save the rendered flyer
        on_progress: Progress callback
        option: Option letter (B or C)
    """
    from structured_layout.style_dna_renderer import is_style_dna_layout, render_style_dna_from_layout

    if is_style_dna_layout(layout):
        emit_progress(
            on_progress,
            step="render",
            substep="style_dna",
            message=f"Rendering Style DNA archetype for option {option}…",
            option=option,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        render_style_dna_from_layout(layout, photo_path, output_path)
        emit_progress(
            on_progress,
            step="render",
            substep="complete",
            message=f"Style DNA render complete for option {option}",
            option=option,
        )
        return

    emit_progress(
        on_progress,
        step="render",
        substep="start",
        message=f"Rendering structured layout for option {option}...",
        option=option,
    )
    
    bounds_issues = validate_layout_bounds(layout)
    if bounds_issues:
        raise LayoutRenderError("; ".join(bounds_issues))
    
    canvas_size = (layout.canvas_width, layout.canvas_height)
    frame = layout.photo_frame
    photo_bbox = (
        int(canvas_size[0] * frame.x / 100),
        int(canvas_size[1] * frame.y / 100),
        int(canvas_size[0] * (frame.x + frame.width) / 100),
        int(canvas_size[1] * (frame.y + frame.height) / 100),
    )
    
    emit_progress(
        on_progress,
        step="render",
        substep="background",
        message="Rendering background...",
        option=option,
    )
    canvas = _render_background(
        Image.new("RGBA", canvas_size, (255, 255, 255, 255)),
        layout.background,
        photo_bbox=photo_bbox,
    )
    
    for element in layout.graphic_elements:
        if element.element_type in ("box", "line", "divider", "starburst", "ticket_stub", "corner_strip"):
            draw = ImageDraw.Draw(canvas)
            _render_graphic(canvas, draw, element, canvas_size)
    
    emit_progress(
        on_progress,
        step="render",
        substep="photo",
        message="Compositing band photo (immutable source)...",
        option=option,
    )
    if photo_path.is_file():
        photo_layer, photo_pos = _render_photo(
            photo_path, layout.photo_frame, canvas_size, tier=tier
        )
        canvas.paste(photo_layer, photo_pos, photo_layer)
    
    for element in layout.graphic_elements:
        if element.element_type in ("tape", "stamp", "torn_edge"):
            draw = ImageDraw.Draw(canvas)
            _render_graphic(canvas, draw, element, canvas_size)
    
    emit_progress(
        on_progress,
        step="render",
        substep="typography",
        message="Rendering typography...",
        option=option,
    )
    draw = ImageDraw.Draw(canvas)
    for text in layout.text_elements:
        _render_text(draw, _clamp_text_element(text, canvas_size), canvas_size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="PNG")

    readable, luminance_detail = assert_photo_readable(output_path, layout)
    if not readable:
        raise LayoutRenderError(luminance_detail)
    
    emit_progress(
        on_progress,
        step="render",
        substep="saved",
        message=f"Saved structured layout flyer: {output_path.name}",
        option=option,
    )
