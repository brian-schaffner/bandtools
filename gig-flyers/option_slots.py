"""Round option slot configuration (safe structured + optional wild)."""

from __future__ import annotations

import os
from typing import Any

SAFE_LETTERS = ("A", "B")
CLASSIC_LETTERS = ("A", "B", "C")
WILD_LETTER = "D"
THREE_CANVAS_LETTERS = ("A", "B", "C")
ALL_KNOWN_LETTERS = ("A", "B", "C", "D", "E")

WILD_INTENSITY_SPECS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "A",
        "wild",
        "full_canvas_wild_bold",
        "A) Wild — bold",
        "Maximum outlaw-country bar energy — gritty textures, asymmetry, mixed media.",
    ),
    (
        "B",
        "wild_medium",
        "full_canvas_wild_balanced",
        "B) Wild — balanced",
        "Same full-canvas technique with cleaner hierarchy and slightly restrained chaos.",
    ),
    (
        "C",
        "wild_subtle",
        "full_canvas_wild_refined",
        "C) Wild — refined",
        "Toned-down promoter flyer — still one designed image, but more polished and readable.",
    ),
)


def wild_design_enabled() -> bool:
    return os.getenv("WILD_DESIGN_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def wild_round_layout() -> str:
    """safe_plus_wild (A/B structured + D wild) or three_canvas (A/B/C all full-canvas tiers)."""
    raw = os.getenv("WILD_ROUND_LAYOUT", "safe_plus_wild").strip().lower()
    if raw in {"three_canvas", "three_wild", "tiered", "3up"}:
        return "three_canvas"
    return "safe_plus_wild"


def wild_option_letter() -> str:
    letter = os.getenv("WILD_DESIGN_OPTION", WILD_LETTER).strip().upper()
    return letter or WILD_LETTER


def wild_canvas_letters() -> tuple[str, ...]:
    return THREE_CANVAS_LETTERS


def is_wild_option(letter: str) -> bool:
    if not wild_design_enabled():
        return False
    opt = (letter or "").strip().upper()
    if wild_round_layout() == "three_canvas":
        return opt in wild_canvas_letters()
    return opt == wild_option_letter()


def round_option_letters() -> tuple[str, ...]:
    if wild_design_enabled():
        if wild_round_layout() == "three_canvas":
            return wild_canvas_letters()
        return (*SAFE_LETTERS, wild_option_letter())
    return CLASSIC_LETTERS


def structured_layout_letters() -> set[str]:
    if wild_design_enabled() and wild_round_layout() == "three_canvas":
        return set()
    if wild_design_enabled():
        default = "A,B"
    else:
        default = "A,B,C"
    override = os.getenv("STRUCTURED_LAYOUT_OPTIONS", default).strip().upper()
    return {part.strip() for part in override.split(",") if part.strip()}


def uses_structured_layout(letter: str) -> bool:
    return (letter or "").strip().upper() in structured_layout_letters()


def wild_d_band_mode() -> str:
    """How wild D embeds the band photo: full_canvas (default) | composite | constrained."""
    mode = os.getenv("WILD_D_BAND_MODE", "full_canvas").strip().lower()
    if mode in {"composite", "constrained", "full_canvas"}:
        return mode
    return "full_canvas"


def wild_variation_for_letter(letter: str) -> dict[str, str]:
    opt = (letter or "").strip().upper()
    for spec_letter, tier, generation_mode, label, description in WILD_INTENSITY_SPECS:
        if spec_letter == opt:
            return {
                "id": f"wild_{tier}",
                "label": label,
                "tier": tier,
                "generation_mode": generation_mode,
                "description": description,
                "wild_intensity": tier,
            }
    return wild_variation()


def wild_variations() -> list[dict[str, str]]:
    return [wild_variation_for_letter(letter) for letter in wild_canvas_letters()]


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
            "Full-canvas AI poster — outlaw-country bar energy, integrated typography and graphics. "
            "Experimental; faces may not match the reference photo."
        )
    return {
        "id": "wild_design",
        "label": f"{wild_letter}) Fully designed",
        "tier": "wild",
        "generation_mode": generation_mode,
        "description": description,
        "wild_intensity": "wild",
    }


def valid_option_letters() -> frozenset[str]:
    return frozenset(round_option_letters())


def select_round_variations(
    style: dict[str, Any],
    used: list[str],
    *,
    select_variations_fn,
) -> list[dict[str, Any]]:
    """Pick variations for the current round (2 safe + wild, 3 canvas tiers, or classic A/B/C)."""
    if wild_design_enabled() and wild_round_layout() == "three_canvas":
        return wild_variations()
    if wild_design_enabled():
        safe = select_variations_fn(style, len(SAFE_LETTERS), used)
        return [*safe, wild_variation()]
    return select_variations_fn(style, len(CLASSIC_LETTERS), used)
