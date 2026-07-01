"""Style DNA renderers — delegates to Graphic Composer (Option C production path)."""

from __future__ import annotations

from pathlib import Path

from structured_layout.graphic_composer import (
    ARCHETYPES,
    build_recipe,
    compose_from_layout,
    compose_graphic_flyer,
    is_style_dna_layout,
    parse_archetype_from_layout,
    pick_creative_archetype,
    recipe_signature,
    render_option_c_best,
)
from structured_layout.layout_spec import LayoutSpec

# Backward-compatible exports
CREATIVE_ARCHETYPE_KEYS = ARCHETYPES
STYLE_DNA_PREFIX = "style dna"


def parse_style_dna_archetype(layout: LayoutSpec) -> str | None:
    return parse_archetype_from_layout(layout)


def render_style_dna_from_layout(
    layout: LayoutSpec,
    photo_path: Path,
    output_path: Path,
) -> None:
    render_option_c_best(layout, photo_path, output_path)


def _render_archetype(archetype: str, **kwargs) -> None:
    import random

    seed = kwargs.pop("seed", 7)
    out_path = kwargs.pop("out_path")
    photo_path = kwargs.pop("photo_path")
    facts = {
        "venue": kwargs.pop("venue"),
        "band": kwargs.pop("band"),
        "date": kwargs.pop("date"),
        "time": kwargs.pop("time"),
        "address": kwargs.pop("address"),
    }
    recipe = build_recipe(random.Random(seed), archetype=archetype)
    recipe = type(recipe)(
        archetype=recipe.archetype,
        palette_id=recipe.palette_id,
        palette=recipe.palette,
        accent=recipe.accent,
        layers=recipe.layers,
        mirror=recipe.mirror,
        seed=seed,
    )
    compose_graphic_flyer(recipe, facts, photo_path, out_path)


def render_style_dna_xerox(**kwargs) -> None:
    _render_archetype("xerox_punk", **kwargs)


def render_style_dna_duotone(**kwargs) -> None:
    _render_archetype("duotone_modern", **kwargs)


def render_style_dna_psychedelic(**kwargs) -> None:
    _render_archetype("psychedelic", **kwargs)


def render_style_dna_boutique(**kwargs) -> None:
    _render_archetype("boutique", **kwargs)


CANVAS = (1024, 1536)
