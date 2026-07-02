"""Style-aware band photo + logo integration for shell pass 2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from shell_references import ShellReference
from shell_asset_policy import AssetMode, asset_mode_for_shell, uses_band_logo, uses_band_photo
from structured_layout.band_mark import _luminance, _tint_logo
from structured_layout.graphic_primitives import duotone_photo

CANVAS_BACKGROUND = (242, 235, 220)

# Partial duotone keeps faces readable while still matching the shell palette.
_DUOTONE_STRENGTH: dict[str, float] = {
    "letterpress_handbill": 0.28,
    "type_only": 0.28,
    "xerox": 0.38,
    "psychedelic_illustrative": 0.48,
    "folk_illustrative": 0.48,
    "mixed_indie": 0.50,
}
_DEFAULT_DUOTONE_STRENGTH = 0.52

# Where the integrated photo belongs on the shell (must match pass-1 layout intent).
_LOWER_LEFT_FAMILIES = frozenset({"gritty_sidebar_bill"})
_FOOTER_INSET_FAMILIES = frozenset({"festival_hero_grid"})
_CENTER_HERO_FAMILIES = frozenset(
    {
        "letterpress_stack",
        "letterpress_country",
        "arena_photo_dominant",
        "jazz_club",
        "blues_festival",
        "blues_screenprint",
        "theater_debut",
        "vintage_broadside",
        "modern_club",
        "neon_club",
        "modern_metal_arena",
        "reggae_flyer",
        "instrument_hook",
        "xerox_folk_flyer",
        "punk_screenprint",
        "swiss_jazz",
        "underground_zine",
        "swiss_grid",
    }
)


@dataclass
class ShellPass2Compose:
    """Layers + placement for post-OpenAI fidelity and design restore."""

    photo_bbox: tuple[int, int, int, int]
    photo_clear_bbox: tuple[int, int, int, int]
    photo_layer: Image.Image
    logo_bbox: tuple[int, int, int, int]
    logo_layer: Image.Image
    shell_layer: Image.Image
    text_edit_zones: tuple[tuple[int, int, int, int], ...]
    canvas_size: tuple[int, int]
    asset_mode: AssetMode = "photo_hero"
    backdrop_rgb: tuple[int, int, int] = CANVAS_BACKGROUND


def _hex_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        return (40, 40, 40)
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))


def shell_palette_rgb(shell: ShellReference) -> tuple[tuple[int, int, int], ...]:
    colors: list[tuple[int, int, int]] = []
    for entry in shell.palette:
        if entry.startswith("#"):
            colors.append(_hex_rgb(entry))
        elif entry.startswith("rgb"):
            inner = entry[entry.find("(") + 1 : entry.find(")")]
            parts = [int(p.strip()) for p in inner.split(",")[:3]]
            if len(parts) == 3:
                colors.append(tuple(parts))  # type: ignore[arg-type]
    if not colors:
        colors = [(242, 235, 220), (17, 17, 17), (179, 27, 27)]
    return tuple(colors)


def _pick_roles(colors: tuple[tuple[int, int, int], ...]) -> dict[str, tuple[int, int, int]]:
    by_lum = sorted(colors, key=_luminance)
    paper = by_lum[-1]
    ink = by_lum[0]
    mid = by_lum[len(by_lum) // 2]
    accent = max(colors, key=lambda c: abs(_luminance(c) - 128))
    return {"paper": paper, "ink": ink, "shadow": ink, "highlight": mid, "accent": accent}


def _sample_backdrop_ring(
    img: Image.Image,
    box: tuple[int, int, int, int],
    *,
    ring: int = 8,
) -> tuple[int, int, int]:
    """Sample shell backdrop from a ring just outside the photo slot (avoids placeholder pixels)."""
    x1, y1, x2, y2 = box
    w, h = img.size
    strips: list[tuple[int, int, int]] = []
    if y1 - ring > 0:
        strips.append(_sample_zone_mean(img, (x1, max(0, y1 - ring * 3), x2, y1)))
    if y2 + ring < h:
        strips.append(_sample_zone_mean(img, (x1, y2, x2, min(h, y2 + ring * 3))))
    if x1 - ring > 0:
        strips.append(_sample_zone_mean(img, (max(0, x1 - ring * 3), y1, x1, y2)))
    if x2 + ring < w:
        strips.append(_sample_zone_mean(img, (x2, y1, min(w, x2 + ring * 3), y2)))
    if not strips:
        return _sample_zone_mean(img, (0, 0, w, min(h, max(40, h // 8))))
    r = sum(s[0] for s in strips) // len(strips)
    g = sum(s[1] for s in strips) // len(strips)
    b = sum(s[2] for s in strips) // len(strips)
    return (r, g, b)


def _clear_pad_for_slot(slot: str) -> int:
    return {"center_hero": 48, "footer_inset": 28, "lower_left": 24}.get(slot, 32)


def clear_photo_slot(
    canvas: Image.Image,
    zone: tuple[int, int, int, int],
    *,
    backdrop: tuple[int, int, int],
    pad: int = 24,
) -> tuple[int, int, int, int]:
    """Remove pass-1 placeholder imagery from the photo slot before overlay."""
    x1, y1, x2, y2 = zone
    left = max(0, x1 - pad)
    top = max(0, y1 - pad)
    right = min(canvas.width, x2 + pad)
    bottom = min(canvas.height, y2 + pad)
    layer = canvas.convert("RGBA")
    draw = ImageDraw.Draw(layer)
    draw.rectangle([left, top, right, bottom], fill=(*backdrop, 255))
    canvas.paste(layer, (0, 0), layer)
    return (left, top, right, bottom)


def _sample_zone_mean(img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    crop = img.crop((x1, y1, min(img.width, x2), min(img.height, y2))).convert("RGB")
    if crop.width < 2 or crop.height < 2:
        return (80, 40, 100)
    small = crop.resize((24, 24), Image.Resampling.BILINEAR)
    px = list(small.getdata())
    r = sum(p[0] for p in px) // len(px)
    g = sum(p[1] for p in px) // len(px)
    b = sum(p[2] for p in px) // len(px)
    return (r, g, b)


def blend_duotone_photo(
    photo: Image.Image,
    *,
    shadow: tuple[int, int, int],
    highlight: tuple[int, int, int],
    strength: float,
) -> Image.Image:
    """Mix original photo with duotone so facial detail survives grading."""
    layer = photo.convert("RGBA")
    strength = max(0.0, min(1.0, strength))
    if strength <= 0.01:
        return layer
    toned = duotone_photo(layer, shadow=shadow, highlight=highlight)
    if strength >= 0.99:
        return toned
    return Image.blend(layer, toned, strength)


def knockout_studio_background(
    photo: Image.Image,
    *,
    target: tuple[int, int, int],
    threshold: int = 238,
) -> Image.Image:
    """Replace near-white studio backdrop with transparency + target tint."""
    layer = photo.convert("RGBA")
    pixels = layer.load()
    w, h = layer.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            if min(r, g, b) > threshold and max(r, g, b) - min(r, g, b) < 28:
                t = min(1.0, (min(r, g, b) - threshold) / max(1, 255 - threshold))
                nr = int(r * (1 - t) + target[0] * t)
                ng = int(g * (1 - t) + target[1] * t)
                nb = int(b * (1 - t) + target[2] * t)
                na = int(a * (1 - t * 0.65))
                pixels[x, y] = (nr, ng, nb, na)
    return layer


def soften_photo_edges(photo: Image.Image, *, radius: int = 10) -> Image.Image:
    layer = photo.convert("RGBA")
    r, g, b, a = layer.split()
    a = a.filter(ImageFilter.GaussianBlur(radius=radius))
    return Image.merge("RGBA", (r, g, b, a))


def _oval_mask(size: tuple[int, int]) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([2, 2, w - 3, h - 3], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(3, min(w, h) // 40)))
    return mask


def add_photo_mat(
    photo: Image.Image,
    *,
    accent: tuple[int, int, int],
    paper: tuple[int, int, int],
    pad: int = 14,
    style: str = "rounded",
) -> Image.Image:
    """Mat + double border so the photo reads as part of the poster."""
    w, h = photo.size
    framed = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(framed)
    outer = [1, 1, w + pad * 2 - 2, h + pad * 2 - 2]
    inner = [5, 5, w + pad * 2 - 6, h + pad * 2 - 6]
    if style == "oval":
        draw.ellipse(outer, outline=(*accent, 255), width=3)
        draw.ellipse(inner, outline=(*paper, 180), width=1)
    else:
        draw.rounded_rectangle(outer, radius=10, outline=(*accent, 255), width=3)
        draw.rounded_rectangle(inner, radius=8, outline=(*paper, 200), width=1)
    framed.alpha_composite(photo, (pad, pad))
    return framed


def _duotone_strength(style: str) -> float:
    return _DUOTONE_STRENGTH.get(style, _DEFAULT_DUOTONE_STRENGTH)


def integrate_band_photo(
    photo: Image.Image,
    shell: ShellReference,
    *,
    backdrop: tuple[int, int, int],
    hero: bool = False,
) -> Image.Image:
    """Grade, knock out studio white, light duotone blend, feather — ready to paste on shell."""
    roles = _pick_roles(shell_palette_rgb(shell))
    shadow, highlight = roles["shadow"], roles["highlight"]
    style = shell.style

    layer = knockout_studio_background(photo, target=backdrop)
    contrast = 1.02 if hero else 1.04
    color = 0.98 if hero else (0.94 if style in {"letterpress_handbill", "type_only", "xerox"} else 0.97)
    layer = ImageEnhance.Contrast(layer).enhance(contrast)
    layer = ImageEnhance.Color(layer).enhance(color)
    strength = _duotone_strength(style) * (0.55 if hero else 1.0)
    layer = blend_duotone_photo(
        layer,
        shadow=shadow,
        highlight=highlight,
        strength=strength,
    )

    if style in {"psychedelic_illustrative", "folk_illustrative", "mixed_indie"}:
        mask = _oval_mask(layer.size)
        r, g, b, a = layer.split()
        a = Image.composite(a, Image.new("L", layer.size, 0), mask)
        layer = Image.merge("RGBA", (r, g, b, a))
        mat_style = "oval"
    else:
        layer = soften_photo_edges(layer, radius=4 if hero else 6)
        mat_style = "rounded"

    mat_pad = 8 if hero else 14
    return add_photo_mat(
        layer,
        accent=roles["accent"],
        paper=roles["paper"],
        style=mat_style,
        pad=mat_pad,
    )


def integrate_band_logo(
    logo: Image.Image,
    shell: ShellReference,
    *,
    zone_color: tuple[int, int, int],
) -> Image.Image:
    """Tint logo + subtle badge so it matches shell palette."""
    roles = _pick_roles(shell_palette_rgb(shell))
    accent, paper, ink = roles["accent"], roles["paper"], roles["ink"]
    zone_dark = _luminance(zone_color) < 120

    layer = _load_logo_from_image(logo)
    if zone_dark:
        layer = _tint_logo(layer, accent if _luminance(accent) > 90 else paper)
    elif shell.style in {"letterpress_handbill", "type_only"}:
        layer = _tint_logo(layer, ink)
    else:
        layer = _tint_logo(layer, accent)

    pad_x, pad_y = 18, 12
    badge = Image.new(
        "RGBA",
        (layer.width + pad_x * 2, layer.height + pad_y * 2),
        (*paper, 0),
    )
    draw = ImageDraw.Draw(badge)
    box = [0, 0, badge.width - 1, badge.height - 1]
    fill_alpha = 200 if zone_dark else 230
    draw.rounded_rectangle(box, radius=8, fill=(*paper, fill_alpha), outline=(*accent, 255), width=2)
    if zone_dark:
        glow = layer.filter(ImageFilter.GaussianBlur(radius=3))
        badge.alpha_composite(glow, (pad_x, pad_y))
    badge.alpha_composite(layer, (pad_x, pad_y))
    return badge


def _load_logo_from_image(logo: Image.Image) -> Image.Image:
    cropped = logo.convert("RGBA")
    bbox = cropped.getbbox()
    if bbox:
        cropped = cropped.crop(bbox)
    return cropped


def photo_slot_for_shell(shell: ShellReference) -> str:
    """Return placement slot id: center_hero, footer_inset, or lower_left."""
    mode = asset_mode_for_shell(shell)
    if mode == "typography_only":
        return "none"
    family = shell.design_family
    if family in _LOWER_LEFT_FAMILIES:
        return "lower_left"
    if family in _FOOTER_INSET_FAMILIES:
        return "footer_inset"
    if family in _CENTER_HERO_FAMILIES or shell.style == "photographic":
        return "center_hero"
    prompt = shell.personalize_prompt.lower()
    if "lower-left" in prompt or "lower left" in prompt:
        return "lower_left"
    if "footer inset" in prompt:
        return "footer_inset"
    return "center_hero"


def photo_slot_label(slot: str) -> str:
    return {
        "center_hero": "center hero portrait frame",
        "footer_inset": "footer inset slot",
        "lower_left": "lower-left inset",
        "none": "typography-only (no photo slot)",
    }.get(slot, "designated photo slot")


def placement_zones(
    canvas_size: tuple[int, int],
    shell: ShellReference | None = None,
) -> dict[str, tuple[int, int, int, int]]:
    w, h = canvas_size
    slot = photo_slot_for_shell(shell) if shell is not None else "lower_left"
    mode = asset_mode_for_shell(shell) if shell is not None else "photo_inset"

    if slot == "none":
        photo_box = (0, 0, 0, 0)
    elif slot == "center_hero":
        photo_w, photo_h = int(w * 0.78), int(h * 0.44)
        px, py = (w - photo_w) // 2, int(h * 0.26)
    elif slot == "footer_inset":
        photo_w, photo_h = int(w * 0.50), int(h * 0.16)
        px, py = (w - photo_w) // 2, int(h * 0.72)
    else:
        photo_w, photo_h = int(w * 0.42), int(h * 0.26)
        px, py = int(w * 0.05), int(h * 0.60)

    photo_box = (px, py, px + photo_w, py + photo_h)
    logo_w, logo_h = int(w * 0.34), int(h * 0.10)
    lx = w - logo_w - int(w * 0.05)
    ly = int(h * 0.52) if slot == "center_hero" else int(h * 0.76)
    logo_box = (lx, ly, lx + logo_w, ly + logo_h)
    return {"photo": photo_box, "logo": logo_box, "photo_slot": slot}


def fit_layer_in_box(
    layer: Image.Image,
    box: tuple[int, int, int, int],
    *,
    cover: bool = False,
) -> Image.Image:
    x1, y1, x2, y2 = box
    max_w, max_h = x2 - x1, y2 - y1
    if cover:
        ratio = max(max_w / layer.width, max_h / layer.height)
        nw, nh = max(1, int(layer.width * ratio)), max(1, int(layer.height * ratio))
        resized = layer.resize((nw, nh), Image.Resampling.LANCZOS)
        left = max(0, (nw - max_w) // 2)
        top = max(0, (nh - max_h) // 2)
        return resized.crop((left, top, left + max_w, top + max_h))
    ratio = min(max_w / layer.width, max_h / layer.height)
    nw, nh = max(1, int(layer.width * ratio)), max(1, int(layer.height * ratio))
    return layer.resize((nw, nh), Image.Resampling.LANCZOS)


def compose_integrated_assets(
    shell_img: Image.Image,
    photo: Image.Image,
    logo: Image.Image,
    shell: ShellReference,
    canvas_size: tuple[int, int],
) -> tuple[Image.Image, Image.Image, tuple[int, int], tuple[int, int]]:
    """Return integrated photo layer, logo layer, and paste positions."""
    zones = placement_zones(canvas_size, shell)
    photo_zone = zones["photo"]
    logo_zone = zones["logo"]
    backdrop = _sample_zone_mean(shell_img, photo_zone)
    hero = zones.get("photo_slot") == "center_hero"

    photo_layer = integrate_band_photo(photo, shell, backdrop=backdrop, hero=hero)
    photo_layer = fit_layer_in_box(photo_layer, photo_zone, cover=hero)
    if hero:
        px, py = photo_zone[0], photo_zone[1]
    else:
        px = photo_zone[0]
        py = photo_zone[1] + (photo_zone[3] - photo_zone[1] - photo_layer.height) // 2

    logo_backdrop = _sample_zone_mean(shell_img, logo_zone)
    logo_layer = integrate_band_logo(logo, shell, zone_color=logo_backdrop)
    logo_layer = fit_layer_in_box(logo_layer, logo_zone)
    lx = logo_zone[2] - logo_layer.width
    ly = logo_zone[1] + (logo_zone[3] - logo_zone[1] - logo_layer.height) // 2

    return photo_layer, logo_layer, (px, py), (lx, ly)


def integration_summary(shell: ShellReference) -> dict[str, Any]:
    roles = _pick_roles(shell_palette_rgb(shell))
    slot = photo_slot_for_shell(shell)
    return {
        "style": shell.style,
        "design_family": shell.design_family,
        "asset_mode": asset_mode_for_shell(shell),
        "photo_slot": slot,
        "duotone_strength": _duotone_strength(shell.style),
        "roles": {k: "#{:02x}{:02x}{:02x}".format(*v) for k, v in roles.items()},
    }


def enforce_shell_logo(output_path: Path, compose: ShellPass2Compose) -> bool:
    """Restore the pre-integrated logo layer after OpenAI pass 2."""
    if compose.asset_mode == "typography_only" or not output_path.is_file():
        return False

    model = Image.open(output_path).convert("RGBA")
    orig_w, orig_h = compose.canvas_size
    if model.size != (orig_w, orig_h):
        model = model.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    lx, ly = compose.logo_bbox[0], compose.logo_bbox[1]
    result = model.copy()
    result.alpha_composite(compose.logo_layer, (lx, ly))
    result.convert("RGB").save(output_path, format="PNG")
    return True


def enforce_shell_photo(output_path: Path, compose: ShellPass2Compose) -> bool:
    """Restore the pre-integrated photo layer after OpenAI pass 2."""
    if compose.asset_mode == "typography_only" or not output_path.is_file():
        return False

    model = Image.open(output_path).convert("RGBA")
    orig_w, orig_h = compose.canvas_size
    if model.size != (orig_w, orig_h):
        model = model.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    left, top, right, bottom = compose.photo_clear_bbox
    px, py = compose.photo_bbox[0], compose.photo_bbox[1]
    result = model.copy()
    clear = Image.new("RGBA", (right - left, bottom - top), (*compose.backdrop_rgb, 255))
    result.paste(clear, (left, top))
    result.alpha_composite(compose.photo_layer, (px, py))
    result.convert("RGB").save(output_path, format="PNG")
    return True
