"""Standard logo placements for wild full-canvas flyers — layout-first branding."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LogoPlacement:
    key: str
    box: tuple[int, int, int, int]
    variant: str  # lockup | badge
    prompt_lines: tuple[str, ...]


# Canvas 1024×1536 — boxes are (x1, y1, x2, y2), generous for fan-visible lockups.
FOOTER_HERO = LogoPlacement(
    "footer_hero",
    (56, 1020, 968, 1310),
    "lockup",
    (
        "RESERVED BAND LOGO ZONE (footer hero — center, large):",
        "- Keep y≈1020–1310 and horizontal center ~70% of width visually open.",
        "- No venue/date text across this band — gig facts sit above or below, not on the logo.",
        "- Official Lindsey Lane Band lockup will be composited LARGE here after render.",
    ),
)

TOP_BANNER = LogoPlacement(
    "top_banner",
    (48, 48, 976, 300),
    "lockup",
    (
        "RESERVED BAND LOGO ZONE (top banner — center, large):",
        "- Keep y≈48–300 open for a wide horizontal band logo under the headline area.",
        "- Event title/venue can sit below this zone; do not crowd the logo band.",
        "- Official Lindsey Lane Band lockup will be composited LARGE here after render.",
    ),
)

CORNER_BADGE = LogoPlacement(
    "corner_badge",
    (680, 36, 1000, 200),
    "badge",
    (
        "RESERVED CORNER BADGE (small): top-right clear patch for circular band mark only.",
    ),
)

_PLACEMENTS: dict[str, LogoPlacement] = {
    p.key: p
    for p in (FOOTER_HERO, TOP_BANNER, CORNER_BADGE)
}


def _placement_mode() -> str:
    return os.getenv("FLY_LOGO_PLACEMENT", "per_option").strip().lower()


def placement_for_option(letter: str) -> LogoPlacement:
    """Pick one of a small fixed set of logo slots (default: A/C footer, B top)."""
    mode = _placement_mode()
    if mode in {"footer", "footer_hero", "all_footer"}:
        return FOOTER_HERO
    if mode in {"top", "top_banner", "all_top"}:
        return TOP_BANNER
    if mode in {"corner", "corner_badge"}:
        return CORNER_BADGE
    # per_option — two standard slots fans learn quickly
    opt = (letter or "A").strip().upper()
    if opt == "B":
        return TOP_BANNER
    return FOOTER_HERO


def logo_reserve_prompt_block(letter: str) -> str:
    placement = placement_for_option(letter)
    return "\n".join(placement.prompt_lines)


def band_photo_pass2_prompt_block() -> str:
    if os.getenv("WILD_BAND_REPLACE_AFTER_GEN", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return ""
    return (
        "BAND PHOTO PASS 2 (after this render):\n"
        "- A real group publicity photo will replace AI musicians in a second pass.\n"
        "- Keep one clear band focal region (center or lower 55% of poster) with replaceable stand-ins.\n"
        "- Do not paint tiny faces or illegible crowds — one readable band moment is enough.\n"
        "- Preserve typography and logo reserve zones; only the band depiction will be swapped."
    )


def combined_layout_reserve_prompt(letter: str) -> str:
    parts = [logo_reserve_prompt_block(letter)]
    photo = band_photo_pass2_prompt_block()
    if photo:
        parts.append(photo)
    return "\n\n".join(parts)
