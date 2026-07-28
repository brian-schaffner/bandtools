"""Verbatim gig-fact blocks for wild prompts and revision briefs."""

from __future__ import annotations

import os

from gig_calendar import GigEvent
from text_validation import footer_required_strings, resolve_venue_address


def wild_fact_locks_enabled() -> bool:
    return os.getenv("WILD_FACT_LOCKS", "0").strip().lower() in {"1", "true", "yes", "on"}


def build_fact_lock_prompt_block(event: GigEvent, *, band: str) -> str:
    """Non-negotiable spellings for full-canvas wild generation."""
    if not wild_fact_locks_enabled():
        return ""

    venue = (event.venue or "Venue TBA").strip()
    band_name = (band or event.title or "Live music").strip()
    date = event.to_dict().get("short_date") or event.event_date.strftime("%b %d, %Y")
    time_label = (event.time_label or "TBA").strip()
    address = resolve_venue_address(event)

    lines = [
        "FACT LOCKS (highest priority after COLOR LOCK — verbatim spelling, no substitutions):",
        f'- Band name EXACTLY: "{band_name}" (not Lindesley, LINDSELY, Lindsey Lane, or abbreviations)',
        f'- Venue EXACTLY: "{venue}"',
        f'- Date EXACTLY: "{date}"',
        f'- Show time EXACTLY: "{time_label}"',
    ]
    if address:
        lines.append(f'- Full address EXACTLY: "{address}" (zip and street must match character-for-character)')
    for req in footer_required_strings(event, band=band_name):
        if req not in (venue, band_name, address):
            lines.append(f'- Must also include: "{req}"')
    lines.append(
        "Spell-check every headline before finishing — typos in band or venue names are automatic failures."
    )
    return "\n".join(lines)
