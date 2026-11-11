"""Flyer generator guided by visual studies of real poster artwork."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

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
)
from structured_layout.graphic_composer import build_recipe, compose_graphic_flyer, recipe_signature
from structured_layout.tier_archetypes import load_tier_archetype
from structured_layout.validation import validate_structured_flyer
from text_validation import resolve_venue_address
from visual_studies import (
    VisualStudy,
    all_studies,
    combined_guidance,
    pick_study_for_research,
)

ROOT = Path(__file__).resolve().parent


@dataclass
class VisualDesignBrief:
    """Layout brief derived from studying one real poster."""

    gig_id: str
    venue: str
    venue_type: str
    study_id: str
    study_title: str
    source_url: str
    option_letter: str
    medium_variant: str | None
    graphic_archetype: str | None
    palette: list[str]
    layout_rules: list[str]
    observations: list[dict[str, str]]
    guidance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_visual_brief(event, research: dict[str, Any] | None) -> tuple[VisualDesignBrief, VisualStudy]:
    """Pick the best-matching visual study and turn its observations into a brief."""
    study = pick_study_for_research(research)
    venue_type = str((research or {}).get("venue_type") or "regional_club")

    if study.medium_variant:
        option_letter = "B"
    elif study.graphic_archetype:
        option_letter = "C"
    else:
        option_letter = "B"

    return (
        VisualDesignBrief(
            gig_id=event.gig_id,
            venue=event.venue,
            venue_type=venue_type,
            study_id=study.id,
            study_title=study.title,
            source_url=study.source_url,
            option_letter=option_letter,
            medium_variant=study.medium_variant,
            graphic_archetype=study.graphic_archetype,
            palette=list(study.palette),
            layout_rules=list(study.layout_rules),
            observations=[{"element": o.element, "detail": o.detail} for o in study.observations],
            guidance=study.guidance_lines(),
        ),
        study,
    )


def _facts(event, band: str) -> dict[str, str]:
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    return {
        "venue": event.venue,
        "band": band,
        "date": date_str,
        "time": event.time_label or "TBA",
        "address": resolve_venue_address(event),
    }


def _layout_from_visual_brief(
    brief: VisualDesignBrief,
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
        recipe = build_recipe(rng, archetype=brief.graphic_archetype)
        layout = create_collage_layout(
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            archetype=archetype,
            rng=rng,
        )
        from dataclasses import replace

        layout = replace(
            layout,
            style_notes=f"Visual study {brief.study_id} → {recipe_signature(recipe)}",
        )
        return layout, recipe

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


def generate_visual_guided_flyer(
    gig_id: str,
    *,
    round_num: int = 1,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Study-matched real poster → layout rules → one PNG + manifest."""
    event = resolve_gig_event(gig_id)
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")

    emit_progress(on_progress, step="research", substep="gig", message="Researching gig context…", progress=5)
    research = research_gig(event, on_progress=on_progress)

    emit_progress(
        on_progress,
        step="research",
        substep="visual_study",
        message="Matching gig to visual poster study…",
        progress=15,
    )
    brief, study = build_visual_brief(event, research)

    emit_progress(on_progress, step="research", substep="photo", message="Selecting band photo…", progress=25)
    selected_photo = select_band_photo(event, research, on_progress=on_progress)
    photo_path = None
    if selected_photo and selected_photo.get("path"):
        photo_path = ROOT / selected_photo["path"]

    layout, recipe = _layout_from_visual_brief(
        brief, event, band=band, research=research, round_num=round_num
    )

    out_dir = gig_output_dir(event) / "visual_guided"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"visual_guided_r{round_num}.png"

    emit_progress(
        on_progress,
        step="render",
        substep="layout",
        message=f"Rendering layout learned from {study.title[:40]}…",
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

    constraint_report = None
    from visual_constraints import get_constraints, validate_layout_constraints

    constraints = get_constraints(study.id)
    if constraints and brief.medium_variant:
        constraint_report = validate_layout_constraints(
            layout,
            constraints,
            venue=event.venue,
            band=band,
        )

    manifest = {
        "gig_id": gig_id,
        "round": round_num,
        "path_rel": output_relative(out_path),
        "brief": brief.to_dict(),
        "study_guidance": combined_guidance(study),
        "research_design_language": research.get("design_language"),
        "layout_score": layout_score,
        "validation": validation.to_dict() if validation else {},
        "constraint_report": constraint_report.to_dict() if constraint_report else {},
    }

    manifest_path = out_dir / f"manifest_r{round_num}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    emit_progress(on_progress, step="done", substep="complete", message="Visual-guided flyer ready", progress=100)
    return manifest


def load_studies_for_ui() -> dict[str, Any]:
    """Expose visual studies + guidance for UI or prompt injection."""
    studies = all_studies()
    return {
        "study_count": len(studies),
        "studies": [s.to_dict() for s in studies],
    }
