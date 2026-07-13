"""Gig board: upcoming gigs with generation source indicators."""

from __future__ import annotations

import os
from typing import Any, Optional

from gig_calendar import get_cache_info, get_future_gigs, get_local_today
from option_slots import is_wild_option
from photo_selector import list_band_photos
from state import can_regenerate, get_gig_state, has_existing_generation, is_approved

_PICKER_MAX_DAYS = int(os.getenv("GIG_FLYERS_PICKER_DAYS", "60"))


def _generation_source_label(source: Optional[str]) -> tuple[str, str]:
    """Return (key, human label) for generation source."""
    normalized = (source or "").strip().lower()
    if normalized == "auto":
        return "background", "Background generated"
    if normalized == "interactive":
        return "interactive", "Interactive generated"
    if normalized == "agent":
        return "agent", "Agent generated"
    if normalized:
        return normalized, normalized.replace("_", " ").title()
    return "none", "No flyers yet"


def _gig_working_status(gig_id: str) -> dict[str, Any]:
    record = get_gig_state(gig_id) or {}
    status = record.get("status", "new")
    source_key, source_label = _generation_source_label(record.get("generation_source"))
    has_gen = has_existing_generation(gig_id)

    if is_approved(gig_id):
        workflow = "approved"
        workflow_label = "Approved"
    elif status == "pending_review":
        workflow = "pending"
        workflow_label = "Pending review"
    elif has_gen:
        workflow = "in_progress"
        workflow_label = "In progress"
    elif record:
        workflow = "known"
        workflow_label = "Known"
    else:
        workflow = "new"
        workflow_label = "New"

    return {
        "workflow": workflow,
        "workflow_label": workflow_label,
        "generation_source": source_key,
        "generation_source_label": source_label,
        "has_flyers": has_gen,
        "round": int(record.get("round") or 0),
        "can_generate": not is_approved(gig_id) and not has_gen,
        "can_regenerate": can_regenerate(gig_id),
        "can_revise": has_gen and not is_approved(gig_id),
        "approved_option": record.get("approved_option"),
    }


def build_agent_gig_board(*, max_days: int = _PICKER_MAX_DAYS) -> dict[str, Any]:
    today = get_local_today()
    gigs = get_future_gigs(min_days=0, max_days=max_days, background_refresh=True)
    cache = get_cache_info()
    items: list[dict[str, Any]] = []

    for event in gigs:
        record = get_gig_state(event.gig_id) or {}
        status = _gig_status(event.gig_id)
        items.append(
            {
                "gig_id": event.gig_id,
                "date": event.event_date.isoformat(),
                "short_date": event.event_date.strftime("%b %d"),
                "time": event.time_label,
                "venue": event.venue,
                "title": event.title,
                "days_out": (event.event_date - today).days,
                **status,
                "options": record.get("options") or {},
                "approved_path": record.get("approved_path"),
            }
        )

    return {
        "today": today.isoformat(),
        "max_days": max_days,
        "count": len(items),
        "gigs": items,
        "cache": {
            "fetched_at": cache.fetched_at,
            "is_stale": cache.is_stale,
            "source": cache.source,
            "age_seconds": cache.age_seconds,
        },
    }


def _gig_status(gig_id: str) -> dict[str, Any]:
    return _gig_working_status(gig_id)


def build_gig_detail(gig_id: str) -> Optional[dict[str, Any]]:
    from gig_resolve import resolve_gig_event

    try:
        event = resolve_gig_event(gig_id)
    except Exception:
        return None

    record = get_gig_state(gig_id) or {}
    status = _gig_working_status(gig_id)
    options = record.get("options") or {}

    flyer_previews: list[dict[str, Any]] = []
    for letter, rel_path in sorted(options.items()):
        flyer_previews.append(
            {
                "option": letter.upper(),
                "path": rel_path,
                "prompt": (record.get("prompts") or {}).get(letter),
                "is_wild": is_wild_option(letter.upper()),
            }
        )

    return {
        "gig_id": gig_id,
        "event": event.to_dict(),
        **status,
        "flyers": flyer_previews,
        "band_photos": [p.to_dict() for p in list_band_photos()],
        "research": record.get("research"),
        "selected_photo": record.get("selected_photo"),
        "feedback_history": record.get("feedback_history") or [],
        "round": int(record.get("round") or 0),
        "updated_at": record.get("updated_at") or "",
    }
