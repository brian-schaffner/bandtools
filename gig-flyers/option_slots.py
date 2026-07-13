"""Round option slot configuration (safe structured + optional wild)."""

from __future__ import annotations

import os
from typing import Any

SAFE_LETTERS = ("A", "B")
CLASSIC_LETTERS = ("A", "B", "C")
WILD_LETTER = "D"
ALL_KNOWN_LETTERS = ("A", "B", "C", "D")


def wild_design_enabled() -> bool:
    return os.getenv("WILD_DESIGN_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def wild_option_letter() -> str:
    letter = os.getenv("WILD_DESIGN_OPTION", WILD_LETTER).strip().upper()
    return letter or WILD_LETTER


def is_wild_option(letter: str) -> bool:
    return wild_design_enabled() and (letter or "").strip().upper() == wild_option_letter()


def round_option_letters() -> tuple[str, ...]:
    if wild_design_enabled():
        return (*SAFE_LETTERS, wild_option_letter())
    return CLASSIC_LETTERS


def structured_layout_letters() -> set[str]:
    if wild_design_enabled():
        default = "A,B"
    else:
        default = "A,B,C"
    override = os.getenv("STRUCTURED_LAYOUT_OPTIONS", default).strip().upper()
    return {part.strip() for part in override.split(",") if part.strip()}


def uses_structured_layout(letter: str) -> bool:
    return (letter or "").strip().upper() in structured_layout_letters()


def wild_d_band_mode() -> str:
    """How wild D embeds the band photo: composite | constrained | full_canvas."""
    mode = os.getenv("WILD_D_BAND_MODE", "composite").strip().lower()
    if mode in {"composite", "constrained", "full_canvas"}:
        return mode
    return "composite"


def wild_variation() -> dict[str, str]:
    wild_letter = wild_option_letter()
    mode = wild_d_band_mode()
    if mode == "composite":
        generation_mode = "wild_pil_composite"
        description = (
            "Western-style wild poster with your exact band photo pasted in — "
            "faces and instruments match the reference; creative shell around the photo."
        )
    elif mode == "constrained":
        generation_mode = "wild_constrained_single_pass"
        description = (
            "Single-pass Gemini wild poster designed around your attached band photo — "
            "faces should stay recognizable; experimental integration."
        )
    else:
        generation_mode = "full_canvas_wild"
        description = (
            "Full-canvas AI poster design — typography, graphics, and band depiction "
            "composed as one image. Experimental; faces may not match the reference photo."
        )
    return {
        "id": "wild_design",
        "label": f"{wild_letter}) Fully designed",
        "tier": "wild",
        "generation_mode": generation_mode,
        "description": description,
    }


def valid_option_letters() -> frozenset[str]:
    return frozenset(round_option_letters())


def select_round_variations(
    style: dict[str, Any],
    used: list[str],
    *,
    select_variations_fn,
) -> list[dict[str, Any]]:
    """Pick variations for the current round (2 safe + wild, or classic A/B/C)."""
    if wild_design_enabled():
        safe = select_variations_fn(style, len(SAFE_LETTERS), used)
        return [*safe, wild_variation()]
    return select_variations_fn(style, len(CLASSIC_LETTERS), used)
