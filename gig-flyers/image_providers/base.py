"""Image provider abstraction for flyer generation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from image_providers.errors import ImageGenerationError, friendly_generation_error, is_quota_error
from progress_helper import ProgressCallback, emit_progress

OPTION_LETTERS = ("A", "B", "C", "D")
_DEFAULT_SPLIT_PROVIDERS = {"A": "openai", "B": "gemini", "C": "gemini", "D": "gemini"}
_GEMINI_ALIASES = frozenset({"gemini", "nano_banana", "google", "nano-banana"})


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_provider_name(name: str) -> str:
    return name.strip().lower()


def is_provider_split_enabled() -> bool:
    """True when split mode is on or any per-option provider override is set."""
    if _truthy_env("GIG_IMAGE_PROVIDER_SPLIT"):
        return True
    return any(os.getenv(f"GIG_IMAGE_PROVIDER_{letter}", "").strip() for letter in OPTION_LETTERS)


def resolve_image_provider() -> str:
    """Choose provider from env; auto-pick gemini when only Google key is set."""
    explicit = os.getenv("GIG_IMAGE_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if _google_key() and not _openai_key():
        return "gemini"
    return "openai"


def resolve_image_provider_for_option(option: str) -> str:
    """Resolve provider for option letter A/B/C (split mode or per-option env)."""
    letter = (option or "").strip().upper()
    if letter in OPTION_LETTERS:
        explicit = os.getenv(f"GIG_IMAGE_PROVIDER_{letter}", "").strip().lower()
        if explicit:
            return explicit
        if is_provider_split_enabled():
            return _DEFAULT_SPLIT_PROVIDERS.get(letter, resolve_image_provider())
    return resolve_image_provider()


def resolve_provider_map() -> dict[str, str]:
    """Map each option letter to its resolved provider name."""
    return {letter: resolve_image_provider_for_option(letter) for letter in OPTION_LETTERS}


def provider_short_label(provider: str = "") -> str:
    """Compact label for per-option progress UI."""
    name = _normalize_provider_name(provider or resolve_image_provider())
    if name in _GEMINI_ALIASES:
        return "Gemini Nano"
    if name == "openai":
        return "OpenAI"
    return name or "unknown"


def split_provider_summary() -> str:
    """Human-readable split summary, e.g. 'A: OpenAI · B: Gemini Nano · C: Gemini Nano'."""
    return " · ".join(
        f"{letter}: {provider_short_label(resolve_image_provider_for_option(letter))}"
        for letter in OPTION_LETTERS
    )


class ImageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_path: Path,
        *,
        reference_photo_path: Optional[Path] = None,
        design_reference_path: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        option: str = "",
        attempt: int = 0,
        progress: int = 0,
        quality: Optional[str] = None,
        tier: str = "",
    ) -> None:
        """Generate a flyer image and write it to output_path."""


def _openai_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _google_key() -> str:
    from agent_secrets import resolve_google_api_key

    return resolve_google_api_key()


def get_image_provider(name: Optional[str] = None) -> ImageProvider:
    provider = (name or resolve_image_provider()).strip().lower()
    if provider in {"gemini", "nano_banana", "google", "nano-banana"}:
        from image_providers.gemini import GeminiImageProvider

        return GeminiImageProvider()
    from image_providers.openai import OpenAIImageProvider

    return OpenAIImageProvider()


def provider_display_label(provider: str = "") -> str:
    """Human-readable label for progress UI."""
    name = _normalize_provider_name(provider or resolve_image_provider())
    if name in _GEMINI_ALIASES:
        model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip()
        return f"Gemini Nano Banana ({model})"
    if name == "openai":
        model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
        return f"OpenAI {model}"
    return name or "unknown"


def generate_with_fallback(
    prompt: str,
    output_path: Path,
    *,
    reference_photo_path: Optional[Path] = None,
    design_reference_path: Optional[Path] = None,
    on_progress: Optional[ProgressCallback] = None,
    option: str = "",
    attempt: int = 0,
    progress: int = 0,
    provider: Optional[str] = None,
    quality: Optional[str] = None,
    tier: str = "",
) -> str:
    """Generate using configured provider; fall back to OpenAI on Gemini quota errors."""
    primary = _normalize_provider_name(provider or resolve_image_provider())
    opt = option or "?"

    try:
        get_image_provider(primary).generate(
            prompt,
            output_path,
            reference_photo_path=reference_photo_path,
            design_reference_path=design_reference_path,
            on_progress=on_progress,
            option=opt,
            attempt=attempt,
            progress=progress,
            quality=quality,
            tier=tier,
        )
        return primary
    except Exception as exc:
        if primary != "gemini" or not _openai_key() or not is_quota_error(exc):
            raise friendly_generation_error(exc, primary) from exc

        emit_progress(
            on_progress,
            step="generate",
            substep="fallback",
            message="Gemini quota exceeded, falling back to OpenAI",
            detail=str(exc)[:240],
            progress=progress,
            option=opt,
            attempt=attempt,
            option_phase="generating",
            provider_label=provider_display_label("openai"),
            active_provider="openai",
        )
        try:
            get_image_provider("openai").generate(
                prompt,
                output_path,
                reference_photo_path=reference_photo_path,
                design_reference_path=design_reference_path,
                on_progress=on_progress,
                option=opt,
                attempt=attempt,
                progress=progress,
                quality=quality,
                tier=tier,
            )
            return "openai"
        except Exception as fallback_exc:
            raise ImageGenerationError(
                "Gemini quota exceeded and OpenAI fallback also failed. "
                f"Gemini: {exc}. OpenAI: {fallback_exc}",
                provider="openai",
            ) from fallback_exc
