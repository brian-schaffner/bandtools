"""Hard constraints extracted from annotated real poster studies."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from text_validation import MONTH_NAME_RE, YEAR_RE

from visual_studies import HATCH_INK, HATCH_PAPER, HATCH_RED

# ---------------------------------------------------------------------------
# Hatch Show Print — Hank Williams 1953 (annotated from reference image)
# ---------------------------------------------------------------------------

HATCH_STACK_ORDER: tuple[str, ...] = (
    "venue",
    "date",
    "presenter_bar",
    "photo",
    "band",
    "time",
)

HATCH_PALETTE: tuple[str, ...] = (HATCH_PAPER, HATCH_INK, HATCH_RED)


@dataclass(frozen=True)
class StudyConstraints:
    """Machine-checkable layout contract for one visual study."""

    study_id: str
    title: str
    stack_order: tuple[str, ...]
    palette_hex: tuple[str, ...]
    max_ink_colors: int
    center_aligned: bool
    band_font_min_ratio: float
    photo_height_pct: tuple[float, float]
    photo_centered: bool
    presenter_bar_required: bool
    venue_above_band: bool
    medium_variant: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HATCH_CONSTRAINTS = StudyConstraints(
    study_id="hatch_hank_williams_1953",
    title="Hatch Show Print — Hank Williams 1953",
    stack_order=HATCH_STACK_ORDER,
    palette_hex=HATCH_PALETTE,
    max_ink_colors=2,
    center_aligned=True,
    band_font_min_ratio=1.5,
    photo_height_pct=(30.0, 42.0),
    photo_centered=True,
    presenter_bar_required=True,
    venue_above_band=True,
    medium_variant="hatch_stack",
)


CONSTRAINTS_BY_STUDY: dict[str, StudyConstraints] = {
    HATCH_CONSTRAINTS.study_id: HATCH_CONSTRAINTS,
}


def get_constraints(study_id: str) -> StudyConstraints | None:
    return CONSTRAINTS_BY_STUDY.get(study_id)


@dataclass
class ConstraintCheck:
    id: str
    label: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConstraintReport:
    study_id: str
    passed: bool
    checks: list[ConstraintCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
        }

    def checklist_lines(self) -> list[str]:
        return [
            f"{'PASS' if c.passed else 'FAIL'} — {c.label}: {c.detail}"
            for c in self.checks
        ]


def _norm_hex(hex_color: str) -> str:
    h = hex_color.lstrip("#").upper()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"#{h}"


def _is_date_text(text: str) -> bool:
    lower = text.lower()
    return bool(MONTH_NAME_RE.search(lower) and YEAR_RE.search(lower))


def _is_time_text(text: str) -> bool:
    return bool(re.search(r"\d{1,2}:\d{2}|\b\d{1,2}\s*(am|pm)\b", text.lower()))


def _find_role_elements(
    layout,
    *,
    venue: str,
    band: str,
) -> dict[str, Any]:
    """Map constraint roles to layout elements."""
    venue_upper = venue.upper()
    band_upper = band.upper()
    roles: dict[str, Any] = {}

    for text in layout.text_elements:
        content_upper = text.content.upper()
        if venue_upper in content_upper or content_upper in venue_upper:
            roles.setdefault("venue", text)
        elif band_upper in content_upper:
            roles.setdefault("band", text)
        elif _is_date_text(text.content):
            roles.setdefault("date", text)
        elif _is_time_text(text.content):
            roles.setdefault("time", text)
        elif "LIVE MUSIC" in content_upper or "GRAND OLE" in content_upper:
            roles.setdefault("presenter_label", text)

    roles["photo"] = layout.photo_frame
    roles["presenter_bar"] = next(
        (g for g in layout.graphic_elements if g.element_type == "box" and g.height >= 3.0),
        None,
    )
    return roles


def validate_layout_constraints(
    layout,
    constraints: StudyConstraints,
    *,
    venue: str,
    band: str,
) -> ConstraintReport:
    """Validate a LayoutSpec against a study's hard constraints."""
    checks: list[ConstraintCheck] = []
    roles = _find_role_elements(layout, venue=venue, band=band)

    def add(check_id: str, label: str, ok: bool, detail: str) -> None:
        checks.append(ConstraintCheck(id=check_id, label=label, passed=ok, detail=detail))

    venue_el = roles.get("venue")
    band_el = roles.get("band")
    date_el = roles.get("date")
    bar = roles.get("presenter_bar")
    photo = roles.get("photo")

    add(
        "venue_present",
        "Venue text present",
        venue_el is not None,
        "found venue block" if venue_el else "missing venue text",
    )
    add(
        "band_present",
        "Band name present",
        band_el is not None,
        "found band name" if band_el else "missing band name",
    )

    if constraints.venue_above_band and venue_el and band_el:
        add(
            "venue_above_band",
            "Venue above band name",
            venue_el.y < band_el.y,
            f"venue y={venue_el.y}, band y={band_el.y}",
        )

    if venue_el and band_el:
        ratio = band_el.font_size / max(venue_el.font_size, 1)
        add(
            "band_largest_type",
            f"Band type ≥ {constraints.band_font_min_ratio}× venue",
            ratio >= constraints.band_font_min_ratio,
            f"ratio={ratio:.2f} (band {band_el.font_size}pt, venue {venue_el.font_size}pt)",
        )

    if constraints.presenter_bar_required:
        add(
            "presenter_bar",
            "Black presenter bar",
            bar is not None,
            "present" if bar else "missing horizontal bar",
        )

    if photo and constraints.photo_centered:
        cx = photo.x + photo.width / 2
        add(
            "photo_centered",
            "Photo centered horizontally",
            48.0 <= cx <= 52.0,
            f"photo center x={cx:.1f}%",
        )

    if photo:
        lo, hi = constraints.photo_height_pct
        add(
            "photo_height",
            f"Photo height {lo:.0f}–{hi:.0f}% of canvas",
            lo <= photo.height <= hi,
            f"photo height={photo.height:.1f}%",
        )

    if constraints.center_aligned and venue_el:
        add(
            "center_aligned",
            "Primary type center-aligned",
            venue_el.alignment.value == "center",
            f"venue alignment={venue_el.alignment.value}",
        )

    # Stack order: venue < date < bar < photo < band (by y)
    order_ok = True
    order_detail: list[str] = []
    if venue_el and date_el:
        order_ok = order_ok and venue_el.y < date_el.y
        order_detail.append(f"venue({venue_el.y})<date({date_el.y})")
    if date_el and bar:
        order_ok = order_ok and date_el.y < bar.y
        order_detail.append(f"date<{bar.y}")
    if bar and photo:
        order_ok = order_ok and bar.y < photo.y
        order_detail.append(f"bar<photo({photo.y})")
    if photo and band_el:
        order_ok = order_ok and photo.y + photo.height < band_el.y + 1
        order_detail.append(f"photo<band({band_el.y})")
    if order_detail:
        add(
            "stack_order",
            "Stack order matches study",
            order_ok,
            ", ".join(order_detail),
        )

    palette_used = {_norm_hex(layout.background.color.hex)}
    for text in layout.text_elements:
        palette_used.add(_norm_hex(text.color.hex))
    for graphic in layout.graphic_elements:
        if graphic.fill_color:
            palette_used.add(_norm_hex(graphic.fill_color.hex))

    allowed = {_norm_hex(c) for c in constraints.palette_hex}
    extra = palette_used - allowed
    add(
        "palette",
        f"Palette ≤ {constraints.max_ink_colors} inks + paper",
        len(palette_used - {_norm_hex(constraints.palette_hex[0])}) <= constraints.max_ink_colors
        and not extra - allowed,
        f"colors used: {sorted(palette_used)}",
    )

    passed = all(c.passed for c in checks)
    return ConstraintReport(study_id=constraints.study_id, passed=passed, checks=checks)


def hatch_predict_prompt_block(
    *,
    venue: str,
    date: str,
    time: str,
    band: str,
    address: str = "",
) -> str:
    """Prompt block for AI image prediction matching Hatch study constraints."""
    lines = [
        "STYLE TARGET: 1953 Hatch Show Print letterpress poster (IMAGE 1).",
        "Match its layout structure exactly:",
        "  1. Cream paper background — red and black ink only, no gradients",
        "  2. Top: VENUE NAME in large red caps, centered",
        "  3. Next: DATE in red caps, centered",
        "  4. Black horizontal presenter bar with white uppercase label (e.g. LIVE MUSIC)",
        "  5. Centered band portrait photo (already on canvas in IMAGE 2 — do NOT modify)",
        "  6. MEGA BAND NAME at bottom in red condensed caps — largest type on page",
        "  7. Show time in black below band name",
        "",
        "EVENT FACTS (copy exactly):",
        f"  Venue: {venue}",
        f"  Date: {date}",
        f"  Time: {time}",
        f"  Band: {band}",
    ]
    if address:
        lines.append(f"  Address: {address}")
    lines.extend(
        [
            "",
            "Do NOT add hype lines, ticket URLs, or extra decoration.",
            "Do NOT redraw, duplicate, or frame the band photo.",
        ]
    )
    return "\n".join(lines)
