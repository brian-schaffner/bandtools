"""Shared image provider error helpers."""

from __future__ import annotations

import re
from typing import Any, Optional


class ImageGenerationError(RuntimeError):
    """User-facing image generation failure."""

    def __init__(self, message: str, *, provider: str = "", retryable: bool = False) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


def _exc_text(exc: BaseException) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def is_quota_error(exc: BaseException) -> bool:
    text = _exc_text(exc).lower()
    if "resource_exhausted" in text or "quota" in text:
        return True
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code == 429:
        return True
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status == 429:
            return True
    return False


def is_retryable_429(exc: BaseException) -> bool:
    if not is_quota_error(exc):
        return False
    text = _exc_text(exc).lower()
    # Hard quota (limit: 0) won't clear with a short wait — skip retry.
    if "limit: 0" in text or "limit:0" in text:
        return False
    return True


def retry_delay_seconds(exc: BaseException, *, default: float = 58.0, maximum: float = 60.0) -> float:
    text = _exc_text(exc)
    match = re.search(r"retry(?:_delay)?[^\d]*(\d+(?:\.\d+)?)\s*s", text, re.IGNORECASE)
    if match:
        return min(maximum, max(1.0, float(match.group(1))))
    details = getattr(exc, "details", None)
    if isinstance(details, list):
        for item in details:
            retry = getattr(item, "retry_delay", None)
            if retry is not None:
                seconds = getattr(retry, "seconds", None)
                if seconds is not None:
                    return min(maximum, max(1.0, float(seconds)))
    return default


def friendly_generation_error(exc: BaseException, provider: str) -> ImageGenerationError:
    text = _exc_text(exc)
    if is_quota_error(exc):
        if provider == "gemini":
            return ImageGenerationError(
                "Gemini image quota exceeded. Set GIG_IMAGE_PROVIDER=openai or upgrade Gemini billing.",
                provider=provider,
            )
        return ImageGenerationError(f"{provider} quota exceeded: {exc}", provider=provider)
    return ImageGenerationError(f"{provider} image generation failed: {exc}", provider=provider)
