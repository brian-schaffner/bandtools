#!/usr/bin/env python3
"""Run one typography-only flyer generation (option B / medium) for pipeline experiments."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load .env if present
env_path = ROOT / ".env"
if env_path.is_file():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

from image_providers.openai import OpenAIImageProvider  # noqa: E402

REF = ROOT / "bandphotos" / "679394308_1366641221939459_1410337987474015419_n.jpg"
OUT = ROOT / "output" / "experiments" / "typography_only_B.png"

PROMPT = """Create a single concert flyer image that looks like a real regional promoter made it quickly.

CREATIVITY TIER — B) Medium:
Balanced authentic promoter handbill with modest layout flair.
Portrait orientation. Venue and date dominate the header.
Band name and show time clearly readable above the empty photo slot.
Full address in footer: 230 East Main Street, Louisville, KY 40202.
Show time: 9:30 pm. Date: Friday, June 26, 2026.
Venue: Stevie Ray's Blues Bar. Band: Lindsey Lane Band.

Leave the center photo slot plain cream — band photo is composited separately.
"""


def main() -> int:
    os.environ["OPENAI_IMAGE_PIPELINE"] = "typography_only"
    os.environ.setdefault("OPENAI_IMAGE_SIZE", "1024x1536")
    os.environ.setdefault("OPENAI_IMAGE_QUALITY", "medium")

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set — skipping live API call", file=sys.stderr)
        return 1
    if not REF.is_file():
        print(f"Reference photo missing: {REF}", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    provider = OpenAIImageProvider()
    print(f"Generating typography-only option B → {OUT}", flush=True)
    provider.generate(
        PROMPT,
        OUT,
        reference_photo_path=REF,
        option="B",
        tier="medium",
    )
    print(f"Done: {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
