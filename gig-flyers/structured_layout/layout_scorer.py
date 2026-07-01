"""Layout quality scorer for Structured Layout Mode.

Scores layouts before rendering to ensure quality thresholds are met.
Only renders flyers when the layout score exceeds the threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from gig_calendar import GigEvent
from structured_layout.layout_spec import LayoutSpec, TextElement, PhotoFrame
from structured_layout.structured_renderer import estimate_text_overflow_issues
from structured_layout.layout_geometry import text_overlaps_photo, validate_layout_bounds
from text_validation import (
    SAFE_MARGIN_PX,
    is_house_series_gig,
    validate_required_footer_text,
    halftone_unsafe_for_band_photo,
)


@dataclass
class LayoutScore:
    """Detailed breakdown of layout quality scores."""
    visual_balance: float  # 0-10
    typography: float  # 0-10
    photo_integration: float  # 0-10
    readability: float  # 0-10
    hierarchy: float  # 0-10
    overall: float  # 0-10 (weighted average)
    issues: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "visual_balance": round(self.visual_balance, 2),
            "typography": round(self.typography, 2),
            "photo_integration": round(self.photo_integration, 2),
            "readability": round(self.readability, 2),
            "hierarchy": round(self.hierarchy, 2),
            "overall": round(self.overall, 2),
            "issues": self.issues,
        }


def _score_visual_balance(layout: LayoutSpec) -> tuple[float, list[str]]:
    """Score the visual balance of the layout (0-10)."""
    score = 10.0
    issues: list[str] = []
    
    photo = layout.photo_frame
    photo_center_x = photo.x + photo.width / 2
    photo_center_y = photo.y + photo.height / 2
    
    x_offset = abs(photo_center_x - 50)
    if x_offset > 30:
        score -= 2
        issues.append(f"Photo horizontally off-center by {x_offset:.0f}%")
    elif x_offset > 15:
        score -= 1
    
    text_count = len(layout.text_elements)
    if text_count < 3:
        score -= 2
        issues.append("Too few text elements (need venue, date, band, time)")
    elif text_count > 8:
        score -= 1
        issues.append("Too many text elements may look cluttered")
    
    text_above = sum(1 for t in layout.text_elements if t.y < photo.y)
    text_below = sum(1 for t in layout.text_elements if t.y > photo.y + photo.height)
    
    if text_above == 0 and text_below == 0:
        score -= 3
        issues.append("No text above or below photo")
    elif text_above == 0:
        score -= 1
        issues.append("No text above photo")
    elif text_below == 0:
        score -= 1
        issues.append("No text below photo")
    
    return max(0, score), issues


def _score_typography(layout: LayoutSpec) -> tuple[float, list[str]]:
    """Score typography quality (0-10)."""
    score = 10.0
    issues: list[str] = []
    
    font_sizes = [t.font_size for t in layout.text_elements]
    if font_sizes:
        max_size = max(font_sizes)
        min_size = min(font_sizes)
        
        if max_size < 48:
            score -= 2
            issues.append("Largest text too small (< 48pt)")
        
        if max_size > 0 and min_size / max_size > 0.8:
            score -= 1
            issues.append("Insufficient size variation in typography")
    
    for text in layout.text_elements:
        if text.x < 0 or text.x > 100:
            score -= 1
            issues.append(f"Text '{text.content[:20]}...' x position out of bounds")
        min_y_pct = SAFE_MARGIN_PX / layout.canvas_height * 100
        max_y_pct = 100 - min_y_pct
        if text.y < min_y_pct or text.y > max_y_pct:
            score -= 1
            issues.append(
                f"Text '{text.content[:20]}...' outside safe margin ({SAFE_MARGIN_PX}px)"
            )
    
    for i, t1 in enumerate(layout.text_elements):
        for t2 in layout.text_elements[i+1:]:
            if abs(t1.y - t2.y) < 5:
                score -= 0.5
                issues.append(f"Text elements may overlap: '{t1.content[:15]}' and '{t2.content[:15]}'")
    
    return max(0, score), issues


def _score_photo_integration(layout: LayoutSpec) -> tuple[float, list[str]]:
    """Score how well the photo is integrated (0-10)."""
    score = 10.0
    issues: list[str] = []
    
    photo = layout.photo_frame
    
    if photo.width < 50:
        score -= 2
        issues.append("Photo too small (< 50% canvas width)")
    elif photo.width < 70:
        score -= 0.5
    
    if photo.height < 30:
        score -= 2
        issues.append("Photo too short (< 30% canvas height)")
    elif photo.height < 40:
        score -= 0.5
    
    if photo.width > 98 and photo.height > 98:
        score -= 2
        issues.append("Photo fills entire canvas (no room for typography)")
    
    if abs(photo.rotation) > 2.0:
        score -= 1
        issues.append(f"Photo rotation too extreme ({photo.rotation}° > ±2°)")
    
    if photo.crop_top + photo.crop_bottom > 30:
        score -= 1
        issues.append("Photo cropped too much vertically (may cut off band members)")
    if photo.crop_left + photo.crop_right > 30:
        score -= 1
        issues.append("Photo cropped too much horizontally")
    
    if photo.film_grain > 0 or photo.paper_texture > 0:
        score += 0.5

    if halftone_unsafe_for_band_photo(photo):
        score -= 5
        issues.append("Halftone on band photo destroys face detail — disabled in structured mode")
    
    if photo.edge_feather > 0 or photo.border_width > 0:
        score += 0.5
    
    return max(0, min(10, score)), issues


def _score_text_fit(layout: LayoutSpec) -> tuple[float, list[str]]:
    """Penalize text that would overflow its allocated width (0-10)."""
    score = 10.0
    issues = estimate_text_overflow_issues(layout)
    if issues:
        score -= min(10.0, len(issues) * 4.0)
    return max(0, score), issues


def _score_readability(layout: LayoutSpec, event: GigEvent) -> tuple[float, list[str]]:
    """Score text readability and information completeness (0-10)."""
    score = 10.0
    issues: list[str] = []
    
    all_text = " ".join(t.content.lower() for t in layout.text_elements)
    
    venue_lower = event.venue.lower()
    venue_words = venue_lower.split()
    if not any(word in all_text for word in venue_words if len(word) > 3):
        score -= 3
        issues.append(f"Venue name '{event.venue}' not found in text elements")
    
    date_parts = event.event_date.strftime('%B %d %Y').lower().split()
    date_found = sum(1 for part in date_parts if part in all_text)
    if date_found < 2:
        score -= 2
        issues.append("Date information missing or incomplete")
    
    band_name = __import__("os").getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    band_words = band_name.lower().split()
    if not any(word in all_text for word in band_words if len(word) > 3):
        score -= 2
        issues.append("Band name not found in text elements")

    footer_issues = validate_required_footer_text(all_text, event, band=band_name)
    if footer_issues:
        score -= 3
        issues.extend(footer_issues)
    
    photo = layout.photo_frame
    for text in layout.text_elements:
        if text_overlaps_photo(text, layout):
            score -= 5
            issues.append(f"Text overlaps photo frame: '{text.content[:30]}'")
        elif text.font_size >= 36:
            text_bottom = text.y + (text.font_size / 15)
            text_top = text.y
            if (text_top < photo.y + photo.height and 
                text_bottom > photo.y and
                text.x < photo.x + photo.width and
                text.x + text.width > photo.x):
                score -= 1
                issues.append(f"Large text '{text.content[:20]}' may overlap photo")
    
    bounds_issues = validate_layout_bounds(layout)
    if bounds_issues:
        score -= min(5.0, len(bounds_issues) * 2.5)
        issues.extend(bounds_issues)
    
    return max(0, score), issues


def _score_hierarchy(layout: LayoutSpec, event: Optional[GigEvent] = None) -> tuple[float, list[str]]:
    """Score information hierarchy (0-10)."""
    score = 10.0
    issues: list[str] = []
    
    if not layout.text_elements:
        return 0.0, ["No text elements"]
    
    sorted_by_size = sorted(layout.text_elements, key=lambda t: t.font_size, reverse=True)
    sorted_by_y = sorted(layout.text_elements, key=lambda t: t.y)
    
    largest = sorted_by_size[0] if sorted_by_size else None
    topmost = sorted_by_y[0] if sorted_by_y else None
    
    if largest and topmost and largest != topmost:
        if largest.font_size > topmost.font_size * 1.2:
            pass
        else:
            score -= 1
            issues.append("Top element should be largest or second-largest")

    if event and is_house_series_gig(event):
        band = __import__("os").getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
        band_sizes = [
            t.font_size
            for t in layout.text_elements
            if band.lower() in t.content.lower() or "featuring" in t.content.lower()
        ]
        venue_sizes = [
            t.font_size
            for t in layout.text_elements
            if any(w in t.content.lower() for w in event.venue.lower().split() if len(w) > 3)
        ]
        if band_sizes and venue_sizes and max(band_sizes) < max(venue_sizes) * 0.85:
            score -= 2
            issues.append(
                "Featured band name should be at least as prominent as series/venue title"
            )
    else:
        venue_found = False
        for text in sorted_by_size[:2]:
            if any(word in text.content.lower() for word in ["club", "bar", "legion", "vfw", "hall"]):
                venue_found = True
                break
        if not venue_found and len(sorted_by_size) >= 2:
            score -= 0.5
    
    return max(0, score), issues


def score_layout(layout: LayoutSpec, event: GigEvent) -> float:
    """Calculate overall layout quality score (0-10).
    
    Weights:
    - Visual balance: 20%
    - Typography: 25%
    - Photo integration: 25%
    - Readability: 20%
    - Hierarchy: 10%
    """
    balance_score, _ = _score_visual_balance(layout)
    typo_score, _ = _score_typography(layout)
    photo_score, _ = _score_photo_integration(layout)
    read_score, _ = _score_readability(layout, event)
    hier_score, _ = _score_hierarchy(layout, event)
    fit_score, _ = _score_text_fit(layout)
    
    overall = (
        balance_score * 0.18 +
        typo_score * 0.22 +
        photo_score * 0.22 +
        read_score * 0.18 +
        hier_score * 0.10 +
        fit_score * 0.10
    )
    
    return overall


def score_layout_detailed(layout: LayoutSpec, event: GigEvent) -> LayoutScore:
    """Calculate detailed layout quality scores with issue tracking."""
    balance_score, balance_issues = _score_visual_balance(layout)
    typo_score, typo_issues = _score_typography(layout)
    photo_score, photo_issues = _score_photo_integration(layout)
    read_score, read_issues = _score_readability(layout, event)
    hier_score, hier_issues = _score_hierarchy(layout, event)
    fit_score, fit_issues = _score_text_fit(layout)
    
    all_issues = (
        balance_issues + typo_issues + photo_issues + read_issues + hier_issues + fit_issues
    )
    
    overall = (
        balance_score * 0.18 +
        typo_score * 0.22 +
        photo_score * 0.22 +
        read_score * 0.18 +
        hier_score * 0.10 +
        fit_score * 0.10
    )
    
    return LayoutScore(
        visual_balance=balance_score,
        typography=typo_score,
        photo_integration=photo_score,
        readability=read_score,
        hierarchy=hier_score,
        overall=overall,
        issues=all_issues,
    )
