"""Shared bbox estimation and photo/text separation for structured layout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw, ImageFont

from text_validation import MONTH_NAME_RE, YEAR_RE, ADDRESS_ZIP_RE, ADDRESS_STREET_RE

if TYPE_CHECKING:
    from structured_layout.layout_spec import LayoutSpec, TextElement, FontWeight, TextAlignment

MAX_TEXT_WIDTH_PCT = 90.0
TEXT_MARGIN_X_PCT = 5.0
VERTICAL_GAP_PCT = 1.2


def _get_font(family: str, size: int, weight: Any) -> ImageFont.FreeTypeFont:
    from structured_layout.structured_renderer import _get_font as renderer_get_font

    return renderer_get_font(family, size, weight)


def _fit_font(
    draw: ImageDraw.ImageDraw,
    content: str,
    family: str,
    size: int,
    weight: Any,
    max_width_px: int,
    *,
    min_size: int = 12,
) -> ImageFont.FreeTypeFont:
    from structured_layout.structured_renderer import _fit_text_font

    font, _size = _fit_text_font(
        draw, content, family, size, weight, max_width_px, min_size=min_size
    )
    return font


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    content: str,
    font: ImageFont.FreeTypeFont,
    max_width_px: int,
) -> list[str]:
    from structured_layout.structured_renderer import _wrap_text_lines

    return _wrap_text_lines(draw, content, font, max_width_px)


def photo_frame_rect_pct(layout: LayoutSpec) -> tuple[float, float, float, float]:
    """Photo frame as (left, top, right, bottom) in canvas percent."""
    frame = layout.photo_frame
    return (
        frame.x,
        frame.y,
        frame.x + frame.width,
        frame.y + frame.height,
    )


def _rects_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    pad: float = 0.0,
) -> bool:
    al, at, ar, ab = a
    bl, bt, br, bb = b
    return not (ar + pad <= bl or br + pad <= al or ab + pad <= bt or bb + pad <= at)


def estimate_text_bbox_pct(text: TextElement, layout: LayoutSpec) -> tuple[float, float, float, float]:
    """Estimated text bbox as (left, top, right, bottom) in canvas percent."""
    from structured_layout.layout_spec import TextAlignment

    canvas_w, canvas_h = layout.canvas_width, layout.canvas_height
    probe = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)

    width_pct = min(text.width, MAX_TEXT_WIDTH_PCT)
    x_pct = max(TEXT_MARGIN_X_PCT, min(text.x, 100 - TEXT_MARGIN_X_PCT - width_pct))
    max_width_px = int(canvas_w * width_pct / 100)
    content = text.content.upper() if text.all_caps else text.content
    font = _fit_font(draw, content, text.font_family, text.font_size, text.font_weight, max_width_px)
    lines = _wrap_lines(draw, content, font, max_width_px)

    line_height_px = max(1, int(text.font_size * text.line_height))
    total_h_px = line_height_px * max(1, len(lines))
    max_line_w_px = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_line_w_px = max(max_line_w_px, bbox[2] - bbox[0])

    left_px = int(canvas_w * x_pct / 100)
    top_px = int(canvas_h * text.y / 100)
    if text.alignment == TextAlignment.CENTER:
        left_px += (max_width_px - max_line_w_px) // 2
    elif text.alignment == TextAlignment.RIGHT:
        left_px += max_width_px - max_line_w_px

    right_px = left_px + max_line_w_px
    bottom_px = top_px + total_h_px

    return (
        left_px / canvas_w * 100,
        top_px / canvas_h * 100,
        right_px / canvas_w * 100,
        bottom_px / canvas_h * 100,
    )


def text_overlaps_photo(text: TextElement, layout: LayoutSpec, *, pad_pct: float = 0.5) -> bool:
    """True when estimated text bbox intersects the photo frame."""
    return _rects_overlap(estimate_text_bbox_pct(text, layout), photo_frame_rect_pct(layout), pad=pad_pct)


def text_exceeds_canvas(text: TextElement, layout: LayoutSpec) -> bool:
    """True when text bbox extends outside canvas bounds."""
    left, top, right, bottom = estimate_text_bbox_pct(text, layout)
    margin_x = TEXT_MARGIN_X_PCT
    margin_y = 48 / layout.canvas_height * 100
    tol = 0.25  # sub-percent rounding from font metrics
    return (
        left < margin_x - tol
        or right > 100 - margin_x + tol
        or top < margin_y - tol
        or bottom > 100 - margin_y + tol
    )


def _is_featuring_line(content: str) -> bool:
    return "featuring" in content.lower()


def _is_date_line(content: str) -> bool:
    lower = content.lower()
    return bool(MONTH_NAME_RE.search(lower) and YEAR_RE.search(lower))


def _is_address_line(content: str) -> bool:
    return bool(ADDRESS_ZIP_RE.search(content) or ADDRESS_STREET_RE.search(content))


def clamp_text_element(text: TextElement, layout: LayoutSpec) -> TextElement:
    """Clamp width to 90% canvas and keep x inside safe horizontal band."""
    from structured_layout.layout_spec import TextElement

    width = min(text.width, MAX_TEXT_WIDTH_PCT)
    x = max(TEXT_MARGIN_X_PCT, min(text.x, 100 - TEXT_MARGIN_X_PCT - width))
    margin_y = 48 / layout.canvas_height * 100
    y = max(margin_y, text.y)
    return TextElement(
        content=text.content,
        x=x,
        y=y,
        width=width,
        font_size=text.font_size,
        font_family=text.font_family,
        font_weight=text.font_weight,
        color=text.color,
        alignment=text.alignment,
        rotation=text.rotation,
        letter_spacing=text.letter_spacing,
        line_height=text.line_height,
        all_caps=text.all_caps,
    )


def enforce_no_text_on_photo(layout: LayoutSpec) -> LayoutSpec:
    """Move any text overlapping the photo frame to a safe zone."""
    from structured_layout.layout_spec import TextElement, TextAlignment

    photo_left, photo_top, photo_right, photo_bottom = photo_frame_rect_pct(layout)
    gap = VERTICAL_GAP_PCT

    # Vertical split posters: type lives in a dedicated right column beside the photo.
    if "vertical split" in (layout.style_notes or "").lower():
        layout.text_elements = [clamp_text_element(t, layout) for t in layout.text_elements]
        return layout

    below_photo_y = photo_bottom + gap

    header_stack_y = 48 / layout.canvas_height * 100

    new_elements: list[TextElement] = []
    for text in layout.text_elements:
        clamped = clamp_text_element(text, layout)
        if clamped.x >= photo_right - 1.0:
            new_elements.append(clamped)
            continue
        if not text_overlaps_photo(clamped, layout):
            new_elements.append(clamped)
            continue

        _, t_top, _, t_bottom = estimate_text_bbox_pct(clamped, layout)
        text_h = max(gap, t_bottom - t_top)
        content = clamped.content

        if _is_featuring_line(content):
            y = max(header_stack_y, photo_top - gap - text_h)
            new_elements.append(
                TextElement(
                    content=clamped.content,
                    x=TEXT_MARGIN_X_PCT,
                    y=round(y, 1),
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=clamped.font_size,
                    font_family=clamped.font_family,
                    font_weight=clamped.font_weight,
                    color=clamped.color,
                    alignment=TextAlignment.CENTER,
                    rotation=0.0,
                    letter_spacing=clamped.letter_spacing,
                    line_height=clamped.line_height,
                    all_caps=clamped.all_caps,
                )
            )
            continue

        if _is_date_line(content) or _is_address_line(content):
            new_elements.append(
                TextElement(
                    content=clamped.content,
                    x=TEXT_MARGIN_X_PCT,
                    y=round(below_photo_y, 1),
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=clamped.font_size,
                    font_family=clamped.font_family,
                    font_weight=clamped.font_weight,
                    color=clamped.color,
                    alignment=TextAlignment.CENTER,
                    rotation=0.0,
                    letter_spacing=clamped.letter_spacing,
                    line_height=clamped.line_height,
                    all_caps=clamped.all_caps,
                )
            )
            below_photo_y += text_h + gap
            continue

        if t_top >= photo_top:
            new_elements.append(
                TextElement(
                    content=clamped.content,
                    x=TEXT_MARGIN_X_PCT,
                    y=round(below_photo_y, 1),
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=clamped.font_size,
                    font_family=clamped.font_family,
                    font_weight=clamped.font_weight,
                    color=clamped.color,
                    alignment=TextAlignment.CENTER,
                    rotation=0.0,
                    letter_spacing=clamped.letter_spacing,
                    line_height=clamped.line_height,
                    all_caps=clamped.all_caps,
                )
            )
            below_photo_y += text_h + gap
        else:
            y = max(header_stack_y, photo_top - gap - text_h)
            new_elements.append(
                TextElement(
                    content=clamped.content,
                    x=TEXT_MARGIN_X_PCT,
                    y=round(y, 1),
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=clamped.font_size,
                    font_family=clamped.font_family,
                    font_weight=clamped.font_weight,
                    color=clamped.color,
                    alignment=TextAlignment.CENTER,
                    rotation=0.0,
                    letter_spacing=clamped.letter_spacing,
                    line_height=clamped.line_height,
                    all_caps=clamped.all_caps,
                )
            )
            header_stack_y = y + text_h + gap

    layout.text_elements = sorted(new_elements, key=lambda t: (t.y, t.x))
    return layout


def validate_layout_bounds(layout: LayoutSpec) -> list[str]:
    """Return issues for text on photo or out-of-canvas bounds."""
    photo_left, _photo_top, photo_right, _photo_bottom = photo_frame_rect_pct(layout)
    split_layout = "vertical split" in (layout.style_notes or "").lower()
    issues: list[str] = []
    for text in layout.text_elements:
        clamped = clamp_text_element(text, layout)
        if not (split_layout and clamped.x >= photo_right):
            if text_overlaps_photo(clamped, layout):
                issues.append(f"Text overlaps photo frame: '{clamped.content[:40]}'")
        if text_exceeds_canvas(clamped, layout):
            issues.append(f"Text exceeds canvas bounds: '{clamped.content[:40]}'")
    return issues
