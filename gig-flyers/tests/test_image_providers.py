#!/usr/bin/env python3
"""Tests for image providers."""

from __future__ import annotations

import base64
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from image_providers.base import (  # noqa: E402
    get_image_provider,
    is_provider_split_enabled,
    resolve_image_provider,
    resolve_image_provider_for_option,
    resolve_provider_map,
    split_provider_summary,
)  # noqa: E402
from image_providers.gemini import GeminiImageProvider  # noqa: E402
from image_providers.openai import OpenAIImageProvider, _resolve_image_quality  # noqa: E402
from image_providers.reference_compose import PhotoValidationResult  # noqa: E402
from PIL import Image  # noqa: E402


def _make_test_jpeg(path: Path, size: tuple[int, int] = (320, 210)) -> None:
    img = Image.new("RGB", size, color=(210, 200, 190))
    img.save(path, format="JPEG")


def _fake_png_b64(width: int = 1024, height: int = 1536) -> str:
    import base64
    import io

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(30, 30, 30)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _mock_png_b64(size: tuple[int, int] = (1024, 1536)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(230, 230, 230)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _canvas_b64_for_ref(ref: Path, *, tier: str = "medium") -> str:
    """Mock API returns unchanged photo-on-canvas (passes validation)."""
    from image_providers.reference_compose import prepare_canvas_with_photo

    with tempfile.TemporaryDirectory() as tmp:
        compose = prepare_canvas_with_photo(
            ref,
            (1024, 1536),
            tier=tier,
            work_dir=Path(tmp),
            create_mask=True,
        )
        return base64.b64encode(compose.canvas_path.read_bytes()).decode()


class ImageProviderTest(unittest.TestCase):
    def test_resolve_defaults_openai(self) -> None:
        with patch.dict("os.environ", {"GIG_IMAGE_PROVIDER": "", "OPENAI_API_KEY": "x"}, clear=False):
            self.assertEqual(resolve_image_provider(), "openai")

    def test_resolve_gemini_when_configured(self) -> None:
        with patch.dict(
            "os.environ",
            {"GIG_IMAGE_PROVIDER": "gemini", "GOOGLE_API_KEY": "x"},
            clear=False,
        ):
            self.assertEqual(resolve_image_provider(), "gemini")
            self.assertIsInstance(get_image_provider(), GeminiImageProvider)

    def test_get_openai_provider(self) -> None:
        with patch.dict("os.environ", {"GIG_IMAGE_PROVIDER": "openai"}, clear=False):
            self.assertIsInstance(get_image_provider(), OpenAIImageProvider)

    def test_split_defaults(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GIG_IMAGE_PROVIDER_SPLIT": "1",
                "GIG_IMAGE_PROVIDER": "gemini",
                "OPENAI_API_KEY": "x",
                "GOOGLE_API_KEY": "y",
            },
            clear=False,
        ):
            self.assertTrue(is_provider_split_enabled())
            self.assertEqual(resolve_image_provider_for_option("A"), "openai")
            self.assertEqual(resolve_image_provider_for_option("B"), "gemini")
            self.assertEqual(resolve_image_provider_for_option("C"), "gemini")
            self.assertEqual(
                resolve_provider_map(),
                {"A": "openai", "B": "gemini", "C": "gemini"},
            )
            self.assertIn("A: OpenAI", split_provider_summary())

    def test_per_option_override_without_split_flag(self) -> None:
        with patch.dict(
            "os.environ",
            {"GIG_IMAGE_PROVIDER_B": "openai", "GIG_IMAGE_PROVIDER": "gemini"},
            clear=False,
        ):
            self.assertTrue(is_provider_split_enabled())
            self.assertEqual(resolve_image_provider_for_option("B"), "openai")
            # Other letters use split defaults when any per-option override is set
            self.assertEqual(resolve_image_provider_for_option("A"), "openai")
            self.assertEqual(resolve_image_provider_for_option("C"), "gemini")

    @patch("image_providers.base.get_image_provider")
    def test_generate_with_fallback_uses_explicit_provider(self, mock_get) -> None:
        from image_providers.base import generate_with_fallback

        mock_provider = MagicMock()
        mock_get.return_value = mock_provider
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            with patch.dict("os.environ", {"GIG_IMAGE_PROVIDER": "gemini"}, clear=False):
                used = generate_with_fallback("prompt", out, provider="openai", option="A")
            self.assertEqual(used, "openai")
            mock_get.assert_called_with("openai")
            mock_provider.generate.assert_called_once()

    def test_resolve_image_quality_defaults(self) -> None:
        with patch.dict("os.environ", {"OPENAI_IMAGE_QUALITY": "medium"}, clear=False):
            self.assertEqual(_resolve_image_quality(), "medium")
            self.assertEqual(_resolve_image_quality("high"), "high")

    @patch("image_providers.openai.validate_flyer_photo", return_value=PhotoValidationResult(passed=True, checks=[]))
    @patch("openai.OpenAI")
    def test_openai_generate_uses_quality_before_api_call(
        self, mock_openai_cls: MagicMock, _mock_validate: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _make_test_jpeg(ref)
            item.b64_json = _canvas_b64_for_ref(ref, tier="creative")
            with patch.dict(
                "os.environ",
                {"OPENAI_API_KEY": "test-key", "OPENAI_IMAGE_QUALITY": "medium", "OPENAI_IMAGE_USE_REFERENCE": "1"},
                clear=False,
            ):
                provider = OpenAIImageProvider()
                provider.generate("prompt", out, reference_photo_path=ref, option="C", quality="high")
            mock_client.images.edit.assert_called_once()
            self.assertEqual(mock_client.images.edit.call_args.kwargs["quality"], "high")
            self.assertTrue(out.is_file())

    @patch("image_providers.openai.validate_flyer_photo", return_value=PhotoValidationResult(passed=True, checks=[]))
    @patch("openai.OpenAI")
    def test_openai_generate_edit_path_with_reference(
        self, mock_openai_cls: MagicMock, _mock_validate: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _make_test_jpeg(ref)
            item.b64_json = _canvas_b64_for_ref(ref, tier="medium")
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_IMAGE_USE_REFERENCE": "1",
                    "OPENAI_IMAGE_INPUT_FIDELITY": "high",
                },
                clear=False,
            ):
                provider = OpenAIImageProvider()
                provider.generate("prompt", out, reference_photo_path=ref, option="A", quality="medium")
            mock_client.images.edit.assert_called_once()
            self.assertEqual(mock_client.images.edit.call_args.kwargs["quality"], "medium")
            self.assertEqual(mock_client.images.edit.call_args.kwargs["input_fidelity"], "high")
            self.assertIn("mask", mock_client.images.edit.call_args.kwargs)

    @patch("image_providers.openai.validate_flyer_photo", return_value=PhotoValidationResult(passed=True, checks=[]))
    @patch("openai.OpenAI")
    def test_generate_image_tier_quality_integration(
        self, mock_openai_cls: MagicMock, _mock_validate: MagicMock
    ) -> None:
        from flyer_generator import generate_image

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _make_test_jpeg(ref)
            item.b64_json = _canvas_b64_for_ref(ref, tier="creative")
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "GIG_IMAGE_PROVIDER": "openai",
                    "OPENAI_IMAGE_USE_REFERENCE": "1",
                },
                clear=False,
            ):
                generate_image(
                    "prompt",
                    out,
                    reference_photo_path=ref,
                    option="C",
                    tier="creative",
                )
            mock_client.images.edit.assert_called_once()
            self.assertEqual(mock_client.images.edit.call_args.kwargs["quality"], "high")
            self.assertEqual(mock_client.images.edit.call_args.kwargs["input_fidelity"], "high")

    @patch("image_providers.openai.validate_flyer_photo", return_value=PhotoValidationResult(passed=True, checks=[]))
    @patch("openai.OpenAI")
    def test_conservative_tier_uses_high_quality_with_reference(
        self, mock_openai_cls: MagicMock, _mock_validate: MagicMock
    ) -> None:
        from flyer_generator import generate_image

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _make_test_jpeg(ref)
            item.b64_json = _canvas_b64_for_ref(ref, tier="conservative")
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "GIG_IMAGE_PROVIDER": "openai",
                    "OPENAI_IMAGE_USE_REFERENCE": "1",
                },
                clear=False,
            ):
                generate_image(
                    "prompt",
                    out,
                    reference_photo_path=ref,
                    option="A",
                    tier="conservative",
                )
            self.assertEqual(mock_client.images.edit.call_args.kwargs["quality"], "high")

    @patch("image_providers.openai.validate_flyer_photo", return_value=PhotoValidationResult(passed=True, checks=[]))
    @patch("openai.OpenAI")
    def test_openai_edit_prepends_reference_fidelity_prefix(
        self, mock_openai_cls: MagicMock, _mock_validate: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _make_test_jpeg(ref)
            item.b64_json = _canvas_b64_for_ref(ref, tier="medium")
            with patch.dict(
                "os.environ",
                {"OPENAI_API_KEY": "test-key", "OPENAI_IMAGE_USE_REFERENCE": "1"},
                clear=False,
            ):
                from image_providers.openai import REFERENCE_EDIT_PROMPT_PREFIX, OpenAIImageProvider

                provider = OpenAIImageProvider()
                provider.generate("layout prompt here", out, reference_photo_path=ref, option="A")
            prompt_sent = mock_client.images.edit.call_args.kwargs["prompt"]
            self.assertTrue(prompt_sent.startswith(REFERENCE_EDIT_PROMPT_PREFIX))
            self.assertIn("layout prompt here", prompt_sent)

    @patch("openai.OpenAI")
    def test_openai_wild_band_replace_uses_dual_images(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        item.b64_json = _mock_png_b64()
        mock_client.images.edit.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            poster = Path(tmp) / "poster.png"
            band = Path(tmp) / "band.jpg"
            _make_test_jpeg(band)
            Image.new("RGB", (1024, 1536), color=(40, 30, 20)).save(poster, format="PNG")
            with patch.dict(
                "os.environ",
                {"OPENAI_API_KEY": "test-key", "OPENAI_IMAGE_USE_REFERENCE": "1"},
                clear=False,
            ):
                from image_providers.openai import WILD_BAND_REPLACE_PROMPT_PREFIX, OpenAIImageProvider

                provider = OpenAIImageProvider()
                provider.generate(
                    "swap band members",
                    out,
                    reference_photo_path=band,
                    design_reference_path=poster,
                    option="D",
                )
            kwargs = mock_client.images.edit.call_args.kwargs
            self.assertEqual(kwargs["input_fidelity"], "high")
            self.assertTrue(kwargs["prompt"].startswith(WILD_BAND_REPLACE_PROMPT_PREFIX))
            self.assertIn("swap band members", kwargs["prompt"])
            self.assertIsInstance(kwargs["image"], list)
            self.assertEqual(len(kwargs["image"]), 2)
            self.assertEqual(kwargs["image"][0][0], "poster.png")
            self.assertEqual(kwargs["image"][1][0], "band.jpg")

    def test_openai_missing_reference_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            missing = Path(tmp) / "missing.jpg"
            with patch.dict(
                "os.environ",
                {"OPENAI_API_KEY": "test-key", "OPENAI_IMAGE_USE_REFERENCE": "1"},
                clear=False,
            ):
                provider = OpenAIImageProvider()
                with self.assertRaises(RuntimeError):
                    provider.generate("prompt", out, reference_photo_path=missing)

    @patch("openai.OpenAI")
    def test_openai_text_to_image_without_reference(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        item = MagicMock()
        item.url = None
        item.b64_json = _mock_png_b64()
        mock_client.images.generate.return_value = MagicMock(data=[item])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            with patch.dict(
                "os.environ",
                {"OPENAI_API_KEY": "test-key", "OPENAI_IMAGE_USE_REFERENCE": "1"},
                clear=False,
            ):
                provider = OpenAIImageProvider()
                provider.generate("wild poster prompt", out, reference_photo_path=None, option="A")
            mock_client.images.generate.assert_called_once()
            mock_client.images.edit.assert_not_called()

    @patch("google.genai.Client")
    def test_gemini_generate_writes_file(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        part = MagicMock()
        candidate = MagicMock()
        candidate.content.parts = [part]
        mock_client.models.generate_content.return_value = MagicMock(candidates=[candidate])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _make_test_jpeg(ref)
            from image_providers.reference_compose import prepare_canvas_with_photo

            compose = prepare_canvas_with_photo(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            part.inline_data.data = compose.canvas_path.read_bytes()
            with patch.dict(
                "os.environ",
                {"GOOGLE_API_KEY": "test", "GEMINI_IMAGE_MODEL": "gemini-2.5-flash-image"},
            ), patch(
                "image_providers.gemini.validate_flyer_photo",
                return_value=MagicMock(passed=True, checks=[]),
            ), patch("image_providers.gemini.enforce_photo_bbox"):
                provider = GeminiImageProvider()
                provider.generate("prompt", out, reference_photo_path=ref)
            self.assertTrue(out.is_file())


class BandReplaceFallbackTests(unittest.TestCase):
  @patch("image_providers.base.get_image_provider")
  def test_falls_back_to_gemini_when_openai_fails(self, mock_get_provider: MagicMock) -> None:
    from image_providers.base import generate_band_replace_with_fallback

    openai = MagicMock()
    openai.generate.side_effect = RuntimeError("openai edit failed")
    gemini = MagicMock()
    mock_get_provider.side_effect = lambda name: openai if name == "openai" else gemini

    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp) / "flyer.png"
      poster = Path(tmp) / "poster.png"
      band = Path(tmp) / "band.jpg"
      _make_test_jpeg(band)
      Image.new("RGB", (1024, 1536), color=(20, 20, 20)).save(poster)
      with patch("image_providers.base._openai_key", return_value="test"), patch(
        "image_providers.base._google_key", return_value="test"
      ):
        used = generate_band_replace_with_fallback(
          "swap band",
          out,
          reference_photo_path=band,
          design_reference_path=poster,
          provider="openai",
          option="B",
        )
      self.assertEqual(used, "gemini")
      gemini.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
