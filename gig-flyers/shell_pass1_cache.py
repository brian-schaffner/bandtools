"""Pass 1 design shell disk cache — shell-static, gig-independent."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from shell_model_policy import ShellModelChoice
from shell_references import ShellReference


def pass1_cache_enabled() -> bool:
    return (os.getenv("SHELL_PASS1_CACHE") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def pass1_cache_key(shell: ShellReference, prompt: str, choice: ShellModelChoice) -> str:
    raw = "|".join(
        (
            shell.id,
            shell.design_family,
            choice.model,
            choice.quality,
            choice.size,
            prompt,
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def pass1_manifest_path(output_dir: Path, shell_id: str) -> Path:
    return output_dir / f"{shell_id}_pass1_manifest.json"


def pass1_shell_path(output_dir: Path, shell_id: str) -> Path:
    return output_dir / f"{shell_id}_design_shell.png"


def load_pass1_cache(
    shell: ShellReference,
    output_dir: Path,
    *,
    prompt: str,
    choice: ShellModelChoice,
) -> dict[str, Any] | None:
    """Return cached pass-1 manifest when shell image + key match."""
    if not pass1_cache_enabled():
        return None

    shell_path = pass1_shell_path(output_dir, shell.id)
    manifest_path = pass1_manifest_path(output_dir, shell.id)
    if not shell_path.is_file() or shell_path.stat().st_size < 5000:
        return None
    if not manifest_path.is_file():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    key = pass1_cache_key(shell, prompt, choice)
    if manifest.get("cache_key") != key:
        return None

    manifest["cache_hit"] = True
    return manifest


def annotate_pass1_manifest(
    manifest: dict[str, Any],
    shell: ShellReference,
    *,
    prompt: str,
    choice: ShellModelChoice,
) -> dict[str, Any]:
    manifest = {**manifest, "cache_key": pass1_cache_key(shell, prompt, choice), "cache_hit": False}
    return manifest
