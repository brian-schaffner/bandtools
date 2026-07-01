#!/usr/bin/env python3
"""Tests for mask-protected band photo pre-compose."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from image_providers.reference_compose import (  # noqa: E402
    CANVAS_BACKGROUND,
    PHOTO_DRIFT_THRESHOLD,
    TYPO_EXCLUSION_PAD_PX,
    composite_band_photo,
    detect_double_band_photo,
    detect_footer_band_duplicate,
    detect_horizontal_strip,
    enforce_photo_bbox,
    photo_bbox_drift,
    prepare_photo_compose,
    protection_zone,
    typography_zones,
    validate_flyer_photo,
)


def _write_test_jpeg(path: Path, size: tuple[int, int] = (800, 600)) -> None:
    Image.new("RGB", size, color=(120, 80, 60)).save(path, format="JPEG")


class ReferenceComposeTest(unittest.TestCase):
    def test_compose_creates_opaque_photo_mask_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            work = Path(tmp) / "work"
            _write_test_jpeg(ref)
            result = prepare_photo_compose(
                ref,
                (1024, 1536),
                tier="medium",
                work_dir=work,
                create_mask=True,
            )
            self.assertTrue(result.canvas_path.is_file())
            self.assertIsNotNone(result.mask_path)
            assert result.mask_path is not None

            canvas = Image.open(result.canvas_path)
            mask = Image.open(result.mask_path)
            self.assertEqual(canvas.size, (1024, 1536))
            self.assertEqual(mask.size, (1024, 1536))

            x, y, right, bottom = result.photo_bbox
            cx, cy = (x + right) // 2, (y + bottom) // 2
            self.assertNotEqual(canvas.getpixel((cx, cy))[:3], CANVAS_BACKGROUND)
            sample = mask.getpixel((x + 2, y + 2))
            self.assertEqual(sample[3], 255)
            pl, pt, pr, pb = result.protection_bbox
            band_sample = mask.getpixel((pr - 2, (pt + pb) // 2))
            self.assertEqual(band_sample[3], 255)
            top = mask.getpixel((100, 20))
            self.assertEqual(top[3], 0, "header above photo must be editable")
            _, ptop, _, _ = result.photo_bbox
            if ptop > TYPO_EXCLUSION_PAD_PX + 40:
                above_photo = mask.getpixel((512, ptop - TYPO_EXCLUSION_PAD_PX - 20))
                self.assertEqual(above_photo[3], 0, "paper above photo must be editable")

    def test_protection_zone_wraps_photo_with_padding(self) -> None:
        bbox = (200, 400, 700, 900)
        zone = protection_zone(bbox, (1024, 1536))
        self.assertLessEqual(zone[0], bbox[0])
        self.assertLessEqual(zone[1], bbox[1])
        self.assertGreaterEqual(zone[2], bbox[2])
        self.assertGreaterEqual(zone[3], bbox[3])
        self.assertGreaterEqual(bbox[0] - zone[0], TYPO_EXCLUSION_PAD_PX - 1)
        self.assertGreaterEqual(bbox[1] - zone[1], TYPO_EXCLUSION_PAD_PX - 1)

    def test_typography_zones_clear_photo_border_margin(self) -> None:
        bbox = (100, 500, 900, 1100)
        zones = typography_zones((1024, 1536), photo_bbox=bbox)
        top_zone = zones[0]
        bottom_zone = zones[1]
        self.assertLessEqual(top_zone[3], bbox[1] - TYPO_EXCLUSION_PAD_PX + 1)
        self.assertGreaterEqual(bottom_zone[1], bbox[3] + TYPO_EXCLUSION_PAD_PX - 1)

    def test_detect_double_band_photo_on_synthetic_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            work = Path(tmp) / "work"
            _write_test_jpeg(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=work, create_mask=False
            )
            flyer = Image.new("RGB", (1024, 1536), color=(245, 240, 230))
            left, top, right, bottom = compose.photo_bbox
            ref_img = Image.open(ref).convert("RGB")
            flyer.paste(ref_img.resize((right - left, bottom - top)), (left, top))
            dup_w = max(96, (right - left) // 4)
            dup_h = max(72, (bottom - top) // 4)
            flyer.paste(ref_img.resize((dup_w, dup_h)), (40, 40))
            flyer.save(out, format="PNG")
            self.assertTrue(detect_double_band_photo(out, compose))

    def test_tier_placements_differ(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            _write_test_jpeg(ref)
            conservative = prepare_photo_compose(
                ref, (1024, 1536), tier="conservative", work_dir=Path(tmp) / "a", create_mask=False
            )
            creative = prepare_photo_compose(
                ref, (1024, 1536), tier="creative", work_dir=Path(tmp) / "c", create_mask=False
            )
            self.assertNotEqual(conservative.photo_bbox, creative.photo_bbox)

    def test_enforce_replaces_photo_region_after_resize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            work = Path(tmp) / "work"
            _write_test_jpeg(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="conservative", work_dir=work, create_mask=False
            )
            # Simulate API returning a different size than the input canvas
            Image.new("RGB", (512, 768), color=(200, 200, 200)).save(out, format="PNG")
            enforce_photo_bbox(out, compose, force=True)
            restored = Image.open(out)
            self.assertEqual(restored.size, (1024, 1536))
            x, y, _, _ = compose.photo_bbox
            pixel = restored.getpixel((x + 5, y + 5))
            self.assertNotEqual(pixel, (200, 200, 200))

    def test_composite_band_photo_legacy_overlay(self) -> None:
        """Legacy post-overlay path — paste onto cream plate without pre-placed photo."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            work = Path(tmp) / "work"
            band = Image.new("RGB", (500, 350), color=(90, 70, 55))
            band.save(ref, format="JPEG")
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=work, create_mask=False
            )
            # Legacy: start from cream plate (simulate typography-only API output)
            Image.new("RGB", (1024, 1536), color=CANVAS_BACKGROUND).save(out, format="PNG")
            composite_band_photo(out, compose)
            self.assertFalse(detect_double_band_photo(out, compose))
            left, top, right, bottom = compose.photo_bbox
            restored = Image.open(out)
            gutter_y = bottom + 8
            if gutter_y < 1536 - 4:
                gutter_pixel = restored.getpixel((left + 10, gutter_y))
                self.assertEqual(
                    gutter_pixel,
                    (245, 240, 230),
                    "composite must not leave a band strip below the photo",
                )
            result = validate_flyer_photo(out, ref, compose)
            self.assertTrue(result.passed)

    def test_detect_horizontal_strip_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            _write_test_jpeg(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            flyer = Image.new("RGB", (1024, 1536), color=CANVAS_BACKGROUND)
            left, top, right, bottom = compose.photo_bbox
            ref_img = Image.open(ref).convert("RGB").resize((right - left, bottom - top))
            flyer.paste(ref_img, (left, top))
            row = ref_img.crop((0, ref_img.height - 1, ref_img.width, ref_img.height))
            flyer.paste(row.resize((right - left, 1)), (left, bottom))
            flyer.save(out, format="PNG")
            self.assertTrue(detect_horizontal_strip(out, compose))

    def test_detect_footer_band_duplicate_multiline_strip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            _write_test_jpeg(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="conservative", work_dir=Path(tmp) / "work", create_mask=False
            )
            flyer = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            band_patch = Image.open(ref).convert("RGB").resize((right - left, bottom - top))
            strip_h = max(48, (bottom - top) // 4)
            strip = band_patch.crop((0, bottom - top - strip_h, right - left, bottom - top))
            flyer.paste(strip, (left, bottom + 72))
            flyer.save(out, format="PNG")
            self.assertTrue(detect_footer_band_duplicate(out, compose))
            self.assertTrue(detect_horizontal_strip(out, compose))

    def test_enforce_clears_footer_strip_hazard_zone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            _write_test_jpeg(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            flyer = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            band_patch = Image.open(ref).convert("RGB").resize((right - left, bottom - top))
            strip_h = max(48, (bottom - top) // 4)
            strip = band_patch.crop((0, bottom - top - strip_h, right - left, bottom - top))
            flyer.paste(strip, (left, bottom + 72))
            flyer.save(out, format="PNG")
            enforce_photo_bbox(out, compose, force=True)
            self.assertFalse(detect_horizontal_strip(out, compose))
            restored = Image.open(out)
            gutter_pixel = restored.getpixel((left + 10, bottom + 80))
            self.assertEqual(gutter_pixel, CANVAS_BACKGROUND)

    def test_enforce_single_paste_no_double_photo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            work = Path(tmp) / "work"
            band = Image.new("RGB", (500, 350), color=(90, 70, 55))
            band.save(ref, format="JPEG")
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=work, create_mask=False
            )
            Image.new("RGB", (1024, 1536), color=(245, 240, 230)).save(out, format="PNG")
            enforce_photo_bbox(out, compose, force=True)
            self.assertFalse(detect_double_band_photo(out, compose))
            left, top, right, bottom = compose.photo_bbox
            restored = Image.open(out)
            gutter_y = bottom + 8
            if gutter_y < 1536 - 4:
                gutter_pixel = restored.getpixel((left + 10, gutter_y))
                self.assertEqual(
                    gutter_pixel,
                    (245, 240, 230),
                    "enforce must not leave a band strip below the photo",
                )

    def test_creative_tier_drift_uses_canvas_baseline(self) -> None:
        """Rotated creative photo has transparent corners — drift vs canvas, not black-filled layer."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            _write_test_jpeg(ref, (800, 600))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="creative", work_dir=Path(tmp) / "work", create_mask=False
            )
            out = Path(tmp) / "flyer.png"
            Image.open(compose.canvas_path).convert("RGB").save(out, format="PNG")
            self.assertLessEqual(photo_bbox_drift(out, compose), PHOTO_DRIFT_THRESHOLD)

    def test_enforce_clears_model_band_before_paste(self) -> None:
        """Simulate AI band under reference — enforce must erase then paste once."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            work = Path(tmp) / "work"
            _write_test_jpeg(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=work, create_mask=False
            )
            flyer = Image.new("RGB", (1024, 1536), color=(245, 240, 230))
            left, top, right, bottom = compose.photo_bbox
            # Model drew a different AI band inside the photo region only
            fake_band = Image.new("RGB", (right - left, bottom - top), color=(180, 120, 90))
            flyer.paste(fake_band, (left, top))
            flyer.save(out, format="PNG")
            self.assertGreater(photo_bbox_drift(out, compose), PHOTO_DRIFT_THRESHOLD)
            enforce_photo_bbox(out, compose, force=True)
            self.assertFalse(detect_double_band_photo(out, compose))

    def test_enforce_bbox_matches_reference_within_tint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            out = Path(tmp) / "flyer.png"
            work = Path(tmp) / "work"
            band = Image.new("RGB", (500, 350), color=(90, 70, 55))
            band.save(ref, format="JPEG")
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=work, create_mask=False
            )
            Image.new("RGB", (1024, 1536), color=(30, 30, 30)).save(out, format="PNG")
            enforce_photo_bbox(out, compose, force=True)
            drift = photo_bbox_drift(out, compose)
            self.assertLessEqual(drift, PHOTO_DRIFT_THRESHOLD)

    def test_photo_bbox_drift_zero_for_unchanged_canvas_all_tiers(self) -> None:
        """Drift compares against cream-composited layer (not black-filled RGBA corners)."""
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            _write_test_jpeg(ref, (800, 600))
            for tier in ("conservative", "medium", "creative"):
                compose = prepare_photo_compose(
                    ref,
                    (1024, 1536),
                    tier=tier,
                    work_dir=Path(tmp) / tier,
                    create_mask=False,
                )
                out = Path(tmp) / f"{tier}.png"
                Image.open(compose.canvas_path).convert("RGB").save(out, format="PNG")
                drift = photo_bbox_drift(out, compose)
                self.assertLessEqual(
                    drift,
                    PHOTO_DRIFT_THRESHOLD,
                    f"{tier} unchanged canvas drift={drift:.2f}",
                )

    def test_photo_fills_substantial_canvas_height(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            _write_test_jpeg(ref, (800, 600))
            for tier in ("conservative", "medium", "creative"):
                compose = prepare_photo_compose(
                    ref,
                    (1024, 1536),
                    tier=tier,
                    work_dir=Path(tmp) / tier,
                    create_mask=False,
                )
                _, top, _, bottom = compose.photo_bbox
                height_frac = (bottom - top) / 1536
                self.assertGreaterEqual(
                    height_frac,
                    0.40,
                    f"{tier} photo should fill at least 40% of canvas height",
                )

    @patch("openai.OpenAI")
    def test_openai_single_pass_no_post_overlay(self, mock_openai_cls: MagicMock) -> None:
        from image_providers.openai import OpenAIImageProvider

        mock_client = mock_openai_cls.return_value
        item = MagicMock()
        import base64

        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.jpg"
            _write_test_jpeg(ref)
            from image_providers.reference_compose import prepare_canvas_with_photo

            compose = prepare_canvas_with_photo(
                ref, (1024, 1536), tier="conservative", work_dir=Path(tmp) / "work", create_mask=True
            )
            # API returns canvas unchanged (typography-only edit would change header, not photo)
            canvas_bytes = compose.canvas_path.read_bytes()
            item.b64_json = base64.b64encode(canvas_bytes).decode()
            item.url = None
            mock_client.images.edit.return_value = MagicMock(data=[item])

            out = Path(tmp) / "flyer.png"
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_IMAGE_USE_REFERENCE": "1",
                    "OPENAI_IMAGE_POST_COMPOSE": "1",
                    "OPENAI_IMAGE_POST_OVERLAY": "0",
                    "OPENAI_IMAGE_EDIT_MASK": "1",
                    "OPENAI_IMAGE_ENFORCE_PHOTO": "0",
                },
                clear=False,
            ):
                provider = OpenAIImageProvider()
                provider.generate("layout prompt", out, reference_photo_path=ref, option="A", tier="conservative")
            mock_client.images.edit.assert_called_once()
            kwargs = mock_client.images.edit.call_args.kwargs
            self.assertIn("mask", kwargs)
            self.assertEqual(kwargs["input_fidelity"], "high")
            self.assertTrue(out.is_file())
            result = validate_flyer_photo(out, ref, compose)
            self.assertTrue(result.passed)

    @patch("openai.OpenAI")
    def test_photo_bbox_restored_after_model_drift(self, mock_openai_cls: MagicMock) -> None:
        """Model mutates photo region — enforce_photo_bbox restores layer; generation succeeds."""
        from image_providers.openai import OpenAIImageProvider

        mock_client = mock_openai_cls.return_value
        item = MagicMock()
        import base64

        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.jpg"
            out = Path(tmp) / "flyer.png"
            _write_test_jpeg(ref, (400, 300))
            from image_providers.reference_compose import prepare_canvas_with_photo

            compose = prepare_canvas_with_photo(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            # Simulate model redrawing band photo (wrong pixels in bbox)
            flyer = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            fake_band = Image.new("RGB", (right - left, bottom - top), color=(180, 120, 90))
            flyer.paste(fake_band, (left, top))
            buf = io.BytesIO()
            flyer.save(buf, format="PNG")
            item.b64_json = base64.b64encode(buf.getvalue()).decode()
            item.url = None
            mock_client.images.edit.return_value = MagicMock(data=[item])

            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_IMAGE_USE_REFERENCE": "1",
                    "OPENAI_IMAGE_POST_COMPOSE": "1",
                    "OPENAI_IMAGE_POST_OVERLAY": "0",
                    "OPENAI_IMAGE_ENFORCE_PHOTO": "0",
                },
                clear=False,
            ):
                provider = OpenAIImageProvider()
                provider.generate("layout prompt", out, reference_photo_path=ref, option="B", tier="medium")

            self.assertTrue(out.is_file())
            result = validate_flyer_photo(out, ref, compose)
            self.assertTrue(result.passed)
            drift_check = next(c for c in result.checks if c["name"] == "photo_bbox_drift")
            self.assertTrue(drift_check["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
