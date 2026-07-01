"""Graphic Composer — layered Option C renderer for maximum visual quality.

Deterministic: display typography, textures, accents, photo treatments.
Seeded recipe: archetype × palette × accent × mirror.
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from structured_layout.graphic_primitives import (
    CANVAS,
    compact_day,
    concentric_rings,
    draw_corner_strip,
    draw_diagonal_band,
    draw_double_rule,
    draw_starburst,
    draw_stroked_text_layer,
    draw_tape_strip,
    draw_ticket_stub,
    duotone_photo,
    grain,
    halftone_dots,
    halftone_photo,
    load_font,
    load_photo,
    oval_mask_photo,
    save_rgb,
    text_size,
    threshold_photo,
    torn_paste,
)
from structured_layout.layout_spec import LayoutSpec

STYLE_DNA_PREFIX = "style dna"

ARCHETYPES = (
    "xerox_punk",
    "duotone_modern",
    "psychedelic",
    "boutique",
    "neon_bar",
    "pasteup_zine",
    "broadside",
    "country_fair",
)

ACCENTS = ("starburst", "tape", "stamp", "none")
LAYER_ELEMENTS = ("corner_strip", "ticket_stub", "tape_corner", "rings", "double_rule")


@dataclass(frozen=True)
class Palette:
    paper: tuple[int, int, int]
    ink: tuple[int, int, int]
    accent: tuple[int, int, int]
    footer_bg: tuple[int, int, int]
    footer_fg: tuple[int, int, int]


PALETTES: dict[str, list[tuple[str, Palette]]] = {
    "xerox_punk": [
        ("cream_black", Palette((235, 228, 210), (15, 15, 15), (180, 40, 40), (12, 12, 12), (245, 245, 245))),
        ("newsprint_red", Palette((220, 215, 200), (20, 20, 20), (160, 30, 30), (20, 20, 20), (240, 230, 220))),
    ],
    "duotone_modern": [
        ("yellow_black", Palette((245, 197, 24), (12, 12, 12), (12, 12, 12), (12, 12, 12), (245, 197, 24))),
        ("red_cream", Palette((220, 50, 45), (255, 248, 235), (255, 248, 235), (40, 20, 20), (255, 230, 210))),
        ("blue_white", Palette((25, 55, 120), (255, 255, 255), (255, 210, 60), (15, 35, 80), (255, 255, 255))),
    ],
    "psychedelic": [
        ("magenta", Palette((255, 250, 240), (10, 10, 10), (199, 21, 133), (10, 10, 10), (255, 250, 240))),
        ("orange_teal", Palette((255, 245, 230), (0, 80, 90), (230, 90, 30), (0, 60, 70), (255, 240, 210))),
    ],
    "boutique": [
        ("navy_brick", Palette((250, 245, 235), (25, 42, 86), (168, 58, 42), (25, 42, 86), (250, 245, 235))),
        ("forest_gold", Palette((245, 240, 228), (34, 68, 45), (196, 140, 40), (34, 68, 45), (245, 235, 210))),
    ],
    "neon_bar": [
        ("dark_neon", Palette((18, 18, 22), (255, 255, 255), (255, 45, 120), (255, 45, 120), (18, 18, 22))),
        ("blue_glow", Palette((12, 16, 28), (240, 248, 255), (80, 200, 255), (80, 200, 255), (12, 16, 28))),
    ],
    "pasteup_zine": [
        ("zine_bw", Palette((240, 235, 225), (25, 25, 25), (200, 50, 50), (25, 25, 25), (240, 235, 225))),
    ],
    "broadside": [
        ("ink_cream", Palette((248, 242, 230), (15, 15, 15), (120, 30, 30), (15, 15, 15), (248, 242, 230))),
    ],
    "country_fair": [
        ("fair_banner", Palette((255, 252, 240), (120, 30, 30), (30, 80, 40), (120, 30, 30), (255, 252, 240))),
    ],
}


@dataclass(frozen=True)
class GraphicRecipe:
    archetype: str
    palette_id: str
    palette: Palette
    accent: str
    layers: tuple[str, ...]
    mirror: bool
    seed: int


def is_style_dna_layout(layout: LayoutSpec) -> bool:
    return STYLE_DNA_PREFIX in (layout.style_notes or "").lower()


def pick_creative_archetype(rng: random.Random) -> str:
    return ARCHETYPES[rng.randint(0, len(ARCHETYPES) - 1)]


def build_recipe(rng: random.Random, archetype: str | None = None) -> GraphicRecipe:
    arch = archetype or pick_creative_archetype(rng)
    options = PALETTES.get(arch, PALETTES["xerox_punk"])
    palette_id, palette = options[rng.randint(0, len(options) - 1)]
    accent = ACCENTS[rng.randint(0, len(ACCENTS) - 1)]
    if accent == "stamp" and arch not in ("xerox_punk", "pasteup_zine", "broadside"):
        accent = "starburst"
    layer_pool = [layer for layer in LAYER_ELEMENTS if not (layer == "tape_corner" and accent == "tape")]
    rng.shuffle(layer_pool)
    layer_count = rng.randint(2, min(3, len(layer_pool)))
    layers = tuple(layer_pool[:layer_count])
    return GraphicRecipe(
        archetype=arch,
        palette_id=palette_id,
        palette=palette,
        accent=accent,
        layers=layers,
        mirror=rng.random() < 0.35,
        seed=rng.randint(1, 2**31 - 1),
    )


def recipe_signature(recipe: GraphicRecipe) -> str:
    layer_sig = ",".join(recipe.layers) if recipe.layers else "none"
    return (
        f"style dna pro — {recipe.archetype}/{recipe.palette_id}/"
        f"{recipe.accent}+{layer_sig}{'/mirror' if recipe.mirror else ''} (seed {recipe.seed})"
    )


def parse_archetype_from_layout(layout: LayoutSpec) -> str | None:
    notes = (layout.style_notes or "").lower()
    for key in ARCHETYPES:
        if key in notes:
            return key
    return None


def _seed_from_layout(layout: LayoutSpec) -> int:
    match = re.search(r"seed (\d+)", layout.style_notes or "")
    return int(match.group(1)) if match else 42


def _facts_from_layout(layout: LayoutSpec) -> dict[str, str]:
    ordered = [t.content for t in sorted(layout.text_elements, key=lambda t: (t.y, t.x))]
    return {
        "venue": ordered[0] if len(ordered) > 0 else "",
        "band": ordered[1] if len(ordered) > 1 else "",
        "date": ordered[2] if len(ordered) > 2 else "",
        "time": ordered[3] if len(ordered) > 3 else "",
        "address": ordered[4] if len(ordered) > 4 else "",
    }


def _apply_primary_accent(canvas: Image.Image, recipe: GraphicRecipe, *, date: str, time: str) -> None:
    pal = recipe.palette
    if recipe.accent == "starburst":
        cx = 860 if not recipe.mirror else 164
        draw_starburst(
            canvas, cx, 140, 90,
            fill=(*pal.accent, 230),
            outline=(*pal.ink, 255),
            spikes=14,
        )
        font = load_font(28, "display")
        draw_stroked_text_layer(
            canvas, (cx, 140), compact_day(date), font, (*pal.footer_fg, 255),
            stroke=(*pal.ink, 255), stroke_width=2, anchor="mm",
        )
        draw_stroked_text_layer(
            canvas, (cx, 175), time.upper(), load_font(22, "body"), (*pal.ink, 255),
            stroke=(255, 255, 255, 255), stroke_width=1, anchor="mm",
        )
    elif recipe.accent == "tape":
        draw_tape_strip(canvas, (40, 36, 280, 78))
    elif recipe.accent == "stamp":
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        cx, cy = (164, 130) if recipe.mirror else (860, 130)
        d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=(*pal.accent, 255), width=4)
        font = load_font(22, "typewriter")
        draw_stroked_text_layer(
            canvas, (cx, cy - 8), compact_day(date), font, (*pal.accent, 255),
            stroke=(*pal.ink, 255), stroke_width=1, anchor="mm",
        )


def _apply_creative_layers(canvas: Image.Image, recipe: GraphicRecipe) -> None:
    """Stack 2–3 decorative layers on Option C (beyond the primary accent)."""
    pal = recipe.palette
    rng = random.Random(recipe.seed + 313)
    for layer in recipe.layers:
        if layer == "corner_strip":
            draw_corner_strip(
                canvas, corner="top_left", size=(140, 110),
                color=(*pal.accent, rng.randint(160, 220)),
            )
            draw_corner_strip(
                canvas, corner="bottom_right", size=(120, 100),
                color=(*pal.ink, rng.randint(140, 200)),
            )
        elif layer == "ticket_stub":
            side = "left" if recipe.mirror else "right"
            box = (24, 420, 130, 920) if side == "left" else (894, 420, CANVAS[0] - 24, 920)
            draw_ticket_stub(
                canvas, box=box, edge=side,
                perforations=rng.randint(12, 18),
                color=(*pal.ink, 170),
            )
        elif layer == "tape_corner":
            draw_tape_strip(
                canvas,
                (CANVAS[0] - 240, 48, CANVAS[0] - 60, 96) if not recipe.mirror else (60, 48, 240, 96),
                rotation=rng.uniform(-12, 8),
            )
        elif layer == "rings":
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            concentric_rings(
                ImageDraw.Draw(overlay),
                CANVAS[0] // 2,
                rng.randint(520, 640),
                [pal.accent, pal.paper, pal.ink],
                rng.randint(180, 280),
                rng.randint(24, 36),
            )
            overlay.putalpha(overlay.split()[3].point(lambda a: int(a * 0.22)))
            canvas.alpha_composite(overlay)
        elif layer == "double_rule":
            draw_double_rule(
                canvas,
                y=rng.randint(1180, 1240),
                color=(*pal.ink, 200),
            )


def _finish_creative(
    img: Image.Image,
    recipe: GraphicRecipe,
    *,
    date: str,
    time: str,
    band: str = "",
    grain_strength: float = 0.08,
    skip_logo: bool = False,
) -> Image.Image:
    if band.strip() and not skip_logo and recipe.archetype != "xerox_punk":
        from structured_layout.band_mark import draw_band_mark

        pal = recipe.palette
        draw_band_mark(
            img,
            band,
            style=recipe.archetype,
            ink=pal.ink,
            accent=pal.accent,
            paper=pal.paper,
            seed=recipe.seed,
        )
    _apply_primary_accent(img, recipe, date=date, time=time)
    _apply_creative_layers(img, recipe)
    return grain(img, grain_strength, seed=recipe.seed)


def _render_xerox_punk(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    if facts.get("band", "").strip():
        from structured_layout.band_mark import draw_band_mark

        draw_band_mark(
            img, facts["band"], style="xerox_punk",
            ink=pal.ink, accent=pal.accent, paper=pal.paper, seed=recipe.seed,
        )
    ht = halftone_dots(CANVAS, bg=pal.paper, dot=pal.ink, spacing=18, seed=recipe.seed)
    img = Image.alpha_composite(img, ht)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, CANVAS[0] - 20, CANVAS[1] - 20], outline=pal.ink, width=5)
    font_sm = load_font(24, "typewriter")
    draw_stroked_text_layer(img, (48, 40), "PRESENTS", font_sm, (*pal.ink, 255))

    photo_box = (72, 110, 952, 710)
    ph = threshold_photo(load_photo(photo, photo_box))
    img.paste(ph, (photo_box[0], photo_box[1]), ph)

    band_font = load_font(88, "display")
    draw_stroked_text_layer(
        img, (48, 740), facts["band"].upper(), band_font, (*pal.ink, 255),
        stroke=(255, 255, 255, 255), stroke_width=2,
    )
    draw.line([(48, 840), (976, 840)], fill=(*pal.ink, 255), width=4)
    draw_stroked_text_layer(img, (48, 860), facts["date"].upper(), load_font(36, "body"), (*pal.ink, 255))
    draw_stroked_text_layer(img, (48, 910), facts["time"].upper(), load_font(52, "display"), (*pal.accent, 255))

    draw.rectangle([0, 1270, CANVAS[0], CANVAS[1]], fill=(*pal.footer_bg, 255))
    draw_stroked_text_layer(
        img, (48, 1300), facts["venue"].upper(), load_font(44, "display"), (*pal.footer_fg, 255),
    )
    draw_stroked_text_layer(
        img, (48, 1360), facts["address"], load_font(24, "body"), (*pal.footer_fg, 200),
    )
    return _finish_creative(
        img, recipe, date=facts["date"], time=facts["time"], band=facts["band"],
        grain_strength=0.1, skip_logo=True,
    )


def _render_duotone(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    for i in range(0, CANVAS[0], 36):
        draw.rectangle([i, 0, i + 24, 16], fill=(*pal.ink, 255))

    venue_font = load_font(64, "display")
    draw_stroked_text_layer(
        img, (48, 44), facts["venue"].upper(), venue_font, (*pal.ink, 255),
        stroke=(*pal.accent, 255) if pal.paper != pal.ink else (255, 255, 255, 255), stroke_width=2,
    )

    panels = [(48, 190, 310, 670), (358, 190, 620, 670), (668, 190, 930, 670)]
    for box in panels:
        dt = duotone_photo(load_photo(photo, box), pal.ink, pal.paper)
        img.paste(dt, (box[0], box[1]), dt)

    draw_stroked_text_layer(
        img, (48, 700), facts["band"].upper(), load_font(92, "display"), (*pal.ink, 255),
        stroke=(*pal.paper, 255), stroke_width=3,
    )
    draw_stroked_text_layer(img, (48, 810), compact_day(facts["date"]), load_font(68, "display"), (*pal.ink, 255))
    draw_stroked_text_layer(img, (48, 890), facts["time"].upper(), load_font(56, "display"), (*pal.accent, 255))

    draw.rectangle([0, 1310, CANVAS[0], CANVAS[1]], fill=(*pal.footer_bg, 255))
    draw_stroked_text_layer(
        img, (48, 1350), facts["address"], load_font(30, "body"), (*pal.footer_fg, 255),
    )
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.06)


def _render_psychedelic(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([48, 70, CANVAS[0] - 48, CANVAS[1] - 100], fill=(*pal.accent, 255))
    draw.rectangle([68, 90, CANVAS[0] - 68, CANVAS[1] - 120], fill=(*pal.ink, 255))
    concentric_rings(draw, CANVAS[0] // 2, 610, [pal.accent, pal.ink, pal.paper], 360, 32)

    photo_box = (200, 460, 824, 870)
    ph = oval_mask_photo(load_photo(photo, photo_box))
    img.paste(ph, (photo_box[0], photo_box[1]), ph)

    band_font = load_font(72, "display")
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 150), facts["band"].upper(), band_font, (*pal.paper, 255),
        stroke=(*pal.ink, 255), stroke_width=4, anchor="mm",
    )
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 960), facts["venue"].upper(), load_font(48, "display"), (*pal.paper, 255),
        stroke=(*pal.ink, 255), stroke_width=2, anchor="mm",
    )
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 1040), facts["date"].upper()[:32], load_font(28, "body"), (*pal.paper, 255),
        anchor="mm",
    )
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 1090), facts["time"].upper(), load_font(40, "display"), (*pal.accent, 255),
        anchor="mm",
    )
    draw_stroked_text_layer(img, (80, CANVAS[1] - 88), facts["address"], load_font(22, "body"), (*pal.paper, 255))
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.07)


def _render_boutique(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    for x in range(36, CANVAS[0] - 36, 64):
        draw.line([(x, 28), (x + 30, 48)], fill=(180, 160, 120), width=2)
        draw.ellipse([x + 26, 44, x + 42, 60], fill=(255, 230, 180))

    band_font = load_font(56, "serif")
    bw, _ = text_size(facts["band"].upper(), band_font)
    draw_stroked_text_layer(
        img, ((CANVAS[0] - bw) // 2, 72), facts["band"].upper(), band_font, (*pal.ink, 255),
    )

    photo_box = (96, 190, 928, 710)
    ph = load_photo(photo, photo_box)
    img.paste(ph, (photo_box[0], photo_box[1]), ph)

    draw.rounded_rectangle((72, 750, 952, 1070), radius=16, fill=(210, 180, 140, 255), outline=(*pal.ink, 255), width=3)
    draw_stroked_text_layer(img, (112, 780), facts["venue"].upper(), load_font(34, "body"), (*pal.ink, 255))
    draw_stroked_text_layer(img, (112, 840), "LIVE MUSIC", load_font(80, "display"), (*pal.accent, 255))
    draw_stroked_text_layer(img, (112, 950), compact_day(facts["date"]), load_font(58, "display"), (*pal.ink, 255))
    draw_stroked_text_layer(img, (112, 1020), facts["time"].upper(), load_font(34, "body"), (*pal.ink, 255))

    draw.rectangle([0, 1410, CANVAS[0], CANVAS[1]], fill=(*pal.footer_bg, 255))
    draw_stroked_text_layer(img, (112, 1370), facts["address"], load_font(24, "body"), (*pal.ink, 255))
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 1455), "Live Music · Good Food · Great Community",
        load_font(24, "body"), (*pal.footer_fg, 255), anchor="mm",
    )
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.05)


def _render_neon_bar(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    draw_diagonal_band(img, color=(*pal.ink, 40), y_center=200, height=220, angle=-6)

    venue_font = load_font(78, "display")
    draw_stroked_text_layer(
        img, (48, 48), facts["venue"].upper(), venue_font, (*pal.accent, 255),
        stroke=(255, 255, 255, 80), stroke_width=3,
    )

    photo_box = (80, 280, 944, 820)
    ph = duotone_photo(load_photo(photo, photo_box), (20, 20, 30), pal.accent)
    img.paste(ph, (photo_box[0], photo_box[1]), ph)

    draw_stroked_text_layer(
        img, (48, 860), facts["band"].upper(), load_font(72, "display"), (*pal.accent, 255),
        stroke=(0, 0, 0, 255), stroke_width=3,
    )
    draw_stroked_text_layer(img, (48, 950), facts["date"].upper(), load_font(32, "body"), (255, 255, 255, 255))
    draw_stroked_text_layer(img, (48, 1000), facts["time"].upper(), load_font(48, "display"), (*pal.accent, 255))

    draw.rectangle([0, 1280, CANVAS[0], CANVAS[1]], fill=(*pal.footer_bg, 255))
    draw_stroked_text_layer(img, (48, 1320), facts["address"], load_font(28, "body"), (*pal.footer_fg, 255))
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.08)


def _render_pasteup_zine(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    draw_diagonal_band(img, color=(*pal.accent, 200), y_center=120, height=140, angle=-10)

    venue_font = load_font(64, "display")
    draw_stroked_text_layer(
        img, (56, 56), facts["venue"].upper(), venue_font, (255, 255, 255, 255),
        stroke=(*pal.ink, 255), stroke_width=3,
    )

    photo_box = (100, 260, 924, 780)
    ph = load_photo(photo, photo_box)
    torn_paste(img, halftone_photo(ph, 4), (photo_box[0], photo_box[1]), seed=recipe.seed)

    draw_tape_strip(img, (60, 240, 220, 290), rotation=-8)
    draw_stroked_text_layer(
        img, (72, 820), facts["band"].upper(), load_font(76, "display"), (*pal.ink, 255),
    )
    draw_stroked_text_layer(img, (72, 910), facts["date"].upper(), load_font(34, "typewriter"), (*pal.ink, 255))
    draw_stroked_text_layer(img, (72, 960), facts["time"].upper(), load_font(44, "display"), (*pal.accent, 255))

    draw.rectangle([0, 1290, CANVAS[0], CANVAS[1]], fill=(*pal.footer_bg, 255))
    draw_stroked_text_layer(
        img, (72, 1330), f"{facts['venue'].upper()}  ·  {facts['address']}",
        load_font(26, "typewriter"), (*pal.footer_fg, 255),
    )
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.12)


def _render_broadside(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    venue_font = load_font(110, "display")
    draw_stroked_text_layer(
        img, (48, 40), facts["venue"].upper(), venue_font, (*pal.ink, 255),
        stroke=(*pal.accent, 255), stroke_width=4,
    )
    draw_stroked_text_layer(
        img, (48, 200), compact_day(facts["date"]), load_font(96, "display"), (*pal.accent, 255),
        stroke=(*pal.ink, 255), stroke_width=3,
    )
    draw_stroked_text_layer(img, (48, 320), facts["time"].upper(), load_font(64, "display"), (*pal.ink, 255))

    photo_box = (580, 400, 960, 720)
    img.paste(load_photo(photo, photo_box), (photo_box[0], photo_box[1]), load_photo(photo, photo_box))

    draw_stroked_text_layer(
        img, (48, 780), facts["band"].upper(), load_font(68, "display"), (*pal.ink, 255),
    )
    draw.line([(48, 870), (976, 870)], fill=(*pal.ink, 255), width=3)
    draw_stroked_text_layer(img, (48, 890), facts["address"], load_font(28, "body"), (*pal.ink, 255))
    draw_stroked_text_layer(
        img, (48, 980), "FEATURING", load_font(24, "typewriter"), (*pal.accent, 255),
    )
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.05)


def _render_country_fair(facts: dict, photo: Path, recipe: GraphicRecipe) -> Image.Image:
    pal = recipe.palette
    img = Image.new("RGBA", CANVAS, (*pal.paper, 255))
    draw = ImageDraw.Draw(img)
    stripe_h = 28
    for i, y in enumerate(range(0, 180, stripe_h)):
        c = pal.accent if i % 2 == 0 else pal.paper
        draw.rectangle([0, y, CANVAS[0], y + stripe_h], fill=(*c, 255))

    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 90), facts["venue"].upper(), load_font(52, "display"),
        (255, 255, 255, 255), stroke=(*pal.ink, 255), stroke_width=2, anchor="mm",
    )

    photo_box = (112, 220, 912, 700)
    img.paste(load_photo(photo, photo_box), (photo_box[0], photo_box[1]), load_photo(photo, photo_box))

    draw.rounded_rectangle((80, 740, 944, 1040), radius=8, outline=(*pal.ink, 255), width=4)
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 790), facts["band"].upper(), load_font(64, "serif"), (*pal.ink, 255), anchor="mm",
    )
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 880), f"{compact_day(facts['date'])}  ·  {facts['time'].upper()}",
        load_font(40, "display"), (*pal.accent, 255), anchor="mm",
    )
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 960), facts["date"].upper(), load_font(24, "body"), (*pal.ink, 255), anchor="mm",
    )

    draw.rectangle([0, 1380, CANVAS[0], CANVAS[1]], fill=(*pal.footer_bg, 255))
    draw_stroked_text_layer(
        img, (CANVAS[0] // 2, 1420), facts["address"], load_font(26, "body"), (*pal.footer_fg, 255), anchor="mm",
    )
    return _finish_creative(img, recipe, date=facts["date"], time=facts["time"], band=facts["band"], grain_strength=0.06)


_RENDERERS: dict[str, Callable[..., Image.Image]] = {
    "xerox_punk": _render_xerox_punk,
    "duotone_modern": _render_duotone,
    "psychedelic": _render_psychedelic,
    "boutique": _render_boutique,
    "neon_bar": _render_neon_bar,
    "pasteup_zine": _render_pasteup_zine,
    "broadside": _render_broadside,
    "country_fair": _render_country_fair,
}


def compose_graphic_flyer(
    recipe: GraphicRecipe,
    facts: dict[str, str],
    photo_path: Path,
    out_path: Path,
) -> None:
    fn = _RENDERERS.get(recipe.archetype)
    if fn is None:
        raise ValueError(f"Unknown archetype: {recipe.archetype}")
    img = fn(facts, photo_path, recipe)
    save_rgb(img, out_path)


def compose_from_layout(layout: LayoutSpec, photo_path: Path, output_path: Path) -> None:
    facts = _facts_from_layout(layout)
    arch = parse_archetype_from_layout(layout) or "xerox_punk"
    seed = _seed_from_layout(layout)
    rng = random.Random(seed)
    recipe = build_recipe(rng, archetype=arch)
    # Preserve seed from layout stub for reproducibility
    recipe = GraphicRecipe(
        archetype=recipe.archetype,
        palette_id=recipe.palette_id,
        palette=recipe.palette,
        accent=recipe.accent,
        layers=recipe.layers,
        mirror=recipe.mirror,
        seed=seed,
    )
    compose_graphic_flyer(recipe, facts, photo_path, output_path)


def premium_hybrid_enabled() -> bool:
    raw = os.getenv("OPTION_C_PREMIUM_HYBRID", "0").strip().lower()
    return raw in {"1", "true", "yes"} and bool(os.getenv("OPENAI_API_KEY", "").strip())


def render_option_c_best(
    layout: LayoutSpec,
    photo_path: Path,
    output_path: Path,
) -> None:
    """Graphic composer first; optional OpenAI premium enhancement."""
    from structured_layout.option_c_premium import enhance_with_hybrid_if_enabled

    work = output_path.parent / ".option_c_work"
    work.mkdir(parents=True, exist_ok=True)
    base = work / f"{output_path.stem}_graphic.png"
    compose_from_layout(layout, photo_path, base)
    if premium_hybrid_enabled():
        enhance_with_hybrid_if_enabled(
            layout, photo_path, base, output_path,
        )
    else:
        output_path.write_bytes(base.read_bytes())
