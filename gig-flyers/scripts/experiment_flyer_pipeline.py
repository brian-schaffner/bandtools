#!/usr/bin/env python3
"""Flyer pipeline experiments — 3-cycle scientific loop (local, fast)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from image_providers.reference_compose import (  # noqa: E402
    CANVAS_BACKGROUND,
    ComposeResult,
    detect_band_outside_protection,
    detect_double_band_photo,
    detect_horizontal_strip,
    parse_output_size,
    photo_bbox_drift,
    prepare_canvas_with_photo,
    protection_zone,
    typography_zones,
    validate_flyer_photo,
)

REF = ROOT / "bandphotos" / "679394308_1366641221939459_1410337987474015419_n.jpg"
SIZE = (1024, 1536)


@dataclass
class FlyerMetrics:
    path: str
    tier: str
    drift: float
    duplicate: bool
    strip: bool
    outside_band: bool
    margin_band: bool
    validation_passed: bool
    white_cream_delta: float
    header_band_fraction: float
    footer_band_fraction: float
    photo_top_frac: float
    typo_header_px: int
    typo_footer_px: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _zone_band_fraction(flyer: Image.Image, zone: tuple[int, int, int, int]) -> float:
    zl, zt, zr, zb = zone
    if zr <= zl or zb <= zt:
        return 0.0
    band_like = 0
    total = 0
    bg = CANVAS_BACKGROUND
    tol = 18
    for y in range(zt, zb, 4):
        for x in range(zl, zr, 4):
            total += 1
            r, g, b = flyer.getpixel((x, y))[:3]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > tol:
                band_like += 1
    return band_like / max(total, 1)


def _white_cream_delta(flyer: Image.Image, compose: ComposeResult) -> float:
    """Mean |RGB diff| between photo-edge white and canvas cream (integration metric)."""
    left, top, right, bottom = compose.photo_bbox
    samples: list[float] = []
    for x in range(left + 4, right - 4, 16):
        pr, pg, pb = flyer.getpixel((x, top + 2))[:3]
        samples.append(
            (abs(pr - CANVAS_BACKGROUND[0]) + abs(pg - CANVAS_BACKGROUND[1]) + abs(pb - CANVAS_BACKGROUND[2]))
            / 3
        )
    return sum(samples) / max(len(samples), 1)


def measure_flyer(path: Path, tier: str, reference: Path = REF) -> FlyerMetrics:
    with tempfile.TemporaryDirectory(prefix="exp-compose-") as tmp:
        compose = prepare_canvas_with_photo(
            reference, SIZE, tier=tier, work_dir=Path(tmp), create_mask=False
        )
    validation = validate_flyer_photo(path, reference, compose)
    checks = {c["name"]: c for c in validation.checks}
    flyer = Image.open(path).convert("RGB")
    if flyer.size != SIZE:
        flyer = flyer.resize(SIZE, Image.Resampling.LANCZOS)
    zones = typography_zones(SIZE, tier=tier, photo_bbox=compose.photo_bbox)
    header = zones[0] if zones else (0, 0, SIZE[0], 0)
    footer = zones[1] if len(zones) > 1 else (0, SIZE[1], SIZE[0], SIZE[1])
    _, top, _, bottom = compose.photo_bbox
    return FlyerMetrics(
        path=str(path),
        tier=tier,
        drift=checks.get("photo_bbox_drift", {}).get("value", 0.0) or 0.0,
        duplicate=not checks.get("no_duplicate_band_photo", {}).get("passed", True),
        strip=not checks.get("no_horizontal_strip", {}).get("passed", True),
        outside_band=not checks.get("no_band_outside_protection", {}).get("passed", True),
        margin_band=not checks.get("no_band_in_protection_margin", {}).get("passed", True),
        validation_passed=validation.passed,
        white_cream_delta=_white_cream_delta(flyer, compose),
        header_band_fraction=_zone_band_fraction(flyer, header),
        footer_band_fraction=_zone_band_fraction(flyer, footer),
        photo_top_frac=top / SIZE[1],
        typo_header_px=header[3] - header[1],
        typo_footer_px=footer[3] - footer[1],
    )


def simulate_model_ghost(compose: ComposeResult, out_path: Path) -> None:
    """Synthetic fixture: model redraws top strip of band in header zone (Medium-tier failure)."""
    canvas = Image.open(compose.canvas_path).convert("RGBA")
    left, top, right, bottom = compose.photo_bbox
    strip_h = max(24, (bottom - top) // 12)
    ghost = compose.photo_layer.crop((0, 0, compose.photo_layer.width, strip_h))
    # Place ghost in header, just above photo frame (inside protection margin)
    gy = max(8, top - strip_h - 12)
    canvas.paste(ghost, (left, gy), ghost)
    canvas.convert("RGB").save(out_path, format="PNG")


def simulate_model_footer_strip(compose: ComposeResult, out_path: Path) -> None:
    """Synthetic fixture: model tiles bottom row below photo."""
    canvas = Image.open(compose.canvas_path).convert("RGBA")
    left, top, right, bottom = compose.photo_bbox
    strip_h = max(32, (bottom - top) // 8)
    strip = compose.photo_layer.crop(
        (0, compose.photo_layer.height - strip_h, compose.photo_layer.width, compose.photo_layer.height)
    )
    canvas.paste(strip, (left, bottom + 8), strip)
    canvas.convert("RGB").save(out_path, format="PNG")


def prepare_blank_typography_canvas(
    output_size: tuple[int, int],
    *,
    tier: str,
    work_dir: Path,
    reference_path: Path,
) -> ComposeResult:
    """H1: cream canvas only — photo slot reserved, no band pixels sent to API."""
    canvas_w, canvas_h = output_size
    # Reuse placement math but don't paste photo — only record bbox + layer for post-compose.
    compose_with_photo = prepare_canvas_with_photo(
        reference_path, output_size, tier=tier, work_dir=work_dir, create_mask=False
    )
    blank = Image.new("RGB", (canvas_w, canvas_h), CANVAS_BACKGROUND)
    left, top, right, bottom = compose_with_photo.photo_bbox
    draw = ImageDraw.Draw(blank)
    # Subtle slot marker (barely visible — not band imagery)
    draw.rectangle([left, top, right, bottom], outline=(235, 228, 215), width=2)
    blank_path = work_dir / "typography_canvas.png"
    blank.save(blank_path, format="PNG")
    return ComposeResult(
        canvas_path=blank_path,
        mask_path=None,
        photo_bbox=compose_with_photo.photo_bbox,
        protection_bbox=compose_with_photo.protection_bbox,
        photo_layer=compose_with_photo.photo_layer,
        canvas_size=output_size,
        tier=tier,
        reference_path=reference_path,
    )


def composite_typography_only(
    typography_path: Path,
    compose: ComposeResult,
    output_path: Path,
) -> None:
    """H1: photo as bottom layer, model typography on top (photo slot cleared first)."""
    typo = Image.open(typography_path).convert("RGBA")
    orig_w, orig_h = compose.canvas_size
    if typo.size != (orig_w, orig_h):
        typo = typo.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    left, top, right, bottom = compose.photo_bbox
    result = typo.copy()
    # Clear photo slot to cream so paste is clean
    clear = Image.new("RGBA", (right - left, bottom - top), (*CANVAS_BACKGROUND, 255))
    result.paste(clear, (left, top))
    # Photo under typography
    base = Image.new("RGBA", (orig_w, orig_h), (*CANVAS_BACKGROUND, 255))
    base.paste(compose.photo_layer, (left, top), compose.photo_layer)
    base.alpha_composite(result)
    base.convert("RGB").save(output_path, format="PNG")


def simulate_typography_layer(compose: ComposeResult, out_path: Path) -> None:
    """Fake API typography output on blank canvas (no band pixels)."""
    w, h = compose.canvas_size
    img = Image.new("RGBA", (w, h), (*CANVAS_BACKGROUND, 255))
    draw = ImageDraw.Draw(img)
    left, top, right, bottom = compose.photo_bbox
    # Header block
    draw.rectangle([40, 40, w - 40, top - 20], fill=(20, 20, 20, 255))
    draw.text((60, 60), "STEVIE RAY'S BLUES BAR", fill=(245, 240, 230, 255))
    draw.text((60, 120), "FRIDAY, JUNE 26, 2026", fill=(245, 240, 230, 255))
    draw.text((60, 180), "LINDSEY LANE BAND", fill=(245, 240, 230, 255))
    draw.text((60, 240), "9:30 PM", fill=(245, 240, 230, 255))
    # Footer
    draw.rectangle([40, bottom + 20, w - 40, h - 40], fill=(20, 20, 20, 255))
    draw.text(
        (60, bottom + 40),
        "230 EAST MAIN STREET, LOUISVILLE, KY 40202",
        fill=(245, 240, 230, 255),
    )
    # Leave photo slot cream-only (no band)
    draw.rectangle([left, top, right, bottom], fill=(*CANVAS_BACKGROUND, 255))
    img.save(out_path, format="PNG")


def cycle1_failure_analysis() -> dict[str, Any]:
    failures = [
        ("/Users/brian/.cursor/projects/Users-brian-dev-gig-flyers/assets/image-2d976771-4833-44c6-8cbc-c5182d79823e.png", "conservative"),
        ("/Users/brian/.cursor/projects/Users-brian-dev-gig-flyers/assets/image-c4299a25-023a-4e49-a724-03a749ad9dbc.png", "medium"),
        ("/Users/brian/.cursor/projects/Users-brian-dev-gig-flyers/assets/image-5cfec420-264f-48cd-92be-d2d41af02be9.png", "creative"),
    ]
    r11 = [
        (ROOT / "output/2026-06-26_stevie-ray-s-blues-bar/option-A_r11.png", "conservative"),
        (ROOT / "output/2026-06-26_stevie-ray-s-blues-bar/option-B_r11.png", "medium"),
        (ROOT / "output/2026-06-26_stevie-ray-s-blues-bar/option-C_r11.png", "creative"),
    ]
    results = []
    for path_str, tier in failures + r11:
        p = Path(path_str)
        if not p.is_file():
            continue
        m = measure_flyer(p, tier)
        results.append(m.to_dict())
    return {"cycle": 1, "metrics": results}


def cycle2_synthetic_compare() -> dict[str, Any]:
    """Compare current-pipeline failure modes vs typography-only composite."""
    from image_providers.typography_compose import (
        composite_typography_with_photo,
        prepare_blank_typography_canvas,
    )

    with tempfile.TemporaryDirectory(prefix="exp-c2-") as tmp:
        work = Path(tmp)
        compose = prepare_canvas_with_photo(REF, SIZE, tier="medium", work_dir=work, create_mask=True)

        ghost_path = work / "synthetic_ghost.png"
        strip_path = work / "synthetic_strip.png"
        simulate_model_ghost(compose, ghost_path)
        simulate_model_footer_strip(compose, strip_path)

        blank = prepare_blank_typography_canvas(REF, SIZE, tier="medium", work_dir=work)
        typo_path = work / "fake_typography.png"
        simulate_typography_layer(blank, typo_path)
        h1_path = work / "h1_composite.png"
        composite_typography_with_photo(typo_path, blank, h1_path)

        cases = {
            "synthetic_ghost": ghost_path,
            "synthetic_strip": strip_path,
            "h1_typography_only": h1_path,
            "compose_baseline": compose.canvas_path,
        }
        out: dict[str, Any] = {"cycle": 2, "cases": {}}
        for name, path in cases.items():
            tier = "medium"
            c = blank if name == "h1_typography_only" else compose
            if name == "compose_baseline":
                c = compose
            validation = validate_flyer_photo(path, REF, c)
            m = measure_flyer(path, tier) if name != "compose_baseline" else None
            out["cases"][name] = {
                "validation_passed": validation.passed,
                "checks": validation.checks,
                "metrics": m.to_dict() if m else None,
            }
        return out


def cycle3_preintegration_test() -> dict[str, Any]:
    """H3: vignette/knockout on photo layer — does white-cream delta improve without API?"""
    from image_providers.typography_compose import apply_photo_preintegration

    with tempfile.TemporaryDirectory(prefix="exp-c3-") as tmp:
        work = Path(tmp)
        compose = prepare_canvas_with_photo(REF, SIZE, tier="medium", work_dir=work, create_mask=False)
        raw_path = work / "raw_compose.png"
        integrated_path = work / "integrated_compose.png"

        Image.open(compose.canvas_path).convert("RGB").save(raw_path)
        integrated = apply_photo_preintegration(compose.photo_layer, tier="medium")
        canvas = Image.new("RGB", SIZE, CANVAS_BACKGROUND)
        left, top, _, _ = compose.photo_bbox
        canvas.paste(integrated, (left, top), integrated)
        canvas.save(integrated_path)

        return {
            "cycle": 3,
            "raw_white_cream_delta": _white_cream_delta(Image.open(raw_path), compose),
            "integrated_white_cream_delta": _white_cream_delta(Image.open(integrated_path), compose),
            "raw_validation": validate_flyer_photo(raw_path, REF, compose).passed,
            "integrated_validation": validate_flyer_photo(integrated_path, REF, compose).passed,
        }


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "cycle1":
        print(json.dumps(cycle1_failure_analysis(), indent=2))
    elif cmd == "cycle2":
        print(json.dumps(cycle2_synthetic_compare(), indent=2))
    elif cmd == "cycle3":
        print(json.dumps(cycle3_preintegration_test(), indent=2))
    elif cmd == "all":
        print(json.dumps({
            "cycle1": cycle1_failure_analysis(),
            "cycle2": cycle2_synthetic_compare(),
            "cycle3": cycle3_preintegration_test(),
        }, indent=2))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
