#!/usr/bin/env python3
"""Regression tests for wild Gemini generation — import safety and color-lock wiring."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from image_providers.gemini import GeminiImageProvider  # noqa: E402
from wild_design.palette import wild_color_prefix  # noqa: E402
from wild_design.prompt import build_wild_design_prompt  # noqa: E402
from option_slots import wild_variation_for_letter  # noqa: E402


def _mock_png_bytes() -> bytes:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (64, 96), color=(20, 20, 20)).save(buf, format="PNG")
    return buf.getvalue()


class WildGeminiIntegrationTests(unittest.TestCase):
    def test_gemini_provider_class_loads(self) -> None:
        """Regression: GeminiImageProvider must inherit ImageProvider (import not broken)."""
        from image_providers.base import ImageProvider

        self.assertTrue(issubclass(GeminiImageProvider, ImageProvider))

    @patch("google.genai.Client")
    def test_wild_text_to_image_prepends_color_lock(self, mock_client_cls: MagicMock) -> None:
        part = MagicMock()
        part.inline_data.data = _mock_png_bytes()
        candidate = MagicMock()
        candidate.content.parts = [part]
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(candidates=[candidate])
        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wild-a.png"
            with patch.dict(
                "os.environ",
                {"GOOGLE_API_KEY": "test", "GEMINI_IMAGE_MODEL": "gemini-2.5-flash-image"},
                clear=False,
            ), patch("image_providers.gemini._gemini_api_key", return_value="test-key"):
                provider = GeminiImageProvider()
                provider.generate(
                    "Design a bar flyer",
                    out,
                    option="A",
                    tier="wild",
                )

            self.assertTrue(out.is_file())
            sent = mock_client.models.generate_content.call_args.kwargs["contents"]
            prompt_sent = sent[0]
            self.assertIn("COLOR LOCK", prompt_sent)
            self.assertIn("mustard", prompt_sent.lower())
            self.assertIn("cream", prompt_sent.lower())
            self.assertIn("halftone", prompt_sent.lower())
            self.assertTrue(prompt_sent.startswith("COLOR LOCK"))

    def test_wild_prompt_bans_cream_and_yellow_halftone(self) -> None:
        event = GigEvent(
            event_date=__import__("datetime").date(2026, 6, 28),
            time_label="7:00 PM",
            title="Lindsey Lane Band",
            venue="Two Lane Tavern",
            suggested_name="Jun 28 Two Lane Tavern",
        )
        prompt = build_wild_design_prompt(
            {},
            event,
            wild_variation_for_letter("A"),
            1,
            option_letter="A",
        )
        lower = prompt.lower()
        self.assertIn("color lock", lower)
        self.assertIn("cream", lower)
        self.assertIn("halftone", lower)
        self.assertIn("natural skin", lower)

    def test_color_prefix_matches_option_letter(self) -> None:
        a = wild_color_prefix("A")
        b = wild_color_prefix("B")
        self.assertIn("brick-red", a.lower())
        self.assertIn("denim-blue", b.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
