"""Resolve API keys from standard env names and Cursor agent secret aliases."""

from __future__ import annotations

import os
import re

_GOOGLE_KEY_RE = re.compile(r"AIza[A-Za-z0-9_-]{20,}")

# Cursor agent secret names (spaces allowed) + standard env vars.
_GOOGLE_KEY_ENV_NAMES: tuple[str, ...] = (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "gemini api key",
    "Gemini API Key",
    "GEMINI API KEY",
    "Apikey",
)


def _extract_google_key(raw: str) -> str:
    """Return a Google API key from env value (supports embedded AIza… in notes)."""
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("AIza") and len(text) >= 30:
        return text
    match = _GOOGLE_KEY_RE.search(text)
    return match.group(0) if match else ""


def _google_key_env_candidates() -> list[str]:
    """Env var names that may hold a Google/Gemini API key."""
    seen: set[str] = set()
    names: list[str] = []
    for name in _GOOGLE_KEY_ENV_NAMES:
        if name not in seen:
            seen.add(name)
            names.append(name)
    for name in os.environ:
        low = name.lower()
        if "gemini" in low and "key" in low and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def resolve_google_api_key_source() -> tuple[str, str]:
    """Return (env_var_name, key) for the first valid Google API key found."""
    for name in _google_key_env_candidates():
        key = _extract_google_key(os.getenv(name, ""))
        if key:
            return name, key
    return "", ""


def resolve_google_api_key() -> str:
    """GOOGLE_API_KEY / GEMINI_API_KEY / agent alias gemini api key / Apikey."""
    _, key = resolve_google_api_key_source()
    return key


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
