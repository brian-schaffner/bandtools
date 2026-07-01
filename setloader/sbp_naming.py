#!/usr/bin/env python3
"""Shared naming helpers for gig suggestions and Song Book Pro set titles."""

from __future__ import annotations

import os
import re
from typing import Optional

# Song Book Pro stores set names as plain JSON strings — no documented hard limit.
# In practice, long names truncate awkwardly in the mobile Sets list.
RECOMMENDED_SBP_SET_NAME_MAX = 40
DEFAULT_GIG_NAME_MAX = int(os.getenv("GIG_NAME_MAX_LEN", "36"))
DEFAULT_VENUE_MAX = int(os.getenv("GIG_VENUE_MAX_LEN", "22"))

_VENUE_DROP_WORDS = {
    "the", "archangel", "church", "concert", "series", "world", "famous",
    "hosting", "blues", "bar", "tavern", "gaming", "downtown", "lodge",
    "rd", "dr", "street", "main", "ky", "in", "louisville", "blvd", "ave", "road",
}
_AMERICAN_LEGION = re.compile(
    r"^American\s+Legion(?:\s+Post)?(?:\s+#?(\d+))?(?:\s.*)?$",
    re.I,
)
_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}
_EVENT_WORDS = {"picnic", "fundraiser", "jam", "benefit", "festival"}


def truncate_name(name: str, max_len: int) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    trimmed = cleaned[:max_len].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed.rstrip(" -_")


def _normalize_venue_phrases(text: str) -> str:
    """Expand known multi-word venue names before generic word dropping."""
    match = _AMERICAN_LEGION.match(text.strip())
    if match:
        post_num = match.group(1)
        if post_num:
            return f"Am Legion {post_num}"
        return "Am Legion"
    return text


def shorten_venue(venue: str, max_len: Optional[int] = None) -> str:
    """Reduce a calendar event title to a short venue/event label."""
    max_len = max_len or DEFAULT_VENUE_MAX
    text = re.sub(r"\s+", " ", (venue or "").strip())
    if not text:
        return "Gig"

    text = _normalize_venue_phrases(text)

    words = text.split()
    event_suffix = None
    if words and words[-1].lower().strip("'s") in _EVENT_WORDS:
        event_suffix = words[-1]
        words = words[:-1]

    kept: list[str] = []
    for word in words:
        token = word.lower().strip("'s").replace(".", "")
        if token in _WEEKDAYS:
            continue
        if token in _VENUE_DROP_WORDS and kept:
            continue
        kept.append(word)
        if len(kept) >= 3:
            break

    if not kept:
        kept = words[:2]

    short = " ".join(kept)
    if event_suffix and event_suffix.lower() not in short.lower():
        short = f"{short} {event_suffix}"

    # Normalize "St Raphael's" -> "St Raphael"
    short = re.sub(r"'s\b", "", short)
    return truncate_name(short, max_len)


def build_gig_suggested_name(event_date_label: str, venue: str, max_len: Optional[int] = None) -> str:
    max_len = max_len or DEFAULT_GIG_NAME_MAX
    short_venue = shorten_venue(venue)
    return truncate_name(f"{event_date_label} {short_venue}", max_len)


def shorten_pdf_set_label(label: str) -> str:
    label = (label or "Set").strip()
    match = re.match(r"^Set\s+(\d+)$", label, re.I)
    if match:
        return f"S{match.group(1)}"
    if label.lower() == "extras":
        return "X"
    return truncate_name(label, 8)


def format_sbp_set_name(
    base_name: str,
    pdf_set_label: str,
    *,
    total_pdf_sets: int,
    has_extras: bool,
    max_len: int = RECOMMENDED_SBP_SET_NAME_MAX,
) -> str:
    """Build a compact Song Book Pro set list title."""
    base = truncate_name(base_name, max_len)
    short_label = shorten_pdf_set_label(pdf_set_label)

    if pdf_set_label.lower() == "extras" or short_label == "X":
        if total_pdf_sets <= 1 and not has_extras:
            return truncate_name(f"{base} X", max_len)
        return truncate_name(f"{base} X", max_len)

    if total_pdf_sets == 1 and not has_extras:
        return base

    return truncate_name(f"{base} {short_label}", max_len)
