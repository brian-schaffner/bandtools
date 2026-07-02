#!/usr/bin/env python3
"""Generate a Hatch-style flyer by showing the model the Hank poster + photo + logo."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Reference-guided AI flyer (Hank + photo + logo)")
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini"),
        default=None,
        help="Image API (default: openai, or REFERENCE_STUDY_PROVIDER env)",
    )
    args = parser.parse_args()

    set_test_mode(True)
    event = GigEvent(
        event_date=date(2026, 7, 4),
        time_label="6:30 PM",
        title="Lindsey Lane Band at American Legion Post 15",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )

    print("Generating with reference poster + band photo + logo…")
    manifest = generate_reference_study_flyer(event, provider=args.provider)
    print(f"  Provider: {manifest['provider']}")
    print(f"  Flyer:    {manifest['path_rel']}")
    print(f"  Eval:     {manifest['evaluation_card_rel']}")
    print(f"  Input:    {manifest['input_sheet_rel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
