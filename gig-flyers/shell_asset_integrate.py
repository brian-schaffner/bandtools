"""Style-aware band photo + logo integration for shell pass 2."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from shell_references import ShellReference
from structured_layout.band_mark import _luminance, _tint_logo
from structured_layout.graphic_primitives import duotone_photo


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


def knockout_studio_background(
    photo: Image.Image,
    *,
    target: tuple[int, int, int],
    threshold: int = 225,
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
            if min(r, g, b) > threshold and max(r, g, b) - min(r, g, b) < 20:
                t = min(1.0, (min(r, g, b) - threshold) / max(1, 255 - threshold))
                nr = int(r * (1 - t) + target[0] * t)
                ng = int(g * (1 - t) + target[1] * t)
                nb = int(b * (1 - t) + target[2] * t)
                na = int(a * (1 - t * 0.95))
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


def integrate_band_photo(
    photo: Image.Image,
    shell: ShellReference,
    *,
    backdrop: tuple[int, int, int],
) -> Image.Image:
    """Grade, knock out studio white, duotone, feather — ready to paste on shell."""
    roles = _pick_roles(shell_palette_rgb(shell))
    shadow, highlight = roles["shadow"], roles["highlight"]
    style = shell.style

    layer = knockout_studio_background(photo, target=backdrop, threshold=222)
    layer = ImageEnhance.Contrast(layer).enhance(1.12)
    layer = ImageEnhance.Color(layer).enhance(0.85 if style in {"letterpress_handbill", "type_only"} else 0.95)

    if style in {"letterpress_handbill", "type_only", "xerox"}:
        gray = layer.convert("L")
        layer = Image.merge("RGBA", (gray, gray, gray, layer.split()[3]))
    else:
        layer = duotone_photo(layer, shadow=shadow, highlight=highlight)

    if style in {"psychedelic_illustrative", "folk_illustrative", "mixed_indie"}:
        mask = _oval_mask(layer.size)
        r, g, b, a = layer.split()
        a = Image.composite(a, Image.new("L", layer.size, 0), mask)
        layer = Image.merge("RGBA", (r, g, b, a))
        mat_style = "oval"
    else:
        layer = soften_photo_edges(layer, radius=8)
        mat_style = "rounded"

    return add_photo_mat(layer, accent=roles["accent"], paper=roles["paper"], style=mat_style)


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


def placement_zones(canvas_size: tuple[int, int]) -> dict[str, tuple[int, int, int, int]]:
    w, h = canvas_size
    photo_w, photo_h = int(w * 0.36), int(h * 0.22)
    px, py = int(w * 0.06), int(h * 0.64)
    photo_box = (px, py, px + photo_w, py + photo_h)
    logo_w, logo_h = int(w * 0.38), int(h * 0.11)
    lx = w - logo_w - int(w * 0.06)
    ly = int(h * 0.76)
    logo_box = (lx, ly, lx + logo_w, ly + logo_h)
    return {"photo": photo_box, "logo": logo_box}


def fit_layer_in_box(layer: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = box
    max_w, max_h = x2 - x1, y2 - y1
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
    zones = placement_zones(canvas_size)
    photo_zone = zones["photo"]
    logo_zone = zones["logo"]
    backdrop = _sample_zone_mean(shell_img, photo_zone)

    photo_layer = integrate_band_photo(photo, shell, backdrop=backdrop)
    photo_layer = fit_layer_in_box(photo_layer, photo_zone)
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
    return {
        "style": shell.style,
        "design_family": shell.design_family,
        "roles": {k: "#{:02x}{:02x}{:02x}".format(*v) for k, v in roles.items()},
    }
