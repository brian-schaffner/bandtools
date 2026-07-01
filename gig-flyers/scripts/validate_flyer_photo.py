#!/usr/bin/env python3
"""CLI wrapper for validate_flyer_photo — check band photo fidelity on existing flyers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from image_providers.reference_compose import _cli_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(_cli_main())
