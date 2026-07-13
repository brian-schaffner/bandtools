"""Per-option color locks for wild full-canvas generation — fight the AI-yellow default."""

from __future__ import annotations

import re

_YELLOW_PATTERN = re.compile(
    r"\b(yellow|mustard|gold|amber|sepia|golden|parchment|tungsten|sun-?faded|"
    r"warm earth|aged paper|vintage filter|cream paper)\b",
    re.I,
)

_WILD_PALETTE_LOCKS: dict[str, str] = {
    "A": (
        "OPTION A PALETTE (mandatory): dark walnut / espresso brown background, black ink "
        "typography, brick-red accents only. High-contrast dive-bar night interior. "
        "FORBIDDEN: yellow, gold, mustard, amber, sepia, golden-hour wash, or yellow-tinted skin."
    ),
    "B": (
        "OPTION B PALETTE (mandatory): charcoal gray or denim-blue base, newsprint-white type, "
        "rust-orange accent only. Cool shadows, blues-club handbill energy. "
        "FORBIDDEN: yellow, gold, mustard, amber, sepia, golden-hour wash, or yellow-tinted skin."
    ),
    "C": (
        "OPTION C PALETTE (mandatory): black + brick red + newsprint white on dark wood — "
        "two- or three-ink promoter flyer, no filters. Clean readable hierarchy. "
        "FORBIDDEN: yellow, gold, mustard, amber, sepia, golden-hour wash, or yellow-tinted skin."
    ),
}


def wild_palette_lock(letter: str) -> str:
    """Non-negotiable per-option palette block for wild Gemini/OpenAI prompts."""
    key = (letter or "A").strip().upper()
    return _WILD_PALETTE_LOCKS.get(key, _WILD_PALETTE_LOCKS["A"])


def wild_color_prefix(letter: str) -> str:
    """Short prefix placed at the very start of wild image prompts."""
    lock = wild_palette_lock(letter)
    return (
        "COLOR LOCK — highest priority; overrides any other color or vintage guidance:\n"
        f"{lock}\n"
        "This must look like real ink on paper/wood — NOT an AI 'vintage photo' filter."
    )


def sanitize_research_note(note: str) -> str | None:
    """Drop venue research lines that nudge yellow/gold vintage palettes."""
    text = (note or "").strip()
    if not text:
        return None
    if _YELLOW_PATTERN.search(text):
        return None
    return text


def sanitize_research_notes(notes: list[str]) -> list[str]:
    cleaned: list[str] = []
    for note in notes:
        kept = sanitize_research_note(note)
        if kept:
            cleaned.append(kept)
    return cleaned
