"""Decide when pass 2 uses a band photo vs typography-only hero treatment."""

from __future__ import annotations

from typing import Literal

from shell_references import ShellReference

AssetMode = Literal["typography_only", "photo_inset", "photo_hero"]
FinalRoute = Literal["text_only", "photo_logo"]

# Shells where HEADLINER should become stylized band name — no photo overlay.
_TYPOGRAPHY_ONLY_FAMILIES = frozenset(
    {
        "fillmore_psychedelic",
        "avalon_psychedelic",
        "victorian_circus",
    }
)

_PHOTO_INSET_FAMILIES = frozenset(
    {
        "gritty_sidebar_bill",
        "festival_hero_grid",
        "xerox_folk_flyer",
        "punk_screenprint",
        "underground_zine",
    }
)

_PHOTO_HERO_FAMILIES = frozenset(
    {
        "letterpress_stack",
        "letterpress_country",
        "arena_photo_dominant",
        "jazz_club",
        "blues_festival",
        "blues_screenprint",
        "theater_debut",
        "vintage_broadside",
        "modern_club",
        "neon_club",
        "modern_metal_arena",
        "reggae_flyer",
        "instrument_hook",
        "swiss_jazz",
        "swiss_grid",
    }
)


def asset_mode_for_shell(shell: ShellReference) -> AssetMode:
    """Return how pass 2 should integrate band identity for this shell."""
    family = shell.design_family
    if family in _TYPOGRAPHY_ONLY_FAMILIES:
        return "typography_only"

    prompt = shell.personalize_prompt.lower()
    if "footer inset" in prompt or "photo lower-left" in prompt or "lower-left" in prompt:
        return "photo_inset"
    if family in _PHOTO_INSET_FAMILIES:
        return "photo_inset"

    if shell.style == "photographic" or family in _PHOTO_HERO_FAMILIES:
        return "photo_hero"
    if "photo as hero" in prompt or "portrait slot" in prompt or "centered portrait" in prompt:
        return "photo_hero"

    if shell.style == "psychedelic_illustrative":
        return "typography_only"

    if "lettering" in prompt and "photo" not in prompt:
        return "typography_only"

    return "photo_inset"


def uses_band_photo(mode: AssetMode) -> bool:
    return mode != "typography_only"


def uses_band_logo(mode: AssetMode) -> bool:
    return mode != "typography_only"


def asset_mode_label(mode: AssetMode) -> str:
    return {
        "typography_only": "Typography hero (no photo)",
        "photo_inset": "Small photo inset",
        "photo_hero": "Large hero photo",
    }[mode]


def suggest_final_route(shell: ShellReference) -> FinalRoute:
    """Heuristic recommendation for pre-pass review."""
    if asset_mode_for_shell(shell) == "typography_only":
        return "text_only"
    return "photo_logo"


def asset_mode_for_route(shell: ShellReference, route: FinalRoute) -> AssetMode:
    """Map a user-chosen final route to pass-2 asset integration mode."""
    if route == "text_only":
        return "typography_only"
    mode = asset_mode_for_shell(shell)
    if mode == "typography_only":
        return "photo_inset"
    return mode


def final_route_label(route: FinalRoute) -> str:
    return {
        "text_only": "Finalize text-only (no photo or logo)",
        "photo_logo": "Finalize with photo & logo",
    }[route]
