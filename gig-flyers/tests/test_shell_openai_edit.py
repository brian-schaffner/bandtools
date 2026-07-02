#!/usr/bin/env python3
"""Tests for shell OpenAI edit helper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_model_policy import ShellModelChoice  # noqa: E402
from shell_openai_edit import shell_images_edit  # noqa: E402


class ShellOpenAiEditTest(unittest.TestCase):
    def test_passes_input_fidelity_when_set(self) -> None:
        client = MagicMock()
        client.images.edit.return_value = MagicMock()
        image = MagicMock()
        choice = ShellModelChoice(
            step="final_text",
            model="gpt-image-1.5",
            quality="high",
            size="1024x1536",
            input_fidelity="high",
            score=90,
            rationale="test",
        )
        shell_images_edit(client, image=image, prompt="hello", choice=choice)
        kwargs = client.images.edit.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-image-1.5")
        self.assertEqual(kwargs["input_fidelity"], "high")

    def test_omits_input_fidelity_when_none(self) -> None:
        client = MagicMock()
        client.images.edit.return_value = MagicMock()
        image = MagicMock()
        choice = ShellModelChoice(
            step="pass1",
            model="gpt-image-2",
            quality="high",
            size="1024x1536",
            input_fidelity=None,
            score=100,
            rationale="test",
        )
        shell_images_edit(client, image=image, prompt="hello", choice=choice)
        kwargs = client.images.edit.call_args.kwargs
        self.assertNotIn("input_fidelity", kwargs)


if __name__ == "__main__":
    unittest.main()
