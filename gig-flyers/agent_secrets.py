"""Resolve API keys from standard env names and Cursor agent secret aliases."""

from __future__ import annotations

import os
import re

_GOOGLE_KEY_RE = re.compile(r"AIza[A-Za-z0-9_-]{20,}")


def _extract_google_key(raw: str) -> str:
    """Return a Google API key from env value (supports embedded AIza… in notes)."""
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("AIza") and len(text) >= 30:
        return text
    match = _GOOGLE_KEY_RE.search(text)
    return match.group(0) if match else ""


def resolve_google_api_key() -> str:
    """GOOGLE_API_KEY / GEMINI_API_KEY / agent alias Apikey (and embedded AIza in value)."""
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "Apikey"):
        key = _extract_google_key(os.getenv(name, ""))
        if key:
            return key
    return ""


def bootstrap_google_api_key_env() -> str:
    """If only agent aliases are set, export GOOGLE_API_KEY for downstream libraries."""
    key = resolve_google_api_key()
    if key and not (os.getenv("GOOGLE_API_KEY") or "").strip():
        os.environ["GOOGLE_API_KEY"] = key
    if key and not (os.getenv("GEMINI_API_KEY") or "").strip():
        os.environ["GEMINI_API_KEY"] = key
    return key


def google_api_key_configured() -> bool:
    return bool(resolve_google_api_key())
