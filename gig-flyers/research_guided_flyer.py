"""Small flyer generator guided by public design research corpus."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional

from flyer_design_research import (
    FlyerDesignBrief,
    build_design_brief,
    corpus_summary,
    design_brief_prompt_block,
)
from flyer_generator import gig_output_dir, resolve_gig_event
from gig_research import research_gig
from output_paths import output_relative
from photo_selector import select_band_photo
from progress_helper import ProgressCallback, emit_progress
from structured_layout import render_flyer, score_layout
from structured_layout.fixed_templates import (
    _make_rng,
    create_collage_layout,
    create_handbill_layout,
    create_simple_stack_layout,
    layout_for_option,
)
from structured_layout.graphic_composer import build_recipe, compose_graphic_flyer, recipe_signature
from structured_layout.tier_archetypes import load_tier_archetype
from structured_layout.validation import validate_structured_flyer
from text_validation import resolve_venue_address

ROOT = Path(__file__).resolve().parent


def _facts(event, band: str) -> dict[str, str]:
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    return {
        "venue": event.venue,
        "band": band,
        "date": date_str,
        "time": event.time_label or "TBA",
        "address": resolve_venue_address(event),
    }


def _layout_from_brief(
    brief: FlyerDesignBrief,
    event,
    *,
    band: str,
    research: dict[str, Any],
    round_num: int = 1,
):
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    address = resolve_venue_address(event)
    letter = brief.option_letter.upper()
    tier_map = {"A": "conservative", "B": "medium", "C": "creative"}
    tier = tier_map.get(letter, "medium")
    archetype = load_tier_archetype(tier, event=event, research=research)
    rng = _make_rng(event.gig_id, letter, round_num)

    if letter == "C" and brief.graphic_archetype:
        layout = create_collage_layout(
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            archetype=archetype,
            rng=rng,
            research=research,
            graphic_archetype=brief.graphic_archetype,
        )
        recipe = build_recipe(rng, archetype=brief.graphic_archetype)
        from dataclasses import replace

        layout = replace(layout, style_notes=recipe_signature(recipe))
        return layout, recipe

    if letter == "B":
        layout = create_handbill_layout(
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            archetype=archetype,
            rng=rng,
            medium_variant=brief.medium_variant,
        )
        return layout, None

    if letter == "A":
        layout = create_simple_stack_layout(
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            archetype=archetype,
            rng=rng,
        )
        return layout, None

    return layout_for_option(
        letter,
        event.venue,
        band,
        date_str,
        time_str,
        address=address,
        event=event,
        research=research,
        gig_id=event.gig_id,
        option_letter=letter,
        round_num=round_num,
    ), None


def generate_research_guided_flyer(
    gig_id: str,
    *,
    round_num: int = 1,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Research gig context + public poster corpus → one PNG + manifest."""
    event = resolve_gig_event(gig_id)
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")

    emit_progress(on_progress, step="research", substep="gig", message="Researching gig context…", progress=5)
    research = research_gig(event, on_progress=on_progress)

    emit_progress(on_progress, step="research", substep="corpus", message="Building design brief from poster corpus…", progress=15)
    brief = build_design_brief(event, research)

    emit_progress(on_progress, step="research", substep="photo", message="Selecting band photo…", progress=25)
    selected_photo = select_band_photo(event, research, on_progress=on_progress)
    photo_path = None
    if selected_photo and selected_photo.get("path"):
        photo_path = ROOT / selected_photo["path"]

    layout, recipe = _layout_from_brief(brief, event, band=band, research=research, round_num=round_num)

    out_dir = gig_output_dir(event) / "research_guided"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"research_guided_r{round_num}.png"

    emit_progress(
        on_progress,
        step="render",
        substep="layout",
        message=f"Rendering {brief.recommended_style.replace('_', ' ')} layout…",
        progress=55,
    )

    if dry_run:
        out_path.write_bytes(b"")
    elif recipe is not None and photo_path and photo_path.is_file():
        compose_graphic_flyer(recipe, _facts(event, band), photo_path, out_path)
    elif photo_path and photo_path.is_file():
        tier = {"A": "conservative", "B": "medium", "C": "creative"}.get(brief.option_letter, "medium")
        render_flyer(layout, photo_path, out_path, tier=tier)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"")

    layout_score = float(score_layout(layout, event)) if not dry_run else 0.0
    validation = (
        validate_structured_flyer(out_path, layout, event, band=band)
        if not dry_run and out_path.stat().st_size > 0
        else None
    )

    manifest = {
        "gig_id": gig_id,
        "round": round_num,
        "path_rel": output_relative(out_path),
        "brief": brief.to_dict(),
        "corpus": corpus_summary(),
        "research_design_language": research.get("design_language"),
        "layout_score": layout_score,
        "validation": validation.to_dict() if validation else {},
        "prompt_block": design_brief_prompt_block(brief),
    }

    manifest_path = out_dir / f"manifest_r{round_num}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    emit_progress(on_progress, step="done", substep="complete", message="Research-guided flyer ready", progress=100)
    return manifest


def load_corpus_for_ui() -> dict[str, Any]:
    """Expose principles + samples for future UI or prompt injection."""
    from flyer_design_research import DESIGN_PRINCIPLES, REFERENCE_SAMPLES

    return {
        "summary": corpus_summary(),
        "principles": [p.__dict__ for p in DESIGN_PRINCIPLES],
        "samples": [s.__dict__ for s in REFERENCE_SAMPLES],
    }
