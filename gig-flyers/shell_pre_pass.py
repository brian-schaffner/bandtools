"""Fast text-only mockup on a pass-1 shell — preview before choosing final route."""

from __future__ import annotations

import os
from pathlib import Path

from shell_model_policy import ShellModelChoice, select_model_for_step
from shell_references import ShellReference


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
) -> tuple[Path, ShellModelChoice]:
    """Swap placeholder text with gig facts — no photo, no logo, draft quality."""
    from openai import OpenAI

    from personalize_shell_flyer import personalize_shell_typography_sequential

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    choice = model_choice or select_model_for_step(shell, "prepass")
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
    )
    return result, choice
