"""Ordered post-render steps for wild full-canvas flyers."""

from __future__ import annotations

from pathlib import Path

from wild_design.color_correct import correct_wild_flyer_colors


def enrich_wild_poster(path: Path, letter: str) -> bool:
    """Run staging-wild enrichments before logo overlay. Returns True if any step modified the file."""
    changed = False
    if correct_wild_flyer_colors(path, letter):
        changed = True
    return changed
