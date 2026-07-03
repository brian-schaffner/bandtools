#!/usr/bin/env python3
"""Tests for pre-pass mockup module."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_model_policy import ShellModelChoice  # noqa: E402
from shell_pre_pass import build_prepass_mockup  # noqa: E402
from shell_references import get_shell  # noqa: E402


class ShellPrePassTest(unittest.TestCase):
    def test_build_prepass_mockup_uses_pil_for_hybrid(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        with tempfile.TemporaryDirectory() as tmp:
            shell_path = Path(tmp) / "shell.png"
            Image.new("RGB", (400, 600), (255, 220, 0)).save(shell_path)
            out_path = Path(tmp) / "mockup.png"

            result_path, used = build_prepass_mockup(
                shell,
                shell_path,
                out_path,
                band="Lindsey Lane Band",
                venue="Test Venue",
                date="Friday, July 4, 2026",
                time="6:30 PM",
            )
            self.assertEqual(result_path, out_path)
            self.assertEqual(used.model, "pil")
            self.assertTrue(out_path.is_file())

    def test_build_prepass_mockup_openai_when_forced(self) -> None:
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
                with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "SHELL_PREPASS_OPENAI": "1"}):
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


if __name__ == "__main__":
    unittest.main()
