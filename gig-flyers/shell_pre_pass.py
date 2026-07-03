"""Fast text-only mockup on a pass-1 shell — preview before choosing final route."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from shell_deterministic_text import apply_deterministic_text
from shell_model_policy import ShellModelChoice, select_model_for_step
from shell_references import PLACEHOLDER_LABELS, ShellReference
from shell_render_registry import get_render_spec


def _prepass_use_openai(spec_text_engine: str) -> bool:
    if spec_text_engine == "openai":
        return True
    override = (os.getenv("SHELL_PREPASS_OPENAI") or "").strip().lower()
    return override in {"1", "true", "yes", "on"}


def build_prepass_mockup_deterministic(
    shell: ShellReference,
    shell_image_path: Path,
    output_path: Path,
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
) -> Path:
    """PIL-only gig fact preview — no OpenAI (headliner is plain text until final pass)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(shell_image_path, output_path)
    apply_deterministic_text(
        output_path,
        shell,
        band=band,
        venue=venue,
        date=date,
        time=time,
        labels=PLACEHOLDER_LABELS,
    )
    return output_path


def build_prepass_mockup(
    shell: ShellReference,
    shell_image_path: Path,
    output_path: Path,
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
    model_choice: ShellModelChoice | None = None,
    on_openai_call: Callable[[], None] | None = None,
) -> tuple[Path, ShellModelChoice]:
    """Swap placeholder text with gig facts — PIL preview by default, OpenAI when required."""
    spec = get_render_spec(shell)
    choice = model_choice or select_model_for_step(shell, "prepass")

    if not _prepass_use_openai(spec.text_engine):
        result = build_prepass_mockup_deterministic(
            shell,
            shell_image_path,
            output_path,
            band=band,
            venue=venue,
            date=date,
            time=time,
        )
        pil_choice = ShellModelChoice(
            step="prepass",
            model="pil",
            quality="preview",
            size=choice.size,
            input_fidelity=None,
            score=choice.score,
            rationale="PIL-only pre-pass (deterministic/hybrid — stylized headliner on final pass)",
        )
        return result, pil_choice

    from openai import OpenAI

    from personalize_shell_flyer import personalize_shell_typography_sequential

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    client = OpenAI(api_key=api_key)
    result = personalize_shell_typography_sequential(
        shell,
        shell_image_path,
        output_path,
        band=band,
        venue=venue,
        date=date,
        time=time,
        client=client,
        model_choice=choice,
        on_openai_call=on_openai_call,
    )
    return result, choice
