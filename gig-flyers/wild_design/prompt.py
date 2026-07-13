"""Prompt builder for wild full-canvas flyer generation."""

from __future__ import annotations

from typing import Any, Optional

from gig_calendar import GigEvent


def build_wild_design_prompt(
    style: dict[str, Any],
    event: GigEvent,
    variation: dict[str, Any],
    round_num: int,
    *,
    feedback: Optional[str] = None,
    research: Optional[dict[str, Any]] = None,
    selected_photo: Optional[dict[str, Any]] = None,
) -> str:
    """Build a full-canvas poster prompt — no photo-fidelity or template constraints."""
    principles = style.get("core_principles") or []
    anti_visual = (style.get("anti_slop") or {}).get("visual_tropes") or []
    venue = event.venue or "Venue TBA"
    band = event.title or "Live music"
    date = event.to_dict().get("short_date") or event.event_date.strftime("%b %d, %Y")
    time_label = event.time_label or "TBA"

    research_bits: list[str] = []
    design_language = ""
    if research:
        design_language = str(research.get("design_language") or "").strip()
        if design_language:
            research_bits.append(f"Venue design language: {design_language}")
        notes = research.get("design_notes") or []
        research_bits.extend(str(n).strip() for n in notes[:2] if str(n).strip())

    photo_hint = ""
    if selected_photo and selected_photo.get("description"):
        photo_hint = (
            f"Band lineup inspiration (stylize freely): {selected_photo['description']}. "
            "Paint, collage, halftone, or reimagine the musicians inside the poster — "
            "face distortion is acceptable."
        )

    # Default aesthetic when venue research is thin: outlaw-country bar flyer.
    venue_lower = f"{venue} {design_language}".lower()
    western_cues = any(
        k in venue_lower
        for k in ("tavern", "bar", "saloon", "honky", "country", "western", "roadhouse", "lane")
    )
    style_anchor = (
        "Outlaw-country / roadhouse bar flyer: dark wood or weathered plank background, "
        "torn-paper labels, rust and cream typography, barbed wire or rope accents, "
        "boots-and-beer authenticity. Band integrated INTO the art — not a stock photo "
        "pasted on plain rectangles."
        if western_cues or not design_language
        else f"Match venue energy ({design_language}) with bold promoter/zine collage — "
        "still one unified designed poster, not a template with pasted photo blocks."
    )

    lines = [
        "PRIMARY DIRECTIVE: Design a complete concert flyer poster as ONE unified designed image.",
        "Typography, textures, graphics, and band depiction must feel like a single "
        "hand-made outlaw-country or dive-bar poster — NOT a clean Canva layout.",
        "",
        "EVENT FACTS (must be correct and readable):",
        f"- Band: {band}",
        f"- Venue: {venue}",
        f"- Date: {date}",
        f"- Time: {time_label}",
        "",
        "VISUAL DNA (wild D — prioritize this over photo accuracy):",
        f"- {style_anchor}",
        "- Integrate event text into the design (torn labels, wood type, stamp lettering, "
        "ticket stubs) — never floating captions on blank cream boxes.",
        "- Band/musicians are part of the composition — painted, halftoned, collage-cut, "
        "or stylized; they live inside the poster world.",
        "- Face distortion and artistic reinterpretation of musicians are ALLOWED.",
        "- Memorable, gritty, authentic promoter energy — like a flyer taped in a bar window.",
        "",
        "WILD DESIGN RULES:",
        "- Full creative freedom — asymmetry, layered textures, bold color, mixed media.",
        "- No fixed template grid, no three stacked rectangles with a photo in the middle.",
        "",
        "AVOID:",
        "- Generic festival symmetry, stock marketing polish, sci-fi fantasy unless venue fits.",
        "- Plain white/cream photo mats, PowerPoint-style blocks, illegible text.",
        "- Missing or wrong venue/date/band text.",
    ]
    if principles:
        lines.extend(["", "CORE PRINCIPLES:"] + [f"- {p}" for p in principles[:4]])
    if anti_visual:
        lines.extend(["", "ANTI-SLOP:"] + [f"- No {t}" for t in anti_visual[:5]])
    if research_bits:
        lines.extend(["", "VENUE CONTEXT:"] + [f"- {b}" for b in research_bits])
    if photo_hint:
        lines.extend(["", photo_hint])
    if feedback:
        lines.extend(
            [
                "",
                "REVISION NOTES (apply to this new wild variant):",
                feedback,
            ]
        )
    lines.append(f"\nCreative round: {round_num}. Generation mode: full_canvas_wild.")
    return "\n".join(lines)
