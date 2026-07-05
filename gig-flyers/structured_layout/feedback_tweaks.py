"""Apply natural-language revision feedback to structured layout specs."""

from __future__ import annotations

import colorsys
import re
from copy import deepcopy
from typing import Optional

from structured_layout.layout_spec import ColorSpec, LayoutSpec, TextElement


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


def apply_revision_feedback(layout: LayoutSpec, feedback: Optional[str]) -> LayoutSpec:
    """Return a copy of layout with simple feedback-driven tweaks applied."""
    text = (feedback or "").strip()
    if not text:
        return layout

    spec = deepcopy(layout)
    scale = _font_scale(text)
    lower = text.lower()

    if scale != 1.0:
        updated: list[TextElement] = []
        for element in spec.text_elements:
            updated.append(
                TextElement(
                    content=element.content,
                    x=element.x,
                    y=element.y,
                    width=element.width,
                    font_size=max(12, int(round(element.font_size * scale))),
                    font_family=element.font_family,
                    font_weight=element.font_weight,
                    color=element.color,
                    alignment=element.alignment,
                    rotation=element.rotation,
                    letter_spacing=element.letter_spacing,
                    line_height=element.line_height,
                    all_caps=element.all_caps,
                )
            )
        spec.text_elements = updated

    bg = spec.background.color.hex
    if any(word in lower for word in ("vibrant", "saturated", "bold color", "pop")):
        bg = _adjust_color(bg, saturation=1.35, lightness=1.05)
    if any(word in lower for word in ("warmer", "mustard", "gold", "amber")):
        bg = _adjust_color(bg, saturation=1.2, lightness=1.08)
        if "mustard" in lower or "gold" in lower:
            bg = "#D4A017"
    if any(word in lower for word in ("darker", "moody")):
        bg = _adjust_color(bg, saturation=1.05, lightness=0.82)

    spec.background.color = ColorSpec(hex=bg, opacity=spec.background.color.opacity)
    note = f"Revision feedback: {text[:120]}"
    spec.style_notes = f"{spec.style_notes} | {note}".strip(" |")
    return spec
