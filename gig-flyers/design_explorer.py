"""Design explorer — generate many flyer variants and learn from rankings."""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from gig_calendar import GigEvent
from structured_layout import render_flyer, score_layout
from structured_layout.fixed_templates import (
    MEDIUM_VARIANTS,
    create_collage_layout,
    create_handbill_layout,
    create_simple_stack_layout,
)
from structured_layout.graphic_composer import (
    ACCENTS,
    ARCHETYPES,
    GraphicRecipe,
    LAYER_ELEMENTS,
    PALETTES,
    build_recipe,
    compose_graphic_flyer,
    recipe_signature,
)
from structured_layout.tier_archetypes import load_tier_archetype
from structured_layout.validation import validate_structured_flyer
from output_paths import output_relative
from text_validation import resolve_venue_address

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ExploreSpec:
    spec_id: str
    family: str
    label: str
    tags: dict[str, str]
    wild: bool = False
    recipe: GraphicRecipe | None = None
    medium_variant: str | None = None


@dataclass
class ExploreVariant:
    spec_id: str
    family: str
    label: str
    tags: dict[str, str]
    path_rel: str
    wild: bool = False
    layout_score: float | None = None
    validation_issues: list[str] = field(default_factory=list)
    breaks_rules: bool = False


def explore_max_variants() -> int:
    raw = os.getenv("EXPLORE_MAX_VARIANTS", "16").strip()
    try:
        return max(4, min(32, int(raw)))
    except ValueError:
        return 16


def _explore_rng(gig_id: str, spec_id: str) -> random.Random:
    digest = int(hashlib.sha256(f"explore:{gig_id}:{spec_id}".encode()).hexdigest()[:8], 16)
    return random.Random(digest)


def _wild_recipe(base: GraphicRecipe, rng: random.Random) -> GraphicRecipe:
    accent = rng.choice(ACCENTS)
    layer_pool = list(LAYER_ELEMENTS)
    rng.shuffle(layer_pool)
    layers = tuple(layer_pool[: min(3, len(layer_pool))])
    return GraphicRecipe(
        archetype=base.archetype,
        palette_id=base.palette_id,
        palette=base.palette,
        accent=accent,
        layers=layers,
        mirror=not base.mirror,
        seed=rng.randint(1, 2**31 - 1),
    )


def _layers_for_rng(rng: random.Random, accent: str) -> tuple[str, ...]:
    layer_pool = [layer for layer in LAYER_ELEMENTS if not (layer == "tape_corner" and accent == "tape")]
    rng.shuffle(layer_pool)
    count = rng.randint(2, min(3, len(layer_pool)))
    return tuple(layer_pool[:count])


def _recipe_for_tags(
    arch: str,
    palette_id: str,
    palette: tuple[int, int, int],
    rng: random.Random,
    *,
    wild: bool = False,
) -> GraphicRecipe:
    accent = ACCENTS[rng.randint(0, len(ACCENTS) - 1)]
    if accent == "stamp" and arch not in ("xerox_punk", "pasteup_zine", "broadside"):
        accent = "starburst"
    layers = _layers_for_rng(rng, accent)
    recipe = GraphicRecipe(
        archetype=arch,
        palette_id=palette_id,
        palette=palette,
        accent=accent,
        layers=layers,
        mirror=rng.random() < 0.35,
        seed=rng.randint(1, 2**31 - 1),
    )
    if wild:
        return _wild_recipe(recipe, rng)
    return recipe


def enumerate_explore_specs(gig_id: str, *, max_count: int | None = None) -> list[ExploreSpec]:
    limit = max_count or explore_max_variants()
    specs: list[ExploreSpec] = []

    specs.append(
        ExploreSpec(
            spec_id="a-stack",
            family="A",
            label="Simple stack · conservative",
            tags={"family": "A", "tier": "conservative"},
        )
    )

    for variant in MEDIUM_VARIANTS:
        specs.append(
            ExploreSpec(
                spec_id=f"b-{variant}",
                family="B",
                label=f"Handbill · {variant.replace('_', ' ')}",
                tags={"family": "B", "medium_variant": variant, "tier": "medium"},
                medium_variant=variant,
            )
        )

    for arch in ARCHETYPES:
        palettes = PALETTES.get(arch, PALETTES["xerox_punk"])
        for palette_id, palette in palettes:
            rng = _explore_rng(gig_id, f"c-{arch}-{palette_id}")
            recipe = _recipe_for_tags(arch, palette_id, palette, rng, wild=False)
            specs.append(
                ExploreSpec(
                    spec_id=f"c-{arch}-{palette_id}",
                    family="C",
                    label=f"Style DNA · {arch.replace('_', ' ')} · {palette_id.replace('_', ' ')}",
                    tags={
                        "family": "C",
                        "archetype": arch,
                        "palette": palette_id,
                        "accent": recipe.accent,
                        "layers": ",".join(recipe.layers) or "none",
                        "tier": "creative",
                    },
                    recipe=recipe,
                )
            )
            wild_rng = _explore_rng(gig_id, f"wild-{arch}-{palette_id}")
            wild = _recipe_for_tags(arch, palette_id, palette, wild_rng, wild=True)
            specs.append(
                ExploreSpec(
                    spec_id=f"wild-{arch}-{palette_id}",
                    family="C",
                    label=f"Wild · {arch.replace('_', ' ')} · {palette_id.replace('_', ' ')}",
                    tags={
                        "family": "C",
                        "archetype": arch,
                        "palette": palette_id,
                        "accent": wild.accent,
                        "layers": ",".join(wild.layers) or "none",
                        "tier": "creative",
                        "wild": "1",
                    },
                    wild=True,
                    recipe=wild,
                )
            )

    return specs[:limit] if limit else specs


def spec_signature(spec: ExploreSpec) -> str:
    tags = spec.tags
    return "|".join(
        [
            spec.family,
            tags.get("archetype", ""),
            tags.get("palette", ""),
            tags.get("medium_variant", ""),
            tags.get("accent", ""),
        ]
    )


def materialize_spec_for_round(
    spec: ExploreSpec,
    *,
    gig_id: str,
    round_num: int,
    slot: int,
    preferences: dict[str, Any] | None = None,
) -> ExploreSpec:
    """Fresh seeds and C recipe accents/layers each round — same approach, new execution."""
    from preference_model import preference_weights

    seed_material = f"{gig_id}:{round_num}:{slot}:{spec.spec_id}"
    digest = int(hashlib.sha256(seed_material.encode()).hexdigest()[:8], 16)
    rng = random.Random(digest)
    prefs = preference_weights(preferences)

    recipe = spec.recipe
    if spec.family == "C":
        arch = spec.tags.get("archetype") or "xerox_punk"
        palette_id = spec.tags.get("palette") or "cream_black"
        palettes = PALETTES.get(arch, PALETTES["xerox_punk"])
        palette = next(p for pid, p in palettes if pid == palette_id)
        if spec.wild:
            recipe = _recipe_for_tags(arch, palette_id, palette, rng, wild=True)
        else:
            built = build_recipe(rng, archetype=arch, preferences=prefs)
            recipe = GraphicRecipe(
                archetype=arch,
                palette_id=palette_id,
                palette=palette,
                accent=built.accent,
                layers=built.layers,
                mirror=built.mirror,
                seed=digest,
            )
        tags = dict(spec.tags)
        tags["accent"] = recipe.accent
        tags["layers"] = ",".join(recipe.layers) or "none"
        return ExploreSpec(
            spec_id=f"{spec.spec_id}-r{round_num}-s{slot}",
            family=spec.family,
            label=spec.label,
            tags=tags,
            wild=spec.wild,
            recipe=recipe,
            medium_variant=spec.medium_variant,
        )

    return ExploreSpec(
        spec_id=f"{spec.spec_id}-r{round_num}-s{slot}",
        family=spec.family,
        label=spec.label,
        tags=dict(spec.tags),
        wild=spec.wild,
        recipe=recipe,
        medium_variant=spec.medium_variant,
    )


def _facts(event: GigEvent, band: str) -> dict[str, str]:
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    return {
        "venue": event.venue,
        "band": band,
        "date": date_str,
        "time": event.time_label or "TBA",
        "address": resolve_venue_address(event),
    }


def _layout_stub_for_recipe(recipe: GraphicRecipe, event: GigEvent, band: str, rng: random.Random):
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    layout = create_collage_layout(
        event.venue,
        band,
        date_str,
        time_str,
        address=resolve_venue_address(event),
        event=event,
        rng=rng,
    )
    return replace(layout, style_notes=recipe_signature(recipe))


def _render_explore_spec(
    spec: ExploreSpec,
    *,
    event: GigEvent,
    band: str,
    photo_path: Path,
    out_path: Path,
    research: dict[str, Any],
) -> ExploreVariant:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    address = resolve_venue_address(event)
    rng = _explore_rng(event.gig_id, spec.spec_id)

    if spec.family == "C" and spec.recipe is not None:
        compose_graphic_flyer(spec.recipe, _facts(event, band), photo_path, out_path)
        layout = _layout_stub_for_recipe(spec.recipe, event, band, rng)
    elif spec.family == "B":
        arch = load_tier_archetype("medium", event=event, research=research)
        layout = create_handbill_layout(
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            archetype=arch,
            rng=rng,
            medium_variant=spec.medium_variant,
        )
        render_flyer(layout, photo_path, out_path, tier="medium")
    else:
        arch = load_tier_archetype("conservative", event=event, research=research)
        layout = create_simple_stack_layout(
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            archetype=arch,
            rng=rng,
        )
        render_flyer(layout, photo_path, out_path, tier="conservative")

    layout_score = float(score_layout(layout, event))
    validation = validate_structured_flyer(out_path, layout, event, band=band)
    issues = list(validation.issues)
    breaks_rules = spec.wild or bool(issues) or layout_score < 7.0

    return ExploreVariant(
        spec_id=spec.spec_id,
        family=spec.family,
        label=spec.label,
        tags=dict(spec.tags),
        path_rel=output_relative(out_path),
        wild=spec.wild,
        layout_score=layout_score,
        validation_issues=issues[:5],
        breaks_rules=breaks_rules,
    )


def generate_explore_batch(
    event: GigEvent,
    *,
    band: str,
    photo_path: Path,
    out_dir: Path,
    research: dict[str, Any],
    on_progress: Callable[..., None] | None = None,
    max_count: int | None = None,
) -> dict[str, Any]:
    from progress_helper import emit_progress

    specs = enumerate_explore_specs(event.gig_id, max_count=max_count)
    batch_id = hashlib.sha256(
        f"{event.gig_id}:{len(specs)}:{event.event_date.isoformat()}".encode()
    ).hexdigest()[:12]
    explore_dir = out_dir / "explore" / batch_id
    explore_dir.mkdir(parents=True, exist_ok=True)

    variants: list[dict[str, Any]] = []
    total = len(specs)
    for idx, spec in enumerate(specs):
        emit_progress(
            on_progress,
            step="explore",
            substep="render",
            message=f"Explore {idx + 1}/{total}: {spec.label}",
            progress=int(10 + (idx / max(1, total)) * 85),
        )
        out_path = explore_dir / f"explore_{spec.spec_id}.png"
        try:
            variant = _render_explore_spec(
                spec,
                event=event,
                band=band,
                photo_path=photo_path,
                out_path=out_path,
                research=research,
            )
            variants.append(asdict(variant))
        except Exception as exc:  # noqa: BLE001
            variants.append(
                {
                    "spec_id": spec.spec_id,
                    "family": spec.family,
                    "label": spec.label,
                    "tags": spec.tags,
                    "path_rel": "",
                    "wild": spec.wild,
                    "error": str(exc),
                }
            )

    manifest = {
        "batch_id": batch_id,
        "gig_id": event.gig_id,
        "variant_count": len([v for v in variants if v.get("path_rel")]),
        "variants": variants,
    }
    (explore_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    emit_progress(
        on_progress,
        step="explore",
        substep="done",
        message=f"Explore batch ready ({manifest['variant_count']} variants)",
        progress=100,
    )
    return manifest

