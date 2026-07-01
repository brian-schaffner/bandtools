"""Structured Layout Mode: AI as Art Director, deterministic rendering.

This module implements an alternative flyer generation mode where:
1. AI produces a layout specification (JSON), NOT a finished image
2. The band photo is immutable source artwork (never regenerated)
3. Final flyer is rendered deterministically from spec + photo

Used for Options B and C while Option A uses the existing AI image workflow.
"""

from structured_layout.fixed_templates import (
    create_default_collage_layout,
    create_default_handbill_layout,
    create_simple_stack_layout,
    layout_for_option,
)
from structured_layout.tier_archetypes import TierArchetype, load_tier_archetype
from structured_layout.layout_spec import (
    LayoutSpec,
    TextElement,
    PhotoFrame,
    GraphicElement,
    BackgroundSpec,
    ColorSpec,
    DesignStyle,
    TextAlignment,
    FontWeight,
    PhotoPlacement,
    finalize_layout_spec,
    inject_canonical_event_text,
    sanitize_band_photo_frame,
)
from structured_layout.art_director import (
    generate_layout_spec,
    generate_layout_with_retry,
)
from structured_layout.layout_scorer import (
    score_layout,
    score_layout_detailed,
    LayoutScore,
)
from structured_layout.structured_renderer import render_flyer, estimate_text_overflow_issues
from structured_layout.validation import validate_structured_flyer, StructuredValidationResult

__all__ = [
    # Layout spec
    "LayoutSpec",
    "TextElement",
    "PhotoFrame",
    "GraphicElement",
    "BackgroundSpec",
    "ColorSpec",
    "DesignStyle",
    "TextAlignment",
    "FontWeight",
    "PhotoPlacement",
    "create_default_handbill_layout",
    "create_default_collage_layout",
    "create_simple_stack_layout",
    "layout_for_option",
    "load_tier_archetype",
    "TierArchetype",
    "finalize_layout_spec",
    "inject_canonical_event_text",
    "sanitize_band_photo_frame",
    # Art Director
    "generate_layout_spec",
    "generate_layout_with_retry",
    # Scorer
    "score_layout",
    "score_layout_detailed",
    "LayoutScore",
    # Renderer
    "render_flyer",
    "estimate_text_overflow_issues",
    # Validation
    "validate_structured_flyer",
    "StructuredValidationResult",
]
