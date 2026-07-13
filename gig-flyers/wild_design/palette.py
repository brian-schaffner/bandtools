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
        "OPTION A PALETTE (mandatory): near-black charcoal background, black ink typography, "
        "brick-red accent blocks only. Text labels: torn WHITE or RED paper — never cream, "
        "parchment, tan, or beige blocks. "
        "Band depiction: natural skin tones OR true black-and-white photo — NEVER mustard, "
        "yellow-tan, sepia, or yellow halftone/duotone on faces or skin."
    ),
    "B": (
        "OPTION B PALETTE (mandatory): denim-blue or cool charcoal base, pure white type, "
        "rust-orange accent only. Text labels: white or red torn paper — no cream/parchment. "
        "Band depiction: natural skin tones OR cool B&W — NEVER yellow-tan halftone duotone."
    ),
    "C": (
        "OPTION C PALETTE (mandatory): black + brick red + pure white on dark wood — "
        "limited ink palette, no vintage filters. Text blocks: red or white only. "
        "Band depiction: natural skin tones OR neutral grayscale — no yellow/cream color grade."
    ),
}

_BAND_DEPICTION_RULE = (
    "BAND DEPICTION: If showing musicians, use natural skin tones or honest B&W photography. "
    "Do NOT apply mustard, yellow-tan, sepia, cream, or 'vintage halftone' color grades to faces, "
    "arms, or clothing. No monochromatic yellow-brown duotone over the whole band region."
)


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
        f"{_BAND_DEPICTION_RULE}\n"
        "FORBIDDEN globally: yellow, gold, mustard, amber, sepia, cream/parchment/tan paper blocks, "
        "and AI 'vintage photo' filters."
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
