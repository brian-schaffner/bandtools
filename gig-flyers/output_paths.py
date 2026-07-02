"""Shared output directory path."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def get_output_dir() -> Path:
    explicit = os.getenv("GIG_OUTPUT_DIR", "").strip()
    if explicit:
        return Path(explicit)
    return ROOT / "output"
