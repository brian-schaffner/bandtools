"""AI Art Director: generates layout specifications, NOT finished images.

The Art Director uses AI to produce a structured JSON layout spec that defines:
- Typography placement and hierarchy
- Photo frame position and treatments (crop, color grade, masking)
- Graphic elements (boxes, dividers, stamps, tape)
- Background and texture settings

The actual rendering is done deterministically by the structured_renderer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from gig_calendar import GigEvent
from structured_layout.fixed_templates import (
    create_collage_layout,
    create_handbill_layout,
    layout_for_option,
)
from structured_layout.layout_spec import (
    LayoutSpec,
    DesignStyle,
    finalize_layout_spec,
)
from image_providers.reference_compose import SAFE_MARGIN_PX
from text_validation import (
    footer_prompt_lines,
    is_house_series_gig,
    featured_act_line,
    resolve_venue_address,
    typography_hierarchy_prompt_lines,
)
from progress_helper import ProgressCallback, emit_progress


# Minimum and maximum layout generation attempts before giving up
MIN_LAYOUT_ATTEMPTS = 1
MAX_LAYOUT_ATTEMPTS = 3
DEFAULT_QUALITY_THRESHOLD = 7.0


def _get_art_director_model() -> str:
    """Get the AI model for layout generation."""
    return os.getenv("LAYOUT_ART_DIRECTOR_MODEL", "gpt-4o-mini")


def _build_art_director_prompt(
    event: GigEvent,
    design_style: DesignStyle,
    variation_notes: str = "",
    research: Optional[dict[str, Any]] = None,
) -> str:
    """Build the prompt for the AI Art Director."""
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    
    style_guidance = {
        DesignStyle.HANDBILL: (
            "Classic club HANDBILL style:\n"
            "- Utilitarian, type-heavy layout\n"
            "- Venue name HUGE at top\n"
            "- Stacked vertical layout, centered\n"
            "- Black/white or one accent color only\n"
            "- Photocopy texture, slightly rough\n"
            "- Band photo centered below text\n"
            "- Simple dividers, no fancy graphics\n"
            "- Looks like it was made in 10 minutes"
        ),
        DesignStyle.COLLAGE: (
            "PASTE-UP COLLAGE style:\n"
            "- Layered, offset composition\n"
            "- Slight rotations on elements (max ±3°)\n"
            "- Torn paper edges, tape marks\n"
            "- Mixed typography weights and sizes\n"
            "- Photo placed at angle with white border\n"
            "- Stamps, stickers, or hand-drawn marks\n"
            "- Warm paper/cardboard background\n"
            "- Looks assembled from cut-outs"
        ),
    }
    
    venue_context = ""
    if research:
        venue_type = research.get("venue_type", "regional_club")
        design_lang = research.get("design_language", "")
        venue_context = f"\nVenue type: {venue_type}\nDesign language: {design_lang}"

    address = resolve_venue_address(event)
    hierarchy_block = "\n".join(typography_hierarchy_prompt_lines(event, band=band))
    footer_block = "\n".join(footer_prompt_lines(event, band=band))
    house_note = ""
    if is_house_series_gig(event):
        house_note = (
            f"\nHOUSE SHOW: Header = '{event.venue}', sub-header = '{featured_act_line(band)}' "
            f"(each once). Footer = street address only — do NOT repeat venue or band in footer.\n"
        )

    return f'''You are an expert Art Director creating a flyer layout specification.

TASK: Generate a JSON layout spec for a concert flyer.
DO NOT generate an image. Generate a structured layout specification.

EVENT DETAILS (must appear clearly on flyer):
- Venue: {event.venue}
- Date: {event.event_date.strftime('%A, %B %d, %Y')}
- Band: {band}
- Time: {event.time_label or 'TBA'}
{f"- Address (footer): {address}" if address else ""}
{venue_context}
{house_note}
{hierarchy_block}
{footer_block}

DESIGN STYLE: {design_style.value}
{style_guidance.get(design_style, "")}

{variation_notes}

CANVAS: 1024x1536 pixels (portrait)
All positions are percentages (0-100) of canvas dimensions.
SAFE MARGINS: keep all text at least {SAFE_MARGIN_PX}px ({round(SAFE_MARGIN_PX / 15.36, 1)}% of height) from top, sides, and bottom.

CRITICAL RULES:
1. The band photo is IMMUTABLE. You specify placement, crop, and color treatment ONLY.
2. Photo treatments allowed: crop (%), brightness, contrast, saturation, film_grain, halftone, rotation (max ±2°).
3. Photo treatments FORBIDDEN: Any description of regenerating, redrawing, or modifying the people.
4. All text must be fully readable and not overlap the photo.
5. MANDATORY FOOTER: readable address in bottom margin — never a grey placeholder bar.
6. Do NOT add grey bars, brush strokes, or decorative placeholder strips below the photo.
7. Information hierarchy: see TYPOGRAPHY HIERARCHY above — each fact (venue, band, date, time, address) appears ONCE.
8. HOUSE / JAM shows: series title + featuring line in header; footer is address-only (no repeated venue or band).

OUTPUT FORMAT: Return ONLY valid JSON matching this schema:
{{
  "design_style": "{design_style.value}",
  "style_notes": "Brief description of the design approach",
  "background": {{
    "color": {{"hex": "#F5F0E6", "opacity": 1.0}},
    "texture": "paper|photocopy|cardboard|none",
    "texture_strength": 0.0-1.0,
    "grain_strength": 0.0-0.1
  }},
  "photo_frame": {{
    "x": 0-100, "y": 0-100, "width": 0-100, "height": 0-100,
    "placement": "top|center|bottom|left|right|full_bleed",
    "rotation": -2.0 to 2.0,
    "crop": {{"top": 0-20, "bottom": 0-20, "left": 0-20, "right": 0-20}},
    "edge_feather": 0-10,
    "border_width": 0-10,
    "border_color": {{"hex": "#FFFFFF"}},
    "brightness": 0.8-1.2,
    "contrast": 0.8-1.2,
    "saturation": 0.5-1.2,
    "film_grain": 0.0-0.1,
    "halftone": true|false,
    "paper_texture": 0.0-0.3,
    "mask_shape": "rectangle|rounded|torn_edge|circle",
    "mask_corner_radius": 0-20,
    "blend_mode": "normal|multiply|screen|overlay",
    "opacity": 0.8-1.0
  }},
  "text_elements": [
    {{
      "content": "TEXT CONTENT",
      "x": 0-100, "y": 0-100, "width": 0-100,
      "font_size": 24-120,
      "font_family": "Helvetica Bold Condensed",
      "font_weight": "normal|bold|black",
      "color": {{"hex": "#000000", "opacity": 1.0}},
      "alignment": "left|center|right",
      "rotation": -5.0 to 5.0,
      "letter_spacing": -0.05 to 0.2,
      "line_height": 0.9-1.5,
      "all_caps": true|false
    }}
  ],
  "graphic_elements": [
    {{
      "element_type": "box|line|divider|starburst|stamp|tape|torn_edge",
      "x": 0-100, "y": 0-100, "width": 0-100, "height": 0-100,
      "fill_color": {{"hex": "#000000", "opacity": 0.0-1.0}},
      "stroke_color": {{"hex": "#000000", "opacity": 0.0-1.0}},
      "stroke_width": 0-5,
      "rotation": -45 to 45,
      "opacity": 0.0-1.0,
      "corner_radius": 0-20,
      "properties": {{}}
    }}
  ],
  "photocopy_effect": 0.0-0.3,
  "age_effect": 0.0-0.2
}}

Return ONLY the JSON object, no explanation.'''


def _default_layout(
    event: GigEvent,
    band: str,
    design_style: DesignStyle,
    *,
    option: str = "B",
) -> LayoutSpec:
    date_str = event.event_date.strftime('%A, %B %d, %Y')
    time_str = event.time_label or 'TBA'
    address = resolve_venue_address(event)
    letter = option.upper() if option else (
        "C" if design_style == DesignStyle.COLLAGE else "B"
    )
    return layout_for_option(
        letter,
        event.venue,
        band,
        date_str,
        time_str,
        address=address,
        event=event,
    )


def _use_fixed_templates() -> bool:
    """True when production should use hand-coded templates (default on)."""
    raw = os.getenv("USE_FIXED_TEMPLATES", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _use_ai_layout() -> bool:
    """True when Art Director LLM coordinate generation is enabled."""
    if _use_fixed_templates():
        return False
    backend = os.getenv("LAYOUT_BACKEND", "pictex").strip().lower()
    if backend == "pictex":
        return False
    return os.getenv("STRUCTURED_LAYOUT_USE_AI", "").strip().lower() in {"1", "true", "yes"}


def generate_layout_spec(
    event: GigEvent,
    design_style: DesignStyle,
    research: Optional[dict[str, Any]] = None,
    variation_notes: str = "",
    on_progress: Optional[ProgressCallback] = None,
    option: str = "",
) -> LayoutSpec:
    """Use AI to generate a layout specification.
    
    Args:
        event: The gig event with venue, date, time info
        design_style: HANDBILL or COLLAGE style
        research: Optional venue research context
        variation_notes: Extra guidance for this variation
        on_progress: Progress callback
        option: Option letter (B or C)
    
    Returns:
        LayoutSpec object ready for rendering
    """
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    
    if not _use_ai_layout():
        emit_progress(
            on_progress,
            step="layout",
            substep="template",
            message=f"Using fixed {design_style.value} template for option {option} (AI layout disabled)",
            option=option,
        )
        return _default_layout(event, band, design_style, option=option)
    
    emit_progress(
        on_progress,
        step="layout",
        substep="art_director",
        message=f"Art Director generating {design_style.value} layout for option {option}...",
        option=option,
    )
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        emit_progress(
            on_progress,
            step="layout",
            substep="fallback",
            message=f"No API key, using default {design_style.value} layout",
            option=option,
        )
        if design_style == DesignStyle.COLLAGE:
            return _default_layout(event, band, design_style, option=option)
        return _default_layout(event, band, design_style, option=option)
    
    try:
        from openai import OpenAI
    except ImportError:
        emit_progress(
            on_progress,
            step="layout",
            substep="fallback",
            message="OpenAI not installed, using default layout",
            option=option,
        )
        if design_style == DesignStyle.COLLAGE:
            return _default_layout(event, band, design_style, option=option)
        return _default_layout(event, band, design_style, option=option)
    
    client = OpenAI(api_key=api_key)
    model = _get_art_director_model()
    prompt = _build_art_director_prompt(event, design_style, variation_notes, research)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.7,
        )
        
        raw_json = response.choices[0].message.content or "{}"
        layout_data = json.loads(raw_json)
        
        layout_data.setdefault("canvas_width", 1024)
        layout_data.setdefault("canvas_height", 1536)
        
        layout = LayoutSpec.from_dict(layout_data)
        layout = finalize_layout_spec(
            layout,
            event.venue,
            band,
            event.time_label or "TBA",
            address=resolve_venue_address(event),
            event=event,
        )
        
        emit_progress(
            on_progress,
            step="layout",
            substep="generated",
            message=f"Layout spec generated for option {option}",
            option=option,
        )
        
        return layout
        
    except Exception as exc:
        emit_progress(
            on_progress,
            step="layout",
            substep="error",
            message=f"Layout generation failed: {exc}, using default",
            option=option,
        )
        if design_style == DesignStyle.COLLAGE:
            return _default_layout(event, band, design_style, option=option)
        return _default_layout(event, band, design_style, option=option)


def generate_layout_with_retry(
    event: GigEvent,
    design_style: DesignStyle,
    research: Optional[dict[str, Any]] = None,
    variation_notes: str = "",
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    max_attempts: int = MAX_LAYOUT_ATTEMPTS,
    on_progress: Optional[ProgressCallback] = None,
    option: str = "",
    score_layout_fn: Optional[callable] = None,
) -> tuple[LayoutSpec, float]:
    """Generate layout with quality scoring and retry.
    
    Generates layouts until one exceeds the quality threshold or max attempts reached.
    
    Args:
        event: The gig event
        design_style: HANDBILL or COLLAGE
        research: Optional venue research
        variation_notes: Extra guidance
        quality_threshold: Minimum score to accept (0-10)
        max_attempts: Maximum generation attempts
        on_progress: Progress callback
        option: Option letter
        score_layout_fn: Optional custom scoring function
    
    Returns:
        Tuple of (best_layout, score)
    """
    from structured_layout.layout_scorer import score_layout
    
    scorer = score_layout_fn or score_layout
    best_layout: Optional[LayoutSpec] = None
    best_score: float = 0.0
    
    for attempt in range(1, max_attempts + 1):
        emit_progress(
            on_progress,
            step="layout",
            substep="attempt",
            message=f"Layout attempt {attempt}/{max_attempts} for option {option}",
            option=option,
            attempt=attempt,
        )
        
        layout = generate_layout_spec(
            event,
            design_style,
            research=research,
            variation_notes=variation_notes,
            on_progress=on_progress,
            option=option,
        )
        
        score = scorer(layout, event)
        
        emit_progress(
            on_progress,
            step="layout",
            substep="scored",
            message=f"Layout score: {score:.1f}/10",
            option=option,
            attempt=attempt,
        )
        
        if score > best_score:
            best_layout = layout
            best_score = score
        
        if score >= quality_threshold:
            emit_progress(
                on_progress,
                step="layout",
                substep="accepted",
                message=f"Layout accepted with score {score:.1f}/10",
                option=option,
            )
            return layout, score
    
    emit_progress(
        on_progress,
        step="layout",
        substep="best_effort",
        message=f"Using best layout (score {best_score:.1f}/10) after {max_attempts} attempts",
        option=option,
    )
    
    return best_layout or layout, best_score
