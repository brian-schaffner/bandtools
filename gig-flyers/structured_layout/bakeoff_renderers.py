"""Bake-off renderers — re-exports Style DNA module for comparison scripts."""

from structured_layout.style_dna_renderer import (
    CANVAS,
    render_style_dna_archetype,
    render_style_dna_boutique,
    render_style_dna_duotone,
    render_style_dna_psychedelic,
    render_style_dna_xerox,
)

# Backward-compatible alias used by bakeoff script
render_asset_pack_boutique = render_style_dna_boutique

__all__ = [
    "CANVAS",
    "render_style_dna_xerox",
    "render_style_dna_duotone",
    "render_style_dna_psychedelic",
    "render_style_dna_boutique",
    "render_asset_pack_boutique",
    "render_style_dna_archetype",
]
