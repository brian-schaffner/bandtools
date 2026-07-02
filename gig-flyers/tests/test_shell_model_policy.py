#!/usr/bin/env python3
"""Tests for per-step shell model selection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_model_policy import (  # noqa: E402
    build_run_model_plan,
    select_model_for_step,
)
from shell_references import get_shell  # noqa: E402


class ShellModelPolicyTest(unittest.TestCase):
    def test_auto_selects_gpt_image_2_for_pass1(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        with patch.dict("os.environ", {"SHELL_MODEL_POLICY": "auto"}, clear=False):
            choice = select_model_for_step(shell, "pass1")
        self.assertEqual(choice.model, "gpt-image-2")
        self.assertEqual(choice.quality, "high")

    def test_fillmore_final_text_prefers_gpt_image_2(self) -> None:
        shell = get_shell("fillmore_jefferson_airplane_1966")
        assert shell is not None
        with patch.dict("os.environ", {"SHELL_MODEL_POLICY": "auto"}, clear=False):
            choice = select_model_for_step(shell, "final_text", route="text_only")
        self.assertEqual(choice.model, "gpt-image-2")
        self.assertIn("typography", choice.rationale.lower())

    def test_prepass_uses_draft_quality(self) -> None:
        shell = get_shell("woodstock_festival_1969")
        assert shell is not None
        with patch.dict("os.environ", {"SHELL_MODEL_POLICY": "auto"}, clear=False):
            choice = select_model_for_step(shell, "prepass")
        self.assertEqual(choice.model, "gpt-image-2")
        self.assertEqual(choice.quality, "low")

    def test_fixed_policy_uses_global_model(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        with patch.dict(
            "os.environ",
            {"SHELL_MODEL_POLICY": "fixed", "OPENAI_IMAGE_MODEL": "gpt-image-1"},
            clear=False,
        ):
            choice = select_model_for_step(shell, "final_photo")
        self.assertEqual(choice.model, "gpt-image-1")
        self.assertIn("fixed", choice.rationale.lower())

    def test_env_override_for_step(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        with patch.dict(
            "os.environ",
            {"OPENAI_IMAGE_MODEL_SHELL_PASS1": "gpt-image-1.5"},
            clear=False,
        ):
            choice = select_model_for_step(shell, "pass1")
        self.assertEqual(choice.model, "gpt-image-1.5")
        self.assertIn("override", choice.rationale.lower())

    def test_build_run_model_plan_has_all_steps(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        with patch.dict("os.environ", {"SHELL_MODEL_POLICY": "auto"}, clear=False):
            plan = build_run_model_plan(shell)
        self.assertEqual(plan["policy"], "auto")
        self.assertIn("pass1", plan["steps"])
        self.assertIn("prepass", plan["steps"])
        self.assertIn("final_text", plan["steps"])
        self.assertIn("final_photo", plan["steps"])

    def test_gpt_image_2_omits_input_fidelity(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        with patch.dict("os.environ", {"SHELL_MODEL_POLICY": "auto"}, clear=False):
            choice = select_model_for_step(shell, "final_photo")
        self.assertEqual(choice.model, "gpt-image-2")
        self.assertIsNone(choice.input_fidelity)

    def test_gpt_image_1_uses_input_fidelity(self) -> None:
        shell = get_shell("hendrix_sicks_stadium_1970")
        assert shell is not None
        with patch.dict(
            "os.environ",
            {"SHELL_MODEL_POLICY": "fixed", "OPENAI_IMAGE_MODEL": "gpt-image-1"},
            clear=False,
        ):
            choice = select_model_for_step(shell, "final_photo")
        self.assertEqual(choice.input_fidelity, "high")


if __name__ == "__main__":
    unittest.main()
