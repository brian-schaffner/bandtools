"""Procedural creative layout composer for Option C.

Each run combines independent axes (topology, mood, date treatment, accents,
photo style) into a unique layout — not a fixed template pick.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Optional

from structured_layout.design_system import (
    FONT_BODY_CONDENSED,
    FONT_DISPLAY,
    FONT_DISPLAY_HEAVY,
    TYPE_HERO,
    TYPE_LG,
    TYPE_MD,
    TYPE_SM,
    TYPE_XL,
    TYPE_XS,
    TYPE_XXL,
    snap_pct,
)
from structured_layout.layout_geometry import MAX_TEXT_WIDTH_PCT, TEXT_MARGIN_X_PCT, VERTICAL_GAP_PCT
from structured_layout.layout_spec import (
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
from structured_layout.tier_archetypes import TierArchetype
from text_validation import SAFE_MARGIN_PX, featured_act_line, is_house_series_gig

_DISPLAY_VENUE = FONT_DISPLAY
_DISPLAY_BAND = FONT_DISPLAY_HEAVY

TOPOLOGIES = (
    "column_split",
    "diagonal_hero",
    "layered_pasteup",
    "bottom_bleed",
    "corner_poster",
    "slab_interrupted",
)
MOODS = ("dark_ink", "warm_paper", "split_wash", "duotone_pop")
DATE_STYLES = ("giant_day", "diagonal_band", "starburst", "prose_compact")
ACCENT_POOL = ("tape", "stamp", "corner_strip", "ticket_stub", "perforated_margin")
PHOTO_STYLES = ("torn", "polaroid", "full_bleed", "duotone")


def _safe_y_pct(canvas_height: int = 1536) -> float:
    return round(SAFE_MARGIN_PX / canvas_height * 100, 1)


def _rf(lo: float, hi: float, rng: random.Random, decimals: int = 1) -> float:
    return round(rng.uniform(lo, hi), decimals)


def _ri(lo: int, hi: int, rng: random.Random) -> int:
    return rng.randint(lo, hi)


def _month_day_stack(date: str) -> tuple[str, str]:
    parts = date.replace(",", "").split()
    if len(parts) >= 3:
        return parts[1][:3].upper(), parts[2]
    return date[:6].upper(), ""


def _short_date(date: str) -> str:
    parts = date.replace(",", "").split()
    if len(parts) >= 4:
        return f"{parts[0][:3].upper()} {parts[1][:3].upper()} {parts[2]}"
    return date[:12].upper()


def _starburst_date(date: str) -> str:
    parts = date.replace(",", "").split()
    if len(parts) >= 4:
        return f"{parts[1][:3].upper()}\n{parts[2]}"
    return date[:6].upper()


def _poster_band_lines(band: str) -> tuple[str, str]:
    words = band.upper().split()
    if len(words) <= 1:
        return band.upper(), ""
    if len(words) == 2:
        return words[0], words[1]
    mid = max(1, len(words) // 2)
    return " ".join(words[:mid]), " ".join(words[mid:])


def _render_seed(rng: random.Random) -> int:
    return rng.randint(1, 2_000_000_000)


@dataclass(frozen=True)
class CreativeRecipe:
    topology: str
    mood: str
    date_style: str
    accents: tuple[str, ...]
    photo_style: str
    photo_side: str
    render_seed: int

    @property
    def signature(self) -> str:
        accent_str = "+".join(self.accents) if self.accents else "none"
        return (
            f"procedural creative — {self.topology}/{self.mood}/"
            f"{self.date_style}/{self.photo_style}/{accent_str}"
        )


def _pick_recipe(rng: random.Random) -> CreativeRecipe:
    topology = TOPOLOGIES[rng.randint(0, len(TOPOLOGIES) - 1)]
    mood = MOODS[rng.randint(0, len(MOODS) - 1)]
    date_style = DATE_STYLES[rng.randint(0, len(DATE_STYLES) - 1)]
    photo_style = PHOTO_STYLES[rng.randint(0, len(PHOTO_STYLES) - 1)]
    photo_side = rng.choice(("left", "right", "center"))

    accent_count = rng.randint(1, 2)
    pool = list(ACCENT_POOL)
    rng.shuffle(pool)
    accents = tuple(pool[:accent_count])

    return CreativeRecipe(
        topology=topology,
        mood=mood,
        date_style=date_style,
        accents=accents,
        photo_style=photo_style,
        photo_side=photo_side,
        render_seed=_render_seed(rng),
    )


def _palette(arch: TierArchetype, mood: str) -> tuple[str, str, str, Optional[str]]:
    """Return paper, ink, accent, optional wash."""
    paper = arch.paper_color
    ink = arch.ink_primary
    accent = arch.ink_accent
    if mood == "dark_ink":
        return arch.ink_muted, paper, accent, None
    if mood == "split_wash":
        return paper, ink, accent, arch.ink_muted
    if mood == "duotone_pop":
        return paper, ink, accent, accent
    return paper, ink, accent, None


def _photo_frame(
    rng: random.Random,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    fg: str,
    recipe: CreativeRecipe,
    placement: PhotoPlacement = PhotoPlacement.CENTER,
) -> PhotoFrame:
    mask = "rectangle"
    border = 0.0
    tint: Optional[ColorSpec] = None
    rotation = _rf(-2.0, 2.0, rng)
    if recipe.photo_style == "torn":
        mask = "torn_edge"
        rotation = _rf(-1.2, 1.2, rng)
    elif recipe.photo_style == "polaroid":
        border = _rf(3.0, 6.0, rng)
        rotation = _rf(-3.0, 3.0, rng)
    elif recipe.photo_style == "full_bleed":
        border = 0.0
        rotation = _rf(-0.8, 0.8, rng)
    elif recipe.photo_style == "duotone":
        tint = ColorSpec(recipe.mood == "duotone_pop" and fg or "#8B4513", opacity=0.18)

    return PhotoFrame(
        x=x,
        y=y,
        width=w,
        height=h,
        placement=placement,
        rotation=rotation,
        film_grain=_rf(0.004, 0.011, rng),
        paper_texture=0.0,
        border_width=border,
        border_color=ColorSpec(fg),
        mask_shape=mask,
        brightness=1.01,
        contrast=_rf(1.04, 1.14, rng),
        saturation=_rf(0.88, 1.0, rng),
        color_tint=tint,
        opacity=1.0,
    )


def _add_accents(
    graphics: list[GraphicElement],
    rng: random.Random,
    *,
    recipe: CreativeRecipe,
    accent: str,
    ink: str,
    paper: str,
    date: str,
    photo_x: float,
    photo_y: float,
    photo_w: float,
    photo_h: float,
) -> None:
    for kind in recipe.accents:
        if kind == "tape":
            graphics.append(
                GraphicElement(
                    element_type="tape",
                    x=round(photo_x + photo_w * _rf(0.2, 0.6, rng), 1),
                    y=round(photo_y - 1.0, 1),
                    width=_rf(10, 18, rng),
                    height=_rf(3, 5, rng),
                    rotation=_rf(-8, 8, rng),
                )
            )
        elif kind == "stamp":
            graphics.append(
                GraphicElement(
                    element_type="stamp",
                    x=round(100 - TEXT_MARGIN_X_PCT - 17, 1),
                    y=round(_safe_y_pct() + 0.5, 1),
                    width=16,
                    height=9,
                    stroke_color=ColorSpec(accent),
                    stroke_width=2,
                    rotation=_rf(-14, -4, rng),
                    properties={"text": _short_date(date)},
                )
            )
        elif kind == "corner_strip":
            corner = rng.choice(("top_left", "top_right", "bottom_left", "bottom_right"))
            graphics.append(
                GraphicElement(
                    element_type="corner_strip",
                    x=TEXT_MARGIN_X_PCT if "left" in corner else snap_pct(72.0),
                    y=_safe_y_pct() if "top" in corner else snap_pct(62.0),
                    width=_rf(22, 32, rng),
                    height=_rf(14, 22, rng),
                    fill_color=ColorSpec(accent),
                    properties={"corner": corner},
                )
            )
        elif kind == "ticket_stub":
            graphics.append(
                GraphicElement(
                    element_type="ticket_stub",
                    x=round(TEXT_MARGIN_X_PCT + _rf(0, 8, rng), 1),
                    y=round(photo_y + photo_h - 12, 1),
                    width=_rf(14, 20, rng),
                    height=_rf(10, 14, rng),
                    stroke_color=ColorSpec(ink),
                    properties={"perforations": _ri(8, 14, rng)},
                )
            )
        elif kind == "perforated_margin":
            graphics.append(
                GraphicElement(
                    element_type="perforated_margin",
                    x=TEXT_MARGIN_X_PCT - 1.5,
                    y=_safe_y_pct(),
                    width=2.5,
                    height=snap_pct(88.0),
                    stroke_color=ColorSpec(ink, opacity=0.35),
                    properties={"holes": _ri(18, 28, rng)},
                )
            )


def _date_elements(
    rng: random.Random,
    *,
    recipe: CreativeRecipe,
    date: str,
    time: str,
    x: float,
    y: float,
    width: float,
    ink: str,
    paper: str,
    accent: str,
    graphics: list[GraphicElement],
) -> tuple[list[TextElement], float]:
    month, day = _month_day_stack(date)
    texts: list[TextElement] = []
    cursor_y = y

    if recipe.date_style == "giant_day":
        texts.extend(
            [
                TextElement(
                    content=month,
                    x=x,
                    y=cursor_y,
                    width=width,
                    font_size=TYPE_SM,
                    font_family=FONT_BODY_CONDENSED,
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(accent),
                    letter_spacing=0.08,
                ),
                TextElement(
                    content=day,
                    x=x,
                    y=round(cursor_y + 3.5, 1),
                    width=width,
                    font_size=TYPE_HERO,
                    font_family=_DISPLAY_BAND,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    color=ColorSpec(ink),
                    line_height=0.82,
                ),
            ]
        )
        cursor_y = round(cursor_y + 14.0, 1)
    elif recipe.date_style == "diagonal_band":
        band_y = cursor_y
        graphics.append(
            GraphicElement(
                element_type="diagonal_band",
                x=x - 2,
                y=band_y,
                width=width + 4,
                height=snap_pct(9.0),
                fill_color=ColorSpec(accent),
                rotation=_rf(-10, -4, rng),
                properties={"text": f"{month} {day}".strip(), "label": "date"},
            )
        )
        cursor_y = round(band_y + 11.0, 1)
    elif recipe.date_style == "starburst":
        burst_y = cursor_y
        graphics.append(
            GraphicElement(
                element_type="starburst",
                x=x,
                y=burst_y,
                width=_rf(20, 26, rng),
                height=_rf(14, 18, rng),
                fill_color=ColorSpec(accent),
                properties={"text": _starburst_date(date), "spikes": _ri(8, 12, rng)},
            )
        )
        cursor_y = round(burst_y + 16.0, 1)
    else:
        texts.append(
            TextElement(
                content=date.upper() if len(date) < 40 else date,
                x=x,
                y=cursor_y,
                width=width,
                font_size=TYPE_MD,
                font_family=FONT_BODY_CONDENSED,
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(ink),
            )
        )
        cursor_y = round(cursor_y + 5.5, 1)

    texts.append(
        TextElement(
            content=time.upper() if time else "TBA",
            x=x,
            y=cursor_y,
            width=width,
            font_size=TYPE_XL,
            font_family=_DISPLAY_BAND,
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.LEFT,
            color=ColorSpec(accent if recipe.mood == "dark_ink" else ink),
        )
    )
    return texts, round(cursor_y + 6.0, 1)


def _band_elements(
    rng: random.Random,
    *,
    band_line: str,
    house: bool,
    band: str,
    x: float,
    y: float,
    width: float,
    ink: str,
    paper: str,
    accent: str,
    dark: bool,
) -> tuple[list[TextElement], float]:
    texts: list[TextElement] = []
    fg = paper if dark else ink
    if house:
        texts.append(
            TextElement(
                content="FEATURING",
                x=x,
                y=y,
                width=width,
                font_size=TYPE_MD,
                font_family=FONT_BODY_CONDENSED,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                all_caps=True,
                color=ColorSpec(accent),
            )
        )
        act1, act2 = _poster_band_lines(band)
        y2 = round(y + 4.5, 1)
        texts.append(
            TextElement(
                content=act1,
                x=x,
                y=y2,
                width=width,
                font_size=TYPE_XL,
                font_family=_DISPLAY_BAND,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                all_caps=True,
                color=ColorSpec(fg),
            )
        )
        if act2:
            texts.append(
                TextElement(
                    content=act2,
                    x=x,
                    y=round(y2 + 6.5, 1),
                    width=width,
                    font_size=TYPE_XL,
                    font_family=_DISPLAY_BAND,
                    font_weight=FontWeight.BLACK,
                    alignment=TextAlignment.LEFT,
                    all_caps=True,
                    color=ColorSpec(fg),
                )
            )
            return texts, round(y2 + 13.0, 1)
        return texts, round(y2 + 7.0, 1)

    line1, line2 = _poster_band_lines(band_line)
    texts.append(
        TextElement(
            content=line1,
            x=x,
            y=y,
            width=width,
            font_size=TYPE_HERO,
            font_family=_DISPLAY_BAND,
            font_weight=FontWeight.BLACK,
            alignment=TextAlignment.LEFT,
            color=ColorSpec(fg),
            line_height=0.82,
        )
    )
    if line2:
        y2 = round(y + 8.5, 1)
        texts.append(
            TextElement(
                content=line2,
                x=x,
                y=y2,
                width=width,
                font_size=TYPE_XXL,
                font_family=_DISPLAY_BAND,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(fg),
                line_height=0.85,
            )
        )
        return texts, round(y2 + 7.5, 1)
    return texts, round(y + 8.0, 1)


def _footer_info(
    venue: str,
    month: str,
    day: str,
    time: str,
    address: str,
    y: float,
    ink: str,
) -> TextElement:
    parts = [venue, f"{month} {day}".strip(), time.upper() if time else ""]
    if address:
        parts.append(address)
    return TextElement(
        content="  ·  ".join(p for p in parts if p),
        x=TEXT_MARGIN_X_PCT,
        y=y,
        width=MAX_TEXT_WIDTH_PCT,
        font_size=TYPE_XS,
        font_family=FONT_BODY_CONDENSED,
        font_weight=FontWeight.BOLD,
        alignment=TextAlignment.LEFT,
        color=ColorSpec(ink),
    )


def _compose_column_split(
    rng: random.Random,
    recipe: CreativeRecipe,
    *,
    venue: str,
    band: str,
    band_line: str,
    house: bool,
    date: str,
    time: str,
    address: str,
    arch: TierArchetype,
) -> LayoutSpec:
    paper, ink, accent, wash = _palette(arch, recipe.mood)
    dark = recipe.mood == "dark_ink"
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    photo_left = recipe.photo_side != "right"
    photo_w = snap_pct(_rf(44, 50, rng))
    photo_h = snap_pct(_rf(68, 78, rng))
    photo_x = TEXT_MARGIN_X_PCT if photo_left else snap_pct(100 - TEXT_MARGIN_X_PCT - photo_w)
    panel_x = snap_pct(photo_x + photo_w + 2.5) if photo_left else TEXT_MARGIN_X_PCT
    panel_w = snap_pct(100 - panel_x - TEXT_MARGIN_X_PCT)

    graphics: list[GraphicElement] = []
    if dark or recipe.mood == "split_wash":
        graphics.append(
            GraphicElement(
                element_type="box",
                x=panel_x,
                y=top_y,
                width=panel_w,
                height=photo_h,
                fill_color=ColorSpec(ink if dark else accent, opacity=0.92 if dark else 0.12),
            )
        )
    graphics.append(
        GraphicElement(
            element_type="box",
            x=panel_x - 0.5 if photo_left else photo_x + photo_w,
            y=top_y,
            width=snap_pct(1.0),
            height=photo_h,
            fill_color=ColorSpec(accent),
        )
    )

    type_x, type_w = panel_x, panel_w
    type_fg = paper if dark else ink
    venue_y = round(top_y + 1.5, 1)
    band_y = round(venue_y + 5.5, 1)
    band_texts, after_band = _band_elements(
        rng, band_line=band_line, house=house, band=band,
        x=type_x, y=band_y, width=type_w, ink=ink, paper=paper, accent=accent, dark=dark,
    )
    date_texts, _ = _date_elements(
        rng, recipe=recipe, date=date, time=time,
        x=type_x, y=after_band + 1.5, width=type_w, ink=type_fg, paper=paper, accent=accent,
        graphics=graphics,
    )
    month, day = _month_day_stack(date)
    info_y = round(top_y + photo_h + gap + 1.0, 1)
    graphics.append(
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=info_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=0.35,
            fill_color=ColorSpec(ink),
        )
    )
    _add_accents(graphics, rng, recipe=recipe, accent=accent, ink=ink, paper=paper, date=date,
                 photo_x=photo_x, photo_y=top_y, photo_w=photo_w, photo_h=photo_h)

    bg = BackgroundSpec(
        color=ColorSpec(paper),
        texture=rng.choice(("paper", "photocopy")),
        texture_strength=_rf(0.10, 0.28, rng),
        grain_strength=_rf(0.008, 0.022, rng),
        wash_color=ColorSpec(wash, opacity=0.35) if wash and recipe.mood == "split_wash" else None,
        wash_height_pct=snap_pct(_rf(38, 52, rng)) if wash and recipe.mood == "split_wash" else 0.0,
    )
    return LayoutSpec(
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe.signature,
        render_seed=recipe.render_seed,
        background=bg,
        photo_frame=_photo_frame(
            rng, x=photo_x, y=top_y, w=photo_w, h=photo_h, fg=paper if dark else ink,
            recipe=recipe, placement=PhotoPlacement.LEFT if photo_left else PhotoPlacement.RIGHT,
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=type_x,
                y=venue_y,
                width=type_w,
                font_size=TYPE_LG,
                font_family=_DISPLAY_VENUE,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                all_caps=True,
                color=ColorSpec(accent if not dark else accent),
            ),
            *band_texts,
            *date_texts,
            _footer_info(venue, month, day, time, address, round(info_y + 3.5, 1), ink),
        ],
        graphic_elements=graphics,
    )


def _compose_diagonal_hero(
    rng: random.Random,
    recipe: CreativeRecipe,
    *,
    venue: str,
    band: str,
    band_line: str,
    house: bool,
    date: str,
    time: str,
    address: str,
    arch: TierArchetype,
) -> LayoutSpec:
    paper, ink, accent, wash = _palette(arch, recipe.mood)
    dark = recipe.mood == "dark_ink"
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    graphics: list[GraphicElement] = [
        GraphicElement(
            element_type="diagonal_band",
            x=TEXT_MARGIN_X_PCT,
            y=top_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=snap_pct(22.0),
            fill_color=ColorSpec(ink if dark else accent),
            rotation=_rf(-14, -6, rng),
            properties={"text": venue.upper(), "label": "venue"},
        ),
    ]
    band_y = round(top_y + 16.0, 1)
    band_texts, after_band = _band_elements(
        rng, band_line=band_line, house=house, band=band,
        x=TEXT_MARGIN_X_PCT, y=band_y, width=snap_pct(52.0),
        ink=paper if dark else ink, paper=paper, accent=accent, dark=dark,
    )
    date_texts, _ = _date_elements(
        rng, recipe=recipe, date=date, time=time,
        x=TEXT_MARGIN_X_PCT, y=after_band + 1.0, width=snap_pct(48.0),
        ink=paper if dark else ink, paper=paper, accent=accent, graphics=graphics,
    )
    photo_w = snap_pct(_rf(46, 54, rng))
    photo_h = snap_pct(_rf(36, 44, rng))
    photo_x = snap_pct(100 - TEXT_MARGIN_X_PCT - photo_w + _rf(-2, 2, rng))
    photo_y = round(top_y + 18.0, 1)
    month, day = _month_day_stack(date)
    info_y = round(photo_y + photo_h + gap + 1.0, 1)
    _add_accents(graphics, rng, recipe=recipe, accent=accent, ink=ink, paper=paper, date=date,
                 photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h)

    return LayoutSpec(
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe.signature,
        render_seed=recipe.render_seed,
        background=BackgroundSpec(
            color=ColorSpec(paper if not dark else arch.ink_muted),
            texture="photocopy",
            texture_strength=_rf(0.18, 0.32, rng),
            grain_strength=_rf(0.012, 0.028, rng),
            wash_color=ColorSpec(wash, opacity=0.25) if wash else None,
            wash_height_pct=snap_pct(_rf(30, 45, rng)) if wash else 0.0,
        ),
        photo_frame=_photo_frame(
            rng, x=photo_x, y=photo_y, w=photo_w, h=photo_h, fg=paper, recipe=recipe,
        ),
        text_elements=[
            *band_texts,
            *date_texts,
            _footer_info(venue, month, day, time, address, info_y, ink if not dark else paper),
        ],
        graphic_elements=graphics,
    )


def _compose_layered_pasteup(
    rng: random.Random,
    recipe: CreativeRecipe,
    *,
    venue: str,
    band: str,
    band_line: str,
    house: bool,
    date: str,
    time: str,
    address: str,
    arch: TierArchetype,
) -> LayoutSpec:
    paper, ink, accent, _wash = _palette(arch, recipe.mood)
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    graphics: list[GraphicElement] = []
    for i, (bx, by, bw, bh, rot, col, op) in enumerate(
        [
            (TEXT_MARGIN_X_PCT, top_y + 8, 62, 28, _rf(2, 5, rng), ink, 0.08),
            (snap_pct(28.0), top_y + 2, 58, 24, _rf(-4, -1, rng), accent, 0.18),
            (snap_pct(8.0), top_y + 22, 70, 18, _rf(-2, 3, rng), accent, 0.12),
        ]
    ):
        graphics.append(
            GraphicElement(
                element_type="box",
                x=bx,
                y=by,
                width=bw,
                height=bh,
                fill_color=ColorSpec(col, opacity=op),
                rotation=rot,
            )
        )
    venue_y = round(top_y + 10.0, 1)
    band_texts, after_band = _band_elements(
        rng, band_line=band_line, house=house, band=band,
        x=TEXT_MARGIN_X_PCT, y=round(venue_y + 6.0, 1), width=snap_pct(55.0),
        ink=ink, paper=paper, accent=accent, dark=False,
    )
    photo_w = snap_pct(_rf(72, 86, rng))
    photo_h = snap_pct(_rf(32, 40, rng))
    photo_x = round((100 - photo_w) / 2 + _rf(-4, 4, rng), 1)
    photo_y = round(after_band + gap + 2.0, 1)
    date_texts, _ = _date_elements(
        rng, recipe=recipe, date=date, time=time,
        x=TEXT_MARGIN_X_PCT, y=round(photo_y + photo_h + gap + 1.0, 1), width=snap_pct(50.0),
        ink=ink, paper=paper, accent=accent, graphics=graphics,
    )
    month, day = _month_day_stack(date)
    _add_accents(graphics, rng, recipe=recipe, accent=accent, ink=ink, paper=paper, date=date,
                 photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h)

    return LayoutSpec(
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe.signature,
        render_seed=recipe.render_seed,
        background=BackgroundSpec(
            color=ColorSpec(paper),
            texture="paper",
            texture_strength=_rf(0.14, 0.26, rng),
            grain_strength=_rf(0.010, 0.020, rng),
        ),
        photo_frame=_photo_frame(
            rng, x=photo_x, y=photo_y, w=photo_w, h=photo_h, fg=paper, recipe=recipe,
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=venue_y,
                width=snap_pct(58.0),
                font_size=TYPE_XL,
                font_family=_DISPLAY_VENUE,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(accent),
            ),
            *band_texts,
            *date_texts,
            _footer_info(venue, month, day, time, address, round(photo_y + photo_h + gap + 14.0, 1), ink),
        ],
        graphic_elements=graphics,
    )


def _compose_bottom_bleed(
    rng: random.Random,
    recipe: CreativeRecipe,
    *,
    venue: str,
    band: str,
    band_line: str,
    house: bool,
    date: str,
    time: str,
    address: str,
    arch: TierArchetype,
) -> LayoutSpec:
    paper, ink, accent, wash = _palette(arch, recipe.mood)
    dark = recipe.mood == "dark_ink"
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    photo_h = snap_pct(_rf(48, 56, rng))
    photo_w = snap_pct(_rf(88, 94, rng))
    photo_x = round((100 - photo_w) / 2, 1)
    photo_y = top_y
    graphics: list[GraphicElement] = []
    type_y = round(photo_y + photo_h + gap + 1.0, 1)
    slab_h = snap_pct(_rf(16, 22, rng))
    graphics.append(
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT if rng.random() > 0.5 else snap_pct(22.0),
            y=type_y,
            width=snap_pct(_rf(72, 90, rng)),
            height=slab_h,
            fill_color=ColorSpec(ink if dark else accent, opacity=0.95 if dark else 1.0),
            rotation=_rf(-1.5, 1.5, rng),
        )
    )
    band_texts, after_band = _band_elements(
        rng, band_line=band_line, house=house, band=band,
        x=TEXT_MARGIN_X_PCT + 1.5, y=round(type_y + 2.0, 1), width=snap_pct(70.0),
        ink=paper if dark else paper, paper=paper, accent=accent, dark=True,
    )
    date_texts, _ = _date_elements(
        rng, recipe=recipe, date=date, time=time,
        x=snap_pct(58.0), y=type_y + 2.0, width=snap_pct(36.0),
        ink=paper, paper=paper, accent=accent, graphics=graphics,
    )
    month, day = _month_day_stack(date)
    _add_accents(graphics, rng, recipe=recipe, accent=accent, ink=ink, paper=paper, date=date,
                 photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h)
    info_y = round(type_y + slab_h + gap + 2.0, 1)
    return LayoutSpec(
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe.signature,
        render_seed=recipe.render_seed,
        background=BackgroundSpec(
            color=ColorSpec(paper if not dark else arch.ink_muted),
            texture=rng.choice(("paper", "cardboard")),
            texture_strength=_rf(0.16, 0.30, rng),
            grain_strength=_rf(0.010, 0.024, rng),
            wash_color=ColorSpec(wash, opacity=0.30) if wash and recipe.mood == "split_wash" else None,
            wash_height_pct=snap_pct(_rf(42, 58, rng)) if wash and recipe.mood == "split_wash" else 0.0,
        ),
        photo_frame=_photo_frame(
            rng, x=photo_x, y=photo_y, w=photo_w, h=photo_h, fg=paper, recipe=recipe,
            placement=PhotoPlacement.TOP,
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=round(photo_y + photo_h - 8.0, 1),
                width=snap_pct(60.0),
                font_size=TYPE_LG,
                font_family=_DISPLAY_VENUE,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(accent),
            ),
            *band_texts,
            *date_texts,
            _footer_info(venue, month, day, time, address, info_y, paper if dark else ink),
        ],
        graphic_elements=graphics,
    )


def _compose_corner_poster(
    rng: random.Random,
    recipe: CreativeRecipe,
    *,
    venue: str,
    band: str,
    band_line: str,
    house: bool,
    date: str,
    time: str,
    address: str,
    arch: TierArchetype,
) -> LayoutSpec:
    paper, ink, accent, _wash = _palette(arch, recipe.mood)
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    corner = rng.choice(("bottom_right", "bottom_left", "top_right"))
    photo_w = snap_pct(_rf(34, 42, rng))
    photo_h = snap_pct(_rf(28, 36, rng))
    if "right" in corner:
        photo_x = snap_pct(100 - TEXT_MARGIN_X_PCT - photo_w)
    else:
        photo_x = TEXT_MARGIN_X_PCT
    if "bottom" in corner:
        photo_y = snap_pct(_rf(52, 62, rng))
    else:
        photo_y = round(top_y + 2.0, 1)

    type_x = TEXT_MARGIN_X_PCT
    type_w = snap_pct(58.0)
    graphics: list[GraphicElement] = []
    venue_y = top_y
    band_texts, after_band = _band_elements(
        rng, band_line=band_line, house=house, band=band,
        x=type_x, y=round(venue_y + 7.0, 1), width=type_w,
        ink=ink, paper=paper, accent=accent, dark=False,
    )
    date_texts, _ = _date_elements(
        rng, recipe=recipe, date=date, time=time,
        x=type_x, y=after_band + 1.0, width=type_w,
        ink=ink, paper=paper, accent=accent, graphics=graphics,
    )
    month, day = _month_day_stack(date)
    _add_accents(graphics, rng, recipe=recipe, accent=accent, ink=ink, paper=paper, date=date,
                 photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h)
    info_y = round(photo_y + photo_h + gap + 2.0, 1) if "bottom" in corner else snap_pct(78.0)

    return LayoutSpec(
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe.signature,
        render_seed=recipe.render_seed,
        background=BackgroundSpec(
            color=ColorSpec(paper),
            texture="photocopy",
            texture_strength=_rf(0.12, 0.24, rng),
            grain_strength=_rf(0.008, 0.018, rng),
        ),
        photo_frame=_photo_frame(
            rng, x=photo_x, y=photo_y, w=photo_w, h=photo_h, fg=paper, recipe=recipe,
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=type_x,
                y=venue_y,
                width=type_w,
                font_size=TYPE_XL,
                font_family=_DISPLAY_VENUE,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.LEFT,
                color=ColorSpec(accent),
            ),
            *band_texts,
            *date_texts,
            _footer_info(venue, month, day, time, address, info_y, ink),
        ],
        graphic_elements=graphics,
    )


def _compose_slab_interrupted(
    rng: random.Random,
    recipe: CreativeRecipe,
    *,
    venue: str,
    band: str,
    band_line: str,
    house: bool,
    date: str,
    time: str,
    address: str,
    arch: TierArchetype,
) -> LayoutSpec:
    paper, ink, accent, wash = _palette(arch, recipe.mood)
    dark = recipe.mood == "dark_ink"
    top_y = _safe_y_pct()
    gap = VERTICAL_GAP_PCT
    slab_y = snap_pct(_rf(38, 48, rng))
    slab_h = snap_pct(_rf(14, 20, rng))
    photo_above = rng.random() > 0.5
    graphics: list[GraphicElement] = [
        GraphicElement(
            element_type="box",
            x=TEXT_MARGIN_X_PCT,
            y=slab_y,
            width=MAX_TEXT_WIDTH_PCT,
            height=slab_h,
            fill_color=ColorSpec(ink if dark else accent),
            rotation=_rf(-0.8, 0.8, rng),
        ),
    ]
    photo_w = snap_pct(_rf(78, 90, rng))
    photo_h = snap_pct(_rf(30, 38, rng))
    photo_x = round((100 - photo_w) / 2 + _rf(-3, 3, rng), 1)
    if photo_above:
        photo_y = top_y
        type_y = round(slab_y + 2.0, 1)
    else:
        photo_y = round(slab_y + slab_h + gap + 1.0, 1)
        type_y = top_y

    band_texts, after_band = _band_elements(
        rng, band_line=band_line, house=house, band=band,
        x=TEXT_MARGIN_X_PCT, y=type_y, width=MAX_TEXT_WIDTH_PCT,
        ink=paper if dark else ink, paper=paper, accent=accent, dark=dark,
    )
    date_texts, _ = _date_elements(
        rng, recipe=recipe, date=date, time=time,
        x=TEXT_MARGIN_X_PCT, y=after_band + 1.0, width=snap_pct(48.0),
        ink=paper if dark else ink, paper=paper, accent=accent, graphics=graphics,
    )
    month, day = _month_day_stack(date)
    _add_accents(graphics, rng, recipe=recipe, accent=accent, ink=ink, paper=paper, date=date,
                 photo_x=photo_x, photo_y=photo_y, photo_w=photo_w, photo_h=photo_h)
    footer_y = round((photo_y + photo_h + gap + 2.0) if photo_above else (photo_y + photo_h + gap + 2.0), 1)

    return LayoutSpec(
        design_style=DesignStyle.COLLAGE,
        style_notes=recipe.signature,
        render_seed=recipe.render_seed,
        background=BackgroundSpec(
            color=ColorSpec(paper if not dark else arch.ink_muted),
            texture="paper",
            texture_strength=_rf(0.14, 0.28, rng),
            grain_strength=_rf(0.010, 0.022, rng),
            wash_color=ColorSpec(wash, opacity=0.28) if wash else None,
            wash_height_pct=snap_pct(_rf(35, 50, rng)) if wash else 0.0,
        ),
        photo_frame=_photo_frame(
            rng, x=photo_x, y=photo_y, w=photo_w, h=photo_h, fg=paper, recipe=recipe,
        ),
        text_elements=[
            TextElement(
                content=venue.upper(),
                x=TEXT_MARGIN_X_PCT,
                y=round(slab_y + slab_h + 1.0, 1) if photo_above else round(slab_y - 6.0, 1),
                width=MAX_TEXT_WIDTH_PCT,
                font_size=TYPE_LG,
                font_family=_DISPLAY_VENUE,
                font_weight=FontWeight.BLACK,
                alignment=TextAlignment.CENTER,
                color=ColorSpec(accent if not photo_above else (paper if dark else ink)),
            ),
            *band_texts,
            *date_texts,
            _footer_info(venue, month, day, time, address, footer_y, paper if dark else ink),
        ],
        graphic_elements=graphics,
    )


_BUILDERS = {
    "column_split": _compose_column_split,
    "diagonal_hero": _compose_diagonal_hero,
    "layered_pasteup": _compose_layered_pasteup,
    "bottom_bleed": _compose_bottom_bleed,
    "corner_poster": _compose_corner_poster,
    "slab_interrupted": _compose_slab_interrupted,
}


def compose_creative_layout(
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
    """Build a unique procedural Option C layout from seeded recipe axes."""
    recipe = _pick_recipe(rng)
    house = is_house_series_gig(event) if event is not None else False
    band_line = featured_act_line(band) if house else band
    builder = _BUILDERS[recipe.topology]
    layout = builder(
        rng,
        recipe,
        venue=venue,
        band=band,
        band_line=band_line,
        house=house,
        date=date,
        time=time,
        address=address,
        arch=archetype,
    )
    return finalize_layout_spec(layout, venue, band, time, address=address, event=event)
