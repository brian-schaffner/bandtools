"""Tier archetypes from style.yaml variations + venue research."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from gig_calendar import GigEvent
from gig_research import classify_venue

STYLE_PATH = Path(__file__).resolve().parents[1] / "style.yaml"

# Venue-aware ink palettes (muted, photocopy-safe)
VENUE_PALETTES: dict[str, dict[str, str]] = {
    "blues_bar": {
        "paper": "#F5F0E6",
        "ink": "#111111",
        "accent": "#8B1A1A",
        "muted": "#1e3a5f",
    },
    "country_bar": {
        "paper": "#F2E8D8",
        "ink": "#1A1208",
        "accent": "#8B4513",
        "muted": "#5C4030",
    },
    "member_club": {
        "paper": "#F5F0E6",
        "ink": "#000000",
        "accent": "#000000",
        "muted": "#333333",
    },
    "community_event": {
        "paper": "#F5F0E6",
        "ink": "#000000",
        "accent": "#000000",
        "muted": "#444444",
    },
    "regional_bar": {
        "paper": "#F3EDE3",
        "ink": "#111111",
        "accent": "#6B2D2D",
        "muted": "#3D3D3D",
    },
}

DEFAULT_PALETTE = {
    "paper": "#F5F0E6",
    "ink": "#111111",
    "accent": "#8B0000",
    "muted": "#333333",
}

# Medium-tier accent device per venue type (exactly one)
VENUE_ACCENT: dict[str, str] = {
    "blues_bar": "starburst",
    "regional_bar": "starburst",
    "country_bar": "stamp",
    "member_club": "underline",
    "community_event": "underline",
    "festival": "underline",
    "casino_venue": "starburst",
    "winery": "stamp",
}

# Medium-tier photo column offset
VENUE_PHOTO_SIDE: dict[str, str] = {
    "blues_bar": "right",
    "country_bar": "left",
    "member_club": "left",
    "regional_bar": "right",
}


@dataclass
class TierArchetype:
    """Resolved creative tier + venue context for fixed templates."""

    tier: str
    variation: dict[str, Any]
    venue_type: str
    design_language: str
    paper_color: str = "#F5F0E6"
    ink_primary: str = "#111111"
    ink_accent: str = "#8B0000"
    ink_muted: str = "#333333"
    accent_element: str = "none"  # starburst | underline | stamp | none
    photo_side: str = "bottom"  # bottom | left | right
    photocopy_strength: float = 0.1
    age_strength: float = 0.0
    grain_strength: float = 0.02
    layout_notes: list[str] = field(default_factory=list)


def load_style_variations() -> list[dict[str, Any]]:
    """Load variations[] from style.yaml."""
    data = yaml.safe_load(STYLE_PATH.read_text(encoding="utf-8"))
    return list(data.get("variations") or [])


def load_tier_archetype(
    tier: str,
    event: Optional[GigEvent] = None,
    research: Optional[dict[str, Any]] = None,
) -> TierArchetype:
    """Resolve style.yaml variation + venue_type into template parameters."""
    variations = load_style_variations()
    by_tier = {str(v.get("tier", "")): v for v in variations}
    variation = by_tier.get(tier, by_tier.get("medium", {}))

    if research:
        venue_type = str(research.get("venue_type", "regional_club"))
        design_language = str(research.get("design_language", "regional_promoter_handbill"))
    elif event is not None:
        venue_type, design_language, _, _ = classify_venue(event.venue, event.title or "")
    else:
        venue_type = "regional_club"
        design_language = "regional_promoter_handbill"

    palette = VENUE_PALETTES.get(venue_type, DEFAULT_PALETTE)
    layout_notes = list(variation.get("layout_structure") or [])

    if tier == "conservative":
        return TierArchetype(
            tier=tier,
            variation=variation,
            venue_type=venue_type,
            design_language=design_language,
            paper_color="#F5F0E6",
            ink_primary="#111111",
            ink_accent="#8B1A1A" if venue_type == "blues_bar" else "#111111",
            ink_muted="#1a1a1a",
            accent_element="none",
            photo_side="bottom",
            photocopy_strength=0.08,
            age_strength=0.0,
            grain_strength=0.012,
            layout_notes=layout_notes,
        )

    if tier == "medium":
        return TierArchetype(
            tier=tier,
            variation=variation,
            venue_type=venue_type,
            design_language=design_language,
            paper_color=palette["paper"],
            ink_primary=palette["ink"],
            ink_accent=palette["accent"],
            ink_muted=palette["muted"],
            accent_element=VENUE_ACCENT.get(venue_type, "starburst"),
            photo_side=VENUE_PHOTO_SIDE.get(venue_type, "right"),
            photocopy_strength=0.08,
            age_strength=0.0,
            grain_strength=0.015,
            layout_notes=layout_notes,
        )

    # creative
    creative_paper = {
        "blues_bar": "#E8D4B8",
        "country_bar": "#E6D0B0",
    }.get(venue_type, "#E8E0D0")

    return TierArchetype(
        tier=tier,
        variation=variation,
        venue_type=venue_type,
        design_language=design_language,
        paper_color=creative_paper,
        ink_primary=palette["ink"],
        ink_accent=palette["accent"],
        ink_muted=palette["muted"],
        accent_element="collage",  # tape + ticket stub, not medium accent
        photo_side="center_left",
        photocopy_strength=0.08,
        age_strength=0.0,
        grain_strength=0.015,
        layout_notes=layout_notes,
    )
