#!/usr/bin/env python3
"""Two-pass shell pilot: pass 1 design shell → pass 2 personalize for gig."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from design_shell_generate import generate_design_shell
from gig_calendar import GigEvent, set_test_mode
from personalize_shell_flyer import personalize_design_shell
from shell_evaluation_card import build_shell_evaluation_card
from shell_references import get_shell, pick_shell_for_research
from text_validation import resolve_venue_address


def event_for_research(research: dict) -> GigEvent:
    vt = research.get("venue_type", "regional_club")
    if vt == "festival":
        return GigEvent(
            event_date=date(2026, 8, 15),
            time_label="2:00 PM",
            title="Lindsey Lane Band at Kentucky River Festival",
            venue="Kentucky River Festival",
            suggested_name="Aug 15 Kentucky River Festival",
        )
    if vt in {"blues_bar", "regional_bar"}:
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
    parser = argparse.ArgumentParser(description="Two-pass shell design pilot")
    parser.add_argument(
        "--shell",
        default=None,
        help="Shell id (default: auto from venue_type)",
    )
    parser.add_argument(
        "--venue-type",
        default="festival",
        choices=(
            "festival",
            "member_club",
            "community_event",
            "blues_bar",
            "regional_bar",
            "theater",
            "arena",
            "regional_club",
        ),
        help="Pick shell via venue routing when --shell omitted",
    )
    parser.add_argument(
        "--pass1-only",
        action="store_true",
        help="Stop after design shell generation",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download shell reference image first",
    )
    args = parser.parse_args()

    research = {"venue_type": args.venue_type}
    shell = get_shell(args.shell) if args.shell else pick_shell_for_research(research)
    if shell is None:
        print(f"Unknown shell: {args.shell}")
        return 1

    if args.download:
        from download_shell_references import ensure_shell_image

        ensure_shell_image(shell.id)

    if not shell.has_image():
        print(f"Warning: no reference image for {shell.id} — pass 1 may be weaker")

    set_test_mode(True)
    event = event_for_research(research)
    date_str = event.event_date.strftime("%A, %B %d, %Y")

    print(f"Shell: {shell.id} ({shell.title})")
    print("Pass 1: generating design shell…")
    pass1 = generate_design_shell(shell.id)
    shell_path = ROOT / pass1["shell_rel"]
    print(f"  Shell: {pass1['shell_rel']}")

    if args.pass1_only:
        return 0

    print("Pass 2: personalizing for gig…")
    pass2 = personalize_design_shell(
        event,
        shell.id,
        shell_path,
        address=resolve_venue_address(event),
    )
    print(f"  Flyer: {pass2['personalized_rel']}")

    eval_path = ROOT / "output" / "shell_design" / f"{event.gig_id}_{shell.id}_eval.png"
    ref_path = shell.image_path()
    build_shell_evaluation_card(
        reference_path=ref_path if ref_path.is_file() else shell_path,
        shell_path=shell_path,
        personalized_path=ROOT / pass2["personalized_rel"],
        output_path=eval_path,
        shell_title=shell.title,
        shell_id=shell.id,
        venue=event.venue,
        date=date_str,
        extra_lines=[
            f"Design family: {shell.design_family}",
            f"Provider: openai",
        ],
    )
    print(f"  Eval:  {eval_path.relative_to(ROOT)}")

    summary = {
        "shell_id": shell.id,
        "pass1": pass1,
        "pass2": pass2,
        "evaluation_rel": str(eval_path.relative_to(ROOT)),
    }
    summary_path = ROOT / "output" / "shell_design" / f"{event.gig_id}_{shell.id}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
