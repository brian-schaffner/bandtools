#!/usr/bin/env python3
"""Generate authentic gig flyers from style.yaml and calendar events."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from ai_reviewer import max_reviewer_retries, review_flyer_image, reviewer_enabled
from bridge.review import public_output_url
from image_providers import generate_with_fallback, resolve_image_provider, resolve_image_provider_for_option
from image_providers.base import (
    generate_band_replace_with_fallback,
    is_provider_split_enabled,
    provider_display_label,
    provider_short_label,
)
from image_providers.photo_treatment import (
    photo_treatment_prompt_block,
    PHOTO_ALLOWED,
    PHOTO_FORBIDDEN,
)
from structured_layout import (
    DesignStyle,
    LayoutSpec,
    generate_layout_with_retry,
    render_flyer,
    score_layout_detailed,
)
from structured_layout.validation import validate_structured_flyer
from gig_calendar import GigEvent, find_gig_by_id, get_upcoming_gigs, is_test_mode, event_from_dict, _events_from_mock, set_test_mode
from gig_research import research_gig, research_prompt_block
from gen_timing import record_generate_timing, record_review_timing
from photo_selector import photo_prompt_block, resolve_band_photo_selection, select_band_photo
from progress_helper import ProgressCallback, emit_progress
from text_validation import (
    footer_prompt_lines,
    resolve_venue_address,
    typography_hierarchy_prompt_lines,
)
from state import (
    get_gig_state,
    is_approved,
    is_eligible_for_auto_generation,
    mark_pending_review,
    upsert_gig,
)

ROOT = Path(__file__).resolve().parent
from agent_secrets import bootstrap_secrets  # noqa: E402

bootstrap_secrets(anchor=ROOT)
STYLE_PATH = ROOT / "style.yaml"


from option_slots import (
    is_wild_option,
    round_option_letters,
    select_round_variations as _select_round_variations_from_slots,
    uses_structured_layout,
    wild_design_enabled,
    wild_d_band_mode,
    wild_round_layout,
    wild_variation,
    wild_variation_for_letter,
)
from output_paths import get_output_dir, output_relative
from wild_design import build_wild_design_prompt
from wild_design.band_replace import (
    build_wild_band_replace_prompt,
    resolve_band_replace_provider,
    resolve_prior_option_image,
    should_auto_wild_band_replace,
    should_wild_band_convert,
    should_wild_band_replace,
)
from wild_design.composite import render_wild_composite_poster
from wild_design.constrained import build_wild_constrained_prompt
from wild_design.color_correct import correct_wild_flyer_colors
from wild_design.logo_overlay import overlay_flyer_logo

OPTION_LETTERS = ("A", "B", "C", "D")


def _calendar_band_name(event: GigEvent | None = None) -> str:
    return (os.getenv("GIG_CALENDAR_BAND") or (event.title if event else "") or "Lindsey Lane Band").strip()


def _maybe_overlay_band_logo(path: Path, event: GigEvent) -> None:
    if overlay_flyer_logo(path, _calendar_band_name(event)):
        return


def _maybe_correct_wild_colors(path: Path, letter: str) -> None:
    correct_wild_flyer_colors(path, letter)


def load_style() -> dict[str, Any]:
    with STYLE_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def gig_output_dir(event: GigEvent) -> Path:
    return get_output_dir() / f"{event.event_date.isoformat()}_{_slug(event.venue)}"


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _variation_seed(gig_id: str, option_letter: str, round_num: int) -> str:
    """Deterministic seed so A/B/C diverge even on the same engine."""
    digest = hashlib.sha256(f"{gig_id}:{option_letter}:{round_num}".encode()).hexdigest()
    return digest[:12]


def _tier_palette_hints(research: Optional[dict[str, Any]], tier: str) -> list[str]:
    """Venue-aware color treatment scaled by creativity tier."""
    if not research:
        return []
    design_lang = str(research.get("design_language", "regional_promoter_handbill"))
    venue_type = str(research.get("venue_type", "regional_club"))
    notes = _as_list(research.get("design_notes"))[:2]

    base = {
        "conservative": (
            "COLOR TREATMENT (Conservative): black-and-white photocopy OR one ink (black/red) on cream — "
            "ignore venue color temptations; readability first"
        ),
        "medium": (
            "COLOR TREATMENT (Medium): muted venue palette — 2–3 colors max, photocopy grain, "
            f"inspired by {design_lang} / {venue_type}"
        ),
        "creative": (
            "COLOR TREATMENT (Creative): bolder venue-appropriate color — warm bar tones, beer-brand reds, "
            f"blues-club mood from {design_lang} — still grainy photocopy, NOT fantasy neon"
        ),
    }
    lines = [base.get(tier, base["medium"])]
    if notes and tier != "conservative":
        lines.append("Venue color cues: " + "; ".join(notes))
    return lines


def _reference_edit_preamble(selected_photo: Optional[dict[str, Any]] = None) -> list[str]:
    """Top-of-prompt block for single-pass images.edit — band photo already on canvas."""
    if not selected_photo:
        return []
    member_count = selected_photo.get("member_count")
    members_line = (
        f"- All {member_count} band members are already visible in the canvas photo — do not redraw people"
        if member_count
        else "- All band members are already visible in the canvas photo — do not redraw people"
    )
    return [
        "PHOTO-ON-CANVAS INPUT MODE (band photo already placed on flyer canvas):",
        "- The band photograph is pre-composited on the input canvas at its final position",
        "- Do NOT modify, redraw, regenerate, duplicate, or add a second band image anywhere",
        members_line,
        "- Add flyer typography, venue/date text, and graphic design ONLY in cream paper around the photo",
        "- Layout creativity is typography and graphics only — the band photo region is locked",
        "- Do NOT add borders, frames, or mats around the band photo — it is already pasted on the canvas",
        "- Do NOT duplicate, tile, or crop-repeat any part of the band photo below or beside the main photo",
        "- Keep all typography and graphics clear of the photo margin — never let text overlap the photo area",
        "- Reserve clear paper above the photo for band name — venue/date/time in header/footer margins only",
        "- Do NOT add grey bars, brush strokes, or blank placeholder strips below the photo",
        "- MANDATORY FOOTER: venue name + full street address as readable text in bottom margin",
        "",
    ]


def _band_photo_fidelity_block(
    style: dict[str, Any],
    selected_photo: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Strict band photo rules — identical for all creativity tiers."""
    fidelity = style.get("photo_fidelity", {})
    rules = _as_list(fidelity.get("rules"))
    edit_rules = _as_list(fidelity.get("reference_edit_mode"))
    member_count = (selected_photo or {}).get("member_count")
    members_line = (
        f"- ALL {member_count} band members fully visible — no cropping or cutting off any person"
        if member_count
        else "- ALL band members fully visible — no cropping or cutting off any person"
    )
    lines = [
        "BAND PHOTO FIDELITY (MANDATORY — applies to ALL tiers A/B/C):",
        "- The band photograph must match the reference EXACTLY: same faces, instruments, poses, member count",
        "- NO warping, stretching, re-posing, AI face changes, beauty filters, or cropping of band members",
        members_line,
        "- Flyer design wraps AROUND the locked band photo; typography/graphics must NOT transform the band photo",
        "- Creative layout changes flyer composition only — never redraw or regenerate the reference photo",
        "- Color tinting/grading for print design is OK — do NOT change faces, poses, or who is in the photo",
    ]
    
    lines.extend(photo_treatment_prompt_block())
    
    if edit_rules and selected_photo:
        lines.append("Photo-on-canvas edit mode (band photo already placed — typography/graphics only):")
        lines.extend(f"- {rule}" for rule in edit_rules)
    if rules:
        lines.append("Photo fidelity doctrine:")
        lines.extend(f"- {rule}" for rule in rules)
    note = fidelity.get("creative_tier_note")
    if note:
        lines.append(str(note).strip())
    lines.append("")
    return lines


def _variation_layout_block(
    variation: dict[str, Any],
    *,
    research: Optional[dict[str, Any]] = None,
    option_letter: str = "",
    round_num: int = 1,
    gig_id: str = "",
) -> list[str]:
    label = variation.get("label", variation.get("id", "flyer"))
    tier = variation.get("tier", variation.get("id", "option"))
    description = str(variation.get("description", "")).strip()
    freedom = variation.get("creative_freedom", tier)
    lines = [
        f"CREATIVITY TIER — {label}:",
        description,
        f"Creative freedom level: {freedom}",
    ]
    if option_letter and gig_id:
        seed = _variation_seed(gig_id, option_letter, round_num)
        lines.append(f"Variation seed: {seed} — use this to diverge from sibling options in this round")
    risk = variation.get("risk_level")
    if risk:
        lines.append(f"Risk-taking: {risk}")
    experimentation = variation.get("layout_experimentation")
    if experimentation:
        lines.append(f"Layout experimentation: {experimentation}")

    orientation = variation.get("orientation")
    if orientation:
        lines.append(f"Required orientation / format: {orientation}")

    structure = _as_list(variation.get("layout_structure"))
    if structure:
        lines.append("LAYOUT STRUCTURE (mandatory — do not borrow from other tiers):")
        lines.extend(f"- {item}" for item in structure)

    color_approach = variation.get("color_approach")
    if color_approach:
        lines.append(f"Color approach: {color_approach}")
    lines.extend(_tier_palette_hints(research, str(tier)))

    typography = variation.get("typography_approach")
    if typography:
        lines.append(f"Typography approach: {typography}")
    production = variation.get("production_feel")
    if production:
        lines.append(f"Production feel: {production}")
    photo_placement = variation.get("photo_placement")
    if photo_placement:
        lines.append(f"Photo placement on flyer (position only — do not alter photo content): {photo_placement}")

    directives = _as_list(variation.get("creative_directive"))
    if directives:
        lines.append("Creative directives for this tier:")
        lines.extend(f"- {item}" for item in directives)

    layout_guidance = _as_list(variation.get("layout_guidance"))
    if layout_guidance:
        lines.append("Layout guidance:")
        lines.extend(f"- {item}" for item in layout_guidance)

    negatives = _as_list(variation.get("negative_prompts"))
    if negatives:
        lines.append("NEGATIVE CONSTRAINTS for this tier:")
        lines.extend(f"- {item}" for item in negatives)

    distinct = _as_list(variation.get("distinct_from"))
    if distinct:
        lines.append("This option must look clearly different from sibling options:")
        lines.extend(f"- {item}" for item in distinct)
    return lines


def _sibling_differentiation_block(
    variation: dict[str, Any],
    sibling_variations: list[dict[str, Any]],
    *,
    option_letter: str = "",
) -> list[str]:
    if not sibling_variations:
        return []
    current_id = variation.get("id")
    others = [v for v in sibling_variations if v.get("id") != current_id]
    if not others:
        return []
    sibling_letters = {"conservative": "A", "medium": "B", "creative": "C"}
    other_labels = []
    for sibling in others:
        letter = sibling_letters.get(str(sibling.get("tier", "")), "?")
        label = sibling.get("label", sibling.get("id", "option"))
        other_labels.append(f"Option {letter} ({label})")
    other_list = " and ".join(other_labels) if len(other_labels) <= 2 else ", ".join(other_labels[:-1]) + f", and {other_labels[-1]}"
    lines = [
        "",
        "SIBLING OPTIONS IN THIS ROUND (same engine — prompts MUST produce visibly different layouts):",
    ]
    for sibling in others:
        label = sibling.get("label", sibling.get("id", "option"))
        tier = sibling.get("tier", sibling.get("id", ""))
        freedom = sibling.get("creative_freedom", "")
        desc = str(sibling.get("description", "")).strip()
        orient = sibling.get("orientation", "")
        lines.append(f"- {label} ({tier}, freedom={freedom}): {desc}")
        if orient:
            lines.append(f"  Their required format: {orient}")
        structure = _as_list(sibling.get("layout_structure"))[:1]
        if structure:
            lines.append(f"  Their layout structure: {structure[0]}")
    my_letter = option_letter or sibling_letters.get(str(variation.get("tier", "")), "?")
    lines.extend(
        [
            f"MANDATORY: Option {my_letter} must look distinctly different from {other_list} at a glance.",
            "Do NOT reuse the same flyer grid or color scheme as siblings — different layout around the SAME untransformed band photo.",
            "Conservative = stacked utilitarian handbill; Medium = offset paste-up + one accent; "
            "Creative = collage/ticket-stub/torn-edge energy — band photo composition unchanged in all tiers.",
        ]
    )
    return lines


def _image_quality_for_tier(tier: str, *, use_reference: bool = False) -> str:
    """OpenAI quality per creativity tier (conservative saves cost, creative gets detail)."""
    if use_reference:
        ref_quality = os.getenv("OPENAI_IMAGE_QUALITY_REFERENCE", "high").strip().lower()
        if ref_quality:
            return ref_quality
    explicit = os.getenv(f"OPENAI_IMAGE_QUALITY_{tier.upper()}", "").strip().lower()
    if explicit:
        return explicit
    defaults = {"conservative": "medium", "medium": "medium", "creative": "high"}
    return defaults.get(tier, os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip().lower() or "medium")


def _prior_layout_summary(prior_prompt: str) -> str:
    """Extract layout cues from a prior prompt for anti-repetition."""
    markers = (
        "CREATIVITY TIER",
        "LAYOUT TEMPLATE",
        "Creative freedom level",
        "LAYOUT STRUCTURE",
        "NEGATIVE CONSTRAINTS",
        "Variation seed",
        "COLOR TREATMENT",
        "Orientation:",
        "Required structure",
        "Photo placement:",
        "Production feel",
    )
    summary: list[str] = []
    for line in prior_prompt.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in markers):
            summary.append(stripped)
        if stripped.startswith("- ") and len(summary) < 12:
            summary.append(stripped)
    if summary:
        return "\n".join(summary[:10])
    return prior_prompt[:400].strip()


def _revision_preamble(
    feedback: str,
    prior_prompt: Optional[str],
    round_num: int,
) -> list[str]:
    lines = [
        "=== PRIMARY DIRECTIVE (MANDATORY — highest priority) ===",
        feedback.strip(),
        "",
        "REVISION REQUIREMENTS:",
        "- Treat the PRIMARY DIRECTIVE above as the main creative brief.",
        "- Dramatically redesign the FLYER LAYOUT (type, borders, background) — do NOT redraw or crop the band photo.",
        "- The new flyer must be immediately recognizable as a different layout concept from the previous round.",
        "- The input band reference photo must remain EXACT — same faces, instruments, poses, member count, composition.",
        "- When the PRIMARY DIRECTIVE conflicts with default style rules below, follow the directive "
        "(except band photo fidelity — never alter the reference photo).",
        f"- Creative round {round_num}: this is a fresh attempt, not an iteration on the same layout.",
    ]
    if prior_prompt:
        lines.extend(
            [
                "",
                "ANTI-REPETITION (do NOT recreate these from the previous round):",
                _prior_layout_summary(prior_prompt),
                "",
                "Full previous prompt (reference only — avoid copying layout, composition, or color scheme):",
                prior_prompt,
            ]
        )
    lines.extend(["", "---", ""])
    return lines


def build_prompt(
    style: dict[str, Any],
    event: GigEvent,
    variation: dict[str, Any],
    round_num: int,
    feedback: Optional[str] = None,
    prior_prompt: Optional[str] = None,
    sibling_variations: Optional[list[dict[str, Any]]] = None,
    research: Optional[dict[str, Any]] = None,
    selected_photo: Optional[dict[str, Any]] = None,
    option_letter: str = "",
) -> str:
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    principles = style.get("core_principles", [])
    hierarchy = style.get("information_hierarchy", {}).get("priority_order", [])
    anti_visual = style.get("anti_ai_rules", {}).get("visual_tropes", {}).get("reject_if_present", [])
    anti_design = style.get("anti_ai_rules", {}).get("design_tropes", {}).get("reject_if_present", [])
    photo_pref = style.get("photography", {}).get("preferred", [])
    photo_avoid = style.get("photography", {}).get("avoid", [])
    typo_rules = style.get("typography", {}).get("rules", [])
    
    lines: list[str] = []
    if feedback:
        lines.extend(_revision_preamble(feedback, prior_prompt, round_num))

    opener = (
        "The band photo is already on the input canvas. "
        "Add flyer typography and graphic design in the remaining areas — do not modify or redraw the photo. "
        "The result should look like a real regional promoter made it quickly with limited budget."
        if selected_photo
        else "Create a single concert flyer image that looks like a real regional promoter made it quickly with limited budget."
    )
    
    lines.extend([opener, ""])
    lines.extend(_reference_edit_preamble(selected_photo))
    lines.extend(_band_photo_fidelity_block(style, selected_photo))
    lines.extend(_variation_layout_block(
        variation,
        research=research,
        option_letter=option_letter,
        round_num=round_num,
        gig_id=event.gig_id,
    ))
    lines.extend([
        "",
        "EVENT DETAILS (must be clearly readable on the flyer):",
        f"- Venue (most prominent): {event.venue}",
        f"- Date: {event.event_date.strftime('%A, %B %d, %Y')}",
        f"- Band: {band}",
        f"- Time: {event.time_label or 'TBA'}",
        f"- Event title context: {event.title}",
        "",
        "CRITICAL EVENT TEXT (copy EXACTLY — wrong date, time, band, or venue is automatic failure):",
        f"- DATE MUST READ: {event.event_date.strftime('%A, %B %d, %Y')}",
        f"- TIME MUST READ: {event.time_label or 'TBA'}",
        f"- BAND MUST READ: {band}",
        f"- VENUE MUST READ: {event.venue}",
        "",
    ])
    address = resolve_venue_address(event)
    if address:
        lines.append(f"- ADDRESS MUST READ: {address}")
        lines.append("")
    lines.extend(typography_hierarchy_prompt_lines(event, band=band))
    lines.extend(footer_prompt_lines(event, band=band))
    if research:
        lines.extend(research_prompt_block(research))
    lines.extend(photo_prompt_block(selected_photo))
    lines.extend(
        [
            "CORE PRINCIPLES:",
            *[f"- {p}" for p in principles[:6]],
            "",
            "INFORMATION HIERARCHY (priority order):",
            ", ".join(hierarchy),
            "",
            "TYPOGRAPHY RULES:",
            *[f"- {r}" for r in typo_rules[:5]],
            "",
        ]
    )
    if selected_photo:
        lines.extend(
            [
                "PHOTOGRAPHY:",
                "- Band photo is already on the canvas — add typography and graphics around it; do NOT redraw people.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "PHOTOGRAPHY:",
                "Preferred: " + "; ".join(photo_pref),
                "Avoid: " + "; ".join(photo_avoid),
                "",
            ]
        )
    lines.extend(
        [
            "STRICTLY AVOID (unless PRIMARY DIRECTIVE explicitly requests otherwise):",
            "Visual tropes: " + ", ".join(anti_visual),
            "Design tropes: " + ", ".join(anti_design),
            "No fantasy, no perfect symmetry, no Canva/Instagram/festival poster aesthetics.",
            "",
            f"Creative round: {round_num}.",
        ]
    )
    lines.extend(
        _sibling_differentiation_block(
            variation,
            sibling_variations or [],
            option_letter=option_letter,
        )
    )
    return "\n".join(lines)


def select_variations(style: dict[str, Any], count: int, used: list[str]) -> list[dict[str, Any]]:
    all_vars = style.get("variations") or []
    if not all_vars:
        all_vars = [
            {"id": "conservative", "label": "A) Conservative", "tier": "conservative"},
            {"id": "medium", "label": "B) Medium", "tier": "medium"},
            {"id": "creative", "label": "C) Creative", "tier": "creative"},
        ]

    # A/B/C always maps to the creativity spectrum in style.yaml order.
    tier_order = ("conservative", "medium", "creative")
    by_id = {str(v.get("id", "")): v for v in all_vars}
    ordered = [by_id[t] for t in tier_order if t in by_id]
    if not ordered:
        ordered = all_vars

    if len(ordered) >= count:
        return ordered[:count]

    available = [v for v in ordered if v.get("id") not in used]
    if len(available) >= count:
        return available[:count]
    return ordered[:count]


def _variations_for_base_option(style: dict[str, Any], count: int, base_letter: str) -> list[dict[str, Any]]:
    """Repeat the chosen option's creativity tier for all revision slots."""
    if is_wild_option(base_letter):
        base_var = (
            wild_variation_for_letter(base_letter)
            if wild_round_layout() == "three_canvas"
            else wild_variation()
        )
        return [dict(base_var) for _ in range(count)]
    ordered = select_variations(style, 3, [])
    index = {"A": 0, "B": 1, "C": 2, "D": 3}.get(base_letter.upper(), 0)
    base_var = ordered[min(index, len(ordered) - 1)]
    return [dict(base_var) for _ in range(count)]


def select_round_variations(style: dict[str, Any], used: list[str]) -> list[dict[str, Any]]:
    return _select_round_variations_from_slots(style, used, select_variations_fn=select_variations)


def _fan_out_revision(base_letter: Optional[str], feedback: Optional[str]) -> bool:
    """True when revision should produce N variants of the base option, not fresh B/C."""
    return bool(base_letter and (feedback or "").strip())


def _gemini_stagger_seconds(option_index: int, letter: str = "") -> float:
    """Light stagger when an option uses Gemini to reduce simultaneous 429s."""
    if option_index <= 0:
        return 0.0
    opt_letter = (letter or OPTION_LETTERS[option_index]).upper()
    if resolve_image_provider_for_option(opt_letter) not in {"gemini", "nano_banana", "google", "nano-banana"}:
        return 0.0
    return option_index * 0.35


def _use_structured_layout(letter: str) -> bool:
    """Structured fixed templates for safe options; wild option D uses full-canvas image gen."""
    if os.getenv("STRUCTURED_LAYOUT_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return uses_structured_layout(letter)


def _get_design_style_for_option(letter: str) -> DesignStyle:
    """Get the design style for a Structured Layout Mode option.
    
    - Option B: Handbill style (utilitarian, type-heavy)
    - Option C: Collage style (layered, offset, paste-up energy)
    """
    if letter.upper() == "C":
        return DesignStyle.COLLAGE
    return DesignStyle.HANDBILL


def _structured_layout_backend(letter: str) -> str:
    """Renderer backend for structured options. PicTex default for B/C."""
    backend = os.getenv("LAYOUT_BACKEND", "pictex").strip().lower()
    if backend == "pictex" and letter.upper() in {"B", "C"}:
        return "pictex"
    if backend in {"", "structured", "pil"}:
        return "structured"
    return "structured"


def _use_fixed_templates() -> bool:
    raw = os.getenv("USE_FIXED_TEMPLATES", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _build_fixed_layout(
    letter: str,
    event: GigEvent,
    design_style: DesignStyle,
    *,
    band: str,
    research: Optional[dict[str, Any]] = None,
    round_num: int = 1,
) -> LayoutSpec:
    from structured_layout.fixed_templates import layout_for_option
    from text_validation import resolve_venue_address

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    return layout_for_option(
        letter,
        event.venue,
        band,
        date_str,
        time_str,
        address=resolve_venue_address(event),
        event=event,
        research=research,
        gig_id=event.gig_id,
        option_letter=letter,
        round_num=round_num,
    )


def _generate_structured_layout_option(
    *,
    letter: str,
    option_index: int,
    count: int,
    variation: dict[str, Any],
    style: dict[str, Any],
    event: GigEvent,
    current_round: int,
    research: dict[str, Any],
    selected_photo: Optional[dict[str, Any]],
    reference_photo_path: Optional[Path],
    out_dir: Path,
    dry_run: bool,
    on_progress: Optional[ProgressCallback],
    feedback: Optional[str] = None,
    base_letter: Optional[str] = None,
    fan_out_base: Optional[str] = None,
    revision_brief: Optional[Any] = None,
) -> dict[str, Any]:
    """Generate a flyer using Structured Layout Mode.
    
    1. AI Art Director produces a layout specification (JSON)
    2. Layout is scored for quality
    3. Final flyer is rendered deterministically from spec + photo
    """
    var_id = variation.get("id", letter)
    option_num = option_index + 1
    slot_base = 20 + option_index * 22
    template_letter = (fan_out_base or letter).upper()
    layout_label = variation.get("label") or variation.get("id", template_letter)
    filename = f"option-{letter}_r{current_round}.png"
    path = out_dir / filename
    
    design_style = _get_design_style_for_option(template_letter)
    
    emit_progress(
        on_progress,
        step="generate",
        substep="start",
        message=(
            f"Generating option {letter} as variant {option_num}/{count} of Option {fan_out_base}…"
            if fan_out_base
            else f"Generating option {letter} via Structured Layout Mode ({design_style.value})…"
        ),
        progress=slot_base,
        option=letter,
        attempt=1,
        option_phase="generating",
        option_progress=0,
    )
    
    gen_started = time.monotonic()
    
    variation_notes = ""
    tier = str(variation.get("tier", "medium"))
    if tier == "conservative":
        variation_notes = "Keep layout simple and utilitarian. Minimal decoration. Focus on readability."
    elif tier == "creative":
        variation_notes = "More creative composition allowed. Try interesting angles or layered elements."
    
    if dry_run:
        band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
        layout = _build_fixed_layout(
            template_letter, event, design_style, band=band, research=research, round_num=current_round
        )
        layout_score = 8.0
    elif _use_fixed_templates():
        band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
        layout = _build_fixed_layout(
            template_letter, event, design_style, band=band, research=research, round_num=current_round
        )
        from structured_layout.layout_scorer import score_layout

        layout_score = float(score_layout(layout, event))
        emit_progress(
            on_progress,
            step="layout",
            substep="template",
            message=f"Fixed {design_style.value} template for option {letter} (score: {layout_score:.1f}/10)",
            option=letter,
        )
    else:
        quality_threshold = float(os.getenv("STRUCTURED_LAYOUT_QUALITY_THRESHOLD", "7.0"))
        max_attempts = int(os.getenv("STRUCTURED_LAYOUT_MAX_ATTEMPTS", "3"))
        
        layout, layout_score = generate_layout_with_retry(
            event,
            design_style,
            research=research,
            variation_notes=variation_notes,
            quality_threshold=quality_threshold,
            max_attempts=max_attempts,
            on_progress=on_progress,
            option=letter,
        )

    apply_feedback = bool(
        feedback
        and (
            fan_out_base
            or (base_letter and letter.upper() == base_letter.upper())
        )
    )
    if apply_feedback:
        from structured_layout.feedback_tweaks import apply_revision_feedback

        layout = apply_revision_feedback(
            layout,
            feedback,
            variant_index=option_index,
            variant_count=count,
            revision_brief=revision_brief,
        )
        emit_progress(
            on_progress,
            step="layout",
            substep="feedback",
            message=(
                f"Applied “{feedback[:48]}…” to Option {letter} "
                f"(variant {option_num} of {template_letter})"
            ),
            option=letter,
        )
    
    emit_progress(
        on_progress,
        step="generate",
        substep="layout_ready",
        message=f"Layout spec ready for option {letter} (score: {layout_score:.1f}/10)",
        progress=slot_base + 10,
        option=letter,
        attempt=1,
        option_phase="rendering",
    )
    
    layout_json_path = out_dir / f"option-{letter}_r{current_round}_layout.json"
    layout_json_path.parent.mkdir(parents=True, exist_ok=True)
    layout_json_path.write_text(layout.to_json(indent=2), encoding="utf-8")
    
    if reference_photo_path and reference_photo_path.is_file():
        render_flyer(
            layout,
            reference_photo_path,
            path,
            on_progress=on_progress,
            option=letter,
            tier=tier,
        )
        _maybe_overlay_band_logo(path, event)
    else:
        render_layout = layout
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        emit_progress(
            on_progress,
            step="generate",
            substep="no_photo",
            message=f"No band photo available for option {letter}",
            option=letter,
        )
    
    gen_elapsed = time.monotonic() - gen_started
    
    detailed_score = score_layout_detailed(layout, event)
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    structured_validation = validate_structured_flyer(path, layout, event, band=band)
    post_render_issues = structured_validation.issues
    
    verdict_pass = (
        layout_score >= 7.0
        and not post_render_issues
    )
    
    verdict = {
        "pass": verdict_pass,
        "score": int(layout_score),
        "issues": (detailed_score.issues[:3] if detailed_score.issues else []) + post_render_issues[:3],
        "remake_recommended": bool(post_render_issues),
        "feedback_for_regen": "; ".join(post_render_issues[:2]) if post_render_issues else "",
        "retry_count": 0,
        "display_note": f"Structured Layout ({design_style.value}): {layout_score:.1f}/10",
        "generation_mode": "structured_fixed",
        "template_version": "v4",
        "design_style": design_style.value,
        "layout_scores": detailed_score.to_dict(),
        "structured_validation": structured_validation.to_dict(),
    }
    
    image_url = public_output_url(path)
    emit_progress(
        on_progress,
        step="review",
        substep="passed",
        message=f"Option {letter}: Structured Layout complete ({layout_score:.1f}/10)",
        option=letter,
        attempt=1,
        option_phase="passed",
        option_progress=100,
        option_image_url=image_url,
    )
    
    return {
        "letter": letter,
        "path_rel": output_relative(path),
        "prompt": f"[Structured Layout Mode: {design_style.value}]",
        "verdict": verdict,
        "var_id": var_id,
        "layout_spec_path": output_relative(layout_json_path),
    }


def _wild_composite_seed(event: GigEvent, current_round: int, option_index: int) -> int:
    raw = f"{event.gig_id}:{current_round}:{option_index}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _generate_wild_composite_option(
    *,
    letter: str,
    option_index: int,
    count: int,
    variation: dict[str, Any],
    style: dict[str, Any],
    event: GigEvent,
    current_round: int,
    reference_photo_path: Path,
    out_dir: Path,
    dry_run: bool,
    on_progress: Optional[ProgressCallback],
    fan_out_base: Optional[str] = None,
) -> dict[str, Any]:
    """Wild option D via PIL composite — exact band photo in a western shell (H3)."""
    var_id = variation.get("id", letter)
    option_num = option_index + 1
    slot_base = 20 + option_index * 22
    filename = f"option-{letter}_r{current_round}.png"
    path = out_dir / filename
    tier = str(variation.get("tier", "wild"))

    emit_progress(
        on_progress,
        step="generate",
        substep="start",
        message=(
            f"Generating option {letter} as variant {option_num}/{count} of Option {fan_out_base}…"
            if fan_out_base
            else f"Generating option {letter} (wild composite — exact band photo)…"
        ),
        progress=slot_base,
        option=letter,
        attempt=1,
        option_phase="generating",
        option_progress=0,
    )

    gen_started = time.monotonic()
    seed = _wild_composite_seed(event, current_round, option_index)
    final_prompt = f"[Wild PIL composite: western shell + exact band photo, seed={seed}]"

    if dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    else:
        emit_progress(
            on_progress,
            step="generate",
            substep="compose",
            message=f"Compositing option {letter} with your band photo…",
            progress=slot_base + 2,
            option=letter,
            attempt=1,
            option_phase="generating",
        )
        render_wild_composite_poster(
            event,
            reference_photo_path,
            path,
            tier="wild_composite",
            seed=seed,
        )

    gen_elapsed = time.monotonic() - gen_started
    image_url = public_output_url(path)

    emit_progress(
        on_progress,
        step="review",
        substep="preview",
        message=f"Option {letter} ready for AI review",
        option=letter,
        attempt=1,
        option_phase="reviewing",
        option_progress=100,
        option_image_url=image_url,
    )

    if dry_run or not reviewer_enabled():
        final_verdict = {
            "pass": True,
            "score": 8,
            "issues": [],
            "remake_recommended": False,
            "feedback_for_regen": "",
            "retry_count": 0,
            "display_note": "Passed",
        }
    else:
        final_verdict = review_flyer_image(
            path,
            style,
            event,
            variation,
            dry_run=dry_run,
            retry_count=0,
            option=letter,
            on_progress=on_progress,
            reference_photo_path=reference_photo_path,
            tier=tier,
        )
        record_review_timing(0.5, generate_seconds=gen_elapsed)

    phase = "passed" if final_verdict.get("pass") else "failed"
    emit_progress(
        on_progress,
        step="review",
        substep="passed" if final_verdict.get("pass") else "remake",
        message=f"Option {letter}: {final_verdict.get('display_note', 'Passed')}",
        option=letter,
        attempt=1,
        option_phase=phase,
        option_progress=100,
        option_image_url=image_url,
    )

    return {
        "letter": letter,
        "path_rel": output_relative(path),
        "prompt": final_prompt,
        "verdict": final_verdict,
        "var_id": var_id,
    }


def _generate_wild_band_convert_option(
    *,
    letter: str,
    variation: dict[str, Any],
    style: dict[str, Any],
    event: GigEvent,
    current_round: int,
    research: dict[str, Any],
    selected_photo: Optional[dict[str, Any]],
    reference_photo_path: Path,
    prior_poster_path: Path,
    out_dir: Path,
    dry_run: bool,
    on_progress: Optional[ProgressCallback],
    feedback: Optional[str] = None,
) -> dict[str, Any]:
    """Band-swap only: keep poster design (IMAGE 1), replace musicians from reference photo."""
    from wild_design.band_replace import DEFAULT_CONVERT_FEEDBACK

    var_id = variation.get("id", letter)
    slot_base = 20
    filename = f"option-{letter}_r{current_round}.png"
    path = out_dir / filename
    convert_feedback = (feedback or "").strip() or DEFAULT_CONVERT_FEEDBACK
    variation = {**variation, "generation_mode": "wild_band_replace", "tier": "wild"}

    emit_progress(
        on_progress,
        step="generate",
        substep="band_convert",
        message=f"Converting option {letter} to your band photo…",
        progress=slot_base,
        option=letter,
        attempt=1,
        option_phase="generating",
    )

    gen_started = time.monotonic()
    final_prompt = build_wild_band_replace_prompt(
        event,
        feedback=convert_feedback,
        research=research,
        selected_photo=selected_photo,
    )
    provider_name = resolve_band_replace_provider(letter)

    if dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    else:
        generate_image(
            final_prompt,
            path,
            dry_run=False,
            reference_photo_path=reference_photo_path,
            design_reference_path=prior_poster_path,
            on_progress=on_progress,
            option=letter,
            attempt=1,
            progress=slot_base + 3,
            tier="wild",
            provider=provider_name,
        )
        _maybe_correct_wild_colors(path, letter)
        overlay_flyer_logo(path, _calendar_band_name(event))

    gen_elapsed = time.monotonic() - gen_started
    image_url = public_output_url(path)

    if dry_run or not reviewer_enabled():
        final_verdict = {
            "pass": True,
            "score": 8,
            "issues": [],
            "remake_recommended": False,
            "feedback_for_regen": "",
            "retry_count": 0,
            "display_note": "Band convert complete",
        }
    else:
        final_verdict = review_flyer_image(
            path,
            style,
            event,
            variation,
            dry_run=dry_run,
            retry_count=0,
            option=letter,
            on_progress=on_progress,
            reference_photo_path=reference_photo_path,
            selected_photo=selected_photo,
            tier="wild",
        )

    emit_progress(
        on_progress,
        step="review",
        substep="passed",
        message=f"Option {letter}: converted to your band",
        option=letter,
        attempt=1,
        option_phase="passed",
        option_progress=100,
        option_image_url=image_url,
    )
    if not dry_run:
        record_generate_timing(gen_elapsed, provider=provider_name, quality="high", tier="wild")
        record_review_timing(0.5, generate_seconds=gen_elapsed)

    return {
        "letter": letter,
        "path_rel": output_relative(path),
        "prompt": final_prompt,
        "verdict": final_verdict,
        "var_id": var_id,
    }


def _generate_single_option(
    *,
    letter: str,
    option_index: int,
    count: int,
    variation: dict[str, Any],
    style: dict[str, Any],
    event: GigEvent,
    current_round: int,
    variations: list[dict[str, Any]],
    research: dict[str, Any],
    selected_photo: Optional[dict[str, Any]],
    reference_photo_path: Optional[Path],
    out_dir: Path,
    feedback: Optional[str],
    base_letter: Optional[str],
    base_prior_prompt: Optional[str],
    fan_out_base: Optional[str],
    fan_out_prior_image: Optional[Path],
    revision_brief: Optional[Any],
    dry_run: bool,
    on_progress: Optional[ProgressCallback],
) -> dict[str, Any]:
    """Generate, review, and optionally remake one option (thread-safe progress).
    
    Generation modes:
    - Option A: Existing AI image generation workflow (unchanged)
    - Option B: Structured Layout Mode (handbill style)  
    - Option C: Structured Layout Mode (collage style)
    """
    if _use_structured_layout(letter):
        return _generate_structured_layout_option(
            letter=letter,
            option_index=option_index,
            count=count,
            variation=variation,
            style=style,
            event=event,
            current_round=current_round,
            research=research,
            selected_photo=selected_photo,
            reference_photo_path=reference_photo_path,
            out_dir=out_dir,
            dry_run=dry_run,
            on_progress=on_progress,
            feedback=feedback,
            base_letter=base_letter,
            fan_out_base=fan_out_base,
            revision_brief=revision_brief,
        )

    wild_gen = is_wild_option(letter)
    wild_band_replace = wild_gen and should_wild_band_replace(
        fan_out_base=fan_out_base,
        prior_poster_path=fan_out_prior_image,
        reference_photo_path=reference_photo_path,
    )
    if (
        wild_gen
        and not wild_band_replace
        and wild_d_band_mode() == "composite"
        and reference_photo_path
        and reference_photo_path.is_file()
    ):
        return _generate_wild_composite_option(
            letter=letter,
            option_index=option_index,
            count=count,
            variation=variation,
            style=style,
            event=event,
            current_round=current_round,
            reference_photo_path=reference_photo_path,
            out_dir=out_dir,
            dry_run=dry_run,
            on_progress=on_progress,
            fan_out_base=fan_out_base,
        )

    stagger = _gemini_stagger_seconds(option_index, letter)
    if stagger > 0:
        time.sleep(stagger)

    var_id = variation.get("id", letter)
    option_num = option_index + 1
    slot_base = 20 + option_index * 22
    layout_label = variation.get("label") or variation.get("id", letter)
    letter_prior = base_prior_prompt if feedback and (fan_out_base or letter == base_letter) else None
    extra_feedback: Optional[str] = None
    filename = f"option-{letter}_r{current_round}.png"
    path = out_dir / filename
    final_prompt = ""
    final_verdict: dict[str, Any] = {}
    image_url = ""
    max_remakes = max_reviewer_retries()

    for attempt in range(max_remakes + 1):
        attempt_num = attempt + 1
        attempt_feedback = feedback if (fan_out_base or letter == base_letter) else None
        if attempt_feedback and fan_out_base:
            attempt_feedback = (
                f"{attempt_feedback}\n\n"
                f"Variation {option_index + 1} of {count}: distinct interpretation of Option {fan_out_base} "
                f"with the same revision direction."
            )
        if extra_feedback:
            attempt_feedback = (
                f"{attempt_feedback}\n\n{extra_feedback}" if attempt_feedback else extra_feedback
            )

        phase = "remaking" if attempt > 0 else "generating"
        if attempt == 0:
            emit_progress(
                on_progress,
                step="generate",
                substep="start",
                message=f"Generating option {letter} ({option_num}/{count})…",
                progress=slot_base,
                option=letter,
                attempt=attempt_num,
                option_phase=phase,
                option_progress=0,
            )
        else:
            emit_progress(
                on_progress,
                step="generate",
                substep="remake",
                message=f"Remaking option {letter} (attempt {attempt_num}/{max_remakes + 1})…",
                progress=slot_base + 1,
                option=letter,
                attempt=attempt_num,
                option_phase="remaking",
                option_progress=0,
                option_note=extra_feedback or "",
            )

        gen_started = time.monotonic()
        emit_progress(
            on_progress,
            step="generate",
            substep="prompt",
            message=f"Building prompt for {layout_label}…",
            detail=variation.get("description", ""),
            progress=slot_base + 2,
            option=letter,
            attempt=attempt_num,
            option_phase=phase,
        )
        final_prompt = build_wild_band_replace_prompt(
            event,
            feedback=attempt_feedback,
            research=research,
            selected_photo=selected_photo,
        ) if wild_band_replace else build_wild_constrained_prompt(
            style,
            event,
            current_round,
            feedback=attempt_feedback,
            research=research,
            selected_photo=selected_photo,
        ) if (
            wild_gen
            and wild_d_band_mode() == "constrained"
        ) else build_wild_design_prompt(
            style,
            event,
            variation,
            current_round,
            feedback=attempt_feedback,
            research=research,
            selected_photo=selected_photo,
            option_letter=letter,
        ) if wild_gen else build_prompt(
            style,
            event,
            variation,
            current_round,
            feedback=attempt_feedback,
            prior_prompt=letter_prior,
            sibling_variations=variations,
            research=research,
            selected_photo=selected_photo,
            option_letter=letter,
        )
        tier = str(variation.get("tier", letter))
        if wild_band_replace:
            variation = {**variation, "generation_mode": "wild_band_replace", "tier": "wild"}
        elif wild_gen and wild_d_band_mode() == "constrained":
            variation = {**variation, "generation_mode": "wild_constrained_single_pass", "tier": "wild"}
        if wild_band_replace or (wild_gen and wild_d_band_mode() == "constrained"):
            effective_reference = reference_photo_path
        elif wild_gen:
            effective_reference = None
        else:
            effective_reference = reference_photo_path
        design_reference = fan_out_prior_image if wild_band_replace else None
        auto_band_replace = should_auto_wild_band_replace(
            letter=letter,
            reference_photo_path=reference_photo_path,
            fan_out_base=fan_out_base,
        )
        provider_name = (
            resolve_band_replace_provider(letter)
            if wild_band_replace
            else resolve_image_provider_for_option(letter)
        )
        use_reference = bool(effective_reference and effective_reference.is_file())
        image_quality = _image_quality_for_tier(tier, use_reference=use_reference)
        generate_image(
            final_prompt,
            path,
            dry_run=dry_run,
            reference_photo_path=effective_reference,
            design_reference_path=design_reference,
            on_progress=on_progress,
            option=letter,
            attempt=attempt_num,
            progress=slot_base + 3,
            tier=tier,
            provider=provider_name,
        )
        band_replace_applied = wild_band_replace
        if auto_band_replace and reference_photo_path and path.is_file():
            auto_prompt = build_wild_band_replace_prompt(
                event,
                feedback=attempt_feedback,
                research=research,
                selected_photo=selected_photo,
            )
            variation = {**variation, "generation_mode": "wild_band_replace", "tier": "wild"}
            replace_provider = resolve_band_replace_provider(letter)
            emit_progress(
                on_progress,
                step="generate",
                substep="band_replace",
                message=f"Replacing AI musicians with your band on option {letter} via OpenAI…",
                progress=slot_base + 5,
                option=letter,
                attempt=attempt_num,
                option_phase=phase,
            )
            replace_started = time.monotonic()
            generate_image(
                auto_prompt,
                path,
                dry_run=dry_run,
                reference_photo_path=reference_photo_path,
                design_reference_path=path,
                on_progress=on_progress,
                option=letter,
                attempt=attempt_num,
                progress=slot_base + 6,
                tier="wild",
                provider=replace_provider,
            )
            provider_name = replace_provider
            final_prompt = auto_prompt
            band_replace_applied = True
        image_url = public_output_url(path)
        if not dry_run and wild_gen and path.is_file():
            if correct_wild_flyer_colors(path, letter):
                image_url = public_output_url(path)
            if overlay_flyer_logo(path, _calendar_band_name(event)):
                image_url = public_output_url(path)
        gen_elapsed = time.monotonic() - gen_started
        if not dry_run:
            record_generate_timing(
                gen_elapsed,
                provider=provider_name,
                quality=image_quality,
                tier=tier,
            )
        emit_progress(
            on_progress,
            step="review",
            substep="preview",
            message=f"Option {letter} ready for AI review",
            option=letter,
            attempt=attempt_num,
            option_phase="reviewing",
            option_progress=100,
            option_image_url=image_url,
        )

        if dry_run or not reviewer_enabled():
            final_verdict = {
                "pass": True,
                "score": 8,
                "issues": [],
                "remake_recommended": False,
                "feedback_for_regen": "",
                "retry_count": attempt,
                "display_note": "Passed",
            }
            emit_progress(
                on_progress,
                step="review",
                substep="passed",
                message=f"Option {letter}: Passed",
                option=letter,
                attempt=attempt_num,
                option_phase="passed",
                option_progress=100,
                option_image_url=image_url,
            )
            record_review_timing(0.5, generate_seconds=gen_elapsed)
            break

        review_started = time.monotonic()
        final_verdict = review_flyer_image(
            path,
            style,
            event,
            variation,
            dry_run=dry_run,
            retry_count=attempt,
            option=letter,
            on_progress=on_progress,
            reference_photo_path=(
                None
                if wild_gen and wild_d_band_mode() == "full_canvas" and not band_replace_applied
                else reference_photo_path
            ),
            selected_photo=selected_photo,
            tier=tier,
        )
        review_elapsed = time.monotonic() - review_started

        if final_verdict.get("remake_recommended"):
            exhausted = attempt >= max_remakes
            fail_note = (
                final_verdict.get("display_note")
                or "; ".join(final_verdict.get("issues", [])[:2])
            )
            if exhausted:
                fail_note = f"{fail_note} (auto-remake limit reached)".strip()
            emit_progress(
                on_progress,
                step="review",
                substep="remake",
                message=f"Remake recommended for option {letter}",
                detail=final_verdict.get("feedback_for_regen", ""),
                option=letter,
                attempt=attempt_num,
                option_phase="failed",
                option_progress=100,
                option_note=fail_note,
                option_image_url=image_url,
                option_exhausted=exhausted,
            )
        elif final_verdict.get("pass"):
            emit_progress(
                on_progress,
                step="review",
                substep="passed",
                message=f"Option {letter}: {final_verdict.get('display_note', 'Passed')}",
                option=letter,
                attempt=attempt_num,
                option_phase="passed",
                option_progress=100,
                option_image_url=image_url,
            )

        if not final_verdict.get("remake_recommended") or attempt >= max_remakes:
            record_review_timing(review_elapsed, generate_seconds=gen_elapsed)
            break

        regen_feedback = final_verdict.get("feedback_for_regen", "")
        issues = final_verdict.get("issues", [])
        extra_feedback = (
            "AI REVIEWER FIXES REQUIRED (mandatory):\n"
            f"{regen_feedback}\n"
            f"Issues found: {'; '.join(issues)}"
        ).strip()

    return {
        "letter": letter,
        "path_rel": output_relative(path),
        "prompt": final_prompt,
        "verdict": final_verdict,
        "var_id": var_id,
    }


def generate_image(
    prompt: str,
    output_path: Path,
    dry_run: bool = False,
    reference_photo_path: Optional[Path] = None,
    design_reference_path: Optional[Path] = None,
    on_progress: Optional[ProgressCallback] = None,
    *,
    option: str = "",
    attempt: int = 0,
    progress: int = 0,
    tier: str = "",
    provider: Optional[str] = None,
) -> None:
    opt = option or "?"
    provider_name = (
        provider
        or (resolve_image_provider_for_option(opt) if opt in OPTION_LETTERS else resolve_image_provider())
    )
    provider_label = provider_display_label(provider_name)
    option_engine_label = f"{opt}: {provider_short_label(provider_name)}" if opt in OPTION_LETTERS else provider_label

    if dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"")
        emit_progress(
            on_progress,
            step="generate",
            substep="saved",
            message=f"Saved option {opt} (dry run)",
            progress=progress + 2,
            option=opt,
            attempt=attempt,
            provider_label=option_engine_label,
            active_provider=provider_name,
        )
        return

    use_reference = bool(reference_photo_path and reference_photo_path.is_file())
    use_band_replace = bool(
        use_reference
        and design_reference_path
        and design_reference_path.is_file()
    )
    emit_progress(
        on_progress,
        step="generate",
        substep="provider",
        message=f"Generating option {opt} with {provider_label}",
        progress=progress,
        option=opt,
        attempt=attempt,
        provider_label=option_engine_label,
        active_provider=provider_name,
    )
    try:
        generate_fn = generate_band_replace_with_fallback if use_band_replace else generate_with_fallback
        used = generate_fn(
            prompt,
            output_path,
            reference_photo_path=reference_photo_path,
            design_reference_path=design_reference_path,
            on_progress=on_progress,
            option=opt,
            attempt=attempt,
            progress=progress,
            provider=provider_name,
            quality=_image_quality_for_tier(tier, use_reference=use_reference) if tier else None,
            tier=tier,
        )
        if used != provider_name:
            used_label = provider_display_label(used)
            used_short = f"{opt}: {provider_short_label(used)}" if opt in OPTION_LETTERS else used_label
            emit_progress(
                on_progress,
                step="generate",
                substep="fallback_done",
                message=f"Used OpenAI fallback for option {opt}",
                progress=progress + 1,
                option=opt,
                attempt=attempt,
                provider_label=used_short,
                active_provider=used,
            )
    except Exception as exc:
        note = str(exc)
        if len(note) > 220:
            note = note[:217] + "…"
        emit_progress(
            on_progress,
            step="generate",
            substep="error",
            message=f"Option {opt} failed: {note}",
            detail=note,
            progress=progress,
            option=opt,
            attempt=attempt,
            option_phase="error",
            option_progress=100,
            option_note=note,
        )
        raise


def resolve_gig_event(gig_id: str) -> GigEvent:
    """Resolve gig metadata from state, live calendar, manifests, or mock data."""
    from gig_resolve import resolve_gig_event as _resolve

    return _resolve(gig_id)


def generate_for_gig(
    gig_id: str,
    count: int = 3,
    round_num: Optional[int] = None,
    feedback: Optional[str] = None,
    base_option: Optional[str] = None,
    dry_run: bool = False,
    fresh_start: bool = False,
    on_progress: Optional[ProgressCallback] = None,
    generation_source: Optional[str] = None,
    revision_brief: Optional[Any] = None,
    convert_band: Optional[str] = None,
    band_photo_id: Optional[str] = None,
) -> dict[str, Any]:
    event = resolve_gig_event(gig_id)

    if is_approved(gig_id) and not fresh_start:
        return {"gig_id": gig_id, "skipped": "already approved"}

    emit_progress(
        on_progress,
        step="starting",
        substep="prep",
        message="Preparing generation…",
        detail=f"Round {round_num or 'next'}",
        progress=2,
    )

    style = load_style()
    record = get_gig_state(gig_id) or {}
    current_round = round_num if round_num is not None else int(record.get("round", 0)) + 1
    convert_letter = (convert_band or "").strip().upper() or None

    if convert_letter:
        if not is_wild_option(convert_letter):
            raise ValueError(f"Option {convert_letter} is not a wild full-canvas poster")
        out_dir = gig_output_dir(event)
        prior_poster = resolve_prior_option_image(record, convert_letter, out_dir)
        if not prior_poster or not prior_poster.is_file():
            raise ValueError(f"No existing poster found for option {convert_letter}")

        emit_progress(
            on_progress,
            step="starting",
            substep="band_convert",
            message=f"Converting option {convert_letter} to your band…",
            progress=4,
        )
        research = research_gig(event, on_progress=on_progress)
        selected_photo = resolve_band_photo_selection(
            event, research, photo_id=band_photo_id, on_progress=on_progress
        )
        if not selected_photo or not selected_photo.get("path"):
            raise ValueError("No band reference photo available for convert")
        reference_photo_path = ROOT / selected_photo["path"]
        if not reference_photo_path.is_file():
            raise ValueError(f"Band photo file missing: {reference_photo_path}")

        variation = wild_variation_for_letter(convert_letter)
        result = _generate_wild_band_convert_option(
            letter=convert_letter,
            variation=variation,
            style=style,
            event=event,
            current_round=current_round,
            research=research,
            selected_photo=selected_photo,
            reference_photo_path=reference_photo_path,
            prior_poster_path=prior_poster,
            out_dir=out_dir,
            dry_run=dry_run,
            on_progress=on_progress,
            feedback=feedback,
        )

        options = dict(record.get("options") or {})
        prompts = dict(record.get("prompts") or {})
        reviewer_verdicts = dict(record.get("reviewer_verdicts") or {})
        used_variations = list(record.get("used_variations", []))
        for letter in round_option_letters():
            if letter == convert_letter:
                continue
            sibling_prior = resolve_prior_option_image(record, letter, out_dir)
            if not sibling_prior or not sibling_prior.is_file():
                continue
            sibling_dest = out_dir / f"option-{letter}_r{current_round}.png"
            if dry_run:
                sibling_dest.parent.mkdir(parents=True, exist_ok=True)
                sibling_dest.write_bytes(b"")
            else:
                shutil.copy2(sibling_prior, sibling_dest)
            options[letter] = output_relative(sibling_dest)

        options[convert_letter] = result["path_rel"]
        prompts[convert_letter] = result["prompt"]
        reviewer_verdicts[convert_letter] = result["verdict"]
        var_id = result["var_id"]
        if var_id not in used_variations:
            used_variations.append(var_id)

        mark_pending_review(gig_id, options, prompts, current_round)
        upsert_gig(
            gig_id,
            used_variations=used_variations,
            event=event.to_dict(),
            research=research,
            selected_photo=selected_photo,
            reviewer_verdicts=reviewer_verdicts,
            **({"generation_source": generation_source} if generation_source else {}),
        )
        manifest = {
            "gig_id": gig_id,
            "round": current_round,
            "event": event.to_dict(),
            "options": options,
            "prompts": prompts,
            "research": research,
            "selected_photo": selected_photo,
            "reviewer_verdicts": reviewer_verdicts,
            "output_dir": output_relative(out_dir),
            "convert_band": convert_letter,
            "generation_mode": "wild_band_convert",
        }
        if feedback:
            manifest["feedback"] = feedback
        manifest_path = out_dir / f"manifest_r{current_round}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest

    used_variations = [] if fresh_start else list(record.get("used_variations", []))
    prior_prompts = record.get("prompts", {})
    base_letter = (base_option or "").upper() or None
    base_prior_prompt = prior_prompts.get(base_letter, None) if base_letter else None
    fan_out_base = base_letter if _fan_out_revision(base_letter, feedback) else None

    if fan_out_base:
        variations = _variations_for_base_option(style, count, fan_out_base)
    else:
        variations = select_round_variations(style, used_variations)
    letters = round_option_letters()
    count = min(count, len(letters))
    out_dir = gig_output_dir(event)
    fan_out_prior_image: Optional[Path] = None
    if fan_out_base and is_wild_option(fan_out_base):
        fan_out_prior_image = resolve_prior_option_image(record, fan_out_base, out_dir)
    emit_progress(
        on_progress,
        step="starting",
        substep="variations",
        message=(
            f"Fan-out revision: 3 variants of Option {fan_out_base}"
            + (
                " (swapping in your band photo on wild D)"
                if (
                    fan_out_base
                    and is_wild_option(fan_out_base)
                    and fan_out_prior_image
                    and wild_round_layout() != "three_canvas"
                )
                else ""
            )
            if fan_out_base
            else (
                "Three full-canvas wild tiers: bold → balanced → refined"
                if wild_design_enabled() and wild_round_layout() == "three_canvas"
                else f"Selected creativity tiers: {', '.join(v.get('tier', v.get('id', '?')) for v in variations)}"
            )
        ),
        progress=4,
    )

    research = research_gig(event, on_progress=on_progress)
    selected_photo = select_band_photo(event, research, on_progress=on_progress)
    reference_photo_path = None
    if selected_photo and selected_photo.get("path"):
        reference_photo_path = ROOT / selected_photo["path"]

    options: dict[str, str] = {}
    prompts: dict[str, str] = {}
    reviewer_verdicts: dict[str, dict[str, Any]] = {}

    emit_progress(
        on_progress,
        step="generate",
        substep="parallel",
        message=f"Generating {count} option(s) in parallel…",
        progress=10,
    )

    workers = min(3, max(1, count))
    futures = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for idx, (letter, variation) in enumerate(zip(letters[:count], variations)):
            futures[
                executor.submit(
                    _generate_single_option,
                    letter=letter,
                    option_index=idx,
                    count=count,
                    variation=variation,
                    style=style,
                    event=event,
                    current_round=current_round,
                    variations=variations,
                    research=research,
                    selected_photo=selected_photo,
                    reference_photo_path=reference_photo_path,
                    out_dir=out_dir,
                    feedback=feedback,
                    base_letter=base_letter,
                    base_prior_prompt=base_prior_prompt,
                    fan_out_base=fan_out_base,
                    fan_out_prior_image=fan_out_prior_image,
                    revision_brief=revision_brief,
                    dry_run=dry_run,
                    on_progress=on_progress,
                )
            ] = letter

        for future in as_completed(futures):
            result = future.result()
            letter = result["letter"]
            options[letter] = result["path_rel"]
            prompts[letter] = result["prompt"]
            reviewer_verdicts[letter] = result["verdict"]
            var_id = result["var_id"]
            if var_id not in used_variations:
                used_variations.append(var_id)

    emit_progress(
        on_progress,
        step="finalize",
        substep="state",
        message="Updating state…",
        progress=90,
    )
    mark_pending_review(gig_id, options, prompts, current_round)
    upsert_gig(
        gig_id,
        used_variations=used_variations,
        event=event.to_dict(),
        research=research,
        selected_photo=selected_photo,
        reviewer_verdicts=reviewer_verdicts,
        **({"generation_source": generation_source} if generation_source else {}),
    )

    manifest: dict[str, Any] = {
        "gig_id": gig_id,
        "round": current_round,
        "event": event.to_dict(),
        "options": options,
        "prompts": prompts,
        "research": research,
        "selected_photo": selected_photo,
        "reviewer_verdicts": reviewer_verdicts,
        "output_dir": output_relative(out_dir),
        "template_version": "v4",
        "generation_mode": "structured_fixed",
    }
    if feedback:
        manifest["feedback"] = feedback
    if base_letter:
        manifest["base_option"] = base_letter
    if fan_out_base:
        manifest["fan_out_base"] = fan_out_base
    if revision_brief is not None:
        manifest["revision_brief"] = getattr(revision_brief, "summary", str(revision_brief))
    if fresh_start:
        manifest["regenerate"] = True

    emit_progress(
        on_progress,
        step="finalize",
        substep="manifest",
        message="Writing manifest…",
        progress=92,
    )
    manifest_path = out_dir / f"manifest_r{current_round}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def cmd_scan(min_days: int, max_days: int) -> int:
    style = load_style()
    _ = style  # validate yaml loads
    gigs = get_upcoming_gigs(min_days=min_days, max_days=max_days)
    needs = [
        g.gig_id
        for g in gigs
        if is_eligible_for_auto_generation(g.gig_id)
    ]
    payload = {
        "window_days": [min_days, max_days],
        "count": len(gigs),
        "gigs": [g.to_dict() for g in gigs],
        "needs_generation": needs,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _bridge_send_review_url() -> str:
    port = os.getenv("BRIDGE_PORT", "8010")
    return f"http://127.0.0.1:{port}/send-review"


def post_send_review(manifest: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """POST manifest to local bridge /send-review (iMessage review link)."""
    if dry_run:
        return {"sent": False, "dry_run": True, "gig_id": manifest.get("gig_id")}

    import urllib.error
    import urllib.request

    secret = os.getenv("BRIDGE_SECRET", "")
    body = json.dumps(
        {
            "gig_id": manifest["gig_id"],
            "round": manifest.get("round", 1),
            "event": manifest.get("event", {}),
            "options": manifest.get("options", {}),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _bridge_send_review_url(),
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Secret": secret,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"send-review failed ({exc.code}): {detail}") from exc


def cmd_auto_scan(
    min_days: int,
    max_days: int,
    count: int,
    dry_run: bool,
) -> int:
    results: list[dict[str, Any]] = []
    for event in get_upcoming_gigs(min_days=min_days, max_days=max_days):
        gig_id = event.gig_id
        if not is_eligible_for_auto_generation(gig_id):
            record = get_gig_state(gig_id) or {}
            results.append(
                {
                    "gig_id": gig_id,
                    "skipped": record.get("status", "in_progress"),
                }
            )
            continue

        upsert_gig(gig_id, event=event.to_dict(), generation_source="auto")
        try:
            manifest = generate_for_gig(gig_id, count=count, dry_run=dry_run, generation_source="auto")
            if manifest.get("skipped"):
                results.append(manifest)
                continue
            delivery = post_send_review(manifest, dry_run=dry_run)
            results.append(
                {
                    "gig_id": gig_id,
                    "status": "generated",
                    "round": manifest.get("round"),
                    "delivery": delivery,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"gig_id": gig_id, "error": str(exc)})

    payload = {
        "mode": "auto",
        "window_days": [min_days, max_days],
        "test_mode": is_test_mode(),
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_generate_all(min_days: int, max_days: int, count: int, dry_run: bool) -> int:
    results = []
    for event in get_upcoming_gigs(min_days=min_days, max_days=max_days):
        if not is_eligible_for_auto_generation(event.gig_id):
            record = get_gig_state(event.gig_id) or {}
            results.append({"gig_id": event.gig_id, "skipped": record.get("status", "in_progress")})
            continue
        results.append(generate_for_gig(event.gig_id, count=count, dry_run=dry_run))
    print(json.dumps(results, indent=2))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Gig flyer generator")
    parser.add_argument("--scan", action="store_true", help="List gigs in the target window")
    parser.add_argument("--auto-scan", action="store_true", help="Generate and send review links for new gigs in window")
    parser.add_argument("--generate-all", action="store_true", help="Generate for all eligible gigs")
    parser.add_argument("--gig", help="Gig id to generate for")
    parser.add_argument("--count", type=int, default=3, help="Number of options (2-3)")
    parser.add_argument("--round", type=int, help="Explicit round number")
    parser.add_argument("--feedback", help="Revision feedback text")
    parser.add_argument("--base-option", choices=OPTION_LETTERS, help="Option letter to revise from")
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Fresh round from scratch (works on approved gigs)",
    )
    parser.add_argument("--min-days", type=int, default=21)
    parser.add_argument("--max-days", type=int, default=28)
    parser.add_argument("--dry-run", action="store_true", help="Skip OpenAI calls; write placeholder files")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use fixtures/mock_gigs.json instead of live calendar (also sets GIG_FLYERS_TEST_MODE)",
    )
    args = parser.parse_args(argv)

    if args.test:
        os.environ["GIG_FLYERS_TEST_MODE"] = "1"
        set_test_mode(True)

    if args.scan:
        return cmd_scan(args.min_days, args.max_days)
    if args.auto_scan:
        return cmd_auto_scan(
            args.min_days,
            args.max_days,
            min(max(args.count, 2), 3),
            args.dry_run,
        )
    if args.generate_all:
        return cmd_generate_all(args.min_days, args.max_days, min(max(args.count, 2), 3), args.dry_run)
    if args.gig:
        if args.regenerate:
            from state import begin_regenerate_round, get_gig_state

            record = get_gig_state(args.gig) or {}
            if record.get("status") == "approved":
                begin_regenerate_round(args.gig)
        manifest = generate_for_gig(
            args.gig,
            count=min(max(args.count, 2), 3),
            round_num=args.round,
            feedback=args.feedback,
            base_option=args.base_option,
            dry_run=args.dry_run,
            fresh_start=args.regenerate,
        )
        print(json.dumps(manifest, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
