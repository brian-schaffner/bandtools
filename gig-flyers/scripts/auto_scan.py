#!/usr/bin/env python3
"""Daily auto-scan: generate flyers for new gigs and send review links."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_generator import main

if __name__ == "__main__":
    raise SystemExit(main(["--auto-scan", *sys.argv[1:]]))
