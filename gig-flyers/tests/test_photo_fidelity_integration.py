#!/usr/bin/env python3
"""Integration tests for single-pass photo-on-canvas band photo fidelity."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from image_providers.reference_compose import (  # noqa: E402
    CANVAS_BACKGROUND,
    PHOTO_DRIFT_THRESHOLD,
    PHOTO_VALIDATION_DRIFT_THRESHOLD,
    detect_double_band_photo,
    detect_horizontal_strip,
    photo_bbox_drift,
    prepare_photo_compose,
    validate_flyer_photo,
)


def _band_photo_path() -> Path | None:
    candidates = [
        ROOT / "bandphotos" / "595023002_1261617739108475_4864313333830117636_n.jpg",
        ROOT / "bandphotos" / "679394308_1366641221939459_1410337987474015419_n.jpg",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _synthetic_band(path: Path, size: tuple[int, int] = (800, 600)) -> None:
    img = Image.new("RGB", size, color=(120, 80, 60))
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 60, 720, 540], fill=(180, 140, 100))
    draw.ellipse([200, 120, 320, 240], fill=(220, 190, 160))
    draw.ellipse([480, 120, 600, 240], fill=(210, 180, 150))
    img.save(path, format="JPEG")


class PhotoFidelityIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = _band_photo_path()
        if self.reference is None:
            self.skipTest("No band photo in bandphotos/")

    def test_compose_canvas_includes_band_photo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            compose = prepare_photo_compose(
                self.reference,
                (1024, 1536),
                tier="medium",
                work_dir=Path(tmp),
                create_mask=True,
            )
            canvas = Image.open(compose.canvas_path).convert("RGB")
            cx = (compose.photo_bbox[0] + compose.photo_bbox[2]) // 2
            cy = (compose.photo_bbox[1] + compose.photo_bbox[3]) // 2
            self.assertNotEqual(canvas.getpixel((cx, cy)), CANVAS_BACKGROUND)

    def test_single_pass_canvas_passes_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            out = work / "flyer.png"
            compose = prepare_photo_compose(
                self.reference,
                (1024, 1536),
                tier="conservative",
                work_dir=work / "compose",
                create_mask=False,
            )
            Image.open(compose.canvas_path).convert("RGB").save(out, format="PNG")

            result = validate_flyer_photo(out, self.reference, compose)
            self.assertTrue(result.passed, result.checks)
            drift = next(c for c in result.checks if c["name"] == "photo_bbox_drift")
            self.assertLessEqual(drift["value"], PHOTO_VALIDATION_DRIFT_THRESHOLD)

    def test_photo_pixels_match_pil_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            compose = prepare_photo_compose(
                self.reference,
                (1024, 1536),
                tier="medium",
                work_dir=Path(tmp),
                create_mask=False,
            )
            out = Path(tmp) / "flyer.png"
            Image.open(compose.canvas_path).convert("RGB").save(out, format="PNG")
            drift = photo_bbox_drift(out, compose)
            self.assertLessEqual(drift, PHOTO_DRIFT_THRESHOLD)

    def test_detect_horizontal_strip_on_synthetic_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            _synthetic_band(ref)
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            flyer = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            band_patch = Image.open(ref).convert("RGB").resize((right - left, bottom - top))
            strip_h = 24
            strip = band_patch.crop((0, bottom - top - strip_h, right - left, bottom - top))
            flyer.paste(strip, (left, bottom))
            flyer.save(out, format="PNG")
            self.assertTrue(detect_horizontal_strip(out, compose))

    def test_validation_fails_on_duplicate_outside_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            _synthetic_band(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            flyer = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            ref_img = Image.open(ref).convert("RGB")
            dup_w = max(120, (right - left) // 3)
            dup_h = max(90, (bottom - top) // 3)
            flyer.paste(ref_img.resize((dup_w, dup_h)), (40, 40))
            flyer.save(out, format="PNG")
            result = validate_flyer_photo(out, ref, compose)
            self.assertFalse(result.passed)

    def test_validation_fails_on_model_drift_no_overlay_rescue(self) -> None:
        """Simulate API drawing wrong band in photo region — fail validation, no post-paste fix."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            _synthetic_band(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            flyer = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            fake_band = Image.new("RGB", (right - left, bottom - top), color=(180, 120, 90))
            flyer.paste(fake_band, (left, top))
            flyer.save(out, format="PNG")
            self.assertGreater(photo_bbox_drift(out, compose), PHOTO_DRIFT_THRESHOLD)
            result = validate_flyer_photo(out, ref, compose)
            self.assertFalse(result.passed)
            drift_check = next(c for c in result.checks if c["name"] == "photo_bbox_drift")
            self.assertFalse(drift_check["passed"])

    def test_all_tiers_canvas_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for tier in ("conservative", "medium", "creative"):
                work = Path(tmp) / tier
                out = work / "flyer.png"
                compose = prepare_photo_compose(
                    self.reference,
                    (1024, 1536),
                    tier=tier,
                    work_dir=work / "compose",
                    create_mask=False,
                )
                Image.open(compose.canvas_path).convert("RGB").save(out, format="PNG")
                result = validate_flyer_photo(out, self.reference, compose)
                self.assertTrue(result.passed, f"{tier}: {result.checks}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
