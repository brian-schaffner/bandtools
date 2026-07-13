"""Prompt builder for wild full-canvas flyer generation."""

from __future__ import annotations

from typing import Any, Optional

from gig_calendar import GigEvent

_INTENSITY_BLOCKS: dict[str, dict[str, str]] = {
    "wild": {
        "label": "BOLD",
        "energy": (
            "Maximum outlaw-country bar energy — gritty textures, torn paper, barbed wire, "
            "asymmetry, mixed media, boots-and-beer authenticity."
        ),
        "rules": (
            "Full creative freedom — asymmetry, layered textures, bold color, mixed media. "
            "Face distortion and artistic reinterpretation of musicians are ALLOWED."
        ),
        "avoid_extra": "Plain white/cream photo mats, PowerPoint-style blocks, uniform yellow/gold AI wash.",
    },
    "wild_medium": {
        "label": "BALANCED",
        "energy": (
            "Same full-canvas outlaw-country bar flyer technique, but with clearer hierarchy "
            "and slightly restrained chaos — still hand-made promoter energy, not corporate."
        ),
        "rules": (
            "Keep creative integration of typography and band depiction, but favor readability "
            "over extreme distortion. One strong focal composition; limit competing textures."
        ),
        "avoid_extra": "Over-cluttered collage, illegible type, extreme face warping, mustard/gold monochrome.",
    },
    "wild_subtle": {
        "label": "REFINED",
        "energy": (
            "Toned-down full-canvas bar poster — still one unified designed image with integrated "
            "type and art, but closer to a polished regional promoter flyer."
        ),
        "rules": (
            "Prioritize legibility and clean hierarchy. Subtle textures OK; avoid heavy grunge "
            "or chaotic layering. Musicians can be stylized but should feel intentional, not distorted."
        ),
        "avoid_extra": "Heavy distortion, neon chaos, illegible text, stock festival symmetry, sepia AI filter.",
    },
}


def _resolve_intensity(variation: dict[str, Any]) -> str:
    tier = str(variation.get("tier") or variation.get("wild_intensity") or "wild").strip()
    if tier in _INTENSITY_BLOCKS:
        return tier
    mode = str(variation.get("generation_mode") or "").strip()
    if "subtle" in mode or "refined" in mode:
        return "wild_subtle"
    if "medium" in mode or "balanced" in mode:
        return "wild_medium"
    return "wild"


def build_wild_design_prompt(
    style: dict[str, Any],
    event: GigEvent,
    variation: dict[str, Any],
    round_num: int,
    *,
    feedback: Optional[str] = None,
    research: Optional[dict[str, Any]] = None,
    selected_photo: Optional[dict[str, Any]] = None,
) -> str:
    """Build a full-canvas poster prompt — no photo-fidelity or template constraints."""
    intensity = _resolve_intensity(variation)
    intensity_cfg = _INTENSITY_BLOCKS[intensity]
    generation_mode = str(variation.get("generation_mode") or "full_canvas_wild")
    principles = style.get("core_principles") or []
    anti_visual = (
        (style.get("anti_slop") or {}).get("visual_tropes")
        or (style.get("anti_ai_rules") or {}).get("visual_tropes", {}).get("reject_if_present")
        or []
    )
    anti_texture = (style.get("anti_ai_rules") or {}).get("texture_tropes", {}).get("reject_if_present") or []
    venue = event.venue or "Venue TBA"
    band = event.title or "Live music"
    date = event.to_dict().get("short_date") or event.event_date.strftime("%b %d, %Y")
    time_label = event.time_label or "TBA"

    research_bits: list[str] = []
    design_language = ""
    if research:
        design_language = str(research.get("design_language") or "").strip()
        if design_language:
            research_bits.append(f"Venue design language: {design_language}")
        notes = research.get("design_notes") or []
        research_bits.extend(str(n).strip() for n in notes[:2] if str(n).strip())

    photo_hint = ""
    if selected_photo and selected_photo.get("description"):
        photo_hint = (
            f"Band lineup inspiration (stylize freely): {selected_photo['description']}. "
            "Paint, collage, halftone, or reimagine the musicians inside the poster — "
            "face distortion is acceptable."
        )

    # Default aesthetic when venue research is thin: outlaw-country bar flyer.
    venue_lower = f"{venue} {design_language}".lower()
    western_cues = any(
        k in venue_lower
        for k in ("tavern", "bar", "saloon", "honky", "country", "western", "roadhouse", "lane")
    )
    style_anchor = (
        "Outlaw-country / roadhouse bar flyer: dark wood or weathered plank background, "
        "torn-paper labels, ink-black and off-white typography with rust-red or denim-blue "
        "accents — NOT a uniform golden-yellow wash. Band integrated INTO the art — not a "
        "stock photo pasted on plain rectangles."
        if western_cues or not design_language
        else f"Match venue energy ({design_language}) with bold promoter/zine collage — "
        "varied ink colors on paper/wood, still one unified designed poster, not a template "
        "with pasted photo blocks."
    )

    color_rules = [
        "Use a believable printed-flyer palette: dark wood brown, ink black, off-white/cream "
        "paper, beer-label red, denim blue, faded green — mix 2–4 colors with real contrast.",
        "NEVER drench the whole poster in AI yellow, mustard gold, amber sepia, or vintage "
        "Instagram filter — that screams AI-generated.",
        "Warm tones are OK as accents (rust, brick, tungsten highlights) but the dominant mood "
        "should be bar-window night: wood, ink, and paper — not a yellow fog.",
        "Avoid golden-hour color grading, uniform sepia cast, and yellow-tinted skin on musicians.",
    ]

    lines = [
        "PRIMARY DIRECTIVE: Design a complete concert flyer poster as ONE unified designed image.",
        "Typography, textures, graphics, and band depiction must feel like a single "
        "hand-made outlaw-country or dive-bar poster — NOT a clean Canva layout.",
        "",
        "EVENT FACTS (must be correct and readable):",
        f"- Band: {band}",
        f"- Venue: {venue}",
        f"- Date: {date}",
        f"- Time: {time_label}",
        "",
        f"VISUAL DNA ({intensity_cfg['label']} wild — prioritize design over photo accuracy):",
        f"- {style_anchor}",
        f"- Creative intensity: {intensity_cfg['energy']}",
        "- Integrate event text into the design (torn labels, wood type, stamp lettering, "
        "ticket stubs) — never floating captions on blank cream boxes.",
        "- Band/musicians are part of the composition — painted, halftoned, collage-cut, "
        "or stylized; they live inside the poster world.",
        "- Leave the top-right corner relatively clear — a band logo badge will be added after render.",
        "- Memorable, authentic promoter energy — like a flyer taped in a bar window.",
        "",
        "COLOR (critical — avoid the AI-yellow look):",
    ]
    lines.extend([f"- {rule}" for rule in color_rules])
    lines.extend(
        [
        "",
        "WILD DESIGN RULES:",
        f"- {intensity_cfg['rules']}",
        "- No fixed template grid, no three stacked rectangles with a photo in the middle.",
        "",
        "AVOID:",
        "- Generic festival symmetry, stock marketing polish, sci-fi fantasy unless venue fits.",
        "- Uniform yellow/gold/mustard color cast, sepia AI filter, golden-hour wash, or "
        "'vintage photo' yellow tint over the entire image.",
        "- Over-saturated amber parchment, Canva 'aged paper' yellow, or monotone gold typography.",
        f"- {intensity_cfg['avoid_extra']}",
        "- Missing or wrong venue/date/band text.",
        ]
    )
    if principles:
        lines.extend(["", "CORE PRINCIPLES:"] + [f"- {p}" for p in principles[:4]])
    if anti_visual:
        lines.extend(["", "ANTI-SLOP:"] + [f"- No {t}" for t in anti_visual[:5]])
    if anti_texture:
        lines.extend(["", "TEXTURE AVOID:"] + [f"- No {t}" for t in anti_texture[:4]])
    if research_bits:
        lines.extend(["", "VENUE CONTEXT:"] + [f"- {b}" for b in research_bits])
    if photo_hint:
        lines.extend(["", photo_hint])
    if feedback:
        lines.extend(
            [
                "",
                "REVISION NOTES (apply to this new wild variant):",
                feedback,
            ]
        )
    lines.append(
        f"\nCreative round: {round_num}. Generation mode: {generation_mode} ({intensity_cfg['label']})."
    )
    return "\n".join(lines)
