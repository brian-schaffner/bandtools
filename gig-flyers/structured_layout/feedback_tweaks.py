"""Apply natural-language revision feedback to structured layout specs."""

from __future__ import annotations

import colorsys
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Optional

from structured_layout.layout_spec import ColorSpec, LayoutSpec, TextElement

if TYPE_CHECKING:
    from flyer_agent.revision_brief import RevisionBrief

# Distinct palettes when fanning out one base option into three variants (e.g. pastel).
PASTEL_VARIANTS = (
    {"bg": "#FADADD", "text": "#7A5C6A", "label": "blush pastel"},
    {"bg": "#D4E4F7", "text": "#4A5F7A", "label": "sky pastel"},
    {"bg": "#D8F3DC", "text": "#4A6B55", "label": "mint pastel"},
)

WARM_VARIANTS = (
    {"bg": "#F5E6C8", "text": "#6B4E2E", "label": "warm cream"},
    {"bg": "#E8C872", "text": "#5C4518", "label": "mustard gold"},
    {"bg": "#D4A017", "text": "#3D2E08", "label": "deep amber"},
)


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    raw = (hex_color or "#000000").lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    try:
        r = int(raw[0:2], 16) / 255.0
        g = int(raw[2:4], 16) / 255.0
        b = int(raw[4:6], 16) / 255.0
        return r, g, b
    except ValueError:
        return 0.0, 0.0, 0.0


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(r * 255))),
        max(0, min(255, int(g * 255))),
        max(0, min(255, int(b * 255))),
    )


def _adjust_color(hex_color: str, *, saturation: float = 1.0, lightness: float = 1.0) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = max(0.0, min(1.0, s * saturation))
    v = max(0.0, min(1.0, v * lightness))
    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
    return _rgb_to_hex(nr, ng, nb)


def _font_scale(feedback: str) -> float:
    lower = feedback.lower()
    if re.search(r"\b(larger|bigger|increase)\b.*\b(font|headline|text|type)\b", lower):
        return 1.28
    if re.search(r"\b(font|headline|text|type)\b.*\b(larger|bigger)\b", lower):
        return 1.28
    if re.search(r"\b(smaller|reduce)\b.*\b(font|headline|text|type)\b", lower):
        return 0.82
    if re.search(r"\b(font|headline|text|type)\b.*\b(smaller)\b", lower):
        return 0.82
    return 1.0


def _variant_palette(feedback: str, variant_index: int, variant_count: int) -> Optional[dict[str, str]]:
    lower = feedback.lower()
    idx = variant_index % max(variant_count, 1)
    if "pastel" in lower or "soft color" in lower or "muted color" in lower:
        return PASTEL_VARIANTS[idx % len(PASTEL_VARIANTS)]
    if any(word in lower for word in ("warmer", "mustard", "gold", "amber")):
        return WARM_VARIANTS[idx % len(WARM_VARIANTS)]
    return None


def apply_revision_feedback(
    layout: LayoutSpec,
    feedback: Optional[str],
    *,
    variant_index: int = 0,
    variant_count: int = 1,
    revision_brief: Optional["RevisionBrief"] = None,
) -> LayoutSpec:
    """Return a copy of layout with feedback-driven tweaks (and optional variant palette)."""
    text = (feedback or "").strip()
    if not text and not revision_brief:
        return layout

    spec = deepcopy(layout)
    brief_variant = revision_brief.variant_at(variant_index, variant_count) if revision_brief else None
    scale = revision_brief.font_scale if revision_brief and revision_brief.font_scale != 1.0 else _font_scale(text)
    lower = text.lower()
    palette = None
    if brief_variant:
        palette = {"bg": brief_variant.bg, "text": brief_variant.text, "label": brief_variant.label}
    else:
        palette = _variant_palette(text, variant_index, variant_count)

    if scale != 1.0:
        updated: list[TextElement] = []
        for element in spec.text_elements:
            text_color = element.color
            if palette:
                text_color = ColorSpec(hex=palette["text"], opacity=element.color.opacity)
            updated.append(
                TextElement(
                    content=element.content,
                    x=element.x,
                    y=element.y,
                    width=element.width,
                    font_size=max(12, int(round(element.font_size * scale))),
                    font_family=element.font_family,
                    font_weight=element.font_weight,
                    color=text_color,
                    alignment=element.alignment,
                    rotation=element.rotation,
                    letter_spacing=element.letter_spacing,
                    line_height=element.line_height,
                    all_caps=element.all_caps,
                )
            )
        spec.text_elements = updated
    elif palette:
        spec.text_elements = [
            TextElement(
                content=element.content,
                x=element.x,
                y=element.y,
                width=element.width,
                font_size=element.font_size,
                font_family=element.font_family,
                font_weight=element.font_weight,
                color=ColorSpec(hex=palette["text"], opacity=element.color.opacity),
                alignment=element.alignment,
                rotation=element.rotation,
                letter_spacing=element.letter_spacing,
                line_height=element.line_height,
                all_caps=element.all_caps,
            )
            for element in spec.text_elements
        ]

    if palette:
        bg = palette["bg"]
    else:
        bg = spec.background.color.hex
        if any(word in lower for word in ("vibrant", "saturated", "bold color", "pop")):
            bg = _adjust_color(bg, saturation=1.35, lightness=1.05)
        if any(word in lower for word in ("warmer", "mustard", "gold", "amber")):
            bg = _adjust_color(bg, saturation=1.2, lightness=1.08)
            if "mustard" in lower or "gold" in lower:
                bg = "#D4A017"
        if any(word in lower for word in ("darker", "moody")):
            bg = _adjust_color(bg, saturation=1.05, lightness=0.82)
        if "pastel" in lower:
            bg = PASTEL_VARIANTS[variant_index % len(PASTEL_VARIANTS)]["bg"]

    spec.background.color = ColorSpec(hex=bg, opacity=spec.background.color.opacity)
    variant_note = (palette or {}).get("label") or (brief_variant.label if brief_variant else f"variant {variant_index + 1}")
    summary = revision_brief.summary if revision_brief and revision_brief.summary else text[:100]
    note = f"Revision feedback ({variant_note}): {summary}"
    spec.style_notes = f"{spec.style_notes} | {note}".strip(" |")
    return spec
