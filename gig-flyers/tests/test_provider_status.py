#!/usr/bin/env python3
"""Tests for image provider configuration status."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from image_providers.provider_status import provider_status  # noqa: E402


class ProviderStatusTest(unittest.TestCase):
    def test_split_gemini_missing_key_not_ready(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GIG_IMAGE_PROVIDER_SPLIT": "1",
                "GIG_IMAGE_PROVIDER_B": "gemini",
                "OPENAI_API_KEY": "x",
                "GOOGLE_API_KEY": "",
                "GEMINI_API_KEY": "",
            },
            clear=False,
        ):
            status = provider_status()
        self.assertFalse(status["ready"])
        self.assertFalse(status["gemini_configured"])
        self.assertTrue(any("Gemini" in issue for issue in status["issues"]))

    def test_openai_only_ready_with_openai_key(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GIG_IMAGE_PROVIDER": "openai",
                "GIG_IMAGE_PROVIDER_SPLIT": "0",
                "OPENAI_API_KEY": "x",
                "GOOGLE_API_KEY": "",
            },
            clear=False,
        ):
            status = provider_status()
        self.assertTrue(status["ready"])


if __name__ == "__main__":
    unittest.main()
