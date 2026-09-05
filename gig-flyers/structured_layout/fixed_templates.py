"""Layout templates with per-option aesthetic variation.

Option A: conservative — minimal randomness, always a recognizable bar-stack
Option B: progressive — paste-up two-column or tri-band, one venue accent
Option C: wildly creative — large variation in structure, palette, composition
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Optional

from structured_layout.design_system import (
    FONT_BODY_CONDENSED,
    FONT_DISPLAY,
    FONT_DISPLAY_HEAVY,
    PRO_GAP_PCT,
    TYPE_LG,
    TYPE_MD,
    TYPE_SM,
    TYPE_XL,
    TYPE_XS,
    TYPE_XXL,
    modular_scale,
    snap_pct,
)
from structured_layout.layout_geometry import MAX_TEXT_WIDTH_PCT, TEXT_MARGIN_X_PCT, VERTICAL_GAP_PCT
from structured_layout.tier_archetypes import TierArchetype, load_tier_archetype
from text_validation import SAFE_MARGIN_PX, featured_act_line, is_house_series_gig

def _safe_y_pct(canvas_height: int = 1536) -> float:
    return round(SAFE_MARGIN_PX / canvas_height * 100, 1)


def _make_rng(
    gig_id: Optional[str] = None,
    option_letter: Optional[str] = None,
    round_num: Optional[int] = None,
) -> random.Random:
    """Deterministic RNG when gig/option/round are provided."""
    if gig_id is not None and option_letter is not None and round_num is not None:
        seed_str = f"{gig_id}:{option_letter}:{round_num}"
        digest = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
        return random.Random(digest)
    return random.Random()


def _ri(lo: int, hi: int, rng: random.Random) -> int:
    """Random int in [lo, hi] inclusive."""
    return rng.randint(lo, hi)


def _rf(lo: float, hi: float, rng: random.Random, decimals: int = 1) -> float:
    """Random float in [lo, hi] rounded to decimals."""
    return round(rng.uniform(lo, hi), decimals)


from structured_layout.layout_spec import (  # noqa: E402
    BackgroundSpec,
    ColorSpec,
    DesignStyle,
    GraphicElement,
    LayoutSpec,
    PhotoFrame,
    PhotoPlacement,
    TextAlignment,
    TextElement,
    FontWeight,
    finalize_layout_spec,
)


def _stamp_date(date: str) -> str:
    """Compact two-line date for small stamp badges."""
    parts = date.replace(",", "").split()
    if len(parts) >= 4:
        return f"{parts[1][:3].upper()}\n{parts[2]}"
    return date[:8].upper()


def _short_date(date: str) -> str:
    """Compact date for stamp badge."""
    parts = date.replace(",", "").split()
    if len(parts) >= 4:
        return f"{parts[0][:3].upper()} {parts[1][:3].upper()} {parts[2]}"
    return date[:12].upper()


def _starburst_date(date: str) -> str:
    """Two-line ultra-compact date that fits inside a starburst center."""
    parts = date.replace(",", "").split()
    if len(parts) >= 4:
        return f"{parts[1][:3].upper()}\n{parts[2]}"  # e.g. "JUL\n14"
    return date[:6].upper()


MEDIUM_VARIANTS = ("paste_up", "broadside", "tri_band", "inverted_footer", "hatch_stack", "altamont_sidebar")
CREATIVE_VARIANTS = (
    "dark_field",
    "light_collage",
    "troubadour_inverted",
    "roxy_corners",
    "torn_reveal",
)

_DISPLAY_VENUE_FONT = FONT_DISPLAY
_DISPLAY_BAND_FONT = FONT_DISPLAY_HEAVY


def _select_medium_variant(
    arch: TierArchetype,
    rng: random.Random,
    *,
    preferences: dict[str, dict[str, int]] | None = None,
) -> str:
    """Deterministic medium-tier layout pick; paste_up default for blues_bar."""
    if arch.venue_type == "blues_bar":
        return "paste_up"
    prefs = preferences or {}
    weights = prefs.get("medium_variant", {})
    if weights:
        from preference_model import weighted_choice

        return weighted_choice(rng, list(MEDIUM_VARIANTS), weights)
    return MEDIUM_VARIANTS[rng.randint(0, len(MEDIUM_VARIANTS) - 1)]


def _select_creative_variant(rng: random.Random) -> str:
    """Deterministic creative-tier layout pick."""
    return CREATIVE_VARIANTS[rng.randint(0, len(CREATIVE_VARIANTS) - 1)]


def _compact_date_upper(date: str) -> str:
    """'Tuesday, July 14, 2026' → 'TUESDAY, JULY 14, 2026'."""
    parts = date.replace(",", "").split()
    if len(parts) >= 4:
        return f"{parts[0].upper()}, {parts[1].upper()} {parts[2]}, {parts[3]}"
    return date.upper()


def _creative_palette(arch: TierArchetype, dark: bool) -> tuple[str, str, str]:
    """Return (bg_color, fg_color, accent_color) for creative layouts."""
    if dark:
        return arch.ink_muted, arch.paper_color, arch.ink_accent
    return arch.paper_color, arch.ink_primary, arch.ink_accent


def _add_tape_on_photo_edge(
    graphic_elements: list[GraphicElement],
    *,
    photo_x: float,
    photo_y: float,
    photo_w: float,
    photo_h: float,
    photo_right: bool,
    rng: random.Random,
) -> None:
    """Tape seam on the inner edge of the photo paste-up."""
    tape_w = 4.0
    tape_h = round(photo_h * 0.28, 1)
    tape_y = round(photo_y + photo_h * 0.32, 1)
    if photo_right:
        tape_x = round(photo_x - 2.5, 1)
    else:
        tape_x = round(photo_x + photo_w - 1.5, 1)
    graphic_elements.append(
        GraphicElement(
            element_type="tape",
            x=tape_x,
            y=tape_y,
            width=tape_w,
            height=tape_h,
            rotation=_rf(-10, 10, rng),
        )
    )


def _add_medium_header_double_rule(
    graphic_elements: list[GraphicElement],
    *,
    y: float,
    arch: TierArchetype,
    rng: random.Random,
) -> None:
    """Hairline double rule under venue header — layout chrome, not an accent device."""
    if rng.random() > 0.55:
        return
    for i, opacity in enumerate((0.5, 0.28)):
        graphic_elements.append(
            GraphicElement(
                element_type="divider",
                x=TEXT_MARGIN_X_PCT,
                y=round(y + i * 0.55, 1),
                width=MAX_TEXT_WIDTH_PCT,
                height=0,
                stroke_color=ColorSpec(arch.ink_muted, opacity=opacity),
                stroke_width=1,
            )
        )


def _build_medium_photo_frame(
    arch: TierArchetype,
    rng: random.Random,
    *,
    photo_x: float,
    photo_y: float,
    photo_w: float,
    photo_h: float,
    placement: PhotoPlacement,
    rotation: float,
    contrast: float,
    saturation: float,
) -> PhotoFrame:
    """Option B photo — light halftone, paste-up border, optional paper texture."""
    use_halftone = rng.random() < 0.48
    border_w = 4.0 if rng.random() < 0.38 else 3.0
    return PhotoFrame(
        x=photo_x,
        y=photo_y,
        width=photo_w,
        height=photo_h,
        placement=placement,
        rotation=rotation,
        film_grain=_rf(0.010, 0.018, rng),
        halftone=use_halftone,
        halftone_dot_size=5 if use_halftone else 4,
        paper_texture=_rf(0.05, 0.14, rng) if rng.random() < 0.42 else 0.0,
        border_width=border_w,
        border_color=ColorSpec(arch.ink_primary),
        brightness=1.01,
        contrast=contrast,
        saturation=saturation,
        opacity=1.0,
    )


def _medium_background(arch: TierArchetype, rng: random.Random) -> BackgroundSpec:
    """Slightly richer paper/photocopy texture for medium tier."""
    texture = "photocopy" if rng.random() < 0.35 else "paper"
    return BackgroundSpec(
        color=ColorSpec(arch.paper_color),
        texture=texture,
        texture_strength=_rf(0.26, 0.38, rng),
        grain_strength=arch.grain_strength + _rf(0.01, 0.03, rng),
    )


def _create_handbill_paste_up(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Two-column paste-up: type column + photo offset per arch.photo_side."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    photo_right = arch.photo_side == "right"
    accent = arch.accent_element

    photo_w = snap_pct(50.0)
    type_w = snap_pct(40.0)
    if photo_right:
        photo_x = snap_pct(100 - TEXT_MARGIN_X_PCT - photo_w)
        type_x = TEXT_MARGIN_X_PCT
    else:
        photo_x = TEXT_MARGIN_X_PCT
        type_x = snap_pct(photo_x + photo_w + PRO_GAP_PCT)

    header_h = snap_pct(7.0)
    featuring_row_h = snap_pct(5.0)
    starburst_h = snap_pct(14.0)
    starburst_w = snap_pct(22.0)
    photo_h = snap_pct(48.0)
    photo_rotation = _rf(-1.5, 1.8, rng) if photo_right else _rf(-1.8, 1.5, rng)
    saturation = _rf(0.05, 0.18, rng)
    contrast = _rf(1.05, 1.15, rng)

    featuring_y = round(top_y + header_h + gap, 1)
    if accent == "starburst":
        burst_y = round(featuring_y + (featuring_row_h + gap if house else 0), 1)
        photo_y = round(burst_y + starburst_h + gap, 1)
    else:
        burst_y = None
        photo_y = round(featuring_y + featuring_row_h + gap + 2, 1)

    band_only_y = round(
        featuring_y + featuring_row_h + gap if not house else featuring_y,
        1,
    )

    graphic_elements: list[GraphicElement] = [
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=top_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=header_h,
            fill_color=ColorSpec(arch.ink_muted, opacity=1.0),
        ),
    ]
    _add_medium_header_double_rule(
        graphic_elements,
        y=round(top_y + header_h + 0.4, 1),
        arch=arch,
        rng=rng,
    )

    text_elements: list[TextElement] = [
        TextElement(
            content=venue.upper(),
            x=TEXT_MARGIN_X_PCT,
            y=round(top_y + 1.0, 1),
            width=MAX_TEXT_WIDTH_PCT,
            font_size=TYPE_LG,
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.CENTER,
            all_caps=True,
            color=ColorSpec(arch.paper_color),
            font_family=_DISPLAY_VENUE_FONT,
        ),
    ]

    if house:
        text_elements.append(
            TextElement(
                content=band_line,
                x=type_x,
                y=featuring_y,
                width=type_w,
                font_size=TYPE_MD,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(arch.ink_primary),
            )
        )
    elif accent != "starburst":
        text_elements.append(
            TextElement(
                content=band_line,
                x=type_x,
                y=band_only_y,
                width=type_w,
                font_size=TYPE_XL,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(arch.ink_primary),
                font_family=_DISPLAY_BAND_FONT,
            )
        )

    if accent == "starburst" and burst_y is not None:
        if not house:
            text_elements.append(
                TextElement(
                    content=band_line,
                    x=type_x,
                    y=featuring_y,
                    width=type_w,
                    font_size=TYPE_XL,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(arch.ink_primary),
                )
            )
        burst_x = type_x
        graphic_elements.append(
            GraphicElement(
                element_type="starburst",
                x=burst_x,
                y=burst_y,
                width=starburst_w,
                height=starburst_h,
                fill_color=ColorSpec(arch.ink_accent),
                stroke_color=ColorSpec(arch.ink_primary),
                stroke_width=2,
                properties={"text": _starburst_date(date), "spikes": 12},
            )
        )
    elif accent == "underline":
        rule_y = round((featuring_y + 5) if house else (band_only_y + 5), 1)
        graphic_elements.append(
            GraphicElement(
                element_type="box",
                x=type_x,
                y=rule_y,
                width=type_w,
                height=1.2,
                fill_color=ColorSpec(arch.ink_accent),
            )
        )
        text_elements.append(
            TextElement(
                content=date,
                x=type_x,
                y=round(rule_y + 1.5, 1),
                width=type_w,
                font_size=TYPE_SM,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(arch.ink_primary),
                font_family=FONT_BODY_CONDENSED,
            )
        )
    elif accent == "stamp":
        graphic_elements.append(
            GraphicElement(
                element_type="stamp",
                x=type_x,
                y=round(top_y + header_h + gap, 1),
                width=14,
                height=10,
                stroke_color=ColorSpec(arch.ink_accent),
                stroke_width=2,
                rotation=-6,
                properties={"text": _stamp_date(date)},
            )
        )
        text_elements.append(
            TextElement(
                content=date,
                x=type_x,
                y=round(featuring_y + (featuring_row_h if house else 0) + 1, 1),
                width=type_w,
                font_size=TYPE_SM,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(arch.ink_primary),
                font_family=FONT_BODY_CONDENSED,
            )
        )
    elif accent == "tape":
        _add_tape_on_photo_edge(
            graphic_elements,
            photo_x=photo_x,
            photo_y=photo_y,
            photo_w=photo_w,
            photo_h=photo_h,
            photo_right=photo_right,
            rng=rng,
        )
        text_elements.append(
            TextElement(
                content=date,
                x=type_x,
                y=round(band_only_y + (featuring_row_h if house else 0), 1),
                width=type_w,
                font_size=TYPE_SM,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(arch.ink_primary),
                font_family=FONT_BODY_CONDENSED,
            )
        )

    time_y = round(photo_y + photo_h + gap + 1, 1)
    text_elements.append(
        TextElement(
            content=time.upper() if time else "SHOWTIME TBA",
            x=type_x,
            y=time_y,
            width=type_w,
            font_size=TYPE_XL,
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.LEFT,
            color=ColorSpec(arch.ink_primary),
        )
    )

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Medium paste-up — two-column offset photo, one accent element",
        background=_medium_background(arch, rng),
        photo_frame=_build_medium_photo_frame(
            arch,
            rng,
            photo_x=photo_x,
            photo_y=photo_y,
            photo_w=photo_w,
            photo_h=photo_h,
            placement=PhotoPlacement.RIGHT if photo_right else PhotoPlacement.LEFT,
            rotation=photo_rotation,
            contrast=contrast,
            saturation=saturation,
        ),
        text_elements=text_elements,
        graphic_elements=graphic_elements,
        photocopy_effect=0.0,
        age_effect=0.0,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def _create_handbill_tri_band(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Horizontal tri-band: header type / photo offset / footer type."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    photo_right = arch.photo_side == "right"
    accent = arch.accent_element

    header_h = _rf(7.0, 8.5, rng)
    footer_h = _rf(7.5, 9.0, rng)
    photo_h = _ri(38, 46, rng)
    photo_w = _rf(42, 48, rng)
    saturation = _rf(0.05, 0.18, rng)
    contrast = _rf(1.05, 1.15, rng)

    if photo_right:
        photo_x = round(100 - TEXT_MARGIN_X_PCT - photo_w, 1)
        type_x, type_w = TEXT_MARGIN_X_PCT, round(photo_x - TEXT_MARGIN_X_PCT - 2, 1)
    else:
        photo_x = TEXT_MARGIN_X_PCT
        type_x = round(photo_x + photo_w + 2, 1)
        type_w = round(100 - TEXT_MARGIN_X_PCT - type_x, 1)

    mid_y = round(top_y + header_h + gap + 1, 1)
    photo_y = mid_y
    footer_y = round(photo_y + photo_h + gap + 1, 1)

    graphic_elements: list[GraphicElement] = [
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=top_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=header_h,
            fill_color=ColorSpec(arch.ink_muted),
        ),
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=footer_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=footer_h,
            fill_color=ColorSpec(arch.ink_primary),
        ),
    ]
    _add_medium_header_double_rule(
        graphic_elements,
        y=round(top_y + header_h + 0.35, 1),
        arch=arch,
        rng=rng,
    )

    text_elements: list[TextElement] = [
        TextElement(
            content=venue.upper(),
            x=TEXT_MARGIN_X_PCT,
            y=round(top_y + 1.2, 1),
            width=MAX_TEXT_WIDTH_PCT,
            font_size=_ri(48, 56, rng),
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.CENTER,
            all_caps=True,
            color=ColorSpec(arch.paper_color),
        ),
        TextElement(
            content=band_line.upper() if not house else band_line,
            x=type_x,
            y=round(mid_y + 1, 1),
            width=type_w,
            font_size=_ri(40, 52, rng),
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.LEFT,
            all_caps=not house,
            color=ColorSpec(arch.ink_primary),
        ),
        TextElement(
            content=date,
            x=TEXT_MARGIN_X_PCT,
            y=round(footer_y + 1.0, 1),
            width=MAX_TEXT_WIDTH_PCT * 0.55,
            font_size=_ri(28, 36, rng),
            font_weight=FontWeight.BOLD,
            alignment=TextAlignment.LEFT,
            color=ColorSpec(arch.paper_color),
        ),
        TextElement(
            content=time.upper() if time else "TBA",
            x=round(TEXT_MARGIN_X_PCT + MAX_TEXT_WIDTH_PCT * 0.58, 1),
            y=round(footer_y + 1.0, 1),
            width=round(MAX_TEXT_WIDTH_PCT * 0.38, 1),
            font_size=_ri(32, 44, rng),
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.RIGHT,
            color=ColorSpec(arch.paper_color),
        ),
    ]

    if accent == "starburst":
        graphic_elements.append(
            GraphicElement(
                element_type="starburst",
                x=type_x,
                y=round(mid_y + photo_h - 16, 1),
                width=20,
                height=14,
                fill_color=ColorSpec(arch.ink_accent),
                stroke_color=ColorSpec(arch.ink_primary),
                stroke_width=2,
                properties={"text": _starburst_date(date), "spikes": 10},
            )
        )
    elif accent == "underline":
        graphic_elements.append(
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=round(top_y + header_h - 0.5, 1),
                width=MAX_TEXT_WIDTH_PCT,
                height=1.0,
                fill_color=ColorSpec(arch.ink_accent),
            )
        )
    elif accent == "stamp":
        graphic_elements.append(
            GraphicElement(
                element_type="stamp",
                x=TEXT_MARGIN_X_PCT + 1,
                y=round(mid_y + 1, 1),
                width=14,
                height=10,
                stroke_color=ColorSpec(arch.ink_accent),
                stroke_width=2,
                rotation=-8,
                properties={"text": _stamp_date(date)},
            )
        )
    elif accent == "tape":
        _add_tape_on_photo_edge(
            graphic_elements,
            photo_x=photo_x,
            photo_y=photo_y,
            photo_w=photo_w,
            photo_h=photo_h,
            photo_right=photo_right,
            rng=rng,
        )

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Medium tri-band — header / offset photo / footer type",
        background=_medium_background(arch, rng),
        photo_frame=_build_medium_photo_frame(
            arch,
            rng,
            photo_x=photo_x,
            photo_y=photo_y,
            photo_w=photo_w,
            photo_h=photo_h,
            placement=PhotoPlacement.RIGHT if photo_right else PhotoPlacement.LEFT,
            rotation=_rf(-1.2, 1.2, rng),
            contrast=contrast,
            saturation=saturation,
        ),
        text_elements=text_elements,
        graphic_elements=graphic_elements,
        photocopy_effect=0.0,
        age_effect=0.0,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def _create_handbill_broadside(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Photo top, double rules, solid venue bar — classic broadside."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band

    photo_y = top_y
    photo_h = _ri(42, 48, rng)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 1.0, 1)
    band_h_approx = _rf(11.0, 14.0, rng)
    rule1_y = round(band_y + band_h_approx + 0.3, 1)
    rule2_y = round(rule1_y + 0.8, 1)
    date_y = round(rule2_y + gap + 1.0, 1)
    date_h_approx = _rf(7.5, 9.0, rng)
    venue_bar_y = round(date_y + date_h_approx + gap + 0.5, 1)
    venue_bar_h = _rf(8.5, 10.5, rng)
    venue_text_y = round(venue_bar_y + 1.4, 1)
    time_y = round(venue_bar_y + venue_bar_h + gap + 1.0, 1)
    saturation = _rf(0.05, 0.12, rng)
    contrast = _rf(1.08, 1.18, rng)

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Medium broadside — photo top, massive band, double rule, venue bar",
        background=_medium_background(arch, rng),
        photo_frame=_build_medium_photo_frame(
            arch,
            rng,
            photo_x=TEXT_MARGIN_X_PCT,
            photo_y=photo_y,
            photo_w=MAX_TEXT_WIDTH_PCT,
            photo_h=photo_h,
            placement=PhotoPlacement.TOP,
            rotation=0.0,
            contrast=contrast,
            saturation=saturation,
        ),
        text_elements=[
            TextElement(
                content=band_line.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=band_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(84, 96, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(arch.ink_primary),
            ),
            TextElement(
                content=_compact_date_upper(date),
                x=TEXT_MARGIN_X_PCT,
                y=date_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(42, 52, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(arch.ink_primary),
            ),
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=venue_text_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(36, 44, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(arch.paper_color),
            ),
            TextElement(
                content=time.upper() if time else "SHOWTIME TBA",
                x=TEXT_MARGIN_X_PCT,
                y=time_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(64, 76, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                color=ColorSpec(arch.ink_primary),
            ),
        ],
        graphic_elements=[
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=rule1_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=0.35,
                fill_color=ColorSpec(arch.ink_primary),
            ),
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=rule2_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=0.35,
                fill_color=ColorSpec(arch.ink_primary),
            ),
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=venue_bar_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=venue_bar_h,
                fill_color=ColorSpec(arch.ink_primary),
            ),
        ],
        photocopy_effect=0.0,
        age_effect=0.0,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def _create_handbill_hatch_stack(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Hatch Show Print stack — learned from 1953 Hank Williams poster visual study."""
    from visual_studies import HATCH_INK, HATCH_PAPER, HATCH_RED

    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band

    venue_y = top_y
    date_y = round(venue_y + 9.0, 1)
    bar_y = round(date_y + 8.5, 1)
    bar_h = snap_pct(5.5)
    photo_y = round(bar_y + bar_h + gap + 1.0, 1)
    photo_h = _ri(34, 38, rng)
    photo_w = snap_pct(52.0)
    photo_x = round((100 - photo_w) / 2, 1)
    band_y = round(photo_y + photo_h + gap + 1.5, 1)
    time_y = round(band_y + 13.5, 1)

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Medium hatch_stack — venue/date top, presenter bar, portrait, mega name (visual study)",
        background=BackgroundSpec(
            color=ColorSpec(HATCH_PAPER),
            texture="paper",
            texture_strength=0.04,
            grain_strength=0.02,
        ),
        photo_frame=_build_medium_photo_frame(
            arch,
            rng,
            photo_x=photo_x,
            photo_y=photo_y,
            photo_w=photo_w,
            photo_h=photo_h,
            placement=PhotoPlacement.CENTER,
            rotation=0.0,
            contrast=_rf(1.05, 1.12, rng),
            saturation=_rf(0.0, 0.08, rng),
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=venue_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(40, 48, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content=_compact_date_upper(date),
                x=TEXT_MARGIN_X_PCT,
                y=date_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(34, 42, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content="LIVE MUSIC",
                x=TEXT_MARGIN_X_PCT,
                y=round(bar_y + 1.2, 1),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(22, 26, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_PAPER),
            ),
            TextElement(
                content=band_line.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=band_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(92, 104, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content=time.upper() if time else "SHOWTIME TBA",
                x=TEXT_MARGIN_X_PCT,
                y=time_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(28, 34, rng),
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_INK),
            ),
        ],
        graphic_elements=[
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=bar_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=bar_h,
                fill_color=ColorSpec(HATCH_INK),
            ),
        ],
        photocopy_effect=0.02,
        age_effect=0.04,
    )
    if address:
        layout.text_elements.append(
            TextElement(
                content=address,
                x=TEXT_MARGIN_X_PCT,
                y=round(time_y + 5.5, 1),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_XS,
                font_weight=FontWeight.REGULAR,
                alignment=TextAlignment.CENTER,
                color=ColorSpec(HATCH_INK),
            )
        )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def _create_handbill_altamont_sidebar(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Altamont-style bill — headliner block + photo lower-left + sidebar (visual study)."""
    from visual_studies import HATCH_INK, HATCH_PAPER, HATCH_RED

    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band

    head_y = top_y
    promo_y = round(head_y + 10.0, 1)
    date_y = round(promo_y + 7.0, 1)
    loc_y = round(date_y + 6.5, 1)
    photo_y = round(loc_y + 8.0, 1)
    photo_h = _ri(36, 42, rng)
    photo_w = snap_pct(58.0)
    photo_x = TEXT_MARGIN_X_PCT
    sidebar_x = round(photo_x + photo_w + 2.0, 1)
    sidebar_w = round(100 - sidebar_x - TEXT_MARGIN_X_PCT, 1)
    time_y = round(photo_y + photo_h + gap + 1.0, 1)

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Medium altamont_sidebar — headliner hook, photo left, sidebar guests (visual study)",
        background=BackgroundSpec(
            color=ColorSpec(HATCH_PAPER),
            texture="paper",
            texture_strength=0.03,
            grain_strength=0.02,
        ),
        photo_frame=_build_medium_photo_frame(
            arch,
            rng,
            photo_x=photo_x,
            photo_y=photo_y,
            photo_w=photo_w,
            photo_h=photo_h,
            placement=PhotoPlacement.LEFT,
            rotation=0.0,
            contrast=_rf(1.15, 1.28, rng),
            saturation=0.0,
        ),
        text_elements=[
            TextElement(
                content=band_line.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=head_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(44, 52, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content="LIVE AT",
                x=TEXT_MARGIN_X_PCT,
                y=promo_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(20, 24, rng),
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_INK),
            ),
            TextElement(
                content=_compact_date_upper(date),
                x=TEXT_MARGIN_X_PCT,
                y=date_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(32, 38, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_INK),
            ),
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=loc_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(28, 34, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content="SPECIAL\nGUESTS",
                x=sidebar_x,
                y=round(photo_y + 1.0, 1),
                width=sidebar_w,
                font_size=_ri(16, 18, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content="LOCAL\nOPENERS",
                x=sidebar_x,
                y=round(photo_y + 10.0, 1),
                width=sidebar_w,
                font_size=_ri(14, 16, rng),
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_RED),
            ),
            TextElement(
                content=time.upper() if time else "SHOWTIME TBA",
                x=TEXT_MARGIN_X_PCT,
                y=time_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=_ri(36, 44, rng),
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec(HATCH_INK),
            ),
        ],
        graphic_elements=[],
        photocopy_effect=0.04,
        age_effect=0.02,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def _create_handbill_inverted_footer(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Photo top, type mid-zone, inverted black footer with venue display type."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    accent = arch.accent_element

    photo_y = top_y
    photo_h = _ri(40, 46, rng)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 0.8, 1)
    date_y = round(band_y + 7.5 + gap, 1)
    time_y = round(date_y + 5.5 + gap, 1)
    footer_h = _rf(10.0, 12.5, rng)
    footer_y = round(100 - _safe_y_pct() - footer_h - 1.0, 1)
    venue_text_y = round(footer_y + footer_h * 0.32, 1)
    address_y = round(footer_y + footer_h * 0.62, 1) if address else None
    saturation = _rf(0.05, 0.15, rng)
    contrast = _rf(1.05, 1.15, rng)

    graphic_elements: list[GraphicElement] = [
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=footer_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=footer_h,
            fill_color=ColorSpec(arch.ink_primary),
        ),
    ]
    text_elements: list[TextElement] = [
        TextElement(
            content=band_line.upper() if not house else band_line,
            x=TEXT_MARGIN_X_PCT,
            y=band_y,
            width=MAX_TEXT_WIDTH_PCT,
            font_size=_ri(52, 68, rng),
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.CENTER,
            all_caps=not house,
            color=ColorSpec(arch.ink_primary),
        ),
        TextElement(
            content=date,
            x=TEXT_MARGIN_X_PCT,
            y=date_y,
            width=MAX_TEXT_WIDTH_PCT,
            font_size=_ri(28, 36, rng),
            font_weight=FontWeight.BOLD,
            alignment=TextAlignment.CENTER,
            color=ColorSpec(arch.ink_primary),
        ),
        TextElement(
            content=time.upper() if time else "TBA",
            x=TEXT_MARGIN_X_PCT,
            y=time_y,
            width=MAX_TEXT_WIDTH_PCT,
            font_size=_ri(40, 52, rng),
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.CENTER,
            color=ColorSpec(arch.ink_accent),
        ),
        TextElement(
            content=venue.upper(),
            x=TEXT_MARGIN_X_PCT,
            y=venue_text_y,
            width=MAX_TEXT_WIDTH_PCT,
            font_size=_ri(44, 52, rng),
            font_family=_DISPLAY_VENUE_FONT,
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.CENTER,
            all_caps=True,
            color=ColorSpec(arch.paper_color),
        ),
    ]
    if address:
        text_elements.append(
            TextElement(
                content=address,
                x=TEXT_MARGIN_X_PCT,
                y=address_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_XS,
                font_weight=FontWeight.NORMAL,
                alignment=TextAlignment.CENTER,
                color=ColorSpec(arch.paper_color, opacity=0.85),
                font_family=FONT_BODY_CONDENSED,
            )
        )

    if accent == "starburst":
        graphic_elements.append(
            GraphicElement(
                element_type="starburst",
                x=TEXT_MARGIN_X_PCT + 2,
                y=round(band_y - 2, 1),
                width=18,
                height=12,
                fill_color=ColorSpec(arch.ink_accent),
                stroke_color=ColorSpec(arch.ink_primary),
                stroke_width=2,
                properties={"text": _starburst_date(date), "spikes": 10},
            )
        )
    elif accent == "stamp":
        graphic_elements.append(
            GraphicElement(
                element_type="stamp",
                x=TEXT_MARGIN_X_PCT + 1,
                y=round(date_y - 1, 1),
                width=14,
                height=10,
                stroke_color=ColorSpec(arch.ink_accent),
                stroke_width=2,
                rotation=6,
                properties={"text": _stamp_date(date)},
            )
        )

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Medium inverted footer — photo top, black footer venue bar",
        background=_medium_background(arch, rng),
        photo_frame=_build_medium_photo_frame(
            arch,
            rng,
            photo_x=TEXT_MARGIN_X_PCT,
            photo_y=photo_y,
            photo_w=MAX_TEXT_WIDTH_PCT,
            photo_h=photo_h,
            placement=PhotoPlacement.TOP,
            rotation=_rf(-1.0, 1.0, rng),
            contrast=contrast,
            saturation=saturation,
        ),
        text_elements=text_elements,
        graphic_elements=graphic_elements,
        photocopy_effect=0.0,
        age_effect=0.0,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def create_simple_stack_layout(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: Optional[TierArchetype] = None,
    rng: Optional[random.Random] = None,
) -> LayoutSpec:
    """Option A — utilitarian photocopy: venue/date/time bars, band, photo below."""
    r = rng or _make_rng()
    arch = archetype or load_tier_archetype("conservative", event=event)
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band

    bar_h = snap_pct(6.0)
    venue_font = TYPE_XL
    date_font = TYPE_MD
    time_font = TYPE_SM
    band_font = TYPE_XL
    photo_h = snap_pct(48.0)
    saturation = _rf(0.05, 0.15, r)
    contrast = _rf(1.08, 1.15, r)

    venue_y = top_y
    date_y = round(venue_y + bar_h + gap, 1)
    time_y = round(date_y + bar_h + gap, 1)
    band_y = round(time_y + bar_h + gap + 1, 1)
    photo_y = round(band_y + 7.0, 1)

    ink = arch.ink_primary
    accent = arch.ink_accent
    use_accent_date = accent != ink

    layout = LayoutSpec(
        design_style=DesignStyle.HANDBILL,
        style_notes="Conservative photocopy stack — venue/date/time bars, type-heavy, photo below",
        background=BackgroundSpec(
            color=ColorSpec(arch.paper_color),
            texture="paper",
            texture_strength=0.15,
            grain_strength=min(arch.grain_strength, 0.04),
        ),
        photo_frame=PhotoFrame(
            x=TEXT_MARGIN_X_PCT,
            y=photo_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=photo_h,
            placement=PhotoPlacement.BOTTOM,
            film_grain=0.008,
            paper_texture=0.0,
            brightness=1.02,
            contrast=contrast,
            saturation=saturation,
            opacity=1.0,
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=round(venue_y + 0.8, 1),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=venue_font,
                font_family=_DISPLAY_VENUE_FONT,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                all_caps=True,
                color=ColorSpec("#FFFFFF"),
            ),
            TextElement(
                content=date,
                x=TEXT_MARGIN_X_PCT,
                y=round(date_y + 0.8, 1),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=date_font,
                font_family=FONT_BODY_CONDENSED,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
                color=ColorSpec("#FFFFFF"),
            ),
            TextElement(
                content=time,
                x=TEXT_MARGIN_X_PCT,
                y=round(time_y + 0.7, 1),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=time_font,
                font_family=FONT_BODY_CONDENSED,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
                color=ColorSpec("#FFFFFF"),
            ),
            TextElement(
                content=band_line,
                x=TEXT_MARGIN_X_PCT,
                y=band_y,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=band_font,
                font_family=_DISPLAY_BAND_FONT,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                color=ColorSpec(ink),
            ),
        ],
        graphic_elements=[
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=venue_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=bar_h,
                fill_color=ColorSpec(ink),
            ),
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=date_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=bar_h,
                fill_color=ColorSpec(accent if use_accent_date else ink),
            ),
            GraphicElement(
                element_type="box",
                x=TEXT_MARGIN_X_PCT,
                y=time_y,
                width=MAX_TEXT_WIDTH_PCT,
                height=bar_h,
                fill_color=ColorSpec(ink),
            ),
        ],
        photocopy_effect=0.0,
        age_effect=0.0,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)


def create_handbill_layout(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: Optional[TierArchetype] = None,
    rng: Optional[random.Random] = None,
    medium_variant: Optional[str] = None,
) -> LayoutSpec:
    """Option B — paste-up handbill with venue accent and offset photo."""
    r = rng or _make_rng()
    arch = archetype or load_tier_archetype("medium", event=event)
    if medium_variant and medium_variant in MEDIUM_VARIANTS:
        variant = medium_variant
    else:
        from state import load_design_preferences
        from preference_model import preference_weights

        variant = _select_medium_variant(arch, r, preferences=preference_weights(load_design_preferences()))
    kwargs = {
        "venue": venue,
        "band": band,
        "date": date,
        "time": time,
        "address": address,
        "event": event,
        "archetype": arch,
        "rng": r,
    }
    builders = {
        "paste_up": _create_handbill_paste_up,
        "broadside": _create_handbill_broadside,
        "tri_band": _create_handbill_tri_band,
        "inverted_footer": _create_handbill_inverted_footer,
        "hatch_stack": _create_handbill_hatch_stack,
        "altamont_sidebar": _create_handbill_altamont_sidebar,
    }
    return builders[variant](**kwargs)


def _build_creative_photo(
    arch: TierArchetype,
    rng: random.Random,
    *,
    photo_x: float,
    photo_y: float,
    photo_w: float,
    photo_h: float,
    fg_color: str,
    mask_shape: str = "rectangle",
    rotation: Optional[float] = None,
) -> PhotoFrame:
    """Shared creative photo frame — full opacity, subtle grading only."""
    return PhotoFrame(
        x=photo_x,
        y=photo_y,
        width=photo_w,
        height=photo_h,
        placement=PhotoPlacement.CENTER,
        rotation=rotation if rotation is not None else _rf(-2.0, 2.0, rng),
        film_grain=_rf(0.006, 0.012, rng),
        paper_texture=0.0,
        border_width=_ri(0, 5, rng),
        border_color=ColorSpec(fg_color),
        mask_shape=mask_shape,
        brightness=1.01,
        contrast=_rf(1.05, 1.15, rng),
        saturation=_rf(0.85, 1.0, rng),
        opacity=1.0,
    )


def _create_collage_dark_field(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Dark ink field, cream type, offset photo, stamp + tape accents."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    bg_color, fg_color, accent_color = _creative_palette(arch, dark=True)

    venue_y = round(top_y + 0.5, 1)
    photo_y = round(venue_y + 14.0 + gap, 1)
    photo_h = _ri(38, 44, rng)
    photo_w = _rf(84, 92, rng)
    photo_x = round((100 - photo_w) / 2, 1)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 1.2, 1)
    rule_y = round(band_y + 8.0, 1)
    date_y = round(rule_y + gap + 0.8, 1)
    time_y = round(date_y + 6.0 + gap, 1)

    graphic_els: list[GraphicElement] = [
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=rule_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=0.35,
            fill_color=ColorSpec(accent_color),
        ),
        GraphicElement(
            element_type="stamp",
            x=round(100 - TEXT_MARGIN_X_PCT - 18, 1),
            y=round(venue_y + 1, 1),
            width=16,
            height=9,
            stroke_color=ColorSpec(accent_color),
            stroke_width=2,
            rotation=-10,
            properties={"text": _short_date(date)},
        ),
        GraphicElement(
            element_type="tape",
            x=round(photo_x + photo_w * 0.4, 1),
            y=round(photo_y - 1.2, 1),
            width=16,
            height=4,
            rotation=_rf(-5, 5, rng),
        ),
    ]

    return finalize_layout_spec(
        LayoutSpec(
            design_style=DesignStyle.COLLAGE,
            style_notes="Creative dark_field — ink background, cream type, stamp + tape",
            background=BackgroundSpec(
                color=ColorSpec(bg_color),
                texture="paper",
                texture_strength=_rf(0.28, 0.40, rng),
                grain_strength=arch.grain_strength + 0.02,
                margin_grain_only=True,
            ),
            photo_frame=_build_creative_photo(
                arch, rng,
                photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h,
                fg_color=fg_color, rotation=-1.5,
            ),
            text_elements=[
                TextElement(
                    content=venue.upper(),
                    x=TEXT_MARGIN_X_PCT,
                    y=venue_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(52, 68, rng),
                    font_family=_DISPLAY_VENUE_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    all_caps=True,
                    color=ColorSpec(accent_color),
                ),
                TextElement(
                    content=band_line.upper() if not house else band_line,
                    x=TEXT_MARGIN_X_PCT,
                    y=band_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(72, 92, rng),
                    font_family=_DISPLAY_BAND_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    all_caps=not house,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=date,
                    x=TEXT_MARGIN_X_PCT,
                    y=date_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(30, 40, rng),
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=time.upper() if time else "TBA",
                    x=TEXT_MARGIN_X_PCT,
                    y=time_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(48, 64, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(fg_color),
                ),
            ],
            graphic_elements=graphic_els,
            photocopy_effect=0.0,
            age_effect=0.0,
        ),
        venue, band, time, address=address, event=event,
    )


def _create_collage_light_collage(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Light paste-up collage — ticket stub, tape, layered blocks."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    bg_color, fg_color, accent_color = _creative_palette(arch, dark=False)

    venue_y = round(top_y + 0.5, 1)
    photo_y = round(venue_y + 12.0 + gap, 1)
    photo_h = _ri(36, 44, rng)
    photo_w = _rf(78, 88, rng)
    photo_x = round((100 - photo_w) / 2 + _rf(-3, 3, rng), 1)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 1.5, 1)
    date_y = round(band_y + 8.0 + gap, 1)
    time_y = round(date_y + 5.5 + gap, 1)

    graphic_els: list[GraphicElement] = [
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=venue_y - 0.5,
            width=MAX_TEXT_WIDTH_PCT,
            height=10.5,
            fill_color=ColorSpec(accent_color, opacity=0.12),
        ),
        GraphicElement(
            element_type="ticket_stub",
            x=round(photo_x + photo_w - 12, 1),
            y=round(photo_y + photo_h - 18, 1),
            width=12,
            height=18,
            stroke_color=ColorSpec(fg_color),
            properties={"perforations": 10},
        ),
        GraphicElement(
            element_type="tape",
            x=round(photo_x + photo_w * 0.25, 1),
            y=round(photo_y - 1.5, 1),
            width=20,
            height=4,
            rotation=_rf(-6, 6, rng),
        ),
        GraphicElement(
            element_type="starburst",
            x=TEXT_MARGIN_X_PCT,
            y=round(time_y + 1, 1),
            width=18,
            height=12,
            fill_color=ColorSpec(accent_color),
            stroke_color=ColorSpec(fg_color),
            stroke_width=2,
            properties={"text": _starburst_date(date), "spikes": 10},
        ),
    ]

    return finalize_layout_spec(
        LayoutSpec(
            design_style=DesignStyle.COLLAGE,
            style_notes="Creative light_collage — ticket stub, tape, starburst promo",
            background=BackgroundSpec(
                color=ColorSpec(bg_color),
                texture="paper",
                texture_strength=_rf(0.25, 0.38, rng),
                grain_strength=arch.grain_strength,
            ),
            photo_frame=_build_creative_photo(
                arch, rng,
                photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h,
                fg_color=fg_color, rotation=1.2,
            ),
            text_elements=[
                TextElement(
                    content=venue.upper(),
                    x=TEXT_MARGIN_X_PCT,
                    y=venue_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(48, 60, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    all_caps=True,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=band_line.upper() if not house else band_line,
                    x=TEXT_MARGIN_X_PCT,
                    y=band_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(68, 88, rng),
                    font_family=_DISPLAY_BAND_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    all_caps=not house,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=time.upper() if time else "TBA",
                    x=TEXT_MARGIN_X_PCT,
                    y=time_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(44, 58, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    color=ColorSpec(accent_color),
                ),
            ],
            graphic_elements=graphic_els,
            photocopy_effect=0.0,
            age_effect=0.0,
        ),
        venue, band, time, address=address, event=event,
    )


def _create_collage_troubadour_inverted(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Photo top, cream mid-zone, inverted black footer with display venue."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    bg_color = arch.paper_color
    fg_color = arch.ink_primary
    accent_color = arch.ink_accent

    photo_y = top_y
    photo_h = _ri(40, 46, rng)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 1.0, 1)
    date_y = round(band_y + 7.5 + gap, 1)
    time_y = round(date_y + 5.0 + gap, 1)
    footer_h = _rf(15.0, 18.0, rng)
    footer_y = round(100 - _safe_y_pct() - footer_h - 0.5, 1)
    venue_text_y = round(footer_y + footer_h * 0.2, 1)

    return finalize_layout_spec(
        LayoutSpec(
            design_style=DesignStyle.COLLAGE,
            style_notes="Creative troubadour_inverted — photo top, black footer venue",
            background=BackgroundSpec(
                color=ColorSpec(bg_color),
                texture="paper",
                texture_strength=_rf(0.22, 0.35, rng),
                grain_strength=arch.grain_strength,
            ),
            photo_frame=_build_creative_photo(
                arch, rng,
                photo_x=TEXT_MARGIN_X_PCT, photo_y=photo_y,
                photo_w=MAX_TEXT_WIDTH_PCT, photo_h=photo_h,
                fg_color=fg_color, rotation=0.0,
            ),
            text_elements=[
                TextElement(
                    content=band_line.upper() if not house else band_line,
                    x=TEXT_MARGIN_X_PCT,
                    y=band_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(64, 84, rng),
                    font_family=_DISPLAY_BAND_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    all_caps=not house,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=date,
                    x=TEXT_MARGIN_X_PCT,
                    y=date_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(28, 36, rng),
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=time.upper() if time else "TBA",
                    x=TEXT_MARGIN_X_PCT,
                    y=time_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(44, 56, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    color=ColorSpec(accent_color),
                ),
                TextElement(
                    content=venue.upper(),
                    x=TEXT_MARGIN_X_PCT,
                    y=venue_text_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(48, 60, rng),
                    font_family=_DISPLAY_VENUE_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    all_caps=True,
                    color=ColorSpec(bg_color),
                ),
            ],
            graphic_elements=[
                GraphicElement(
                    element_type="box",
                    x=TEXT_MARGIN_X_PCT,
                    y=footer_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    height=footer_h,
                    fill_color=ColorSpec(arch.ink_primary),
                ),
            ],
            photocopy_effect=0.0,
            age_effect=0.0,
        ),
        venue, band, time, address=address, event=event,
    )


def _create_collage_roxy_corners(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Diagonal corner strips, offset photo, corner date promo."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    bg_color, fg_color, accent_color = _creative_palette(arch, dark=False)

    venue_y = round(top_y + 2.0, 1)
    photo_y = round(venue_y + 11.0 + gap, 1)
    photo_h = _ri(38, 44, rng)
    photo_w = _rf(80, 88, rng)
    photo_x = round((100 - photo_w) / 2, 1)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 1.2, 1)
    date_y = round(band_y + 8.0 + gap, 1)
    time_y = round(date_y + 5.5 + gap, 1)
    strip_w = _rf(22, 28, rng)
    strip_h = _rf(14, 18, rng)

    graphic_els: list[GraphicElement] = [
        GraphicElement(
            element_type="corner_strip",
            x=0,
            y=0,
            width=strip_w,
            height=strip_h,
            fill_color=ColorSpec(accent_color),
            properties={"corner": "top_left"},
        ),
        GraphicElement(
            element_type="corner_strip",
            x=round(100 - strip_w, 1),
            y=round(100 - strip_h - _safe_y_pct(), 1),
            width=strip_w,
            height=strip_h,
            fill_color=ColorSpec(accent_color),
            properties={"corner": "bottom_right"},
        ),
        GraphicElement(
            element_type="stamp",
            x=round(100 - TEXT_MARGIN_X_PCT - 16, 1),
            y=round(venue_y, 1),
            width=14,
            height=8,
            stroke_color=ColorSpec(accent_color),
            stroke_width=2,
            rotation=12,
            properties={"text": _short_date(date)},
        ),
    ]

    return finalize_layout_spec(
        LayoutSpec(
            design_style=DesignStyle.COLLAGE,
            style_notes="Creative roxy_corners — diagonal corner strips, stamp promo",
            background=BackgroundSpec(
                color=ColorSpec(bg_color),
                texture="paper",
                texture_strength=_rf(0.22, 0.34, rng),
                grain_strength=arch.grain_strength,
            ),
            photo_frame=_build_creative_photo(
                arch, rng,
                photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h,
                fg_color=fg_color, rotation=-1.8,
            ),
            text_elements=[
                TextElement(
                    content=venue.upper(),
                    x=TEXT_MARGIN_X_PCT,
                    y=venue_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(50, 64, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    all_caps=True,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=band_line.upper() if not house else band_line,
                    x=TEXT_MARGIN_X_PCT,
                    y=band_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(70, 90, rng),
                    font_family=_DISPLAY_BAND_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    all_caps=not house,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=date,
                    x=TEXT_MARGIN_X_PCT,
                    y=date_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(28, 36, rng),
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=time.upper() if time else "TBA",
                    x=TEXT_MARGIN_X_PCT,
                    y=time_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(48, 62, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.CENTER,
                    color=ColorSpec(accent_color),
                ),
            ],
            graphic_elements=graphic_els,
            photocopy_effect=0.0,
            age_effect=0.0,
        ),
        venue, band, time, address=address, event=event,
    )


def _create_collage_torn_reveal(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: TierArchetype,
    rng: random.Random,
) -> LayoutSpec:
    """Torn-edge photo reveal with tape seams on light paste-up."""
    arch = archetype
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    bg_color, fg_color, accent_color = _creative_palette(arch, dark=rng.random() > 0.4)

    venue_y = round(top_y + 0.5, 1)
    photo_y = round(venue_y + 13.0 + gap, 1)
    photo_h = _ri(38, 46, rng)
    photo_w = _rf(82, 92, rng)
    photo_x = round((100 - photo_w) / 2, 1)
    photo_bottom = round(photo_y + photo_h, 1)
    band_y = round(photo_bottom + gap + 1.5, 1)
    date_y = round(band_y + 7.5 + gap, 1)
    time_y = round(date_y + 5.5 + gap, 1)

    graphic_els: list[GraphicElement] = [
        GraphicElement(
            element_type="tape",
            x=round(photo_x + photo_w * 0.3, 1),
            y=round(photo_y - 1.5, 1),
            width=18,
            height=4,
            rotation=_rf(-5, 5, rng),
        ),
        GraphicElement(
            element_type="tape",
            x=round(photo_x + photo_w * 0.55, 1),
            y=round(photo_y + photo_h - 2.5, 1),
            width=14,
            height=4,
            rotation=_rf(-8, 8, rng),
        ),
    ]

    return finalize_layout_spec(
        LayoutSpec(
            design_style=DesignStyle.COLLAGE,
            style_notes="Creative torn_reveal — torn-edge photo, dual tape seams",
            background=BackgroundSpec(
                color=ColorSpec(bg_color),
                texture="paper",
                texture_strength=_rf(0.28, 0.42, rng),
                grain_strength=arch.grain_strength + 0.02,
                margin_grain_only=True,
            ),
            photo_frame=_build_creative_photo(
                arch, rng,
                photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h,
                fg_color=fg_color, mask_shape="torn_edge",
            ),
            text_elements=[
                TextElement(
                    content=venue.upper(),
                    x=TEXT_MARGIN_X_PCT,
                    y=venue_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(48, 62, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    all_caps=True,
                    color=ColorSpec(accent_color if bg_color != arch.paper_color else fg_color),
                ),
                TextElement(
                    content=band_line.upper() if not house else band_line,
                    x=TEXT_MARGIN_X_PCT,
                    y=band_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(68, 88, rng),
                    font_family=_DISPLAY_BAND_FONT,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    all_caps=not house,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=date,
                    x=TEXT_MARGIN_X_PCT,
                    y=date_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(28, 38, rng),
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(fg_color),
                ),
                TextElement(
                    content=time.upper() if time else "TBA",
                    x=TEXT_MARGIN_X_PCT,
                    y=time_y,
                    width=MAX_TEXT_WIDTH_PCT,
                    font_size=_ri(44, 58, rng),
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(fg_color),
                ),
            ],
            graphic_elements=graphic_els,
            photocopy_effect=0.0,
            age_effect=0.0,
        ),
        venue, band, time, address=address, event=event,
    )


def create_collage_layout(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    archetype: Optional[TierArchetype] = None,
    rng: Optional[random.Random] = None,
    research: Optional[dict[str, Any]] = None,
    graphic_archetype: str | None = None,
) -> LayoutSpec:
    """Option C — Graphic Composer: Style DNA pro archetypes with seeded palette/accent."""
    from structured_layout.graphic_composer import build_recipe, recipe_signature

    r = rng or _make_rng()
    _ = archetype or load_tier_archetype("creative", event=event, research=research)
    from state import load_design_preferences
    from preference_model import preference_weights

    forced_arch = graphic_archetype
    if forced_arch is None and research:
        from visual_studies import pick_study_for_research

        study = pick_study_for_research(research)
        forced_arch = study.graphic_archetype

    recipe = build_recipe(
        r,
        archetype=forced_arch,
        preferences=preference_weights(load_design_preferences()),
    )
    seed = recipe.seed
    date_line = _compact_date_upper(date)

    return LayoutSpec(
        canvas_width=1024,
        canvas_height=1536,
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe_signature(recipe),
        background=BackgroundSpec(color=ColorSpec("#f0ebe0"), texture="none"),
        photo_frame=PhotoFrame(
            x=10,
            y=18,
            width=80,
            height=44,
            placement=PhotoPlacement.CENTER,
            opacity=1.0,
        ),
        text_elements=[
            TextElement(
                content=venue,
                x=TEXT_MARGIN_X_PCT,
                y=_safe_y_pct(),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_XL,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
            ),
            TextElement(
                content=band,
                x=TEXT_MARGIN_X_PCT,
                y=_safe_y_pct() + 8,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_LG,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
            ),
            TextElement(
                content=date_line,
                x=TEXT_MARGIN_X_PCT,
                y=72,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_MD,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
            ),
            TextElement(
                content=time.upper() if time else "TBA",
                x=TEXT_MARGIN_X_PCT,
                y=78,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_MD,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
            ),
            TextElement(
                content=address,
                x=TEXT_MARGIN_X_PCT,
                y=88,
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_SM,
                font_weight=FontWeight.NORMAL,
                alignment=TextAlignment.LEFT,
            ),
        ],
        graphic_elements=[],
        photocopy_effect=0.0,
        age_effect=0.0,
    )


def layout_for_option(
    letter: str,
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
    research: Optional[dict[str, Any]] = None,
    gig_id: Optional[str] = None,
    option_letter: Optional[str] = None,
    round_num: Optional[int] = None,
) -> LayoutSpec:
    """Return the fixed template for option A, B, or C."""
    opt = letter.upper()
    tier_map = {"A": "conservative", "B": "medium", "C": "creative"}
    tier = tier_map.get(opt, "medium")
    archetype = load_tier_archetype(tier, event=event, research=research)
    rng = _make_rng(gig_id, option_letter or opt, round_num)
    kwargs = {
        "address": address,
        "event": event,
        "archetype": archetype,
        "rng": rng,
        "research": research,
    }

    if opt == "A":
        return create_simple_stack_layout(venue, band, date, time, **kwargs)
    if opt == "C":
        return create_collage_layout(venue, band, date, time, **kwargs)
    return create_handbill_layout(venue, band, date, time, **kwargs)


# Backward-compatible aliases
create_default_handbill_layout = create_handbill_layout
create_default_collage_layout = create_collage_layout
