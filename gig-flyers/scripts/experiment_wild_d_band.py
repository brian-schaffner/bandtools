#!/usr/bin/env python3
"""Experiment: 3 hypotheses for wild D posters with accurate band photo.

Usage:
  python scripts/experiment_wild_d_band.py              # local (H3 + synthetic baselines)
  python scripts/experiment_wild_d_band.py --live     # call Gemini for H1/H2 (needs GOOGLE_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

from agent_secrets import (  # noqa: E402
    bootstrap_google_api_key_env,
    google_api_key_configured,
    resolve_google_api_key_source,
)

bootstrap_google_api_key_env()

from gig_calendar import GigEvent  # noqa: E402
from image_providers import generate_with_fallback  # noqa: E402
from wild_design.band_replace import build_wild_band_replace_prompt  # noqa: E402
from wild_design.composite import render_wild_composite_poster  # noqa: E402
from wild_design.constrained import build_wild_constrained_prompt  # noqa: E402
from wild_design.metrics import WildBandMetrics, score_output  # noqa: E402
from wild_design.prompt import build_wild_design_prompt  # noqa: E402
from option_slots import wild_variation  # noqa: E402


OUT_DIR = ROOT / "output" / "experiments" / "wild_d_band"
REF_PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"


def _event() -> GigEvent:
    return GigEvent(
        event_date=date(2026, 6, 28),
        time_label="7:00 PM",
        title="Lindsey Lane Band",
        venue="Two Lane Tavern",
        suggested_name="Jun 28 Two Lane Tavern",
    )


def _has_google_key() -> bool:
    return google_api_key_configured()


def create_synthetic_wild_poster(
    reference_path: Path,
    output_path: Path,
    *,
    seed: int = 7,
) -> Path:
    """Simulate initial wild D: creative shell with deliberately wrong band region."""
    from wild_design.composite import _wood_background

    size = (1024, 1536)
    canvas = _wood_background(size, seed=seed)
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 50), "LINDSEY LANE BAND", fill=(15, 10, 5))
    draw.text((60, 120), "JUN 28 • TWO LANE TAVERN", fill=(40, 20, 10))

    ref = Image.open(reference_path).convert("RGB")
    w, h = size
    cw, ch = int(w * 0.75), int(h * 0.45)
    left, top = (w - cw) // 2, int(h * 0.28)
    wrong = ref.resize((cw, ch), Image.Resampling.BILINEAR)
    wrong = wrong.filter(ImageFilter.GaussianBlur(radius=6))
    wrong = ImageEnhance_wrong(wrong)
    canvas.paste(wrong, (left, top))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def ImageEnhance_wrong(img: Image.Image) -> Image.Image:
    from PIL import ImageEnhance

    img = ImageEnhance.Color(img).enhance(0.3)
    img = ImageEnhance.Brightness(img).enhance(1.2)
    return img


def run_h0_baseline(reference: Path, out: Path) -> WildBandMetrics:
    t0 = time.monotonic()
    create_synthetic_wild_poster(reference, out)
    return score_output(
      "H0_baseline_synthetic_wild_D",
      out,
      reference,
      elapsed_sec=time.monotonic() - t0,
      notes="Simulated initial wild D with blurred/color-wrong band",
    )


def run_h1_band_replace(reference: Path, prior_poster: Path, out: Path, event: GigEvent) -> WildBandMetrics:
    prompt = build_wild_band_replace_prompt(event, feedback="keep western style")
    t0 = time.monotonic()
    generate_with_fallback(
      prompt,
      out,
      reference_photo_path=reference,
      design_reference_path=prior_poster,
      provider="gemini",
      tier="wild",
      option="D",
    )
    return score_output(
      "H1_two_pass_band_replace",
      out,
      reference,
      elapsed_sec=time.monotonic() - t0,
      notes="Poster ref + band ref → Gemini band swap",
    )


def run_h2_constrained_single_pass(reference: Path, out: Path, event: GigEvent) -> WildBandMetrics:
    prompt = build_wild_constrained_prompt({}, event, 1, selected_photo={"description": "four piece band"})
    t0 = time.monotonic()
    generate_with_fallback(
      prompt,
      out,
      reference_photo_path=reference,
      provider="gemini",
      tier="wild",
      option="D",
    )
    return score_output(
      "H2_constrained_single_pass",
      out,
      reference,
      elapsed_sec=time.monotonic() - t0,
      notes="Band ref attached; creative poster around exact photo",
    )


def run_h3_pil_composite(reference: Path, out: Path, event: GigEvent) -> WildBandMetrics:
    t0 = time.monotonic()
    meta = render_wild_composite_poster(event, reference, out, tier="creative", seed=42)
    return score_output(
      "H3_decomposed_pil_composite",
      out,
      reference,
      elapsed_sec=time.monotonic() - t0,
      compose=meta["compose"],
      notes="PIL paste exact band photo into wild western shell",
    )


def rank_results(results: list[WildBandMetrics]) -> list[WildBandMetrics]:
    def key(m: WildBandMetrics) -> tuple:
      val_pass = 1 if m.compose_validation_passed else 0
      return (val_pass, m.band_hist_correlation, -m.band_mse)

    return sorted(results, key=key, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wild D band photo hypothesis experiment")
    parser.add_argument("--live", action="store_true", help="Run H1/H2 with Gemini (needs API key)")
    parser.add_argument("--reference", type=Path, default=REF_PHOTO)
    args = parser.parse_args()

    if not args.reference.is_file():
      print(f"Missing reference photo: {args.reference}", file=sys.stderr)
      return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    event = _event()
    results: list[WildBandMetrics] = []

    prior = OUT_DIR / "fixture_synthetic_wild_D.png"
    results.append(run_h0_baseline(args.reference, prior))

    results.append(
      run_h3_pil_composite(args.reference, OUT_DIR / "H3_pil_composite.png", event)
    )

    if args.live and _has_google_key():
      src_name, _ = resolve_google_api_key_source()
      print(f"Using Gemini key from env: {src_name!r}")
      for name, fn in (
        ("H1", lambda: run_h1_band_replace(args.reference, prior, OUT_DIR / "H1_band_replace.png", event)),
        ("H2", lambda: run_h2_constrained_single_pass(args.reference, OUT_DIR / "H2_constrained.png", event)),
      ):
        try:
          results.append(fn())
        except Exception as exc:
          print(f"{name} failed: {exc}", file=sys.stderr)
    else:
      checked = ", ".join(repr(n) for n in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "gemini api key", "Apikey"))
      print(f"Skipping H1/H2 live Gemini calls (use --live; checked: {checked})")

    ranked = rank_results(results)
    report = {
      "event": event.to_dict(),
      "reference_photo": str(args.reference),
      "ranked": [m.to_dict() for m in ranked],
      "winner": ranked[0].hypothesis if ranked else None,
    }
    report_path = OUT_DIR / "results.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
