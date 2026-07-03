"""Agent context: gigs, band assets, design expertise, and research."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from flyer_generator import load_style
from gig_calendar import GigEvent
from gig_research import research_gig
from photo_selector import list_band_photos, select_band_photo
from structured_layout.band_mark import find_band_logo

from flyer_agent.catalog import load_design_catalog
from flyer_agent.research_worker import load_design_research

ROOT = Path(__file__).resolve().parents[1]


def _style_list(value: Any, *, limit: int | None = None) -> list[str]:
    """Normalize style.yaml fields that may be list, dict, or string."""
    items: list[str] = []
    if value is None:
        pass
    elif isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, dict):
        for key in ("primary", "secondary", "avoid", "reject_if_present", "summary", "description"):
            nested = value.get(key)
            if isinstance(nested, list):
                items.extend(str(v).strip() for v in nested if str(v).strip())
            elif isinstance(nested, str) and nested.strip():
                items.append(nested.strip())
        if not items:
            items = [f"{k}: {v}" for k, v in value.items() if v][: limit or 8]
    elif isinstance(value, str) and value.strip():
        items = [value.strip()]
    else:
        items = [str(value)]
    return items[:limit] if limit is not None else items


def _doctrine_summary(style: dict[str, Any]) -> str:
    doctrine = style.get("doctrine")
    if isinstance(doctrine, str):
        return doctrine.strip()[:500]
    if isinstance(doctrine, dict):
        return str(doctrine.get("summary") or doctrine.get("description") or "")[:500]
    photo = style.get("photo_treatment") or {}
    if isinstance(photo, dict):
        raw = photo.get("doctrine")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()[:500]
    return ""


def _anti_patterns(style: dict[str, Any], *, limit: int = 8) -> list[str]:
    items = _style_list(style.get("anti_patterns"), limit=limit)
    if items:
        return items
    ref = style.get("reference_models") or {}
    if isinstance(ref, dict):
        items = _style_list(ref.get("avoid"), limit=limit)
    if items:
        return items
    anti_ai = style.get("anti_ai_rules") or {}
    if isinstance(anti_ai, dict):
        for section in anti_ai.values():
            if isinstance(section, dict):
                items.extend(_style_list(section.get("reject_if_present")))
            if len(items) >= limit:
                break
    return items[:limit]


def band_asset_summary() -> dict[str, Any]:
    photos = list_band_photos()
    # find_band_logo paper= expects RGB tuple (luminance), not a label string.
    logo_dark = find_band_logo("Lindsey Lane Band", paper=(245, 240, 230))
    logo_light = find_band_logo("Lindsey Lane Band", paper=(30, 30, 30))
    return {
        "photo_count": len(photos),
        "photos": [p.to_dict() for p in photos[:8]],
        "logo_dark": str(logo_dark) if logo_dark else None,
        "logo_light": str(logo_light) if logo_light else None,
    }


def _variation_map(style: dict[str, Any]) -> dict[str, Any]:
    raw = style.get("variations") or {}
    if isinstance(raw, dict):
        return {letter: raw.get(letter, {}) for letter in ("A", "B", "C")}
    if isinstance(raw, list):
        letters = ("A", "B", "C")
        mapped: dict[str, Any] = {}
        for idx, entry in enumerate(raw[:3]):
            if isinstance(entry, dict):
                mapped[letters[idx]] = {
                    "id": entry.get("id"),
                    "label": entry.get("label"),
                    "tier": entry.get("tier"),
                    "description": str(entry.get("description") or "")[:200],
                }
        return mapped
    return {}


def layout_expertise_summary() -> dict[str, Any]:
    style = load_style()
    ref = style.get("reference_models") or {}
    reference_items = _style_list(ref.get("primary") if isinstance(ref, dict) else ref, limit=6)
    if not reference_items:
        reference_items = _style_list(ref, limit=6)
    return {
        "band": style.get("band", "Lindsey Lane Band"),
        "reference_models": reference_items,
        "anti_patterns": _anti_patterns(style, limit=8),
        "variations": _variation_map(style),
        "doctrine_summary": _doctrine_summary(style),
    }


def gig_agent_context(event: GigEvent) -> dict[str, Any]:
    research = research_gig(event)
    selected_photo = select_band_photo(event, research)
    return {
        "gig_id": event.gig_id,
        "event": event.to_dict(),
        "research": research,
        "selected_photo": selected_photo,
        "expertise": layout_expertise_summary(),
        "catalog_highlights": load_design_catalog(limit=6),
        "design_research": load_design_research(limit=5),
    }


def agent_system_context() -> dict[str, Any]:
    """Global knowledge the agent carries into every interaction."""
    return {
        "role": "concert_flyer_design_agent",
        "expertise": layout_expertise_summary(),
        "band_assets": band_asset_summary(),
        "catalog_count": len(load_design_catalog(limit=1000)),
        "design_research_count": len(load_design_research(limit=1000)),
        "capabilities": [
            "Select upcoming gigs from the live calendar",
            "Generate A/B/C flyer options using structured layout + image providers",
            "Revise existing options with natural-language feedback",
            "Regenerate fresh rounds from scratch",
            "Apply venue-aware research and band photo selection",
            "Reference a curated catalog of strong poster designs",
        ],
    }
