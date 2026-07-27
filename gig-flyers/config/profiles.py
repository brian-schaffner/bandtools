"""Environment profiles for Gig Flyers (staging-wild vs prod-safe)."""

from __future__ import annotations

import os
from typing import Mapping

# Keys set only when not already present in the environment (explicit env wins).
_PROFILE_ENV: dict[str, dict[str, str]] = {
    "staging-wild": {
        "GIG_FLYERS_PROFILE": "staging-wild",
        "WILD_DESIGN_ENABLED": "1",
        "WILD_ROUND_LAYOUT": "three_canvas",
        "WILD_BAND_REPLACE_ON_REVISE": "0",
        "WILD_BAND_REPLACE_AFTER_GEN": "0",
        "WILD_BAND_CONVERT_ENABLED": "1",
        "WILD_COLOR_CORRECT": "1",
        "WILD_FACT_LOCKS": "1",
        "FLYER_LOGO_OVERLAY": "1",
        "GIG_IMAGE_PROVIDER_SPLIT": "1",
        "GIG_IMAGE_PROVIDER_A": "gemini",
        "GIG_IMAGE_PROVIDER_B": "gemini",
        "GIG_IMAGE_PROVIDER_C": "gemini",
        "GIG_IMAGE_PROVIDER_BAND_REPLACE": "openai",
        "GEMINI_IMAGE_ASPECT_RATIO": "2:3",
        "FLYER_AGENT_LLM_CHAT": "1",
        "ASSURANCE_ENABLED": "1",
        "ASSURANCE_FACT_GATE": "1",
        "ASSURANCE_HEADER_GHOST": "1",
        "WILD_D_BAND_MODE": "full_canvas",
    },
    "prod-safe": {
        "GIG_FLYERS_PROFILE": "prod-safe",
        "WILD_DESIGN_ENABLED": "0",
        "WILD_ROUND_LAYOUT": "safe_plus_wild",
        "STRUCTURED_LAYOUT_OPTIONS": "A,B,C",
        "USE_FIXED_TEMPLATES": "1",
        "LAYOUT_BACKEND": "pictex",
        "GIG_IMAGE_PROVIDER": "openai",
        "GIG_IMAGE_PROVIDER_SPLIT": "0",
        "OPENAI_IMAGE_USE_REFERENCE": "1",
        "OPENAI_IMAGE_INPUT_FIDELITY": "high",
        "ASSURANCE_ENABLED": "1",
        "ASSURANCE_FACT_GATE": "1",
        "ASSURANCE_HEADER_GHOST": "1",
        "WILD_COLOR_CORRECT": "0",
        "WILD_FACT_LOCKS": "0",
    },
}


def profile_env(name: str) -> Mapping[str, str]:
    key = (name or "").strip().lower()
    if key not in _PROFILE_ENV:
        raise KeyError(f"Unknown GIG_FLYERS_PROFILE: {name!r} (known: {', '.join(_PROFILE_ENV)})")
    return _PROFILE_ENV[key]


def current_profile() -> str:
    return (os.getenv("GIG_FLYERS_PROFILE") or "").strip().lower()


def apply_gig_flyers_profile() -> str:
    """Apply profile defaults via setdefault. Returns active profile name or empty string."""
    raw = (os.getenv("GIG_FLYERS_PROFILE") or "").strip()
    if not raw:
        return ""
    key = raw.lower()
    bundle = _PROFILE_ENV.get(key)
    if bundle is None:
        return key
    for env_key, value in bundle.items():
        if env_key == "GIG_FLYERS_PROFILE":
            continue
        os.environ.setdefault(env_key, value)
    return key


def assurance_enabled() -> bool:
    return os.getenv("ASSURANCE_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def assurance_fact_gate_enabled() -> bool:
    if not assurance_enabled():
        return False
    return os.getenv("ASSURANCE_FACT_GATE", "1").strip().lower() in {"1", "true", "yes", "on"}


def assurance_header_ghost_enabled() -> bool:
    if not assurance_enabled():
        return False
    return os.getenv("ASSURANCE_HEADER_GHOST", "1").strip().lower() in {"1", "true", "yes", "on"}


def wild_fact_locks_enabled() -> bool:
    return os.getenv("WILD_FACT_LOCKS", "0").strip().lower() in {"1", "true", "yes", "on"}
