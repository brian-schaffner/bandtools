"""Post-render validation for Structured Layout Mode.

Skips AI-compose photo bbox drift / duplicate checks (structured renderer
places the photo deterministically). Validates text overflow, footer content,
and halftone quality instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from gig_calendar import GigEvent
from structured_layout.layout_spec import LayoutSpec
from structured_layout.structured_renderer import (
    assert_photo_readable,
    estimate_text_overflow_issues,
)
from structured_layout.layout_geometry import text_overlaps_photo, validate_layout_bounds
from text_validation import validate_required_footer_text


@dataclass
class StructuredValidationResult:
    passed: bool
    issues: list[str]
    checks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": self.issues,
            "checks": self.checks,
        }


def _photo_region_mostly_white(
    output_path: Path,
    layout: LayoutSpec,
    *,
    white_threshold: int = 240,
    min_white_ratio: float = 0.55,
) -> bool:
    """True when the photo slot is mostly flat white (halftone silhouette bug)."""
    from PIL import Image

    if not output_path.is_file():
        return False

    flyer = Image.open(output_path).convert("RGB")
    w, h = flyer.size
    frame = layout.photo_frame
    left = int(w * frame.x / 100)
    top = int(h * frame.y / 100)
    right = int(w * (frame.x + frame.width) / 100)
    bottom = int(h * (frame.y + frame.height) / 100)
    if right <= left or bottom <= top:
        return False

    region = flyer.crop((left, top, right, bottom))
    pixels = list(region.getdata())
    if not pixels:
        return False
    white_count = sum(
        1 for r, g, b in pixels if r >= white_threshold and g >= white_threshold and b >= white_threshold
    )
    return white_count / len(pixels) >= min_white_ratio


def validate_structured_flyer(
    output_path: Path,
    layout: LayoutSpec,
    event: GigEvent,
    *,
    band: str,
) -> StructuredValidationResult:
    """Validate a structured-layout flyer without AI-compose bbox checks."""
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    def _record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "passed": ok, "detail": detail})
        if not ok:
            issues.append(detail)

    all_text = " ".join(t.content for t in layout.text_elements)
    footer_issues = validate_required_footer_text(all_text, event, band=band)
    _record(
        "required_footer_text",
        not footer_issues,
        "; ".join(footer_issues) if footer_issues else "footer content present",
    )

    overflow_issues = estimate_text_overflow_issues(layout)
    _record(
        "no_text_overflow",
        not overflow_issues,
        "; ".join(overflow_issues) if overflow_issues else "text fits allocated width",
    )

    overlap_issues = [
        f"Text overlaps photo: '{t.content[:40]}'"
        for t in layout.text_elements
        if text_overlaps_photo(t, layout)
    ]
    _record(
        "no_text_on_photo",
        not overlap_issues,
        "; ".join(overlap_issues) if overlap_issues else "text clear of photo frame",
    )

    bounds_issues = validate_layout_bounds(layout)
    _record(
        "text_within_canvas",
        not bounds_issues,
        "; ".join(bounds_issues) if bounds_issues else "all text inside canvas bounds",
    )

    halftone = layout.photo_frame.halftone
    _record(
        "halftone_disabled_on_band_photo",
        not halftone,
        "halftone enabled on band photo" if halftone else "halftone off (face detail preserved)",
    )

    if halftone and output_path.is_file() and _photo_region_mostly_white(output_path, layout):
        _record(
            "halftone_preserves_photo",
            False,
            "halftone reduced band photo to dot silhouettes on white",
        )

    if output_path.is_file():
        readable, detail = assert_photo_readable(output_path, layout)
        _record("photo_readable", readable, detail)

    # Structured mode does not use AI-compose photo placement — skip drift/duplicate.
    _record(
        "photo_bbox_drift",
        True,
        "skipped (structured layout — deterministic photo placement)",
    )
    _record(
        "no_duplicate_band_photo",
        True,
        "skipped (structured layout — single photo composite)",
    )

    return StructuredValidationResult(
        passed=len(issues) == 0,
        issues=issues,
        checks=checks,
    )
