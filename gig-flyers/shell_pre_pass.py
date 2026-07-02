"""Fast text-only mockup on a pass-1 shell — preview before choosing final route."""

from __future__ import annotations

import os
from pathlib import Path

from shell_references import ShellReference


def prepass_quality() -> str:
    return (os.getenv("SHELL_PREPASS_QUALITY") or "medium").strip().lower()


def prepass_model() -> str:
    return os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")


def prepass_size() -> str:
    return os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")


def build_prepass_mockup(
    shell: ShellReference,
    shell_image_path: Path,
    output_path: Path,
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
) -> Path:
    """Swap placeholder text with gig facts — no photo, no logo, medium quality."""
    from openai import OpenAI

    from personalize_shell_flyer import personalize_shell_typography_sequential

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    client = OpenAI(api_key=api_key)
    return personalize_shell_typography_sequential(
        shell,
        shell_image_path,
        output_path,
        band=band,
        venue=venue,
        date=date,
        time=time,
        client=client,
        model=prepass_model(),
        size=prepass_size(),
        quality=prepass_quality(),
    )
