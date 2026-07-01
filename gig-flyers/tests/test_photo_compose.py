#!/usr/bin/env python3
"""Tests for mask-protected band photo pre-compose (reference_compose module)."""

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
    TIER_PLACEMENTS,
    edit_mask_enabled,
    post_compose_enabled,
    post_overlay_enabled,
    prepare_photo_compose,
)


class PhotoComposeTest(unittest.TestCase):
    def _make_ref(self, path: Path, size: tuple[int, int] = (800, 600)) -> None:
        img = Image.new("RGB", size, color=(120, 80, 60))
        img.save(path, format="JPEG")

    def test_post_compose_default_on_overlay_off(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            self.assertTrue(post_compose_enabled())
            self.assertTrue(edit_mask_enabled())
            self.assertFalse(post_overlay_enabled())

    def test_compose_creates_opaque_photo_mask_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "band.jpg"
            work = Path(tmp) / "work"
            self._make_ref(ref)
            result = prepare_photo_compose(
                ref,
                (1024, 1536),
                tier="medium",
                work_dir=work,
                create_mask=True,
            )
            canvas = Image.open(result.canvas_path)
            mask = Image.open(result.mask_path)
            self.assertEqual(canvas.size, (1024, 1536))
            self.assertEqual(mask.size, (1024, 1536))

            x, y, right, bottom = result.photo_bbox
            cx, cy = (x + right) // 2, (y + bottom) // 2
            self.assertNotEqual(canvas.getpixel((cx, cy))[:3], CANVAS_BACKGROUND)
            sample = mask.getpixel((x + 2, y + 2))
            self.assertEqual(sample[3], 255)
            top = mask.getpixel((100, 20))
            self.assertEqual(top[3], 0)

    def test_tier_placements_exist(self) -> None:
        self.assertIn("conservative", TIER_PLACEMENTS)
        self.assertIn("creative", TIER_PLACEMENTS)

    @patch("openai.OpenAI")
    def test_openai_edit_uses_mask_compose_no_overlay(self, mock_openai_cls: MagicMock) -> None:
        import base64

        from image_providers.openai import OpenAIImageProvider

        mock_client = mock_openai_cls.return_value
        item = MagicMock()
        item.url = None
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            self._make_ref(ref)
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=True
            )
            item.b64_json = base64.b64encode(compose.canvas_path.read_bytes()).decode()
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_IMAGE_USE_REFERENCE": "1",
                    "OPENAI_IMAGE_POST_COMPOSE": "1",
                    "OPENAI_IMAGE_EDIT_MASK": "1",
                },
                clear=False,
            ):
                provider = OpenAIImageProvider()
                provider.generate("layout prompt", out, reference_photo_path=ref, option="A")
            mock_client.images.edit.assert_called_once()
            kwargs = mock_client.images.edit.call_args.kwargs
            self.assertIn("mask", kwargs)
            self.assertIsNotNone(kwargs["mask"])
            self.assertEqual(kwargs["input_fidelity"], "high")


if __name__ == "__main__":
    unittest.main(verbosity=2)
