"""Wild option D — band photo replace pass after initial full-canvas design."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from gig_calendar import GigEvent
from option_slots import is_wild_option, wild_option_letter

DEFAULT_BAND_REPLACE_INSTRUCTION = (
    "Replace the band/musicians in the poster with the exact people from the reference band photo. "
    "Keep all typography, layout, colors, graphics, and event text from the existing poster design. "
    "Match faces, instruments, poses, and member count from the reference photo."
)


def wild_band_replace_enabled() -> bool:
    return os.getenv("WILD_BAND_REPLACE_ON_REVISE", "1").strip().lower() in {"1", "true", "yes", "on"}


def should_wild_band_replace(
    *,
    fan_out_base: Optional[str],
    prior_poster_path: Optional[Path],
    reference_photo_path: Optional[Path],
) -> bool:
    if not wild_band_replace_enabled():
        return False
    if not fan_out_base or not is_wild_option(fan_out_base):
        return False
    return bool(
        prior_poster_path
        and prior_poster_path.is_file()
        and reference_photo_path
        and reference_photo_path.is_file()
    )


def resolve_prior_option_image(record: dict[str, Any], base_letter: str, out_dir: Path) -> Optional[Path]:
    """Find the most recent poster file for base_option before a new round."""
    from output_paths import resolve_output_path

    letter = (base_letter or "").upper()
    rel = (record.get("options") or {}).get(letter)
    if rel:
        path = resolve_output_path(rel)
        if path.is_file():
            return path

    if not out_dir.is_dir():
        return None
    matches = sorted(out_dir.glob(f"option-{letter}_r*.png"), key=lambda p: p.stat().st_mtime)
    return matches[-1] if matches else None


def build_wild_band_replace_prompt(
    event: GigEvent,
    *,
    feedback: Optional[str] = None,
    research: Optional[dict[str, Any]] = None,
    selected_photo: Optional[dict[str, Any]] = None,
) -> str:
    venue = event.venue or "Venue TBA"
    band = event.title or "Live music"
    date = event.to_dict().get("short_date") or event.event_date.strftime("%b %d, %Y")
    time_label = event.time_label or "TBA"

    lines = [
        "PRIMARY DIRECTIVE: Edit the existing wild poster design (IMAGE 1) by replacing ONLY the band depiction.",
        "",
        "INPUTS:",
        "- IMAGE 1: Current wild poster — preserve typography, layout, color palette, textures, and all event text.",
        "- IMAGE 2: Reference band photo — use these exact musicians, faces, instruments, and poses.",
        "",
        "RULES:",
        f"- Event text must remain correct: {band} · {venue} · {date} · {time_label}",
        "- Do NOT redesign the poster from scratch — this is a band-swap on an approved composition.",
        "- Replace AI/wrong musicians with the real band from IMAGE 2.",
        "- Keep the wild/creative design energy of IMAGE 1 everywhere except the band region.",
        "- All band members from the reference must be visible; no face distortion on the final band.",
        "",
        DEFAULT_BAND_REPLACE_INSTRUCTION,
    ]
    if selected_photo and selected_photo.get("description"):
        lines.extend(["", f"Reference band context: {selected_photo['description']}"])
    if research:
        lang = str(research.get("design_language") or "").strip()
        if lang:
            lines.extend(["", f"Venue design language (preserve): {lang}"])
    if feedback and feedback.strip():
        lines.extend(
            [
                "",
                "ADDITIONAL REVISION NOTES:",
                feedback.strip(),
            ]
        )
    lines.append(f"\nGeneration mode: wild_band_replace (option {wild_option_letter()}).")
    return "\n".join(lines)
