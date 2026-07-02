#!/usr/bin/env python3
"""Tests for pre-pass mockup module."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_pre_pass import build_prepass_mockup, prepass_quality  # noqa: E402
from shell_references import get_shell  # noqa: E402


class ShellPrePassTest(unittest.TestCase):
    def test_prepass_quality_default(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            self.assertEqual(prepass_quality(), "medium")

    def test_build_prepass_mockup_delegates_sequential(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        with tempfile.TemporaryDirectory() as tmp:
            shell_path = Path(tmp) / "shell.png"
            shell_path.write_bytes(b"fake")
            out_path = Path(tmp) / "mockup.png"

            mock_client = MagicMock()
            with patch("openai.OpenAI", return_value=mock_client), patch(
                "personalize_shell_flyer.personalize_shell_typography_sequential",
                return_value=out_path,
            ) as seq:
                with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                    result = build_prepass_mockup(
                        shell,
                        shell_path,
                        out_path,
                        band="Lindsey Lane Band",
                        venue="Test Venue",
                        date="Friday, July 4, 2026",
                        time="6:30 PM",
                    )
            self.assertEqual(result, out_path)
            seq.assert_called_once()
            kwargs = seq.call_args.kwargs
            self.assertEqual(kwargs["quality"], "medium")


if __name__ == "__main__":
    unittest.main()
