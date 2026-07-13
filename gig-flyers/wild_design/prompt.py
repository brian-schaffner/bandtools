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
    if research:
        lang = str(research.get("design_language") or "").strip()
        if lang:
            research_bits.append(f"Venue design language: {lang}")
        notes = research.get("design_notes") or []
        research_bits.extend(str(n).strip() for n in notes[:2] if str(n).strip())

    photo_hint = ""
    if selected_photo and selected_photo.get("description"):
        photo_hint = (
            f"Band photo inspiration (do not copy literally): {selected_photo['description']}. "
            "You may stylize, collage, or reinterpret the band — face distortion is acceptable."
        )

    lines = [
        "PRIMARY DIRECTIVE: Design a complete concert flyer poster as ONE unified image.",
        "Include all event text integrated into the design (not a plain photo with captions pasted on).",
        "",
        "EVENT FACTS (must be correct and readable):",
        f"- Band: {band}",
        f"- Venue: {venue}",
        f"- Date: {date}",
        f"- Time: {time_label}",
        "",
        "WILD DESIGN RULES:",
        "- Full creative freedom — collage, surreal layout, bold color, type over image, mixed media.",
        "- No fixed template or handbill grid required.",
        "- Band depiction may be stylized, painted, halftoned, or reinterpreted.",
        "- Face distortion and artistic reinterpretation of musicians are ALLOWED.",
        "- Prioritize memorable visual impact and authentic promoter/zine energy over photo accuracy.",
        "",
        "AVOID:",
        "- Generic Canva/festival symmetry, stock-photo marketing polish, fantasy sci-fi unless venue fits.",
        "- Missing or illegible venue/date/band text.",
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
