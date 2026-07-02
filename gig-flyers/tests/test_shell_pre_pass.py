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

from shell_model_policy import ShellModelChoice  # noqa: E402
from shell_pre_pass import build_prepass_mockup  # noqa: E402
from shell_references import get_shell  # noqa: E402


class ShellPrePassTest(unittest.TestCase):
    def test_build_prepass_mockup_uses_model_choice(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        choice = ShellModelChoice(
            step="prepass",
            model="gpt-image-2",
            quality="low",
            size="1024x1536",
            input_fidelity=None,
            score=95,
            rationale="test",
        )
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
                    result_path, used = build_prepass_mockup(
                        shell,
                        shell_path,
                        out_path,
                        band="Lindsey Lane Band",
                        venue="Test Venue",
                        date="Friday, July 4, 2026",
                        time="6:30 PM",
                        model_choice=choice,
                    )
            self.assertEqual(result_path, out_path)
            self.assertEqual(used.model, "gpt-image-2")
            seq.assert_called_once()
            self.assertEqual(seq.call_args.kwargs["model_choice"].quality, "low")


if __name__ == "__main__":
    unittest.main()
