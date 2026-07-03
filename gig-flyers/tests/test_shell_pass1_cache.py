#!/usr/bin/env python3
"""Tests for pass 1 disk cache."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design_shell_generate import build_shell_prompt  # noqa: E402
from shell_model_policy import ShellModelChoice  # noqa: E402
from shell_pass1_cache import (  # noqa: E402
    annotate_pass1_manifest,
    load_pass1_cache,
    pass1_manifest_path,
    pass1_shell_path,
)
from shell_references import get_shell  # noqa: E402


class ShellPass1CacheTest(unittest.TestCase):
    def test_cache_hit_when_key_matches(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        choice = ShellModelChoice(
            step="pass1",
            model="gpt-image-2",
            quality="high",
            size="1024x1536",
            input_fidelity=None,
            score=100,
            rationale="test",
        )
        prompt = build_shell_prompt(shell)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            shell_path = pass1_shell_path(output_dir, shell.id)
            Image.new("RGB", (1024, 1536), (255, 220, 0)).save(shell_path)

            manifest = annotate_pass1_manifest(
                {
                    "shell_id": shell.id,
                    "shell_rel": str(shell_path.name),
                    "prompt": prompt,
                },
                shell,
                prompt=prompt,
                choice=choice,
            )
            pass1_manifest_path(output_dir, shell.id).write_text(
                json.dumps(manifest), encoding="utf-8",
            )

            loaded = load_pass1_cache(shell, output_dir, prompt=prompt, choice=choice)
            assert loaded is not None
            self.assertTrue(loaded.get("cache_hit"))
            self.assertEqual(loaded["cache_key"], manifest["cache_key"])

    def test_cache_miss_when_prompt_changes(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        choice = ShellModelChoice(
            step="pass1",
            model="gpt-image-2",
            quality="high",
            size="1024x1536",
            input_fidelity=None,
            score=100,
            rationale="test",
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            shell_path = pass1_shell_path(output_dir, shell.id)
            Image.new("RGB", (1024, 1536), (255, 220, 0)).save(shell_path)
            manifest = annotate_pass1_manifest(
                {"shell_id": shell.id, "prompt": "old"},
                shell,
                prompt="old",
                choice=choice,
            )
            pass1_manifest_path(output_dir, shell.id).write_text(
                json.dumps(manifest), encoding="utf-8",
            )

            loaded = load_pass1_cache(
                shell,
                output_dir,
                prompt=build_shell_prompt(shell),
                choice=choice,
            )
            self.assertIsNone(loaded)


if __name__ == "__main__":
    unittest.main()
