"""Text validation for flyer footer, venue address, and gig-type typography rules."""

from __future__ import annotations

import re
from typing import Optional, Any

from gig_calendar import GigEvent

# Shared layout constant — keep in sync with reference_compose.SAFE_MARGIN_PX
SAFE_MARGIN_PX = 48

# Known venue addresses (pattern → full mailing line for footer)
VENUE_ADDRESS_RULES: list[tuple[str, str]] = [
    (
        r"stevie\s+ray",
        "230 East Main Street, Louisville, KY 40202",
    ),
]

HOUSE_GIG_PATTERNS: tuple[str, ...] = (
    r"tuesday\s+jam",
    r"open\s+mic",
    r"hosting",
    r"jam\s+session",
    r"weekly\s+jam",
)

ADDRESS_ZIP_RE = re.compile(r"\b\d{5}\b")
ADDRESS_STREET_RE = re.compile(
    r"\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|main)\b",
    re.IGNORECASE,
)
MONTH_NAME_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b20\d{2}\b")

# Halftone on structured band photos destroys face detail — always reject when enabled.
def halftone_unsafe_for_band_photo(photo_frame: Any) -> bool:
    """True when halftone is enabled on a band photo frame."""
    return bool(getattr(photo_frame, "halftone", False))


def resolve_venue_address(event: GigEvent) -> str:
    """Resolve a full mailing address for the gig venue."""
    haystack = f"{event.venue} {event.title}".lower()
    for pattern, address in VENUE_ADDRESS_RULES:
        if re.search(pattern, haystack, re.IGNORECASE):
            return address
    return ""


def is_house_series_gig(event: GigEvent) -> bool:
    """True when the band is a featured act at a recurring house show (e.g. Tuesday Jam)."""
    haystack = f"{event.title} {event.venue}".lower()
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in HOUSE_GIG_PATTERNS)


def featured_act_line(band: str) -> str:
    return f"Featuring {band}"


def halftone_unsafe_for_band_photo(photo_frame: object) -> bool:
    """True when halftone would destroy band face detail in structured layout mode."""
    return bool(getattr(photo_frame, "halftone", False))


def footer_required_strings(event: GigEvent, *, band: str) -> list[str]:
    """Strings that must appear on the flyer (any zone — each fact once)."""
    required: list[str] = []
    address = resolve_venue_address(event)
    if address:
        required.append(address)
    if is_house_series_gig(event):
        required.append(event.venue)
        required.append(featured_act_line(band))
    else:
        required.extend([event.venue, band])
    return required


def _text_has_venue(text: str, event: GigEvent) -> bool:
    lower = text.lower()
    venue_words = [w for w in re.split(r"\W+", event.venue.lower()) if len(w) > 3]
    if not venue_words:
        venue_words = [event.venue.lower()]
    return any(word in lower for word in venue_words)


def _text_has_address(text: str, event: GigEvent) -> bool:
    address = resolve_venue_address(event)
    if not address:
        return True
    lower = text.lower()
    if address.lower() in lower:
        return True
    if ADDRESS_ZIP_RE.search(text):
        zip_match = ADDRESS_ZIP_RE.search(address)
        if zip_match and zip_match.group(0) in text:
            return True
    if ADDRESS_STREET_RE.search(text):
        street = ADDRESS_STREET_RE.search(address)
        if street and street.group(0).lower() in lower:
            return True
    return False


def validate_required_footer_text(text: str, event: GigEvent, *, band: str) -> list[str]:
    """Return serious issues when mandatory footer content is missing from text."""
    issues: list[str] = []
    if not _text_has_venue(text, event):
        issues.append(f"Missing venue name in footer: {event.venue}")
    if not _text_has_address(text, event):
        address = resolve_venue_address(event)
        if address:
            issues.append(f"Missing venue address in footer: {address}")
    if is_house_series_gig(event):
        feat = featured_act_line(band).lower()
        band_lower = band.lower()
        lower = text.lower()
        band_prominent = band_lower in lower and (
            feat in lower or text.lower().count(band_lower) >= 1
        )
        if not band_prominent:
            issues.append(
                f"Featured act not prominent for house show — use '{featured_act_line(band)}' "
                f"or make '{band}' as large as the series title"
            )
    return issues


def typography_hierarchy_prompt_lines(event: GigEvent, *, band: str) -> list[str]:
    """Prompt lines for headliner vs house-series typography hierarchy."""
    if is_house_series_gig(event):
        return [
            "TYPOGRAPHY HIERARCHY — HOUSE / JAM SHOW (each fact appears ONCE):",
            f"- Header: series title — {event.venue}",
            f"- Sub-header: '{featured_act_line(band)}' (once only — not repeated in body or footer)",
            "- Body: date and time (highly visible below photo)",
            "- Footer: full street address only (venue already in header — do NOT repeat venue or band in footer)",
            "",
        ]
    return [
        "TYPOGRAPHY HIERARCHY — HEADLINER GIG (each fact appears ONCE):",
        f"- Header: band name ({band}) largest or equal to venue",
        f"- Sub: venue ({event.venue})",
        "- Body: date and time",
        "- Footer: address (+ venue/band only if not already in header)",
        "",
    ]


def footer_prompt_lines(event: GigEvent, *, band: str) -> list[str]:
    """Prompt lines requiring the footer block."""
    address = resolve_venue_address(event)
    lines = [
        "MANDATORY FOOTER BLOCK (bottom margin — always render, never omit):",
    ]
    if is_house_series_gig(event):
        if address:
            lines.append(f"- Address only: {address}")
        lines.append(
            "- Do NOT repeat series title, venue name, or featured-act line in footer "
            "(those belong in the header)"
        )
    else:
        lines.append(f"- Venue: {event.venue}")
        if address:
            lines.append(f"- Full address: {address}")
        lines.append(f"- Band: {band}")
    lines.extend(
        [
            "- Footer must be readable text — NOT a blank grey bar, brush stroke, or decorative placeholder",
            f"- Keep all footer text inside safe margins ({SAFE_MARGIN_PX}px from bottom and sides)",
            "",
        ]
    )
    return lines
