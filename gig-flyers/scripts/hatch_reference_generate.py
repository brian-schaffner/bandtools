#!/usr/bin/env python3
"""Generate a flyer by showing the model a real reference poster + band photo + logo."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from gig_calendar import GigEvent, set_test_mode
from reference_study_generate import generate_reference_study_flyer

STUDY_CHOICES = (
    "hatch",
    "hatch_hank_williams_1953",
    "altamont",
    "altamont_free_concert_1969",
    "woodstock",
    "woodstock_festival_1969",
)

STUDY_ALIASES = {
    "hatch": "hatch_hank_williams_1953",
    "altamont": "altamont_free_concert_1969",
    "woodstock": "woodstock_festival_1969",
}


def resolve_study(raw: str) -> str:
    return STUDY_ALIASES.get(raw, raw)


def event_for_study(study_id: str) -> GigEvent:
    if study_id == "woodstock_festival_1969":
        return GigEvent(
            event_date=date(2026, 8, 15),
            time_label="2:00 PM",
            title="Lindsey Lane Band at Kentucky River Festival",
            venue="Kentucky River Festival",
            suggested_name="Aug 15 Kentucky River Festival",
        )
    if study_id == "altamont_free_concert_1969":
        return GigEvent(
            event_date=date(2026, 6, 21),
            time_label="9:00 PM",
            title="Lindsey Lane Band at Stevie Ray's Blues Bar",
            venue="Stevie Ray's Blues Bar",
            suggested_name="Jun 21 Stevie Ray's Blues Bar",
        )
    return GigEvent(
        event_date=date(2026, 7, 4),
        time_label="6:30 PM",
        title="Lindsey Lane Band at American Legion Post 15",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reference-guided AI flyer (style poster + band photo + logo)"
    )
    parser.add_argument(
        "--study",
        choices=STUDY_CHOICES,
        default="hatch",
        help="Visual study to match (default: hatch letterpress)",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini"),
        default=None,
        help="Image API (default: openai, or REFERENCE_STUDY_PROVIDER env)",
    )
    args = parser.parse_args()

    study_id = resolve_study(args.study)
    set_test_mode(True)
    event = event_for_study(study_id)

    print(f"Generating with {study_id} reference + band photo + logo…")
    manifest = generate_reference_study_flyer(
        event,
        study_id=study_id,
        provider=args.provider,
    )
    print(f"  Study:    {manifest['study_id']}")
    print(f"  Provider: {manifest['provider']}")
    print(f"  Flyer:    {manifest['path_rel']}")
    print(f"  Eval:     {manifest['evaluation_card_rel']}")
    print(f"  Input:    {manifest['input_sheet_rel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
