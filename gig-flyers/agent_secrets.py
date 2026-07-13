"""Resolve API keys: local .env on desktop agents, cloud/repo secrets on Cloud Agent."""

from __future__ import annotations

import os
import re
from pathlib import Path

_GOOGLE_KEY_RE = re.compile(r"AIza[A-Za-z0-9_-]{20,}")

# Brian's local dev checkout (desktop agent). Also covered by relative gig-flyers/.env when cwd matches.
_LOCAL_ENV_PATHS: tuple[str, ...] = (
    "/Users/brian/dev/bandtools/gig-flyers/.env",
    "/Users/brian/dev/bandtools/.env",
)

# Cursor Cloud Agent / environment secrets (spaces allowed) + standard env vars.
_GOOGLE_KEY_ENV_NAMES: tuple[str, ...] = (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "gemini api key",
    "Gemini API Key",
    "GEMINI API KEY",
    "Apikey",
)

_GIG_FLYERS_ROOT = Path(__file__).resolve().parent


def is_cloud_agent() -> bool:
    """True when running as a Cursor Cloud Agent (not a local desktop agent)."""
    if os.getenv("CURSOR_AGENT", "").strip() == "1":
        return True
    if os.getenv("CLOUD_AGENT_ALL_SECRET_NAMES"):
        return True
    if os.getenv("CLOUD_AGENT_INJECTED_SECRET_NAMES"):
        return True
    return False


def candidate_env_paths(*, anchor: Path | None = None) -> list[Path]:
    """`.env` files to try — local Mac path + repo-relative paths."""
    root = anchor or _GIG_FLYERS_ROOT
    paths: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)

    for raw in _LOCAL_ENV_PATHS:
        _add(Path(raw))
    _add(root / ".env")
    _add(root.parent / ".env")
    return paths


def load_env_files(*, anchor: Path | None = None) -> list[Path]:
    """Load existing `.env` files (no-op if dotenv missing or files absent)."""
    loaded: list[Path] = []
    try:
        from dotenv import load_dotenv
    except ImportError:
        return loaded
    for path in candidate_env_paths(anchor=anchor):
        if path.is_file():
            load_dotenv(path, override=False)
            loaded.append(path)
    return loaded


def _extract_google_key(raw: str) -> str:
    """Return a Google API key from env value (supports embedded key in notes)."""
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("AIza") and len(text) >= 30:
        return text
    if text.startswith("AQ.") and len(text) >= 24:
        return text
    match = _GOOGLE_KEY_RE.search(text)
    if match:
        return match.group(0)
    aq = re.search(r"AQ\.[A-Za-z0-9_-]{20,}", text)
    return aq.group(0) if aq else ""


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
    """Resolve Google/Gemini API key from current environment."""
    _, key = resolve_google_api_key_source()
    return key


def bootstrap_google_api_key_env() -> str:
    """Normalize agent/repo secret aliases into GOOGLE_API_KEY / GEMINI_API_KEY."""
    key = resolve_google_api_key()
    if key and not (os.getenv("GOOGLE_API_KEY") or "").strip():
        os.environ["GOOGLE_API_KEY"] = key
    if key and not (os.getenv("GEMINI_API_KEY") or "").strip():
        os.environ["GEMINI_API_KEY"] = key
    return key


def bootstrap_secrets(*, anchor: Path | None = None) -> dict[str, object]:
    """Load secrets for the current agent type.

    - **Local agent:** `gig-flyers/.env` (e.g. `/Users/brian/dev/bandtools/gig-flyers/.env`)
    - **Cloud agent:** Cursor environment secrets (`gemini api key`, etc.), then `.env` if present
    """
    cloud = is_cloud_agent()
    loaded_env: list[Path] = []

    if cloud:
        bootstrap_google_api_key_env()
        loaded_env = load_env_files(anchor=anchor)
        if not resolve_google_api_key():
            bootstrap_google_api_key_env()
    else:
        loaded_env = load_env_files(anchor=anchor)
        bootstrap_google_api_key_env()

    source_name, _ = resolve_google_api_key_source()
    return {
        "cloud_agent": cloud,
        "env_files_loaded": [str(p) for p in loaded_env],
        "env_files_checked": [str(p) for p in candidate_env_paths(anchor=anchor)],
        "google_key_source": source_name,
        "google_key_configured": bool(resolve_google_api_key()),
    }


def google_api_key_configured() -> bool:
    return bool(resolve_google_api_key())
