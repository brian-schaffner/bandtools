"""Shared output directory path helpers."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_PREFIX = "output"


def get_output_dir() -> Path:
    explicit = os.getenv("GIG_OUTPUT_DIR", "").strip()
    if explicit:
        return Path(explicit)
    return ROOT / OUTPUT_PREFIX


def output_relative(path: Path | str) -> str:
    """Logical repo-relative path for URLs/state (always under output/)."""
    p = Path(path)
    if not p.is_absolute():
        text = str(p).replace("\\", "/").lstrip("/")
        if text.startswith(f"{OUTPUT_PREFIX}/") or text == OUTPUT_PREFIX:
            return text
        return f"{OUTPUT_PREFIX}/{text}" if text else OUTPUT_PREFIX

    out_dir = get_output_dir().resolve()
    try:
        rel = p.resolve().relative_to(out_dir)
        return f"{OUTPUT_PREFIX}/{rel.as_posix()}"
    except ValueError:
        pass

    legacy = (ROOT / OUTPUT_PREFIX).resolve()
    try:
        rel = p.resolve().relative_to(legacy)
        return f"{OUTPUT_PREFIX}/{rel.as_posix()}"
    except ValueError:
        pass

    try:
        return str(p.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError as exc:
        raise ValueError(f"{p!s} is not under output directory {out_dir}") from exc


def resolve_output_path(rel: Path | str) -> Path:
    """Resolve logical output/... path (or absolute path) to a filesystem path."""
    p = Path(rel)
    if p.is_absolute():
        return p

    text = str(p).replace("\\", "/").lstrip("/")
    if text.startswith(f"{OUTPUT_PREFIX}/"):
        return get_output_dir() / text[len(OUTPUT_PREFIX) + 1 :]
    if text == OUTPUT_PREFIX:
        return get_output_dir()
    return get_output_dir() / text
