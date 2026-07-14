#!/usr/bin/env python3
"""Generate side-by-side demos: visual-study layouts vs generic handbill."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent
from structured_layout.fixed_templates import create_handbill_layout, _make_rng
from structured_layout.structured_renderer import render_flyer
from structured_layout.tier_archetypes import load_tier_archetype
from visual_guided_flyer import build_visual_brief

DEMO_DIR = ROOT / "output" / "visual_study_demos"
PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"


def _render(label: str, layout, out_name: str) -> Path:
    out = DEMO_DIR / out_name
    render_flyer(layout, PHOTO, out, tier="medium")
    print(f"  {label}: {out} ({out.stat().st_size // 1024} KB)")
    return out


def main() -> None:
    if not PHOTO.is_file():
        print(f"Missing band photo: {PHOTO}")
        sys.exit(1)

    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    legion = GigEvent(
        event_date=__import__("datetime").date(2026, 7, 4),
        time_label="6:30 PM",
        title="Lindsey Lane Band at American Legion Post 15",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )
    blues = GigEvent(
        event_date=__import__("datetime").date(2026, 7, 14),
        time_label="8:00 PM",
        title="Lindsey Lane Band at Stevie Ray's Blues Bar",
        venue="Stevie Ray's Blues Bar",
        suggested_name="Jul 14 Stevie Ray's Blues Bar",
    )

    legion_research = {"venue_type": "member_club", "design_language": "legion_community"}
    blues_research = {"venue_type": "blues_bar", "design_language": "blues_club"}

    legion_brief, legion_study = build_visual_brief(legion, legion_research)
    blues_brief, blues_study = build_visual_brief(blues, blues_research)

    print("Visual studies applied:")
    print(f"  Legion → {legion_study.title} ({legion_brief.medium_variant})")
    print(f"  Blues bar → {blues_study.title} ({blues_brief.medium_variant})")
    print()

    legion_arch = load_tier_archetype("medium", event=legion, research=legion_research)
    blues_arch = load_tier_archetype("medium", event=blues, research=blues_research)
    date_legion = legion.event_date.strftime("%A, %B %d, %Y")
    date_blues = blues.event_date.strftime("%A, %B %d, %Y")

    print("American Legion — Hatch stack vs generic broadside:")
    hatch = create_handbill_layout(
        legion.venue,
        "Lindsey Lane Band",
        date_legion,
        legion.time_label,
        event=legion,
        archetype=legion_arch,
        rng=_make_rng(legion.gig_id, "B", 1),
        medium_variant="hatch_stack",
    )
    broadside = create_handbill_layout(
        legion.venue,
        "Lindsey Lane Band",
        date_legion,
        legion.time_label,
        event=legion,
        archetype=legion_arch,
        rng=_make_rng(legion.gig_id, "B", 1),
        medium_variant="broadside",
    )
    _render("Hatch stack (visual study)", hatch, "legion_hatch_stack.png")
    _render("Broadside (generic)", broadside, "legion_broadside.png")

    print()
    print("Blues bar — Altamont sidebar vs generic paste-up:")
    altamont = create_handbill_layout(
        blues.venue,
        "Lindsey Lane Band",
        date_blues,
        blues.time_label,
        event=blues,
        archetype=blues_arch,
        rng=_make_rng(blues.gig_id, "B", 1),
        medium_variant="altamont_sidebar",
    )
    paste_up = create_handbill_layout(
        blues.venue,
        "Lindsey Lane Band",
        date_blues,
        blues.time_label,
        event=blues,
        archetype=blues_arch,
        rng=_make_rng(blues.gig_id, "B", 1),
        medium_variant="paste_up",
    )
    _render("Altamont sidebar (visual study)", altamont, "blues_altamont_sidebar.png")
    _render("Paste-up (generic)", paste_up, "blues_paste_up.png")


if __name__ == "__main__":
    main()
