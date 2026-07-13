#!/usr/bin/env python3
"""Research gig context: venue type, demographics, holidays, design language."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any, Callable, Optional

from gig_calendar import GigEvent
from progress_helper import ProgressCallback, emit_progress

VENUE_RULES: list[tuple[str, str, str, list[str], list[str]]] = [
  # pattern, venue_type, design_language, demographics, venue_bias
    (r"\b(festival|fair|expo|rodeo)\b", "festival", "county_fair_poster", ["families", "mixed_ages", "outdoor_crowd"], ["bold_dates", "casual_energy"]),
    (r"\b(vfw|american legion|legion post|elks|eagles|fraternal)\b", "member_club", "legion_community", ["veterans", "50_plus", "locals"], ["venue_first", "utilitarian_type"]),
    (r"\b(stevie ray|blues bar|blues)\b", "blues_bar", "blues_club_handbill", ["blues_fans", "30_to_60", "weeknight_crowd"], ["moody_but_readable", "no_neon_cliches"]),
    (r"\b(pbr|country bar|honky tonk|tavern)\b", "country_bar", "country_bar_poster", ["country_fans", "25_to_55", "weekend_crowd"], ["boots_ok", "no_arena_poster"]),
    (r"\b(casino|gaming|racetrack|bally|derby city)\b", "casino_venue", "casino_promo", ["adults_21_plus", "tourist_and_local"], ["venue_branding_room", "nightlife"]),
    (r"\b(winery|vineyard|huber)\b", "winery", "winery_event", ["adults_35_plus", "suburban_couples"], ["refined_but_not_fancy", "afternoon_or_evening"]),
    (r"\b(legion|community|church|hall)\b", "community_event", "community_bulletin", ["locals", "all_ages", "community_members"], ["informational", "low_decoration"]),
    (r"\b(bar|grill|tavern|pub|saloon|shop)\b", "regional_bar", "club_handbill", ["bar_regulars", "25_to_55"], ["photo_forward", "condensed_type"]),
]

DEFAULT_VENUE = (
    "regional_club",
    "regional_promoter_handbill",
    ["cover_band_audience", "30_to_60", "locals"],
    ["utilitarian", "readable_first"],
)

US_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "New Year's Day",
    (2, 14): "Valentine's Day",
    (3, 17): "St. Patrick's Day",
    (7, 4): "Independence Day",
    (10, 31): "Halloween",
    (11, 11): "Veterans Day",
    (12, 24): "Christmas Eve",
    (12, 25): "Christmas Day",
    (12, 31): "New Year's Eve",
}

MEMORIAL_DAY = "Memorial Day weekend"
LABOR_DAY = "Labor Day weekend"
THANKSGIVING = "Thanksgiving weekend"


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday=0 .. Sunday=6"""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last = next_month.toordinal() - 1
    d = date.fromordinal(last)
    while d.weekday() != weekday:
        d = date.fromordinal(d.toordinal() - 1)
    return d


def detect_holiday_context(event_date: date) -> dict[str, Any]:
    key = (event_date.month, event_date.day)
    label = US_HOLIDAYS.get(key)
    notes: list[str] = []

    year = event_date.year
    memorial = _last_weekday(year, 5, 0)  # last Monday in May
    labor = _nth_weekday(year, 9, 0, 1)  # first Monday in September
    thanksgiving = _nth_weekday(year, 11, 3, 4)  # fourth Thursday in November

    for anchor, name in (
        (memorial, MEMORIAL_DAY),
        (labor, LABOR_DAY),
        (thanksgiving, THANKSGIVING),
    ):
        if abs((event_date - anchor).days) <= 3:
            label = label or name
            notes.append(f"Near {name} ({anchor.isoformat()})")

    if (event_date.month, event_date.day) == (7, 3) or (event_date.month, event_date.day) == (7, 5):
        label = label or "Independence Day weekend"
        notes.append("July 4th holiday window")

    return {
        "holiday": label,
        "notes": notes,
        "is_holiday_weekend": bool(label),
    }


def classify_venue(venue: str, title: str = "") -> tuple[str, str, list[str], list[str]]:
    text = f"{venue} {title}".lower()
    for pattern, venue_type, design_language, demographics, bias in VENUE_RULES:
        if re.search(pattern, text, re.I):
            return venue_type, design_language, demographics, bias
    return DEFAULT_VENUE


def _design_language_notes(design_language: str, venue_type: str) -> list[str]:
    notes = {
        "blues_club_handbill": [
            "Lean blues-club photocopy aesthetic — dark accents OK but keep type readable.",
            "Feels like a Louisville blues bar handbill, not a psychedelic poster.",
            "Venue name should feel like a real local blues room.",
        ],
        "country_bar_poster": [
            "Country-bar bulletin energy — boots-and-beer crowd, not Nashville arena art.",
            "Wood, ink, and paper tones — avoid uniform mustard/gold AI yellow wash.",
        ],
        "legion_community": [
            "American Legion / VFW community notice — venue-first, low decoration.",
            "Feels posted at a post hall, not designed by an agency.",
        ],
        "county_fair_poster": [
            "County fair / outdoor event bulletin — practical, date-forward.",
            "Families and mixed ages; keep information obvious.",
        ],
        "club_handbill": [
            "Regional bar handbill — one photo, bold condensed type, fast layout.",
        ],
        "regional_promoter_handbill": [
            "Generic regional promoter photocopy — informational, slightly awkward OK.",
        ],
        "casino_promo": [
            "Casino / nightlife promo — adult crowd, venue branding has room to breathe.",
        ],
        "winery_event": [
            "Winery afternoon/evening event — relaxed, adult, not EDM poster.",
        ],
        "community_bulletin": [
            "Community bulletin board — utilitarian, venue dominates.",
        ],
    }
    return notes.get(design_language, notes["regional_promoter_handbill"])


def research_gig(
    event: GigEvent,
    use_llm: Optional[bool] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> dict[str, Any]:
    emit_progress(
        on_progress,
        step="research",
        substep="venue",
        message=f"Analyzing venue: {event.venue}…",
        progress=5,
    )
    venue_type, design_language, demographics, venue_bias = classify_venue(event.venue, event.title)
    emit_progress(
        on_progress,
        step="research",
        substep="venue_detected",
        message=f"Detected: {venue_type}",
        detail=design_language,
        progress=7,
    )

    short_date = event.event_date.strftime("%b %d")
    emit_progress(
        on_progress,
        step="research",
        substep="date",
        message=f"Checking date: {short_date}…",
        progress=9,
    )
    holiday = detect_holiday_context(event.event_date)
    holiday_label = holiday.get("holiday") or "none"
    emit_progress(
        on_progress,
        step="research",
        substep="holiday",
        message=f"Holiday check: {holiday_label}",
        progress=10,
    )
    emit_progress(
        on_progress,
        step="research",
        substep="design_language",
        message=f"Design language: {design_language}",
        progress=12,
    )

    result: dict[str, Any] = {
        "venue_type": venue_type,
        "demographics": demographics,
        "date_context": holiday,
        "design_language": design_language,
        "design_notes": _design_language_notes(design_language, venue_type),
        "venue_bias": venue_bias,
        "venue": event.venue,
        "title": event.title,
        "source": "heuristics",
    }

    if holiday.get("holiday"):
        result["design_notes"] = list(result["design_notes"]) + [
            f"Date falls near {holiday['holiday']} — subtle seasonal context OK, not cheesy clipart."
        ]

    if use_llm is None:
        use_llm = os.getenv("GIG_RESEARCH_USE_LLM", "").strip().lower() in {"1", "true", "yes"}
    if use_llm and os.getenv("OPENAI_API_KEY"):
        emit_progress(
            on_progress,
            step="research",
            substep="llm",
            message="Enriching research with LLM…",
            progress=13,
        )
        enriched = _maybe_enrich_with_llm(event, result)
        if enriched:
            result.update(enriched)
            result["source"] = "heuristics+llm"
            emit_progress(
                on_progress,
                step="research",
                substep="llm_done",
                message="Research enrichment complete",
                progress=14,
            )

    emit_progress(
        on_progress,
        step="research",
        substep="complete",
        message="Gig research complete",
        progress=15,
    )
    return result


def _maybe_enrich_with_llm(event: GigEvent, base: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    model = os.getenv("GIG_RESEARCH_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    prompt = (
        "Return JSON only with keys design_notes (array of 2 short strings) and demographics "
        f"(array of 3 short tags) for a cover band gig:\n"
        f"Venue: {event.venue}\nTitle: {event.title}\nDate: {event.event_date.isoformat()}\n"
        f"Venue type: {base['venue_type']}\nDesign language: {base['design_language']}\n"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return {
            "design_notes": list(base.get("design_notes", [])) + _as_str_list(data.get("design_notes")),
            "demographics": _as_str_list(data.get("demographics")) or base.get("demographics"),
        }
    except Exception:
        return None


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def research_prompt_block(research: dict[str, Any]) -> list[str]:
    holiday = research.get("date_context", {})
    holiday_label = holiday.get("holiday") or "none"
    return [
        "GIG CONTEXT RESEARCH (customize design for this specific show):",
        f"- Venue type: {research.get('venue_type', 'unknown')}",
        f"- Probable audience: {', '.join(research.get('demographics', []))}",
        f"- Date / holiday context: {holiday_label}",
        f"- Design language: {research.get('design_language', 'regional_promoter_handbill')}",
        "- Venue-specific design bias:",
        *[f"  • {note}" for note in research.get("design_notes", [])[:5]],
        "- Venue bias for layout:",
        *[f"  • {b}" for b in research.get("venue_bias", [])[:4]],
        "",
    ]
