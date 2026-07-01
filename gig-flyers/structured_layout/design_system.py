"""Professional design tokens and layout polish for structured flyers.

Provides a modular type scale, 8px-equivalent spacing grid, and a polish pass
that snaps templates to intentional hierarchy without re-enabling AI coords.
"""

from __future__ import annotations

import re
from typing import Optional

from text_validation import ADDRESS_ZIP_RE, MONTH_NAME_RE, YEAR_RE

from structured_layout.layout_geometry import (
    MAX_TEXT_WIDTH_PCT,
    TEXT_MARGIN_X_PCT,
    VERTICAL_GAP_PCT,
)
from structured_layout.layout_spec import (
    BackgroundSpec,
    ColorSpec,
    FontWeight,
    GraphicElement,
    LayoutSpec,
    TextAlignment,
    TextElement,
)

# --- Type scale (1.25 modular ratio, base 16pt) ---
SCALE_RATIO = 1.25
BASE_PT = 16

TYPE_XS = 16   # footer / utility
TYPE_SM = 20   # date, time facts
TYPE_MD = 25   # featuring, secondary headlines
TYPE_LG = 39   # venue display
TYPE_XL = 61   # band headline
TYPE_XXL = 76  # broadside hero band

PRO_MIN_FONT_PT = 16

# --- Spacing (8px grid ≈ 0.52% on 1536 canvas; snap to 0.5%) ---
GRID_UNIT_PCT = 0.5
PRO_GAP_PCT = 1.5  # ~24px rhythm

# --- Font pairing ---
FONT_DISPLAY = "Impact"
FONT_DISPLAY_HEAVY = "Arial Black"
FONT_BODY_CONDENSED = "Helvetica Bold Condensed"
FONT_BODY = "Arial"

# --- Photo composition ---
PHOTO_MIN_WIDTH_PASTEUP = 48.0
PHOTO_MAX_WIDTH_PASTEUP = 52.0
PHOTO_MIN_HEIGHT_STACK = 47.0
PHOTO_MAX_HEIGHT_STACK = 50.0
PHOTO_ASPECT_4_3 = 4 / 3
PHOTO_ASPECT_16_10 = 16 / 10


def modular_scale(step: int) -> int:
    """Return font size at modular step (0 = base 16pt)."""
    return max(PRO_MIN_FONT_PT, round(BASE_PT * (SCALE_RATIO**step)))


def snap_pct(value: float, unit: float = GRID_UNIT_PCT) -> float:
    """Snap a percentage coordinate to the layout grid."""
    return round(round(value / unit) * unit, 1)


def nearest_scale_size(size: int, *, floor: int = PRO_MIN_FONT_PT) -> int:
    """Map arbitrary pt size to nearest modular scale step."""
    best = floor
    best_diff = abs(size - floor)
    for step in range(10):
        candidate = modular_scale(step)
        diff = abs(size - candidate)
        if diff < best_diff:
            best = candidate
            best_diff = diff
    return best


def _text_role(content: str) -> str:
    """Lightweight role guess for typography polish."""
    lower = content.lower()
    if ADDRESS_ZIP_RE.search(content):
        return "address"
    if MONTH_NAME_RE.search(lower) and YEAR_RE.search(lower):
        return "date"
    if re.search(r"\d{1,2}:\d{2}|\b\d{1,2}\s*(am|pm)\b", lower):
        return "time"
    if "featuring" in lower:
        return "featuring"
    if content.isupper() and len(content) > 12:
        return "venue"
    return "other"


def _tier_from_layout(layout: LayoutSpec) -> str:
    notes = (layout.style_notes or "").lower()
    if "conservative" in notes or "photocopy stack" in notes:
        return "conservative"
    if layout.design_style.value == "collage" or "creative" in notes:
        return "creative"
    return "medium"


def _role_font(role: str, tier: str) -> str:
    if role == "venue":
        return FONT_DISPLAY
    if role in ("featuring", "other") and tier == "creative":
        return FONT_DISPLAY_HEAVY
    if role in ("date", "time", "address"):
        return FONT_BODY_CONDENSED
    if role == "featuring":
        return FONT_BODY_CONDENSED
    return FONT_DISPLAY_HEAVY if tier != "conservative" else FONT_BODY_CONDENSED


def _role_size(role: str, tier: str, current: int) -> int:
    """Optical sizing by role — max 3 tiers per layout enforced later."""
    if role == "address":
        target = TYPE_XS
    elif role in ("date", "time"):
        target = TYPE_SM
    elif role == "featuring":
        target = TYPE_MD
    elif role == "venue":
        target = TYPE_LG if tier != "creative" else TYPE_XL
    else:
        target = TYPE_XL if tier == "creative" else TYPE_MD
    snapped = nearest_scale_size(current)
    if abs(snapped - target) <= modular_scale(1) - BASE_PT:
        return snapped
    return nearest_scale_size(target)


def _polish_typography(layout: LayoutSpec, tier: str) -> LayoutSpec:
    updated: list[TextElement] = []
    for text in layout.text_elements:
        role = _text_role(text.content)
        font_family = text.font_family
        if font_family in ("Helvetica Bold Condensed", "Helvetica", "Arial"):
            font_family = _role_font(role, tier)
        elif role == "venue" and text.font_family not in (FONT_DISPLAY, FONT_DISPLAY_HEAVY):
            font_family = FONT_DISPLAY
        elif role in ("date", "time", "address"):
            font_family = FONT_BODY_CONDENSED

        font_size = max(PRO_MIN_FONT_PT, _role_size(role, tier, text.font_size))
        weight = text.font_weight
        if role in ("venue", "other") and tier != "conservative":
            weight = FontWeight.BLACK
        elif role in ("date", "time"):
            weight = FontWeight.BOLD

        updated.append(
            TextElement(
                content=text.content,
                x=snap_pct(text.x),
                y=snap_pct(text.y),
                width=snap_pct(min(text.width, MAX_TEXT_WIDTH_PCT)),
                font_size=font_size,
                font_family=font_family,
                font_weight=weight,
                color=text.color,
                alignment=text.alignment,
                rotation=text.rotation,
                letter_spacing=text.letter_spacing,
                line_height=text.line_height,
                all_caps=text.all_caps,
            )
        )
    layout.text_elements = _limit_type_sizes(updated)
    return layout


def _limit_type_sizes(elements: list[TextElement], max_sizes: int = 3) -> list[TextElement]:
    """Keep at most max_sizes distinct font sizes; collapse outliers."""
    if len(elements) <= 1:
        return elements
    sizes = sorted({e.font_size for e in elements}, reverse=True)
    if len(sizes) <= max_sizes:
        return elements
    keep = set(sizes[:max_sizes])
    smallest_kept = min(keep)
    result: list[TextElement] = []
    for el in elements:
        if el.font_size in keep:
            result.append(el)
            continue
        result.append(
            TextElement(
                content=el.content,
                x=el.x,
                y=el.y,
                width=el.width,
                font_size=smallest_kept,
                font_family=el.font_family,
                font_weight=el.font_weight,
                color=el.color,
                alignment=el.alignment,
                rotation=el.rotation,
                letter_spacing=el.letter_spacing,
                line_height=el.line_height,
                all_caps=el.all_caps,
            )
        )
    return result


def _polish_photo(layout: LayoutSpec, tier: str) -> LayoutSpec:
    frame = layout.photo_frame
    notes = (layout.style_notes or "").lower()

    frame.x = snap_pct(frame.x)
    frame.y = snap_pct(frame.y)
    frame.width = snap_pct(frame.width)
    frame.height = snap_pct(frame.height)

    if "paste-up" in notes or "two-column" in notes:
        if frame.width < PHOTO_MIN_WIDTH_PASTEUP:
            delta = PHOTO_MIN_WIDTH_PASTEUP - frame.width
            frame.width = PHOTO_MIN_WIDTH_PASTEUP
            if frame.x > 50:
                frame.x = max(snap_pct(frame.x - delta), 48.0)
        frame.width = min(frame.width, PHOTO_MAX_WIDTH_PASTEUP)
        if frame.height < 42.0:
            frame.height = snap_pct(46.0)
        frame.rotation = round(max(-1.5, min(1.5, frame.rotation)), 1)

    elif tier == "conservative":
        frame.height = snap_pct(
            max(PHOTO_MIN_HEIGHT_STACK, min(frame.height, PHOTO_MAX_HEIGHT_STACK))
        )
        frame.width = snap_pct(MAX_TEXT_WIDTH_PCT)
        frame.x = TEXT_MARGIN_X_PCT
        frame.rotation = 0.0

    elif "broadside" in notes or "inverted footer" in notes or "troubadour" in notes:
        if frame.width >= MAX_TEXT_WIDTH_PCT - 2:
            target_h = frame.width / PHOTO_ASPECT_16_10 * (100 / 90) * 0.9
            frame.height = snap_pct(max(frame.height, min(target_h, 50.0)))
        frame.rotation = round(max(-1.0, min(1.0, frame.rotation)), 1)

    elif "showbill" in notes:
        frame.rotation = round(max(-2.0, min(2.0, frame.rotation)), 1)
        frame.border_width = max(frame.border_width, 5.0)
        if frame.width > 52:
            frame.x = snap_pct(min(frame.x, 100 - frame.width - TEXT_MARGIN_X_PCT))

    else:
        if frame.width > 70 and frame.height < 40:
            frame.height = snap_pct(frame.width / PHOTO_ASPECT_4_3 * 0.55)

    frame.opacity = 1.0
    frame.film_grain = min(frame.film_grain, 0.010)
    return layout


def _polish_accents(layout: LayoutSpec) -> LayoutSpec:
    updated: list[GraphicElement] = []
    for el in layout.graphic_elements:
        el.x = snap_pct(el.x)
        el.y = snap_pct(el.y)
        el.width = snap_pct(el.width)
        el.height = snap_pct(el.height)

        if el.element_type == "starburst":
            el.width = max(el.width, 18.0)
            el.height = max(el.height, 12.0)
            el.width = snap_pct(min(el.width, 24.0))
            el.height = snap_pct(min(el.height, 16.0))
        elif el.element_type == "stamp":
            el.width = snap_pct(max(el.width, 14.0))
            el.height = snap_pct(max(el.height, 8.0))
        elif el.element_type == "tape":
            el.width = snap_pct(max(el.width, 12.0))
            el.height = snap_pct(max(el.height, 3.5))

        updated.append(el)
    layout.graphic_elements = updated
    return layout


def _polish_bars(layout: LayoutSpec, tier: str) -> LayoutSpec:
    """Tighter bar height ratios for conservative stack."""
    if tier != "conservative":
        return layout
    bars = [g for g in layout.graphic_elements if g.element_type == "box" and g.height > 2.0]
    if not bars:
        return layout
    target_h = snap_pct(6.0)
    updated: list[GraphicElement] = []
    for el in layout.graphic_elements:
        if el.element_type == "box" and el.height > 2.0 and el.width >= MAX_TEXT_WIDTH_PCT - 5:
            el.height = target_h
        updated.append(el)
    layout.graphic_elements = updated
    return layout


def _polish_footer_band(layout: LayoutSpec) -> LayoutSpec:
    """Integrate address into a designed footer band instead of orphaned text."""
    canvas_h = layout.canvas_height
    footer_threshold = round((canvas_h - 48 * 4) / canvas_h * 100, 1) - 4

    address_indices = [
        i
        for i, t in enumerate(layout.text_elements)
        if ADDRESS_ZIP_RE.search(t.content) or t.y >= footer_threshold
    ]
    if not address_indices:
        return layout

    min_y = min(layout.text_elements[i].y for i in address_indices)
    band_top = snap_pct(max(min_y - 1.0, footer_threshold - 2))
    band_h = snap_pct(8.0)

    has_footer_band = any(
        g.element_type == "box"
        and g.y >= footer_threshold - 6
        and g.width >= MAX_TEXT_WIDTH_PCT - 5
        for g in layout.graphic_elements
    )
    if not has_footer_band:
        bg = layout.background.color.hex
        band_color = "#1A1A1A" if _luminance(bg) > 140 else "#F0EBE0"
        layout.graphic_elements.append(
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=band_top,
                width=MAX_TEXT_WIDTH_PCT,
                height=band_h,
                fill_color=ColorSpec(band_color, opacity=0.08 if _luminance(bg) > 140 else 0.15),
            )
        )

    for idx in address_indices:
        text = layout.text_elements[idx]
        layout.text_elements[idx] = TextElement(
            content=text.content,
            x=TEXT_MARGIN_X_PCT,
            y=snap_pct(band_top + 1.5),
            width=MAX_TEXT_WIDTH_PCT,
            font_size=max(PRO_MIN_FONT_PT, nearest_scale_size(TYPE_XS)),
            font_family=FONT_BODY_CONDENSED,
            font_weight=FontWeight.NORMAL,
            color=text.color,
            alignment=TextAlignment.CENTER,
            rotation=text.rotation,
            letter_spacing=text.letter_spacing,
            line_height=text.line_height,
            all_caps=text.all_caps,
        )
    return layout


def _polish_background(layout: LayoutSpec, tier: str) -> LayoutSpec:
    bg = layout.background
    if tier == "conservative":
        bg.texture = "paper"
        bg.texture_strength = min(bg.texture_strength, 0.18)
        bg.grain_strength = min(bg.grain_strength, 0.04)
    elif tier == "medium":
        bg.texture_strength = min(bg.texture_strength, 0.28)
    layout.photocopy_effect = 0.0
    layout.age_effect = 0.0
    return layout


def _luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def apply_pro_polish(layout: LayoutSpec) -> LayoutSpec:
    """Snap layout to professional design tokens: type, spacing, photo, accents."""
    tier = _tier_from_layout(layout)
    layout = _polish_background(layout, tier)
    layout = _polish_photo(layout, tier)
    layout = _polish_bars(layout, tier)
    layout = _polish_typography(layout, tier)
    layout = _polish_accents(layout)
    layout = _polish_footer_band(layout)
    return layout
