#!/usr/bin/env python3
"""Validate style.yaml has required sections."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "project",
    "core_principles",
    "information_hierarchy",
    "anti_ai_rules",
    "lindsey_lane_band",
    "variations",
]


def main() -> int:
    style = yaml.safe_load((ROOT / "style.yaml").read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in style]
    if missing:
        print("Missing sections:", ", ".join(missing))
        return 1
    if len(style.get("variations", [])) < 3:
        print("Need at least 3 variations")
        return 1
    print("style.yaml validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
