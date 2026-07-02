"""Option C premium path — OpenAI hybrid when API key available, graphic composer fallback."""

from __future__ import annotations

from pathlib import Path

from structured_layout.graphic_composer import parse_archetype_from_layout, _facts_from_layout
from structured_layout.layout_spec import LayoutSpec

_HYBRID_STYLE_BLOCKS: dict[str, str] = {
    "xerox_punk": "STYLE: Xerox punk club flyer — high-contrast black ink on cream, utilitarian type, black footer bar.",
    "duotone_modern": "STYLE: Modern duotone poster — bold two-color panels, Swiss grid energy, photo strip.",
    "psychedelic": "STYLE: Fillmore psychedelic poster — concentric rings, oval photo, 1960s rock poster borders.",
    "boutique": "STYLE: Boutique community event — string lights, warm serif headline, rounded info card.",
    "neon_bar": "STYLE: Dark blues bar handbill — neon accent type on dark field, moody duotone photo.",
    "pasteup_zine": "STYLE: Cut-and-paste zine — torn edges, tape strips, halftone photo, typewriter dates.",
    "broadside": "STYLE: Broadside poster — giant venue/date type, small inset photo, minimal footer.",
    "country_fair": "STYLE: Country fair banner — red/green stripes, serif band name, festive footer.",
}


def _hybrid_prompt(layout: LayoutSpec) -> str:
    from flyer_generator import build_prompt, load_style, select_variations

    style = load_style()
    variations = select_variations(style, 3, [])
    variation = next((v for v in variations if v.get("tier") == "creative"), variations[-1])
    arch = parse_archetype_from_layout(layout) or "xerox_punk"
    style_block = _HYBRID_STYLE_BLOCKS.get(arch, _HYBRID_STYLE_BLOCKS["xerox_punk"])
    photo_meta = {"path": "", "filename": "band.jpg"}
    from gig_calendar import GigEvent
    from datetime import date

    facts = _facts_from_layout(layout)
    # Reconstruct minimal event for build_prompt from layout facts
    event = GigEvent(
        event_date=date(2026, 6, 28),
        time_label=facts.get("time") or "TBA",
        title=f"{facts.get('band')} at {facts.get('venue')}",
        venue=facts.get("venue") or "Venue",
        suggested_name="option-c-premium",
    )
    base = build_prompt(
        style, event, variation, round_num=1,
        selected_photo=photo_meta, option_letter="C",
    )
    return f"{style_block}\n\n{base}"


def enhance_with_hybrid_if_enabled(
    layout: LayoutSpec,
    photo_path: Path,
    graphic_base_path: Path,
    output_path: Path,
) -> None:
    """Try OpenAI hybrid; on failure keep deterministic graphic composer output."""
    from image_providers.openai import OpenAIImageProvider

    prompt = _hybrid_prompt(layout)
    provider = OpenAIImageProvider()
    try:
        provider.generate(
            prompt,
            output_path,
            reference_photo_path=photo_path,
            option="C",
            tier="creative",
            quality="high",
        )
    except RuntimeError as exc:
        if graphic_base_path.is_file() and "Band photo validation failed" in str(exc):
            output_path.write_bytes(graphic_base_path.read_bytes())
            return
        raise
    except Exception:
        if graphic_base_path.is_file():
            output_path.write_bytes(graphic_base_path.read_bytes())
            return
        raise
