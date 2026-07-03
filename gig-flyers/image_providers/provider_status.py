"""Runtime image provider configuration status."""

from __future__ import annotations

import os
from typing import Any

from image_providers.base import (
    _google_key,
    _openai_key,
    is_provider_split_enabled,
    resolve_image_provider,
    resolve_image_provider_for_option,
    resolve_provider_map,
)


def gemini_configured() -> bool:
    return bool(_google_key())


def openai_configured() -> bool:
    return bool(_openai_key())


def provider_status() -> dict[str, Any]:
    """Summary for health checks and smoke tests."""
    split = is_provider_split_enabled()
    provider_map = resolve_provider_map() if split else {}
    default = resolve_image_provider()

    gemini_ready = gemini_configured()
    issues: list[str] = []
    if split:
        for letter, name in provider_map.items():
            if name in {"gemini", "nano_banana", "google", "nano-banana"} and not gemini_ready:
                issues.append(f"Option {letter} uses Gemini but GOOGLE_API_KEY/GEMINI_API_KEY is not set")
    elif default in {"gemini", "nano_banana", "google", "nano-banana"} and not gemini_ready:
        issues.append("GIG_IMAGE_PROVIDER=gemini but GOOGLE_API_KEY/GEMINI_API_KEY is not set")

    if default == "openai" and not openai_configured() and not gemini_ready:
        issues.append("OPENAI_API_KEY is not set")

    return {
        "default_provider": default,
        "split_enabled": split,
        "provider_map": provider_map,
        "openai_configured": openai_configured(),
        "gemini_configured": gemini_ready,
        "gemini_model": os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip(),
        "ready": len(issues) == 0,
        "issues": issues,
    }
