#!/usr/bin/env python3
"""Smoke test Gemini image generation (requires GOOGLE_API_KEY or GEMINI_API_KEY)."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_secrets import bootstrap_secrets  # noqa: E402

bootstrap_secrets(anchor=ROOT)

from image_providers.gemini import GeminiImageProvider  # noqa: E402
from image_providers.provider_status import provider_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Gemini Nano Banana image generation")
    parser.add_argument(
        "--prompt",
        default="Vintage concert poster background, mustard yellow and black, no text, no people",
    )
    args = parser.parse_args()

    status = provider_status()
    print("Provider status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    if not status["gemini_configured"]:
        print("\nERROR: Set GOOGLE_API_KEY or GEMINI_API_KEY in .env or Fly secrets.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="gemini-smoke-") as tmp:
        out = Path(tmp) / "gemini_smoke.png"
        provider = GeminiImageProvider()
        print(f"\nGenerating test image with {status['gemini_model']}…")
        provider.generate(args.prompt, out, option="smoke")
        print(f"OK — wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
