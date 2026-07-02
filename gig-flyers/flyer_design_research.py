"""Public research corpus: what makes effective gig flyers + reference samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from gig_calendar import GigEvent

# ---------------------------------------------------------------------------
# Design principles (synthesized from industry guides + poster archive patterns)
# Sources cited in docstrings on each principle.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DesignPrinciple:
    id: str
    title: str
    summary: str
    source_url: str


DESIGN_PRINCIPLES: tuple[DesignPrinciple, ...] = (
    DesignPrinciple(
        "hierarchy_headliner_first",
        "Headliner first, logistics second",
        "Readers should absorb band name → hook/visual → date & venue → fine print in under three seconds.",
        "https://madegooddesigns.com/concert-poster-design/",
    ),
    DesignPrinciple(
        "legibility_at_distance",
        "Legible from six feet",
        "Band, date, and venue must read from across a dim bar or coffee-shop window; test at arm's length.",
        "https://blog.sonicbids.com/a-graphic-designers-top-tips-for-creating-an-eye-catching-gig-poster",
    ),
    DesignPrinciple(
        "high_contrast",
        "High contrast type",
        "Light-on-dark or dark-on-light; avoid low-contrast colored type on busy backgrounds.",
        "https://blog.sonicbids.com/a-graphic-designers-top-tips-for-creating-an-eye-catching-gig-poster",
    ),
    DesignPrinciple(
        "two_fonts_max",
        "Two typefaces, many weights",
        "One display face for the hook, one neutral face for logistics; use weight—not font count—for tiers.",
        "https://tickts.co.uk/blog/poster-flyer-design-events-guide",
    ),
    DesignPrinciple(
        "negative_space",
        "Protect negative space",
        "Three clear facts beat fifteen cramped ones; whitespace signals professionalism.",
        "https://creativesidekickstudios.com/get-people-to-the-concert-design-101/",
    ),
    DesignPrinciple(
        "essential_info_only",
        "Only essential copy",
        "Skip hype lines like 'best show ever'; include ticket price, age, free entry, or genre tags when they help.",
        "https://blog.sonicbids.com/a-graphic-designers-top-tips-for-creating-an-eye-catching-gig-poster",
    ),
    DesignPrinciple(
        "accuracy",
        "Spell-check and date-check",
        "Wrong weekday or misspelled opener names erode trust before anyone hears a note.",
        "https://blog.sonicbids.com/a-graphic-designers-top-pips-for-creating-an-eye-catching-gig-poster",
    ),
    DesignPrinciple(
        "bottom_info_block",
        "Anchor logistics at the bottom",
        "Strong visual or oversized headliner in the top two-thirds; tidy date/venue block along a shared baseline.",
        "https://madegooddesigns.com/concert-poster-design/",
    ),
    DesignPrinciple(
        "genre_cue_for_unknowns",
        "Genre cue for unfamiliar bills",
        "A short 'rock / blues / soul' tag helps new-market gigs when the headliner isn't widely known.",
        "https://blog.sonicbids.com/a-graphic-designers-top-tips-for-creating-an-eye-catching-gig-poster",
    ),
    DesignPrinciple(
        "venue_appropriate_tone",
        "Match venue energy",
        "Legion halls and county fairs want readable community energy; club bills can carry more art risk.",
        "https://creativesidekickstudios.com/get-people-to-the-concert-design-101/",
    ),
    DesignPrinciple(
        "one_strong_hook",
        "One strong hook",
        "Lead with either a striking photo/illustration OR oversized type—not competing focal points.",
        "https://medium.muz.li/three-rules-of-visual-hierarchy-in-poster-art-a-guide-for-new-and-non-designers-65e79bf4389c",
    ),
    DesignPrinciple(
        "limited_palette_screenprint",
        "Limited palette reads as 'poster'",
        "2–4 ink colors and visible texture echo collectible screen-print gig posters.",
        "https://madegooddesigns.com/concert-poster-design/",
    ),
    DesignPrinciple(
        "screenshot_friendly_date",
        "Date/venue must survive a screenshot",
        "Many fans save the poster image—keep date, city, and venue unmissable and not buried in ornament.",
        "https://madegooddesigns.com/concert-poster-design/",
    ),
    DesignPrinciple(
        "cta_when_relevant",
        "Clear next step",
        "Ticket URL, QR, or 'FREE' should be visible without hunting; don't hide the call to action.",
        "https://tickts.co.uk/blog/poster-flyer-design-events-guide",
    ),
)

# Fix typo in accuracy principle URL
DESIGN_PRINCIPLES = tuple(
    DesignPrinciple(
        p.id,
        p.title,
        p.summary,
        p.source_url.replace("top-pips", "top-tips") if "top-pips" in p.source_url else p.source_url,
    )
    for p in DESIGN_PRINCIPLES
)


@dataclass(frozen=True)
class ReferenceSample:
    """Public reference for learning—not scraped artwork."""

    id: str
    title: str
    url: str
    style: str
    era: str
    venue_context: str
    lessons: tuple[str, ...]
    image_url: str = ""  # optional direct asset when publicly hosted


# 35 public samples (articles, archives, galleries, PD posters)
REFERENCE_SAMPLES: tuple[ReferenceSample, ...] = (
    ReferenceSample(
        "woodstock_1969",
        "Woodstock Festival poster (1969)",
        "https://commons.wikimedia.org/wiki/File:Woodstock_poster.jpg",
        "psychedelic_illustrative",
        "1960s",
        "festival",
        ("Dove-and-guitar icon becomes the hook", "Festival name + dates dominate", "Lineup as tertiary text"),
        "https://upload.wikimedia.org/wikipedia/commons/5/5a/Woodstock_poster.jpg",
    ),
    ReferenceSample(
        "altamont_1969",
        "Altamont Free Concert poster (1969)",
        "https://commons.wikimedia.org/wiki/File:Altamont_free_concert_poster.jpg",
        "type_only",
        "1960s",
        "festival",
        ("Type-only bill with stark contrast", "Venue + date in bold block", "Minimal ornament, maximum clarity"),
    ),
    ReferenceSample(
        "behance_gig_collection_iii",
        "Gig Posters Collection III (Behance)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "mixed_indie",
        "2020s",
        "club_and_theater",
        ("Modern indie posters mix illustration + tight type", "Tour titles as secondary tier", "Venue-specific variants"),
    ),
    ReferenceSample(
        "khruangbin_space_walk",
        "Khruangbin Space Walk Tour (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "psychedelic_illustrative",
        "2020s",
        "theater",
        ("Cosmic illustration matches band aesthetic", "Tour name as secondary headline"),
    ),
    ReferenceSample(
        "goose_stubbs_austin",
        "Goose at Stubb's Austin (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "photographic",
        "2020s",
        "bbq_venue",
        ("Venue-local identity in artwork", "Band name remains largest type element"),
    ),
    ReferenceSample(
        "nude_party_ride_on",
        "The Nude Party Ride On Tour (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "folk_illustrative",
        "2020s",
        "club",
        ("Americana illustration + serif display", "Tour branding repeated across dates"),
    ),
    ReferenceSample(
        "chicano_batman_divino",
        "Chicano Batman & Divino Niño (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "duotone_bold",
        "2020s",
        "club",
        ("Two-color palette feels screen-printed", "Dual headliners balanced in hierarchy"),
    ),
    ReferenceSample(
        "monophonics_sage_motel",
        "Monophonics Sage Motel Tour (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "neon_nightlife",
        "2020s",
        "club",
        ("Retro motel motif as visual hook", "Soul/funk palette: warm paper + neon accent"),
    ),
    ReferenceSample(
        "crumb_boulder",
        "Crumb at Boulder Theater (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "collage_zine",
        "2020s",
        "theater",
        ("Hand-drawn collage energy", "Indie art-school poster tradition"),
    ),
    ReferenceSample(
        "mic_indie_fine_art",
        "15 indie posters as fine art (Mic roundup)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "mixed_indie",
        "2010s",
        "mixed",
        ("Posters mirror band narrative", "Illustration can carry mood when type is restrained"),
    ),
    ReferenceSample(
        "avett_brothers_slater",
        "Avett Brothers — Todd Slater (Mic)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "folk_illustrative",
        "2010s",
        "arena",
        ("Gothic folk illustration at arena scale", "Album-era visual storytelling"),
    ),
    ReferenceSample(
        "the_faint_blake_jones",
        "The Faint — Blake Jones (Mic)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "duotone_bold",
        "2010s",
        "club",
        ("Geometric shapes + bold primaries", "Anti-establishment energy via color"),
    ),
    ReferenceSample(
        "band_of_horses_santora",
        "Band of Horses — Justin Santora (Mic)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "folk_illustrative",
        "2010s",
        "theater",
        ("Sepia narrative scene", "Lyric-driven illustration"),
    ),
    ReferenceSample(
        "war_on_drugs_macadam",
        "The War on Drugs — Daniel MacAdam (Mic)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "photographic",
        "2010s",
        "club",
        ("Atmospheric photo + minimal type", "Moody palette matches dream-pop"),
    ),
    ReferenceSample(
        "washed_out_mcdevitt",
        "Washed Out — Mark McDevitt (Mic)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "collage_zine",
        "2010s",
        "club",
        ("Vintage ad collage tessellation", "Muted hypnotic palette"),
    ),
    ReferenceSample(
        "kraftwerk_hamou",
        "Kraftwerk — Pat Hamou (Mic)",
        "https://www.mic.com/articles/86951/15-beautiful-indie-concert-posters-that-could-pass-as-fine-art",
        "minimalist_swiss",
        "2010s",
        "theater",
        ("Metropolis-inspired grid", "Electronic act → architectural type"),
    ),
    ReferenceSample(
        "gigposters_mudhoney",
        "Mudhoney / Girltrouble — Jim Nadorozny",
        "https://gigposters.com/featured/mudhoney-girltrouble-superbeast.html",
        "screen_print",
        "2020s",
        "club",
        ("Punk club bill with hand-drawn energy", "Local venue name prominent"),
    ),
    ReferenceSample(
        "gigposters_man_or_astroman",
        "Man or Astro-Man? — Superbeast",
        "https://gigposters.com/featured/gig-poster-superbeast.html",
        "screen_print",
        "2020s",
        "club",
        ("Sci-fi surf-punk illustration", "Stacked band names with clear headliner"),
    ),
    ReferenceSample(
        "hatch_digital_archive",
        "Hatch Show Print digital archive",
        "https://digi.countrymusichalloffame.org/digital/collection/hatch3",
        "letterpress_handbill",
        "1920s-2020s",
        "country_venue",
        ("Letterpress wood type hierarchy", "Country/Ryman tradition: name + date + venue"),
    ),
    ReferenceSample(
        "hatch_ryman_gallery",
        "Hatch Show Print × Ryman gallery",
        "https://www.ryman.com/story/hatch-the-ryman-a-historic-partnership-on-display",
        "letterpress_handbill",
        "1940s-2020s",
        "theater",
        ("One poster per show tradition", "Signed prints as collectible merch"),
    ),
    ReferenceSample(
        "gigposters_archive_book",
        "Gig Posters Volume I archive (GigPosters.com)",
        "https://books.google.com/books/about/Gig_Posters_Volume_I.html?id=TbNvDwAAQBAJ",
        "mixed_indie",
        "2000s",
        "mixed",
        ("100k+ poster community archive", "Screen-print limited runs as art objects"),
    ),
    ReferenceSample(
        "sonicbids_tom_shaw",
        "Tom Shaw gig poster tips (Sonicbids)",
        "https://blog.sonicbids.com/a-graphic-designers-top-tips-for-creating-an-eye-catching-gig-poster",
        "minimalist_swiss",
        "2010s",
        "bar",
        ("Professional bar-window legibility", "Myriad Pro weight variation example"),
    ),
    ReferenceSample(
        "creative_sidekick_101",
        "Poster Design 101 (Creative Sidekick)",
        "https://creativesidekickstudios.com/get-people-to-the-concert-design-101/",
        "minimalist_swiss",
        "2020s",
        "mixed",
        ("Hierarchy beats decoration", "Clarity drives attendance decisions"),
    ),
    ReferenceSample(
        "tickts_event_guide",
        "Event poster guide (Tickts)",
        "https://tickts.co.uk/blog/poster-flyer-design-events-guide",
        "minimalist_swiss",
        "2020s",
        "mixed",
        ("A5 flyer front/back split", "Headline act largest, ticket info visible"),
    ),
    ReferenceSample(
        "made_good_concert_tips",
        "Concert poster ideas (Made Good Designs)",
        "https://madegooddesigns.com/concert-poster-design/",
        "mixed_indie",
        "2020s",
        "mixed",
        ("18×24 as workhorse size", "Style families: psychedelic, Swiss, photo, type-only"),
    ),
    ReferenceSample(
        "muzli_hierarchy",
        "Visual hierarchy in poster art (Muzli)",
        "https://medium.muz.li/three-rules-of-visual-hierarchy-in-poster-art-a-guide-for-new-and-non-designers-65e79bf4389c",
        "type_only",
        "2020s",
        "mixed",
        ("Primary / secondary / tertiary type tiers", "Darlingside example: band name spans width"),
    ),
    ReferenceSample(
        "pixies_behance",
        "Pixies gig poster (Behance search)",
        "https://www.behance.net/search/projects/pixies%20gig%20poster",
        "screen_print",
        "2010s",
        "club",
        ("Iconic band → bold simplified portrait", "High contrast single focal image"),
    ),
    ReferenceSample(
        "the_national_gigposter",
        "The National gigposter (Behance)",
        "https://www.behance.net/search/projects/gigposters%20indie",
        "photographic",
        "2010s",
        "theater",
        ("Moody photography + restrained type", "Indie rock prefers muted palettes"),
    ),
    ReferenceSample(
        "beach_fossils_poster",
        "Beach Fossils poster (Behance)",
        "https://www.behance.net/search/projects/beach%20fossils%20poster",
        "collage_zine",
        "2010s",
        "club",
        ("DIY zine collage aesthetic", "Pastel + photocopy texture"),
    ),
    ReferenceSample(
        "screen_print_concert_posters",
        "Screen printed concert posters (Behance)",
        "https://www.behance.net/search/projects/screen%20printed%20concert%20posters",
        "screen_print",
        "2010s",
        "club",
        ("Visible ink layers", "Collectible limited-run mindset"),
    ),
    ReferenceSample(
        "indie_festival_flyer",
        "Indie festival flyer template study (Behance)",
        "https://www.behance.net/search/projects/indie%20gig",
        "festival_poster",
        "2020s",
        "festival",
        ("Multi-act hierarchy", "Date block + lineup grid"),
    ),
    ReferenceSample(
        "disco_tehran_brooklyn",
        "Disco Tehran Brooklyn (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "neon_nightlife",
        "2020s",
        "warehouse",
        ("Global dance party visual language", "Bold color blocks for night events"),
    ),
    ReferenceSample(
        "max_richter_barbican",
        "Max Richter Ambient Orchestra Barbican (Behance collection)",
        "https://www.behance.net/gallery/190327159/Gig-Posters-Collection-III",
        "minimalist_swiss",
        "2020s",
        "classical_hall",
        ("Classical/modern: generous whitespace", "Composer name as sole hook"),
    ),
    ReferenceSample(
        "community_legion_poster",
        "American Legion / VFW community dance poster pattern",
        "https://creativesidekickstudios.com/get-people-to-the-concert-design-101/",
        "letterpress_handbill",
        "2020s",
        "member_club",
        ("Venue-first readable stack", "Patriotic/community cues without clutter"),
    ),
    ReferenceSample(
        "fillmore_tradition",
        "Fillmore / Family Dog poster tradition (Art of Rock)",
        "https://www.jagmo.com/articles/_____Art%20of%20RockELI.pdf",
        "psychedelic_illustrative",
        "1960s",
        "ballroom",
        ("Psychedelic lettering + dense ornament", "Collectible series numbering"),
    ),
)


STYLE_TO_VENUE: dict[str, tuple[str, ...]] = {
    "letterpress_handbill": ("member_club", "community_event", "country_bar", "regional_bar", "regional_club"),
    "minimalist_swiss": ("winery", "regional_club", "community_event"),
    "photographic": ("regional_bar", "regional_club", "blues_bar"),
    "duotone_bold": ("regional_bar", "regional_club", "casino_venue"),
    "screen_print": ("regional_bar", "blues_bar", "regional_club"),
    "psychedelic_illustrative": ("festival", "regional_club"),
    "neon_nightlife": ("casino_venue", "regional_bar"),
    "folk_illustrative": ("winery", "country_bar", "regional_club"),
    "collage_zine": ("regional_bar", "regional_club"),
    "type_only": ("member_club", "community_event", "festival"),
    "festival_poster": ("festival",),
    "mixed_indie": ("regional_club", "regional_bar"),
}


@dataclass
class FlyerDesignBrief:
    """Research output consumed by the guided generator."""

    gig_id: str
    venue: str
    venue_type: str
    recommended_style: str
    option_letter: str
    graphic_archetype: str | None
    medium_variant: str | None
    principles: list[str]
    reference_ids: list[str]
    hierarchy_notes: list[str]
    prompt_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_design_principles() -> list[DesignPrinciple]:
    return list(DESIGN_PRINCIPLES)


def get_reference_samples() -> list[ReferenceSample]:
    return list(REFERENCE_SAMPLES)


def sample_count() -> int:
    return len(REFERENCE_SAMPLES)


def samples_by_style(style: str) -> list[ReferenceSample]:
    return [s for s in REFERENCE_SAMPLES if s.style == style]


def _venue_type(research: dict[str, Any] | None) -> str:
    if not research:
        return "regional_club"
    return str(research.get("venue_type") or "regional_club")


def _score_style(style: str, venue_type: str, design_language: str) -> float:
    score = 0.0
    fits = STYLE_TO_VENUE.get(style, ())
    if venue_type in fits:
        score += 4.0
    if design_language and design_language.replace("_", " ") in style.replace("_", " "):
        score += 2.0
    if style in {"letterpress_handbill", "minimalist_swiss", "type_only"} and venue_type in {
        "member_club",
        "community_event",
    }:
        score += 3.0
    if style in {"neon_nightlife", "duotone_bold"} and venue_type in {"casino_venue", "regional_bar"}:
        score += 2.0
    if style == "festival_poster" and venue_type == "festival":
        score += 5.0
    return score


def recommend_styles(research: dict[str, Any] | None, *, limit: int = 5) -> list[str]:
    venue_type = _venue_type(research)
    language = str((research or {}).get("design_language") or "")
    ranked = sorted(
        {s.style for s in REFERENCE_SAMPLES},
        key=lambda st: _score_style(st, venue_type, language),
        reverse=True,
    )
    return ranked[:limit]


def pick_references(research: dict[str, Any] | None, style: str, *, limit: int = 3) -> list[ReferenceSample]:
    venue_type = _venue_type(research)
    pool = [s for s in REFERENCE_SAMPLES if s.style == style]
    if not pool:
        pool = list(REFERENCE_SAMPLES)
    pool = sorted(pool, key=lambda s: _score_style(s.style, venue_type, ""), reverse=True)
    return pool[:limit]


def _style_to_generator(style: str) -> tuple[str, str | None, str | None]:
    """Map research style → (option letter, graphic archetype, medium variant)."""
    mapping: dict[str, tuple[str, str | None, str | None]] = {
        "letterpress_handbill": ("B", None, "broadside"),
        "minimalist_swiss": ("A", None, None),
        "photographic": ("B", None, "tri_band"),
        "duotone_bold": ("C", "duotone_modern", None),
        "screen_print": ("C", "xerox_punk", None),
        "psychedelic_illustrative": ("C", "woodstock_festival", None),
        "neon_nightlife": ("C", "neon_bar", None),
        "folk_illustrative": ("C", "country_fair", None),
        "collage_zine": ("C", "pasteup_zine", None),
        "type_only": ("A", None, None),
        "festival_poster": ("C", "broadside", None),
        "mixed_indie": ("C", "boutique", None),
    }
    return mapping.get(style, ("B", "xerox_punk", "paste_up"))


def build_design_brief(event: GigEvent, research: dict[str, Any] | None) -> FlyerDesignBrief:
    venue_type = _venue_type(research)
    styles = recommend_styles(research, limit=3)
    style = styles[0] if styles else "letterpress_handbill"
    refs = pick_references(research, style, limit=3)
    option, archetype, medium = _style_to_generator(style)

    principles = [p.id for p in DESIGN_PRINCIPLES[:8]]
    hierarchy = [
        "Tier 1 (largest): band / headliner name",
        "Tier 2: venue name or tour hook",
        "Tier 3: date, time, address/tickets",
        "Keep contrast high; max two type families",
    ]
    if venue_type in {"member_club", "community_event"}:
        hierarchy.insert(1, "Tier 1b: venue name near top (legion/VFW/community bills)")

    prompt_lines = [
        f"Design style target: {style.replace('_', ' ')}",
        f"Reference samples: {', '.join(r.id for r in refs)}",
        "Apply gig-flyer hierarchy: headliner → hook → date/venue → details",
    ]
    for ref in refs:
        prompt_lines.extend(f"Learn from {ref.id}: {lesson}" for lesson in ref.lessons[:2])

    return FlyerDesignBrief(
        gig_id=event.gig_id,
        venue=event.venue,
        venue_type=venue_type,
        recommended_style=style,
        option_letter=option,
        graphic_archetype=archetype,
        medium_variant=medium,
        principles=principles,
        reference_ids=[r.id for r in refs],
        hierarchy_notes=hierarchy,
        prompt_lines=prompt_lines,
    )


def design_brief_prompt_block(brief: FlyerDesignBrief) -> str:
    lines = [
        "FLYER DESIGN RESEARCH (public corpus):",
        f"- Target style: {brief.recommended_style}",
        f"- References: {', '.join(brief.reference_ids)}",
    ]
    lines.extend(f"- {note}" for note in brief.hierarchy_notes)
    lines.extend(f"- {line}" for line in brief.prompt_lines[:6])
    return "\n".join(lines)


def corpus_summary() -> dict[str, Any]:
    """Quick manifest for tooling / UI."""
    styles: dict[str, int] = {}
    for sample in REFERENCE_SAMPLES:
        styles[sample.style] = styles.get(sample.style, 0) + 1
    return {
        "principle_count": len(DESIGN_PRINCIPLES),
        "sample_count": len(REFERENCE_SAMPLES),
        "styles": styles,
        "sample_ids": [s.id for s in REFERENCE_SAMPLES],
    }
