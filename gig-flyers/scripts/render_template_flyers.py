#!/usr/bin/env python3
"""Re-render A/B/C from fixed templates without API calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from gig_calendar import GigEvent, find_gig_by_id  # noqa: E402
from gig_research import research_gig  # noqa: E402
from photo_selector import select_band_photo  # noqa: E402
from structured_layout.fixed_templates import layout_for_option  # noqa: E402
from structured_layout.structured_renderer import render_flyer  # noqa: E402
from structured_layout.validation import validate_structured_flyer  # noqa: E402
from text_validation import resolve_venue_address  # noqa: E402


def _resolve_event(gig_id: str) -> GigEvent:
    event = find_gig_by_id(gig_id)
    if event:
        return event
    if gig_id == "2026-06-30_stevie-ray-s-tuesday-jam":
        return GigEvent(
            event_date=date(2026, 6, 30),
            time_label="7:30 pm",
            title="Hosting Stevie Ray's World Famous Tuesday Jam",
            venue="Stevie Ray's Tuesday Jam",
            suggested_name="Jun 30 Stevie Ray's Tuesday Jam",
        )
    raise SystemExit(f"Unknown gig: {gig_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render template flyers A/B/C")
    parser.add_argument("--gig", required=True, help="Gig id slug")
    parser.add_argument("--round", default="template_v4", help="Output round suffix")
    parser.add_argument("--template-version", default="v4", help="Manifest template version stamp")
    args = parser.parse_args()

    event = _resolve_event(args.gig)
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    research = research_gig(event)
    out_dir = ROOT / "output" / args.gig
    out_dir.mkdir(parents=True, exist_ok=True)

    photo_meta = select_band_photo(event, research={})
    if not photo_meta:
        photo_path = ROOT / "bandphotos/679394308_1366641221939459_1410337987474015419_n.jpg"
    else:
        photo_path = ROOT / "bandphotos" / photo_meta["filename"]
    if not photo_path.is_file():
        raise SystemExit(f"Band photo not found: {photo_path}")

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    address = resolve_venue_address(event)
    tiers = {"A": "conservative", "B": "medium", "C": "creative"}
    results: list[str] = []

    for letter in ("A", "B", "C"):
        layout = layout_for_option(
            letter,
            event.venue,
            band,
            date_str,
            time_str,
            address=address,
            event=event,
            research=research,
        )
        layout_path = out_dir / f"option-{letter}_{args.round}_layout.json"
        layout_path.write_text(layout.to_json(indent=2), encoding="utf-8")

        png_path = out_dir / f"option-{letter}_{args.round}.png"
        tier = tiers[letter]
        render_flyer(layout, photo_path, png_path, option=letter, tier=tier)

        validation = validate_structured_flyer(png_path, layout, event, band=band)
        status = "PASS" if validation.passed else f"FAIL: {validation.issues}"
        results.append(f"  {letter}: {png_path.relative_to(ROOT)} — {status}")
        print(results[-1])

    manifest = {
        "gig_id": args.gig,
        "template_version": args.template_version,
        "generation_mode": "structured_fixed",
        "options": {
            letter: str((out_dir / f"option-{letter}_{args.round}.png").relative_to(ROOT))
            for letter in ("A", "B", "C")
        },
    }
    manifest_path = out_dir / f"manifest_{args.round}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nManifest: {manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
