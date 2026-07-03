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


def band_asset_summary() -> dict[str, Any]:
    photos = list_band_photos()
    logo_dark = find_band_logo("Lindsey Lane Band", paper="dark")
    logo_light = find_band_logo("Lindsey Lane Band", paper="light")
    return {
        "photo_count": len(photos),
        "photos": [p.to_dict() for p in photos[:8]],
        "logo_dark": str(logo_dark) if logo_dark else None,
        "logo_light": str(logo_light) if logo_light else None,
    }


def layout_expertise_summary() -> dict[str, Any]:
    style = load_style()
    doctrine = style.get("doctrine") or {}
    return {
        "band": style.get("band", "Lindsey Lane Band"),
        "reference_models": (style.get("reference_models") or [])[:6],
        "anti_patterns": (style.get("anti_patterns") or [])[:8],
        "variations": {
            letter: (style.get("variations") or {}).get(letter, {})
            for letter in ("A", "B", "C")
        },
        "doctrine_summary": str(doctrine.get("summary") or doctrine.get("description") or "")[:500],
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
