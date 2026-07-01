#!/usr/bin/env python3
"""Tests for structured layout margins, footer, and hierarchy."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from image_providers.reference_compose import SAFE_MARGIN_PX, typography_zones  # noqa: E402
from structured_layout.layout_spec import (  # noqa: E402
    create_default_handbill_layout,
    ensure_footer_elements,
    ensure_prominent_date_time,
    finalize_layout_spec,
    inject_canonical_event_text,
    sanitize_band_photo_frame,
    LayoutSpec,
    PhotoFrame,
    TextElement,
    FontWeight,
    TextAlignment,
)
from structured_layout.layout_scorer import score_layout_detailed  # noqa: E402
from structured_layout.layout_geometry import (  # noqa: E402
    MAX_TEXT_WIDTH_PCT,
    enforce_no_text_on_photo,
    text_overlaps_photo,
)
from structured_layout.structured_renderer import (  # noqa: E402
    _clamp_text_element,
    _apply_halftone,
    assert_photo_readable,
    estimate_text_overflow_issues,
    photo_region_mean_luminance,
    render_flyer,
)
from structured_layout.validation import validate_structured_flyer  # noqa: E402


class StructuredLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tuesday_jam = GigEvent(
            event_date=date(2026, 6, 30),
            time_label="9:30 pm",
            title="Hosting Stevie Ray's World Famous Tuesday Jam",
            venue="Stevie Ray's Tuesday Jam",
            suggested_name="Jun 30 Stevie Ray's Tuesday Jam",
        )

    def test_typography_zones_respect_safe_margin(self) -> None:
        canvas = (1024, 1536)
        photo_bbox = (40, 500, 984, 1100)
        zones = typography_zones(canvas, photo_bbox=photo_bbox)
        self.assertTrue(zones)
        for left, top, right, bottom in zones:
            if left == 0 or left <= SAFE_MARGIN_PX:
                self.assertGreaterEqual(left, SAFE_MARGIN_PX)
            if top == 0 or top <= SAFE_MARGIN_PX:
                self.assertGreaterEqual(top, SAFE_MARGIN_PX)
            if right >= canvas[0] - SAFE_MARGIN_PX:
                self.assertLessEqual(right, canvas[0] - SAFE_MARGIN_PX)

    def test_clamp_text_element_inside_margins(self) -> None:
        text = TextElement(
            content="STEVE RAY'S TUESDAY JAM",
            x=0,
            y=0,
            width=100,
            font_size=72,
            font_weight=FontWeight.BLACK,
        )
        clamped = _clamp_text_element(text, (1024, 1536))
        min_y = SAFE_MARGIN_PX / 1536 * 100
        self.assertGreaterEqual(clamped.y, min_y)
        self.assertGreaterEqual(clamped.x, min_y)

    def test_default_handbill_includes_footer_address(self) -> None:
        layout = create_default_handbill_layout(
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "9:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        all_text = " ".join(t.content for t in layout.text_elements)
        self.assertIn("40202", all_text)
        self.assertIn("Featuring", all_text)

    def test_ensure_footer_adds_missing_address(self) -> None:
        from structured_layout.layout_spec import LayoutSpec

        layout = LayoutSpec(text_elements=[])
        layout = ensure_footer_elements(
            layout,
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "9:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        all_text = " ".join(t.content for t in layout.text_elements)
        self.assertIn("40202", all_text)

    def test_layout_scorer_penalizes_missing_footer(self) -> None:
        layout = LayoutSpec(
            text_elements=[
                TextElement(
                    content="Stevie Ray's Tuesday Jam",
                    x=5,
                    y=5,
                    width=90,
                    font_size=64,
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                ),
            ]
        )
        score = score_layout_detailed(layout, self.tuesday_jam)
        self.assertTrue(any("address" in issue.lower() for issue in score.issues))

    def test_inject_canonical_venue_replaces_llm_typo(self) -> None:
        layout = LayoutSpec(
            text_elements=[
                TextElement(
                    content="STEVE RAY'S TUESDAY JAM",
                    x=10,
                    y=5,
                    width=80,
                    font_size=96,
                    font_weight=FontWeight.BLACK,
                    all_caps=True,
                ),
            ]
        )
        fixed = inject_canonical_event_text(layout, self.tuesday_jam.venue)
        self.assertEqual(fixed.text_elements[0].content, self.tuesday_jam.venue.upper())

    def test_estimate_text_overflow_flags_oversized_headline(self) -> None:
        layout = LayoutSpec(
            text_elements=[
                TextElement(
                    content="STEVE RAY'S TUESDAY JAM EXTRA LONG HEADLINE",
                    x=10,
                    y=5,
                    width=40,
                    font_size=120,
                    font_weight=FontWeight.BLACK,
                ),
            ]
        )
        issues = estimate_text_overflow_issues(layout)
        self.assertTrue(any("overflow" in issue.lower() for issue in issues))

    def test_halftone_overlay_preserves_photo_pixels(self) -> None:
        src = Image.new("RGBA", (120, 120), (80, 120, 200, 255))
        result = _apply_halftone(src, dot_size=4)
        self.assertEqual(result.size, src.size)
        center = result.getpixel((60, 60))
        self.assertNotEqual(center[:3], (255, 255, 255))

    def test_layout_scorer_penalizes_halftone_on_band_photo(self) -> None:
        layout = LayoutSpec(photo_frame=PhotoFrame(x=5, y=35, width=90, height=50, halftone=True))
        score = score_layout_detailed(layout, self.tuesday_jam)
        self.assertTrue(any("halftone" in issue.lower() for issue in score.issues))

    def test_validate_structured_flyer_skips_compose_drift(self) -> None:
        layout = create_default_handbill_layout(
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "9:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            Image.new("RGB", (1024, 1536), (245, 240, 230)).save(out)
            result = validate_structured_flyer(out, layout, self.tuesday_jam, band="Lindsey Lane Band")
            drift = next(c for c in result.checks if c["name"] == "photo_bbox_drift")
            self.assertTrue(drift["passed"])
            self.assertIn("skipped", drift["detail"].lower())
        finally:
            out.unlink(missing_ok=True)

    def test_inject_canonical_event_text_fixes_steve_typo(self) -> None:
        layout = LayoutSpec(
            text_elements=[
                TextElement(
                    content="STEVE RAY'S TUESDAY JAM",
                    x=5,
                    y=5,
                    width=90,
                    font_size=72,
                    font_weight=FontWeight.BLACK,
                    all_caps=True,
                ),
            ]
        )
        fixed = inject_canonical_event_text(layout, self.tuesday_jam.venue)
        self.assertEqual(fixed.text_elements[0].content, "STEVIE RAY'S TUESDAY JAM")

    def test_inject_canonical_event_text_preserves_date(self) -> None:
        layout = LayoutSpec(
            text_elements=[
                TextElement(
                    content="Tuesday, June 30, 2026",
                    x=5,
                    y=70,
                    width=90,
                    font_size=40,
                    font_weight=FontWeight.BOLD,
                ),
            ]
        )
        fixed = inject_canonical_event_text(layout, self.tuesday_jam.venue)
        self.assertEqual(fixed.text_elements[0].content, "Tuesday, June 30, 2026")

    def test_ensure_prominent_date_time_injects_missing_date(self) -> None:
        layout = LayoutSpec(text_elements=[])
        layout = ensure_prominent_date_time(layout, self.tuesday_jam, "7:30 pm")
        all_text = " ".join(t.content for t in layout.text_elements)
        self.assertIn("June 30", all_text)
        self.assertIn("2026", all_text)
        layout = LayoutSpec(photo_frame=PhotoFrame(x=5, y=5, width=80, height=50, halftone=True))
        sanitized = sanitize_band_photo_frame(layout)
        self.assertFalse(sanitized.photo_frame.halftone)

    def test_finalize_layout_spec_combines_gates(self) -> None:
        layout = LayoutSpec(
            photo_frame=PhotoFrame(x=5, y=5, width=80, height=50, halftone=True),
            text_elements=[
                TextElement(
                    content="STEVE RAY'S TUESDAY JAM",
                    x=5,
                    y=5,
                    width=90,
                    font_size=72,
                    font_weight=FontWeight.BLACK,
                    all_caps=True,
                ),
            ],
        )
        final = finalize_layout_spec(
            layout,
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "7:30 PM",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        self.assertFalse(final.photo_frame.halftone)
        self.assertIn("STEVIE", final.text_elements[0].content)
        all_text = " ".join(t.content for t in final.text_elements)
        self.assertIn("40202", all_text)

    def test_finalize_dedupes_house_jam_r6_duplicates(self) -> None:
        """Regression: B_r6 had venue/featuring repeated in header and footer."""
        layout = LayoutSpec.from_json(
            (
                Path(__file__).resolve().parents[1]
                / "output/2026-06-30_stevie-ray-s-tuesday-jam/option-B_r6_layout.json"
            ).read_text(encoding="utf-8")
        )
        before = [t.content for t in layout.text_elements]
        final = finalize_layout_spec(
            layout,
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        after = [t.content for t in final.text_elements]
        venue_count = sum(
            1 for c in after if "tuesday jam" in c.lower() and "featuring" not in c.lower()
        )
        featuring_count = sum(1 for c in after if "featuring" in c.lower())
        self.assertEqual(venue_count, 1, f"venue repeated: {after}")
        self.assertEqual(featuring_count, 1, f"featuring repeated: {after}")
        footer_text = " ".join(
            t.content
            for t in final.text_elements
            if "40202" in t.content or t.y >= 85
        )
        self.assertIn("40202", footer_text)
        self.assertNotIn("Featuring", footer_text)
        self.assertNotIn("Tuesday Jam", footer_text.split("40202")[0])

    def test_enforce_no_text_on_photo_moves_featuring_above(self) -> None:
        layout = LayoutSpec(
            photo_frame=PhotoFrame(x=5, y=28, width=90, height=42),
            text_elements=[
                TextElement(
                    content="Featuring Lindsey Lane Band",
                    x=5,
                    y=35,
                    width=90,
                    font_size=48,
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                ),
            ],
        )
        self.assertTrue(text_overlaps_photo(layout.text_elements[0], layout))
        fixed = enforce_no_text_on_photo(layout)
        self.assertFalse(text_overlaps_photo(fixed.text_elements[0], fixed))
        self.assertLess(fixed.text_elements[0].y, layout.photo_frame.y)

    def test_finalize_moves_overlapping_text_off_photo(self) -> None:
        layout = LayoutSpec.from_json(
            (
                Path(__file__).resolve().parents[1]
                / "output/2026-06-30_stevie-ray-s-tuesday-jam/option-B_r6_layout.json"
            ).read_text(encoding="utf-8")
        )
        layout.text_elements.append(
            TextElement(
                content="Featuring Lindsey Lane Band",
                x=10,
                y=32,
                width=80,
                font_size=72,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
            )
        )
        final = finalize_layout_spec(
            layout,
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        for text in final.text_elements:
            self.assertFalse(
                text_overlaps_photo(text, final),
                f"overlap: {text.content} at y={text.y}",
            )

    def test_option_b_paste_up_blues_bar(self) -> None:
        """Option B paste-up: starburst accent, photo offset, at most one accent."""
        from structured_layout.fixed_templates import layout_for_option
        from structured_layout.tier_archetypes import load_tier_archetype

        arch = load_tier_archetype("medium", event=self.tuesday_jam)
        self.assertEqual(arch.accent_element, "starburst")
        self.assertEqual(arch.photo_side, "right")

        layout = layout_for_option(
            "B",
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
            gig_id=self.tuesday_jam.gig_id,
            option_letter="B",
            round_num=1,
        )

        starbursts = [g for g in layout.graphic_elements if g.element_type == "starburst"]
        self.assertEqual(len(starbursts), 1, layout.graphic_elements)
        self.assertIn("JUN", starbursts[0].properties.get("text", "").upper())

        date_in_text = [
            t for t in layout.text_elements
            if "june" in t.content.lower() and "2026" in t.content
        ]
        self.assertEqual(date_in_text, [], "full date belongs in starburst only")
        self.assertEqual(estimate_text_overflow_issues(layout), [])

        # Photo offset to the right column (type column on left)
        self.assertGreaterEqual(layout.photo_frame.x, 45.0)

        accent_count = sum(
            1 for g in layout.graphic_elements
            if g.element_type in ("starburst", "stamp", "tape")
            or (g.element_type == "box" and g.height <= 2.0)
        )
        self.assertLessEqual(accent_count, 1)

        self.assertEqual(layout.photo_frame.opacity, 1.0)
        self.assertEqual(layout.photocopy_effect, 0.0)
        self.assertEqual(layout.age_effect, 0.0)

    def test_medium_variant_catalog_deterministic(self) -> None:
        """Option B picks from named variants via seeded hash."""
        from structured_layout.fixed_templates import (
            MEDIUM_VARIANTS,
            _select_medium_variant,
            layout_for_option,
        )
        from structured_layout.tier_archetypes import load_tier_archetype

        arch = load_tier_archetype("medium", event=self.tuesday_jam)
        self.assertEqual(_select_medium_variant(arch, __import__("random").Random(0)), "paste_up")

        layout = layout_for_option(
            "B",
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
            gig_id=self.tuesday_jam.gig_id,
            option_letter="B",
            round_num=99,
        )
        self.assertTrue(
            any(
                token in layout.style_notes.lower()
                for token in ("paste-up", "broadside", "tri-band", "inverted footer")
            )
        )
        self.assertEqual(layout.photo_frame.opacity, 1.0)

    def test_creative_variant_catalog_and_footer_contrast(self) -> None:
        """Option C uses named variants; dark bg gets light footer text."""
        from structured_layout.fixed_templates import (
            CREATIVE_VARIANTS,
            layout_for_option,
        )

        layout = layout_for_option(
            "C",
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
            gig_id=self.tuesday_jam.gig_id,
            option_letter="C",
            round_num=3,
        )
        self.assertTrue(
            any(
                token in layout.style_notes.lower()
                for token in ("showbill", "vertical split")
            )
        )
        # Structurally distinct from A/B: photo left, no full-width top bar
        self.assertLess(layout.photo_frame.x, 40.0)
        self.assertGreater(layout.photo_frame.height, 70.0)
        full_bars = [
            g for g in layout.graphic_elements
            if g.element_type == "box"
            and g.width >= MAX_TEXT_WIDTH_PCT - 2
            and g.height > 4.0
        ]
        self.assertEqual(full_bars, [], "Option C should not use full-width ink bars")
        all_text = " ".join(t.content for t in layout.text_elements)
        self.assertIn("40202", all_text)

        accent_types = {g.element_type for g in layout.graphic_elements}
        self.assertIn("box", accent_types)
        self.assertNotIn("diagonal_band", accent_types)
        # No duplicate full prose date injected below photo
        prose_dates = [
            t for t in layout.text_elements
            if "2026" in t.content and "June" in t.content
        ]
        self.assertEqual(len(prose_dates), 0, msg="compact date stack should not get prose date injection")

    def test_creative_showbill_render(self) -> None:
        """Option C showbill paste-up renders with new graphic primitives."""
        from structured_layout.fixed_templates import layout_for_option

        layout = layout_for_option(
            "C",
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
            gig_id=self.tuesday_jam.gig_id,
            option_letter="C",
            round_num=1,
        )
        self.assertIn("vertical split", layout.style_notes.lower())
        self.assertIsNone(layout.background.wash_color)

        photo = ROOT / "bandphotos/679394308_1366641221939459_1410337987474015419_n.jpg"
        if not photo.is_file():
            self.skipTest("band photo fixture missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "golden-C.png"
            render_flyer(layout, photo, out, option="C", tier="creative")
            self.assertTrue(out.is_file())
            result = validate_structured_flyer(
                out, layout, self.tuesday_jam, band="Lindsey Lane Band"
            )
            self.assertTrue(result.passed, result.issues)

    def test_golden_handbill_house_jam(self) -> None:
        """Golden: house-jam handbill has required facts, no text on photo."""
        from structured_layout.fixed_templates import create_handbill_layout

        layout = create_handbill_layout(
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
            rng=__import__("random").Random(42),
        )
        self.assertGreaterEqual(len(layout.text_elements), 4)
        all_text = " ".join(t.content for t in layout.text_elements)
        graphic_text = " ".join(
            str(g.properties.get("text", ""))
            for g in layout.graphic_elements
            if g.properties.get("text")
        )
        combined = f"{all_text} {graphic_text}".replace("\n", " ")
        for needle in ("STEVIE", "Featuring", "JUN 30", "7:30", "40202"):
            self.assertIn(needle, combined, msg=combined)
        for text in layout.text_elements:
            self.assertFalse(text_overlaps_photo(text, layout), text.content)

        photo = ROOT / "bandphotos/679394308_1366641221939459_1410337987474015419_n.jpg"
        self.assertTrue(photo.is_file(), "band photo fixture missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "golden-B.png"
            render_flyer(layout, photo, out, option="B", tier="medium")
            self.assertTrue(out.is_file())
            result = validate_structured_flyer(
                out, layout, self.tuesday_jam, band="Lindsey Lane Band"
            )
            self.assertTrue(result.passed, result.issues)
            readable, detail = assert_photo_readable(out, layout)
            self.assertTrue(readable, detail)
            mean_lum = photo_region_mean_luminance(out, layout)
            self.assertIsNotNone(mean_lum)
            assert mean_lum is not None
            self.assertGreaterEqual(mean_lum, 70)
            self.assertLessEqual(mean_lum, 200)

    def test_photo_luminance_band_fixture(self) -> None:
        """Regression: photo bbox mean luminance stays readable (not washed out)."""
        from structured_layout.fixed_templates import layout_for_option

        layout = layout_for_option(
            "B",
            self.tuesday_jam.venue,
            "Lindsey Lane Band",
            "Tuesday, June 30, 2026",
            "7:30 pm",
            address="230 East Main Street, Louisville, KY 40202",
            event=self.tuesday_jam,
        )
        photo = ROOT / "bandphotos/679394308_1366641221939459_1410337987474015419_n.jpg"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lum-B.png"
            render_flyer(layout, photo, out, option="B", tier="medium")
            mean_lum = photo_region_mean_luminance(out, layout)
            self.assertIsNotNone(mean_lum)
            assert mean_lum is not None
            self.assertGreaterEqual(mean_lum, 70, f"washed out: {mean_lum:.1f}")
            self.assertLessEqual(mean_lum, 200, f"overexposed: {mean_lum:.1f}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
