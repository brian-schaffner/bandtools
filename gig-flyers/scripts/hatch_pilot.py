"""Run Hatch pilot: structured constraints vs AI prediction in parallel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from evaluation_card import build_evaluation_card
from gig_calendar import GigEvent, set_test_mode
from output_paths import get_output_dir, output_relative
from structured_layout.fixed_templates import _make_rng, create_handbill_layout
from structured_layout.structured_renderer import render_flyer
from structured_layout.tier_archetypes import load_tier_archetype
from visual_constraints import HATCH_CONSTRAINTS, validate_layout_constraints
from visual_predict_flyer import predict_visual_flyer
from visual_studies import get_study

DEFAULT_GIG = "2026-07-04_american-legion-post-15"
PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"
PILOT_DIR = get_output_dir() / "hatch_pilot"


def _legion_event() -> GigEvent:
    from datetime import date

    return GigEvent(
        event_date=date(2026, 7, 4),
        time_label="6:30 PM",
        title="Lindsey Lane Band at American Legion Post 15",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )


def run_structured_path(
    event: GigEvent,
    *,
    out_dir: Path,
    round_num: int = 1,
) -> dict:
    """Constraint-driven hatch_stack render + checklist."""
    research = {"venue_type": "member_club", "design_language": "legion_community"}
    arch = load_tier_archetype("medium", event=event, research=research)
    date_str = event.event_date.strftime("%A, %B %d, %Y")

    layout = create_handbill_layout(
        event.venue,
        "Lindsey Lane Band",
        date_str,
        event.time_label or "TBA",
        event=event,
        archetype=arch,
        rng=_make_rng(event.gig_id, "B", round_num),
        medium_variant="hatch_stack",
    )
    report = validate_layout_constraints(
        layout,
        HATCH_CONSTRAINTS,
        venue=event.venue,
        band="Lindsey Lane Band",
    )

    out_path = out_dir / "structured_hatch_stack.png"
    render_flyer(layout, PHOTO, out_path, tier="medium")

    study = get_study(HATCH_CONSTRAINTS.study_id)
    assert study is not None
    card_path = out_dir / "structured_evaluation.png"
    build_evaluation_card(
        reference_path=Path(study.image_path),
        generated_path=out_path,
        output_path=card_path,
        study_title=study.title,
        method="Structured layout (hatch_stack + constraints)",
        constraint_report=report,
    )

    manifest = {
        "method": "structured_constraints",
        "path_rel": output_relative(out_path),
        "evaluation_card_rel": output_relative(card_path),
        "constraint_report": report.to_dict(),
    }
    (out_dir / "structured_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Hatch pilot: structured vs AI predict")
    parser.add_argument("--gig-id", default=DEFAULT_GIG)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--structured-only", action="store_true")
    parser.add_argument("--predict-only", action="store_true")
    args = parser.parse_args()

    if not PHOTO.is_file():
        print(f"Missing band photo: {PHOTO}", file=sys.stderr)
        return 1

    set_test_mode(True)
    out_dir = PILOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {"gig_id": args.gig_id, "outputs": {}}

    if not args.predict_only:
        print("Running structured constraint path…")
        event = _legion_event()
        structured = run_structured_path(event, out_dir=out_dir)
        results["outputs"]["structured"] = structured
        status = "PASS" if structured["constraint_report"]["passed"] else "FAIL"
        print(f"  Structured: {structured['path_rel']} — constraints {status}")
        print(f"  Evaluation: {structured['evaluation_card_rel']}")

    if not args.structured_only:
        from visual_predict_flyer import _gemini_api_key

        if not _gemini_api_key() and not args.dry_run:
            print(
                "Gemini key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY in "
                "gig-flyers/.env or Cloud Agent secrets.",
                file=sys.stderr,
            )
            return 1
        print("Running AI visual prediction path…")
        predict = predict_visual_flyer(args.gig_id, dry_run=args.dry_run)
        results["outputs"]["ai_predict"] = predict
        print(f"  AI predict: {predict['path_rel']}")
        print(f"  Evaluation: {predict['evaluation_card_rel']}")

    (out_dir / "pilot_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nPilot summary: {output_relative(out_dir / 'pilot_summary.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
