"""Single-pass band photo compose: PIL places photo on canvas, API adds typography around it.

This module implements the photo treatment doctrine: band photos are SOURCE ARTWORK,
not inspiration. The AI never regenerates, redraws, or reinterprets the musicians.
All photo operations (crop, scale, color grade, etc.) happen in PIL BEFORE the API call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageEnhance

from image_providers.photo_effects import apply_tier_photo_effects

# Paste-up placement per creativity tier (fractions of canvas width/height).
# Photos fill ~48–55% of canvas height; typography uses remaining paper above/below.
TIER_PLACEMENTS: dict[str, dict[str, float]] = {
    "conservative": {
        "width_frac": 0.92,
        "max_height_frac": 0.48,
        "y_center_frac": 0.60,
        "x_center_frac": 0.50,
        "angle": 0.0,
    },
    "medium": {
        "width_frac": 0.92,
        "max_height_frac": 0.50,
        "y_center_frac": 0.58,
        "x_center_frac": 0.50,
        "angle": 0.0,
    },
    "creative": {
        "width_frac": 0.90,
        "max_height_frac": 0.48,
        "y_center_frac": 0.60,
        "x_center_frac": 0.50,
        "angle": -2.0,
    },
    # Wild D PIL composite — photo higher, more room for typography below.
    "wild_composite": {
        "width_frac": 0.92,
        "max_height_frac": 0.40,
        "y_center_frac": 0.39,
        "x_center_frac": 0.50,
        "angle": 0.0,
    },
}

# Subtle print-style tint per tier (RGB multipliers). Applied in PIL only — faces untouched.
TIER_TINTS: dict[str, tuple[float, float, float]] = {
    "conservative": (0.94, 0.94, 0.98),
    "medium": (1.0, 0.97, 0.95),
    "creative": (0.97, 0.93, 1.02),
}

# Photo treatment settings per tier (all applied in PIL, never by AI)
TIER_PHOTO_TREATMENT: dict[str, dict[str, Any]] = {
    "conservative": {
        "film_grain": 0.012,
        "contrast": 1.01,
        "brightness": 1.02,
        "saturation": 0.97,
        "vignette": 0.0,
        "cream_vignette": 0.06,
    },
    "medium": {
        "film_grain": 0.015,
        "contrast": 1.01,
        "brightness": 1.01,
        "saturation": 0.95,
        "vignette": 0.0,
        "cream_vignette": 0.05,
    },
    "creative": {
        "film_grain": 0.018,
        "contrast": 1.04,
        "brightness": 1.0,
        "saturation": 0.94,
        "vignette": 0.0,
        "cream_vignette": 0.03,
    },
}

CANVAS_BACKGROUND = (245, 240, 230)  # off-white promoter paper
SAFE_MARGIN_PX = 48  # reserve top/side/bottom padding so header/footer text is not clipped
MASK_PAD_PX = 40  # minimum gutter around photo pixels
PHOTO_BORDER_CLEARANCE_PX = 64  # reserve for model-drawn frames/mats bleeding past photo_bbox
TYPO_EXCLUSION_PAD_PX = MASK_PAD_PX + PHOTO_BORDER_CLEARANCE_PX
STRIP_HAZARD_CLEAR_PX = 140  # enforce clears band-like strips in footer below photo_bbox
STRIP_SCAN_DEPTH_PX = 200  # validation scans this far below photo bottom
PHOTO_DRIFT_THRESHOLD = 12.0
PHOTO_VALIDATION_DRIFT_THRESHOLD = 15.0
STRIP_ROW_MAE_THRESHOLD = 8.0
FOOTER_STRIP_MAE_THRESHOLD = 22.0
STRIP_CORRELATION_THRESHOLD = 0.92
OUTSIDE_BAND_MATCH_THRESHOLD = 22.0


@dataclass(frozen=True)
class ComposeResult:
    """Artifacts from preparing photo-on-canvas API input (photo placed once in PIL)."""

    canvas_path: Path
    mask_path: Optional[Path]
    photo_bbox: tuple[int, int, int, int]  # left, top, right, bottom
    protection_bbox: tuple[int, int, int, int]  # photo_bbox + padding — mask/enforce zone
    photo_layer: Image.Image
    canvas_size: tuple[int, int]
    tier: str = "medium"
    reference_path: Optional[Path] = None


@dataclass
class PhotoValidationResult:
    """Automated band-photo fidelity checks for flyers and reviewer pre-flight."""

    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks}


def parse_output_size(size: str) -> tuple[int, int]:
    raw = (size or "1024x1536").strip().lower()
    if "x" not in raw:
        return 1024, 1536
    w, h = raw.split("x", 1)
    return int(w), int(h)


def _placement_for_tier(tier: str) -> dict[str, float]:
    return TIER_PLACEMENTS.get(tier, TIER_PLACEMENTS["medium"])


def protection_zone(
    photo_bbox: tuple[int, int, int, int],
    canvas_size: tuple[int, int],
    *,
    pad: int = TYPO_EXCLUSION_PAD_PX,
) -> tuple[int, int, int, int]:
    """Bbox around band photo incl. border clearance — mask, enforce safety, typography zones."""
    left, top, right, bottom = photo_bbox
    canvas_w, canvas_h = canvas_size
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(canvas_w, right + pad),
        min(canvas_h, bottom + pad),
    )


def _inset_zone(
    zone: tuple[int, int, int, int],
    canvas_size: tuple[int, int],
    *,
    margin: int = SAFE_MARGIN_PX,
) -> Optional[tuple[int, int, int, int]]:
    """Inset a typography zone from canvas edges by safe margin."""
    canvas_w, canvas_h = canvas_size
    left, top, right, bottom = zone
    if left <= 0:
        left = margin
    if top <= 0:
        top = margin
    if right >= canvas_w:
        right = canvas_w - margin
    if bottom >= canvas_h:
        bottom = canvas_h - margin
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def typography_zones(
    canvas_size: tuple[int, int],
    *,
    tier: str = "medium",
    photo_bbox: Optional[tuple[int, int, int, int]] = None,
) -> list[tuple[int, int, int, int]]:
    """Rectangles where typography/graphics may appear (everything outside photo protection)."""
    del tier  # kept for call-site compatibility
    canvas_w, canvas_h = canvas_size
    if photo_bbox is None:
        zone = _inset_zone((0, 0, canvas_w, canvas_h), canvas_size)
        return [zone] if zone else []

    pl, pt, pr, pb = protection_zone(photo_bbox, canvas_size)
    raw_zones: list[tuple[int, int, int, int]] = []
    if pt > 0:
        raw_zones.append((0, 0, canvas_w, pt))
    if pb < canvas_h:
        raw_zones.append((0, pb, canvas_w, canvas_h))
    if pl > 0 and pb > pt:
        raw_zones.append((0, pt, pl, pb))
    if pr < canvas_w and pb > pt:
        raw_zones.append((pr, pt, canvas_w, pb))

    zones: list[tuple[int, int, int, int]] = []
    for zone in raw_zones:
        inset = _inset_zone(zone, canvas_size)
        if inset:
            zones.append(inset)
    return zones


def _fit_photo(photo: Image.Image, max_w: int, max_h: int) -> Image.Image:
    ratio = min(max_w / photo.width, max_h / photo.height)
    new_w = max(1, int(photo.width * ratio))
    new_h = max(1, int(photo.height * ratio))
    return photo.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _apply_tier_tint(photo: Image.Image, tier: str) -> Image.Image:
    """Deterministic per-tier color grade — scale/position only, no face edits."""
    factors = TIER_TINTS.get(tier, TIER_TINTS["medium"])
    if factors == (1.0, 1.0, 1.0):
        return photo
    tinted = photo.convert("RGBA")
    r, g, b, a = tinted.split()
    rf, gf, bf = factors

    def _scale(channel: Image.Image, factor: float) -> Image.Image:
        return channel.point(lambda value: min(255, int(value * factor)))

    tinted = Image.merge(
        "RGBA",
        (_scale(r, rf), _scale(g, gf), _scale(b, bf), a),
    )
    return tinted


def _apply_contrast_brightness(
    photo: Image.Image,
    contrast: float = 1.0,
    brightness: float = 1.0,
) -> Image.Image:
    """Adjust contrast and brightness — ALLOWED operations (PIL only, no AI)."""
    result = photo.convert("RGBA")
    rgb = result.convert("RGB")
    
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(rgb)
        rgb = enhancer.enhance(contrast)
    
    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(rgb)
        rgb = enhancer.enhance(brightness)
    
    r, g, b = rgb.split()
    _, _, _, a = result.split()
    return Image.merge("RGBA", (r, g, b, a))


def _apply_saturation(photo: Image.Image, saturation: float = 1.0) -> Image.Image:
    """Adjust color saturation — ALLOWED operation (PIL only, no AI)."""
    if saturation == 1.0:
        return photo
    
    result = photo.convert("RGBA")
    rgb = result.convert("RGB")
    
    enhancer = ImageEnhance.Color(rgb)
    rgb = enhancer.enhance(saturation)
    
    r, g, b = rgb.split()
    _, _, _, a = result.split()
    return Image.merge("RGBA", (r, g, b, a))


def apply_photo_treatment(
    photo: Image.Image,
    tier: str = "medium",
    *,
    apply_grain: bool = True,
    apply_vignette: bool = True,
) -> Image.Image:
    """Apply all ALLOWED photo treatment operations for the given tier.
    
    This function applies ONLY operations from PHOTO_ALLOWED:
    - Color tinting (tier-specific)
    - Contrast adjustment
    - Brightness adjustment
    - Saturation adjustment
    - Film grain (optional)
    - Vignette (optional)
    
    The AI model NEVER sees or modifies these pixels — all processing is PIL-only.
    """
    treatment = TIER_PHOTO_TREATMENT.get(tier, TIER_PHOTO_TREATMENT["medium"])
    
    result = _apply_tier_tint(photo, tier)
    
    result = _apply_contrast_brightness(
        result,
        contrast=treatment.get("contrast", 1.0),
        brightness=treatment.get("brightness", 1.0),
    )
    
    saturation = treatment.get("saturation", 1.0)
    if saturation != 1.0:
        result = _apply_saturation(result, saturation)

    return apply_tier_photo_effects(
        result,
        tier,
        apply_grain=apply_grain,
        apply_vignette=apply_vignette,
    )


def _build_photo_layer(
    reference_path: Path,
    output_size: tuple[int, int],
    *,
    tier: str,
    apply_treatment: bool = True,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Fit and apply ALLOWED photo treatments — returns layer and bbox (no canvas paste).
    
    All photo modifications happen here in PIL BEFORE any AI model sees the canvas.
    This enforces the photo treatment doctrine: the AI never touches the photo pixels.
    """
    canvas_w, canvas_h = output_size
    placement = _placement_for_tier(tier)

    photo = Image.open(reference_path).convert("RGBA")
    max_w = int(canvas_w * placement["width_frac"])
    max_h = int(canvas_h * placement["max_height_frac"])
    fitted = _fit_photo(photo, max_w, max_h)
    
    if apply_treatment:
        fitted = apply_photo_treatment(fitted, tier)

    angle = float(placement.get("angle", 0.0))
    if angle:
        fitted = fitted.rotate(
            angle,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=(255, 255, 255, 0),
        )

    cx = int(canvas_w * placement["x_center_frac"])
    cy = int(canvas_h * placement["y_center_frac"])
    x = max(0, min(cx - fitted.width // 2, canvas_w - fitted.width))
    y = max(0, min(cy - fitted.height // 2, canvas_h - fitted.height))
    photo_bbox = (x, y, x + fitted.width, y + fitted.height)
    return fitted.copy(), photo_bbox


def prepare_canvas_with_photo(
    reference_path: Path,
    output_size: tuple[int, int],
    *,
    tier: str = "medium",
    work_dir: Path,
    create_mask: bool = True,
) -> ComposeResult:
    """Place band photo on cream canvas (crop/tint/tier position) — sole entry of band pixels."""
    canvas_w, canvas_h = output_size
    photo_layer, photo_bbox = _build_photo_layer(reference_path, output_size, tier=tier)
    protect_bbox = protection_zone(photo_bbox, (canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*CANVAS_BACKGROUND, 255))
    left, top, _, _ = photo_bbox
    canvas.paste(photo_layer, (left, top), photo_layer)

    work_dir.mkdir(parents=True, exist_ok=True)
    canvas_path = work_dir / "compose_canvas.png"
    canvas.convert("RGB").save(canvas_path, format="PNG")

    mask_path: Optional[Path] = None
    if create_mask:
        # OpenAI edit mask: alpha=0 editable in typography zones; alpha=255 preserves photo region.
        mask = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mask)
        pl, pt, pr, pb = protect_bbox
        draw.rectangle([pl, pt, pr, pb], fill=(255, 255, 255, 255))
        mask_path = work_dir / "compose_mask.png"
        mask.save(mask_path, format="PNG")

    return ComposeResult(
        canvas_path=canvas_path,
        mask_path=mask_path,
        photo_bbox=photo_bbox,
        protection_bbox=protect_bbox,
        photo_layer=photo_layer,
        canvas_size=(canvas_w, canvas_h),
        tier=tier,
        reference_path=reference_path,
    )


def prepare_photo_compose(
    reference_path: Path,
    output_size: tuple[int, int],
    *,
    tier: str = "medium",
    work_dir: Path,
    create_mask: bool = True,
) -> ComposeResult:
    """Backward-compatible alias for prepare_canvas_with_photo."""
    return prepare_canvas_with_photo(
        reference_path,
        output_size,
        tier=tier,
        work_dir=work_dir,
        create_mask=create_mask,
    )


def prepare_reference_canvas(
    reference_path: Path,
    output_size: tuple[int, int],
    *,
    tier: str = "medium",
    work_dir: Path,
    create_mask: bool = True,
) -> ComposeResult:
    """Backward-compatible alias for prepare_canvas_with_photo."""
    return prepare_canvas_with_photo(
        reference_path,
        output_size,
        tier=tier,
        work_dir=work_dir,
        create_mask=create_mask,
    )


def composite_band_photo(output_path: Path, compose: ComposeResult) -> None:
    """Legacy post-overlay paste — disabled in production; use only when OPENAI_IMAGE_POST_OVERLAY=1."""
    orig_w, orig_h = compose.canvas_size
    plate = Image.open(output_path).convert("RGBA")
    if plate.size != (orig_w, orig_h):
        plate = plate.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    left, top, _, _ = compose.photo_bbox
    result = plate.copy()
    result.paste(compose.photo_layer, (left, top), compose.photo_layer)
    result.convert("RGB").save(output_path, format="PNG")


def _expected_photo_patch(compose: ComposeResult) -> Image.Image:
    """RGB patch inside photo_bbox as rendered on the compose canvas."""
    layer = compose.photo_layer
    expected = Image.new("RGB", layer.size, CANVAS_BACKGROUND)
    expected.paste(layer, (0, 0), layer)
    return expected


def _patch_mean_abs_error(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        return 255.0
    pa = a.convert("RGB").getdata()
    pb = b.convert("RGB").getdata()
    total = 0
    count = 0
    for (r1, g1, b1), (r2, g2, b2) in zip(pa, pb):
        total += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
        count += 3
    return total / max(count, 1)


def _template_match_positions(
    flyer: Image.Image,
    template: Image.Image,
    *,
    threshold: float,
    step: int = 24,
) -> list[tuple[int, int, float]]:
    tw, th = template.size
    ow, oh = flyer.size
    if ow < tw or oh < th:
        return []
    positions: list[tuple[int, int, float]] = []
    for y in range(0, oh - th + 1, step):
        for x in range(0, ow - tw + 1, step):
            patch = flyer.crop((x, y, x + tw, y + th))
            mae = _patch_mean_abs_error(patch, template)
            if mae <= threshold:
                positions.append((x, y, mae))
    return positions


def _cluster_match_centroids(
    positions: list[tuple[int, int, float]],
    template_size: tuple[int, int],
    *,
    min_sep: int,
) -> list[tuple[int, int]]:
    tw, th = template_size
    clusters: list[tuple[int, int]] = []
    for x, y, _mae in sorted(positions, key=lambda item: item[2]):
        cx, cy = x + tw // 2, y + th // 2
        if all(abs(cx - px) >= min_sep and abs(cy - py) >= min_sep for px, py in clusters):
            clusters.append((cx, cy))
    return clusters


def _gutter_matches_canvas(
    flyer: Image.Image,
    canvas: Image.Image,
    compose: ComposeResult,
    *,
    tolerance: float = 10.0,
) -> bool:
    left, top, right, bottom = compose.photo_bbox
    pl, pt, pr, pb = compose.protection_bbox
    pixels = 0
    diff = 0
    band_like = 0
    for y in range(pt, pb):
        for x in range(pl, pr):
            if left <= x < right and top <= y < bottom:
                continue
            pixels += 1
            fr, fg, fb = flyer.getpixel((x, y))
            cr, cg, cb = canvas.getpixel((x, y))
            pixel_diff = abs(fr - cr) + abs(fg - cg) + abs(fb - cb)
            diff += pixel_diff
            if pixel_diff > 40:
                band_like += 1
    if not pixels:
        return True
    avg_diff = diff / (pixels * 3)
    if band_like / pixels >= 0.012:
        return False
    return avg_diff <= tolerance


def _protection_margin_has_band_match(
    flyer: Image.Image,
    compose: ComposeResult,
    *,
    threshold: float = 22.0,
) -> bool:
    """True when band-like imagery appears in the gutter between photo_bbox and protection_bbox."""
    ref = compose.photo_layer.convert("RGB")
    left, top, right, bottom = compose.photo_bbox
    tw = max(32, min((right - left) // 5, ref.width))
    th = max(24, min((bottom - top) // 5, ref.height))
    template = ref.resize((tw, th), Image.Resampling.LANCZOS)
    pl, pt, pr, pb = compose.protection_bbox

    inside_patch = flyer.crop((left, top, right, bottom)).resize(
        (max(16, (right - left) // 5), max(16, (bottom - top) // 5)),
        Image.Resampling.LANCZOS,
    )
    inside_ref = ref.resize(inside_patch.size, Image.Resampling.LANCZOS)
    inside_mae = _patch_mean_abs_error(inside_patch, inside_ref)
    step = 24

    def _patch_clear_of_photo(px: int, py: int) -> bool:
        cx, cy = px + tw // 2, py + th // 2
        return not (left <= cx < right and top <= cy < bottom)

    for y in range(pt, pb - th + 1, step):
        for x in range(pl, pr - tw + 1, step):
            if not _patch_clear_of_photo(x, y):
                continue
            patch = flyer.crop((x, y, x + tw, y + th))
            mae = _patch_mean_abs_error(patch, template)
            if mae <= threshold and mae < max(6.0, inside_mae * 0.75):
                return True
    return False


def _patch_overlaps_bbox(
    px: int,
    py: int,
    tw: int,
    th: int,
    bbox: tuple[int, int, int, int],
) -> bool:
    left, top, right, bottom = bbox
    return not (px + tw <= left or px >= right or py + th <= top or py >= bottom)


def _typography_zone_has_band_match(
    flyer: Image.Image,
    compose: ComposeResult,
    *,
    threshold: float = 22.0,
) -> bool:
    """True when header/footer typography zones contain reference-like band imagery."""
    left, top, right, bottom = compose.photo_bbox
    sources: list[Image.Image] = [compose.photo_layer.convert("RGB")]
    ref_path = compose.reference_path
    if ref_path is not None and ref_path.is_file():
        sources.append(Image.open(ref_path).convert("RGB"))

    canvas_patch = Image.new("RGB", (64, 48), CANVAS_BACKGROUND)

    for ref in sources:
        for frac in (4, 6, 8, 12, 16):
            tw = max(32, min((right - left) // frac, ref.width))
            th = max(24, min((bottom - top) // frac, ref.height))
            template = ref.resize((tw, th), Image.Resampling.LANCZOS)
            canvas_cmp = canvas_patch.resize((tw, th), Image.Resampling.LANCZOS)
            step = max(12, min(tw, th) // 3)
            for zl, zt, zr, zb in typography_zones(
                compose.canvas_size, tier=compose.tier, photo_bbox=compose.photo_bbox
            ):
                y_end = max(zt, zb - th)
                x_end = max(zl, zr - tw)
                for y in range(zt, y_end + 1, step):
                    for x in range(zl, x_end + 1, step):
                        if _patch_overlaps_bbox(x, y, tw, th, compose.photo_bbox):
                            continue
                        patch = flyer.crop((x, y, x + tw, y + th))
                        mae = _patch_mean_abs_error(patch, template)
                        if mae > threshold:
                            continue
                        canvas_mae = _patch_mean_abs_error(patch, canvas_cmp)
                        if mae <= max(6.0, canvas_mae * 0.55):
                            return True
    return False


def detect_double_band_photo(
    output_path: Path, compose: ComposeResult, *, threshold: float = 22.0
) -> bool:
    """Heuristic: band imagery appears outside the programmatic photo_bbox region."""
    if not output_path.is_file():
        return False

    flyer = Image.open(output_path).convert("RGB")
    orig_w, orig_h = compose.canvas_size
    if flyer.size != (orig_w, orig_h):
        flyer = flyer.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    if _typography_zone_has_band_match(flyer, compose, threshold=threshold):
        return True
    return _protection_margin_has_band_match(flyer, compose, threshold=threshold)


def _row_mean_rgb(image: Image.Image, y: int, x_start: int, x_end: int) -> tuple[float, float, float]:
    if x_end <= x_start:
        return 0.0, 0.0, 0.0
    pixels = [image.getpixel((x, y))[:3] for x in range(x_start, x_end)]
    count = len(pixels)
    return (
        sum(p[0] for p in pixels) / count,
        sum(p[1] for p in pixels) / count,
        sum(p[2] for p in pixels) / count,
    )


def _row_mean_abs_error(
    flyer: Image.Image,
    row_a: int,
    row_b: int,
    x_start: int,
    x_end: int,
) -> float:
    if x_end <= x_start or row_a < 0 or row_b < 0:
        return 255.0
    total = 0
    count = 0
    for x in range(x_start, x_end):
        ra, ga, ba = flyer.getpixel((x, row_a))[:3]
        rb, gb, bb = flyer.getpixel((x, row_b))[:3]
        total += abs(ra - rb) + abs(ga - gb) + abs(ba - bb)
        count += 3
    return total / max(count, 1)


def _row_band_fraction(
    image: Image.Image,
    y: int,
    x_start: int,
    x_end: int,
    *,
    bg: tuple[int, int, int] = CANVAS_BACKGROUND,
    tolerance: int = 18,
) -> float:
    if x_end <= x_start or y < 0 or y >= image.height:
        return 0.0
    band_like = 0
    for x in range(x_start, x_end):
        r, g, b = image.getpixel((x, y))[:3]
        if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > tolerance:
            band_like += 1
    return band_like / (x_end - x_start)


def _flyer_rgb(path: Path, compose: ComposeResult) -> Image.Image:
    flyer = Image.open(path).convert("RGB")
    orig_w, orig_h = compose.canvas_size
    if flyer.size != (orig_w, orig_h):
        flyer = flyer.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
    return flyer


def detect_footer_band_duplicate(
    output_path: Path,
    compose: ComposeResult,
    *,
    threshold: float = FOOTER_STRIP_MAE_THRESHOLD,
    scan_depth: int = STRIP_SCAN_DEPTH_PX,
) -> bool:
    """True when a multi-row crop of the photo bottom reappears below photo_bbox."""
    if not output_path.is_file():
        return False

    flyer = _flyer_rgb(output_path, compose)
    orig_w, orig_h = compose.canvas_size
    left, top, right, bottom = compose.photo_bbox
    if bottom >= orig_h - 8:
        return False

    ref = compose.photo_layer.convert("RGB")
    pw, ph = right - left, bottom - top
    canvas_cmp = Image.new("RGB", (64, 48), CANVAS_BACKGROUND)

    for frac in (3, 4, 5, 6):
        strip_h = max(32, min(ph // frac, ref.height))
        if strip_h >= ph:
            continue
        template = ref.crop((0, ref.height - strip_h, ref.width, ref.height))
        tw, th = template.size
        inside = flyer.crop((left, bottom - strip_h, right, bottom))
        if inside.size != template.size:
            inside = inside.resize(template.size, Image.Resampling.LANCZOS)
        inside_mae = _patch_mean_abs_error(inside, template)
        step = max(12, min(tw, th) // 4)
        scan_end = min(orig_h - th, bottom + scan_depth)

        for y in range(bottom, scan_end + 1, step):
            for x in range(max(0, left - 40), min(orig_w - tw, right + 40), step):
                if _patch_overlaps_bbox(x, y, tw, th, compose.photo_bbox):
                    continue
                patch = flyer.crop((x, y, x + tw, y + th))
                mae = _patch_mean_abs_error(patch, template)
                if mae > threshold:
                    continue
                canvas_mae = _patch_mean_abs_error(
                    patch, canvas_cmp.resize((tw, th), Image.Resampling.LANCZOS)
                )
                if mae <= max(6.0, inside_mae * 0.9) and mae <= canvas_mae * 0.65:
                    return True
    return False


def detect_horizontal_strip(
    output_path: Path,
    compose: ComposeResult,
    *,
    mae_threshold: float = STRIP_ROW_MAE_THRESHOLD,
    scan_depth: int = STRIP_SCAN_DEPTH_PX,
) -> bool:
    """True when band imagery tiles below photo_bbox (single-row or multi-row footer strip)."""
    if detect_footer_band_duplicate(output_path, compose, scan_depth=scan_depth):
        return True

    if not output_path.is_file():
        return False

    flyer = _flyer_rgb(output_path, compose)
    orig_w, orig_h = compose.canvas_size
    left, top, right, bottom = compose.photo_bbox
    if bottom >= orig_h - 2:
        return False

    ref_row = bottom - 1
    x_start = left + 8
    x_end = right - 8
    if x_end <= x_start:
        return False
    if _row_band_fraction(flyer, ref_row, x_start, x_end) < 0.20:
        return False

    row_scan_depth = min(scan_depth, STRIP_HAZARD_CLEAR_PX)
    for offset in range(1, min(row_scan_depth, orig_h - bottom)):
        y = bottom + offset - 1
        if _row_band_fraction(flyer, y, x_start, x_end) < 0.20:
            continue
        mae = _row_mean_abs_error(flyer, ref_row, y, x_start, x_end)
        if mae <= mae_threshold:
            return True
    return False


def _enforce_clear_bbox(compose: ComposeResult) -> tuple[int, int, int, int]:
    """Protection zone extended below photo to scrub model-drawn footer strips."""
    pl, pt, pr, pb = compose.protection_bbox
    _, _, _, bottom = compose.photo_bbox
    canvas_h = compose.canvas_size[1]
    pb = min(canvas_h, max(pb, bottom + STRIP_HAZARD_CLEAR_PX))
    return pl, pt, pr, pb


def detect_band_outside_protection(
    output_path: Path,
    compose: ComposeResult,
    *,
    threshold: float = OUTSIDE_BAND_MATCH_THRESHOLD,
) -> bool:
    """True when reference-like band imagery appears in header/footer typography zones."""
    if not output_path.is_file():
        return False

    flyer = Image.open(output_path).convert("RGB")
    orig_w, orig_h = compose.canvas_size
    if flyer.size != (orig_w, orig_h):
        flyer = flyer.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
    return _typography_zone_has_band_match(flyer, compose, threshold=threshold)


def validate_flyer_photo(
    output_path: Path,
    reference_path: Path,
    compose: ComposeResult,
    *,
    drift_threshold: float = PHOTO_VALIDATION_DRIFT_THRESHOLD,
) -> PhotoValidationResult:
    """Run automated band-photo fidelity checks (reviewer, tests, CLI)."""
    checks: list[dict[str, Any]] = []
    passed = True

    def _record(name: str, ok: bool, detail: str, **extra: Any) -> None:
        nonlocal passed
        if not ok:
            passed = False
        entry: dict[str, Any] = {"name": name, "passed": ok, "detail": detail}
        entry.update(extra)
        checks.append(entry)

    if not output_path.is_file():
        _record("file_exists", False, f"Missing output: {output_path}")
        return PhotoValidationResult(passed=False, checks=checks)

    if not reference_path.is_file():
        _record("reference_exists", False, f"Missing reference: {reference_path}")
        return PhotoValidationResult(passed=False, checks=checks)

    drift = photo_bbox_drift(output_path, compose)
    _record(
        "photo_bbox_drift",
        drift <= drift_threshold,
        f"mean abs error {drift:.2f} (threshold {drift_threshold})",
        value=round(drift, 3),
        threshold=drift_threshold,
    )

    duplicate = detect_double_band_photo(output_path, compose)
    _record(
        "no_duplicate_band_photo",
        not duplicate,
        "duplicate band imagery outside photo_bbox" if duplicate else "no duplicate detected",
    )

    strip = detect_horizontal_strip(output_path, compose)
    _record(
        "no_horizontal_strip",
        not strip,
        "horizontal strip/tiling below photo" if strip else "no strip below photo",
    )

    outside = detect_band_outside_protection(output_path, compose)
    _record(
        "no_band_outside_protection",
        not outside,
        "band-like template match in typography zones" if outside else "clean typography zones",
    )

    flyer = Image.open(output_path).convert("RGB")
    orig_w, orig_h = compose.canvas_size
    if flyer.size != (orig_w, orig_h):
        flyer = flyer.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    margin = _protection_margin_has_band_match(flyer, compose)
    _record(
        "no_band_in_protection_margin",
        not margin,
        "band-like imagery in protection gutter" if margin else "clean protection margin",
    )

    return PhotoValidationResult(passed=passed, checks=checks)


def validate_flyer_photo_from_paths(
    output_path: Path,
    reference_path: Path,
    *,
    tier: str = "medium",
    output_size: Optional[tuple[int, int]] = None,
    work_dir: Optional[Path] = None,
    drift_threshold: float = PHOTO_VALIDATION_DRIFT_THRESHOLD,
) -> PhotoValidationResult:
    """Convenience wrapper: build compose from reference, then validate output."""
    import tempfile

    size = output_size or parse_output_size(os.getenv("OPENAI_IMAGE_SIZE", "1024x1536"))
    if work_dir is None:
        with tempfile.TemporaryDirectory(prefix="gigflyers-validate-") as tmp:
            compose = prepare_photo_compose(
                reference_path,
                size,
                tier=tier,
                work_dir=Path(tmp),
                create_mask=False,
            )
            return validate_flyer_photo(
                output_path,
                reference_path,
                compose,
                drift_threshold=drift_threshold,
            )
    compose = prepare_photo_compose(
        reference_path,
        size,
        tier=tier,
        work_dir=work_dir,
        create_mask=False,
    )
    return validate_flyer_photo(
        output_path,
        reference_path,
        compose,
        drift_threshold=drift_threshold,
    )


def detect_post_compose_defects(
    flyer_path: Path,
    compose: ComposeResult,
) -> list[str]:
    """Heuristic checks for duplicate model-generated band photos."""
    validation = validate_flyer_photo(
        flyer_path,
        compose.reference_path or Path(""),
        compose,
    )
    issues: list[str] = []
    for check in validation.checks:
        if not check.get("passed"):
            issues.append(f"{check['name']}: {check['detail']}")
    return issues


def photo_bbox_drift(
    output_path: Path,
    compose: ComposeResult,
    *,
    threshold: float = PHOTO_DRIFT_THRESHOLD,
) -> float:
    """Mean absolute RGB error inside photo_bbox vs compose canvas photo region."""
    orig_w, orig_h = compose.canvas_size
    flyer = Image.open(output_path).convert("RGB")
    if flyer.size != (orig_w, orig_h):
        flyer = flyer.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
    left, top, right, bottom = compose.photo_bbox
    patch = flyer.crop((left, top, right, bottom))
    expected = _expected_photo_patch(compose)
    if expected.size != patch.size:
        expected = expected.resize(patch.size, Image.Resampling.LANCZOS)
    return _patch_mean_abs_error(patch, expected)


def _bbox_drift_from_image(flyer: Image.Image, compose: ComposeResult) -> float:
    left, top, right, bottom = compose.photo_bbox
    patch = flyer.crop((left, top, right, bottom))
    expected = _expected_photo_patch(compose)
    if expected.size != patch.size:
        expected = expected.resize(patch.size, Image.Resampling.LANCZOS)
    return _patch_mean_abs_error(patch.convert("RGB"), expected)


def enforce_photo_bbox(
    output_path: Path,
    compose: ComposeResult,
    *,
    force: bool = False,
    drift_threshold: float = PHOTO_DRIFT_THRESHOLD,
) -> bool:
    """Replace photo_bbox pixels once: erase region, paste pre-processed reference (never stack)."""
    orig_w, orig_h = compose.canvas_size
    model = Image.open(output_path).convert("RGBA")
    resized = model.size != (orig_w, orig_h)
    if resized:
        model = model.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    if not force and _bbox_drift_from_image(model, compose) <= drift_threshold:
        if resized:
            model.convert("RGB").save(output_path, format="PNG")
        return False

    left, top, right, bottom = compose.photo_bbox
    pl, pt, pr, pb = _enforce_clear_bbox(compose)
    result = model.copy()
    clear = Image.new("RGBA", (pr - pl, pb - pt), (*CANVAS_BACKGROUND, 255))
    result.paste(clear, (pl, pt))
    result.paste(compose.photo_layer, (left, top), compose.photo_layer)
    result.convert("RGB").save(output_path, format="PNG")
    return True


def post_compose_enabled() -> bool:
    """Single-pass compose pipeline: PIL photo on canvas → API edit with mask (default on)."""
    return os.getenv("OPENAI_IMAGE_POST_COMPOSE", "1").strip().lower() not in {"0", "false", "no"}


def post_overlay_enabled() -> bool:
    """Legacy post-API photo paste — off by default; do not use to fix validation failures."""
    return os.getenv("OPENAI_IMAGE_POST_OVERLAY", "0").strip().lower() in {"1", "true", "yes"}


def edit_mask_enabled() -> bool:
    return os.getenv("OPENAI_IMAGE_EDIT_MASK", "1").strip().lower() not in {"0", "false", "no"}


def enforce_photo_enabled() -> bool:
    """Optional legacy drift-based photo replace — off by default."""
    raw = os.getenv("OPENAI_IMAGE_ENFORCE_PHOTO", "").strip().lower()
    if raw:
        return raw not in {"0", "false", "no"}
    restore = os.getenv("OPENAI_IMAGE_RESTORE_PHOTO", "").strip().lower()
    if restore:
        return restore not in {"0", "false", "no"}
    return False


def _cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate band photo fidelity on a generated flyer PNG.",
    )
    parser.add_argument("output", type=Path, help="Flyer PNG to validate")
    parser.add_argument("reference", type=Path, help="Original band reference photo")
    parser.add_argument("--tier", default="medium", choices=["conservative", "medium", "creative"])
    parser.add_argument("--size", default=os.getenv("OPENAI_IMAGE_SIZE", "1024x1536"))
    parser.add_argument("--drift-threshold", type=float, default=PHOTO_VALIDATION_DRIFT_THRESHOLD)
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    result = validate_flyer_photo_from_paths(
        args.output,
        args.reference,
        tier=args.tier,
        output_size=parse_output_size(args.size),
        drift_threshold=args.drift_threshold,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status}: {args.output}")
        for check in result.checks:
            mark = "ok" if check.get("passed") else "FAIL"
            print(f"  [{mark}] {check['name']}: {check['detail']}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(_cli_main())
