"""Hypothesis B — single-pass wild poster with locked band photo reference."""

from __future__ import annotations

from typing import Any, Optional

from gig_calendar import GigEvent


def build_wild_constrained_prompt(
    style: dict[str, Any],
    event: GigEvent,
    round_num: int,
    *,
    feedback: Optional[str] = None,
    research: Optional[dict[str, Any]] = None,
    selected_photo: Optional[dict[str, Any]] = None,
) -> str:
    """One-shot creative poster: design around the EXACT attached band photo."""
    venue = event.venue or "Venue TBA"
    band = event.title or "Live music"
    date = event.to_dict().get("short_date") or event.event_date.strftime("%b %d, %Y")
    time_label = event.time_label or "TBA"

    lines = [
        "PRIMARY DIRECTIVE: Design a complete concert flyer poster as ONE image.",
        "The attached band photograph is SACRED — use it exactly as the band depiction.",
        "",
        "BAND PHOTO RULES (highest priority):",
        "- Use the attached reference photo for ALL musicians — same faces, poses, instruments, member count.",
        "- Do NOT redraw, repaint, stylize, or AI-reinterpret the people.",
        "- You MAY crop, scale, and place the photo within a creative composition.",
        "- Apply color grading or duotone to the photo ONLY if faces remain clearly recognizable.",
        "- No face swaps, no beauty filters, no member removal.",
        "",
        "DESIGN FREEDOM (around the photo):",
        "- Bold western/bar/outlaw-country flyer energy is encouraged.",
        "- Creative typography, textures, ticket stubs, barbed wire, torn paper, boots/beer graphics OK.",
        "- Integrate event text into the design — not plain captions on white.",
        "",
        "EVENT FACTS (must be correct and readable):",
        f"- Band: {band}",
        f"- Venue: {venue}",
        f"- Date: {date}",
        f"- Time: {time_label}",
        "",
        "AVOID: generic festival symmetry, fantasy sci-fi, illegible text, wrong event details.",
    ]
    if selected_photo and selected_photo.get("description"):
        lines.extend(["", f"Band photo context: {selected_photo['description']}"])
    if feedback:
        lines.extend(["", "REVISION NOTES:", feedback.strip()])
    lines.append(f"\nGeneration mode: wild_constrained_single_pass (round {round_num}).")
    return "\n".join(lines)
