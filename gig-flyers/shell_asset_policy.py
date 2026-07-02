"""Map render specs to legacy asset modes and routing — specs are authoritative."""

from __future__ import annotations

from typing import Literal

from shell_references import ShellReference
from shell_render_registry import get_render_spec
from shell_render_spec import ShellRenderSpec

AssetMode = Literal["typography_only", "photo_inset", "photo_hero"]
FinalRoute = Literal["text_only", "photo_logo"]


def render_spec_for_shell(shell: ShellReference) -> ShellRenderSpec:
    return get_render_spec(shell)


def asset_mode_for_shell(shell: ShellReference) -> AssetMode:
    """Legacy compat — derived from photo_style, not prompts."""
    style = get_render_spec(shell).photo_style
    if style == "none":
        return "typography_only"
    if style == "inset_photo":
        return "photo_inset"
    return "photo_hero"


def uses_band_photo(mode: AssetMode) -> bool:
    return mode != "typography_only"


def uses_band_photo_spec(spec: ShellRenderSpec) -> bool:
    return spec.uses_band_photo()


def uses_band_logo(mode: AssetMode) -> bool:
    return mode != "typography_only"


def uses_band_logo_spec(spec: ShellRenderSpec) -> bool:
    return spec.uses_band_logo()


def asset_mode_label(mode: AssetMode) -> str:
    return {
        "typography_only": "Typography hero (no photo)",
        "photo_inset": "Small photo inset",
        "photo_hero": "Large hero photo",
    }[mode]


def photo_style_label(spec: ShellRenderSpec) -> str:
    return {
        "none": "No band image",
        "hero_photo": "Hero photo (flat integrate)",
        "inset_photo": "Inset photo",
        "hero_illustration": "Hero illustration (printed artwork)",
        "background_photo": "Background photo",
        "collage": "Collage",
    }[spec.photo_style]


def suggest_final_route(shell: ShellReference) -> FinalRoute:
    if not get_render_spec(shell).uses_band_photo():
        return "text_only"
    return "photo_logo"


def asset_mode_for_route(shell: ShellReference, route: FinalRoute) -> AssetMode:
    if route == "text_only":
        return "typography_only"
    spec = get_render_spec(shell)
    if spec.photo_style == "none":
        return "photo_inset"
    if spec.photo_style == "inset_photo":
        return "photo_inset"
    return "photo_hero"


def final_route_label(route: FinalRoute) -> str:
    return {
        "text_only": "Finalize text-only (no photo or logo)",
        "photo_logo": "Finalize with photo & logo",
    }[route]
