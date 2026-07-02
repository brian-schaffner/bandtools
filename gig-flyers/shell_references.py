"""Registry of reference poster shells for two-pass AI flyer design.

Pass 1 uses a shell reference to generate a placeholder design (no band assets).
Pass 2 personalizes the shell with gig facts, band photo, and logo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SHELL_CACHE = ROOT / "cache" / "shell_references"
LEGACY_CACHE = ROOT / "cache" / "visual_studies"
BUNDLED_SHELL_REFS = ROOT / "assets" / "shell_references"

PLACEHOLDER_LABELS = (
    "HEADLINER",
    "VENUE NAME",
    "DATE",
    "TIME",
    "SUPPORTING ACTS",
)


@dataclass(frozen=True)
class ShellReference:
    id: str
    title: str
    source_url: str
    era: str
    style: str
    venue_context: str
    design_family: str
    shell_prompt: str
    personalize_prompt: str
    layout_rules: tuple[str, ...]
    palette: tuple[str, ...]
    image_filename: str
    image_url: str = ""
    legacy_image_path: str = ""
    linked_research_id: str = ""
    venue_types: tuple[str, ...] = ()

    def image_path(self) -> Path:
        cached = SHELL_CACHE / self.image_filename
        if cached.is_file() and cached.stat().st_size > 5000:
            return cached
        bundled = BUNDLED_SHELL_REFS / self.image_filename
        if bundled.is_file() and bundled.stat().st_size > 5000:
            return bundled
        if self.legacy_image_path:
            p = Path(self.legacy_image_path)
            if not p.is_absolute():
                p = ROOT / p
            if p.is_file() and p.stat().st_size > 5000:
                return p
        return cached

    def has_image(self) -> bool:
        p = self.image_path()
        return p.is_file() and p.stat().st_size > 5000

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["has_image"] = self.has_image()
        d["resolved_image"] = str(self.image_path())
        return d


def _shell(
    id: str,
    title: str,
    source_url: str,
    *,
    era: str,
    style: str,
    venue_context: str,
    design_family: str,
    shell_prompt: str,
    personalize_prompt: str,
    layout_rules: tuple[str, ...],
    palette: tuple[str, ...],
    image_filename: str,
    image_url: str = "",
    legacy_image_path: str = "",
    linked_research_id: str = "",
    venue_types: tuple[str, ...] = (),
) -> ShellReference:
    return ShellReference(
        id=id,
        title=title,
        source_url=source_url,
        era=era,
        style=style,
        venue_context=venue_context,
        design_family=design_family,
        shell_prompt=shell_prompt,
        personalize_prompt=personalize_prompt,
        layout_rules=layout_rules,
        palette=palette,
        image_filename=image_filename,
        image_url=image_url,
        legacy_image_path=legacy_image_path,
        linked_research_id=linked_research_id,
        venue_types=venue_types,
    )


# ---------------------------------------------------------------------------
# Three legacy visual-study shells (already in cache/visual_studies)
# ---------------------------------------------------------------------------

SHELL_REFERENCES: tuple[ShellReference, ...] = (
    _shell(
        "hatch_hank_williams_1953",
        "Hank Williams at Canton Memorial Auditorium (Hatch Show Print, 1953)",
        "https://digi.countrymusichalloffame.org/digital/collection/hatch3/id/26648",
        era="1953",
        style="letterpress_handbill",
        venue_context="member_club",
        design_family="letterpress_stack",
        shell_prompt=(
            "Letterpress country show poster. Cream paper, red + black ink only. "
            "Vertical stack: venue, date, presenter bar, square portrait zone, mega band name. "
            "Use placeholder text HEADLINER, VENUE NAME, DATE, TIME only."
        ),
        personalize_prompt=(
            "Preserve letterpress stack layout. Replace placeholders with exact gig facts. "
            "Use band photo as centered portrait; include band logo near name."
        ),
        layout_rules=(
            "Stack top→bottom: venue, date, presenter bar, portrait, mega band name.",
            "Two inks + cream paper only.",
        ),
        palette=("#F2EBD4", "#111111", "#B31B1B"),
        image_filename="hatch_hank_williams_1953.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Hank%20Williams%20Show%20Poster.jpg",
        legacy_image_path="cache/visual_studies/hank_hatch.jpg",
        venue_types=("member_club", "community_event"),
    ),
    _shell(
        "altamont_free_concert_1969",
        "Altamont Free Concert (1969)",
        "https://commons.wikimedia.org/wiki/File:Altamont_free_concert_poster.jpg",
        era="1969",
        style="type_only",
        venue_context="festival",
        design_family="gritty_sidebar_bill",
        shell_prompt=(
            "Gritty 1969 rock bill poster. Red/black alternation, asymmetric layout, "
            "sidebar column for openers. High-contrast xerox feel. Placeholders only."
        ),
        personalize_prompt=(
            "Keep asymmetric bill layout and sidebar. Photo lower-left gritty B&W. "
            "Logo visible near headliner block."
        ),
        layout_rules=(
            "Headliner + promo hook first; sidebar for openers.",
            "Red/black line alternation.",
        ),
        palette=("#F5F0E6", "#111111", "#C41E3A"),
        image_filename="altamont_free_concert_1969.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Altamont_free_concert_poster.jpg",
        legacy_image_path="cache/visual_studies/altamont2.jpg",
        venue_types=("regional_bar", "blues_bar", "casino_venue"),
    ),
    _shell(
        "woodstock_festival_1969",
        "Woodstock Music & Art Fair (1969)",
        "https://commons.wikimedia.org/wiki/File:Woodstock_poster.jpg",
        era="1969",
        style="psychedelic_illustrative",
        venue_context="festival",
        design_family="festival_hero_grid",
        shell_prompt=(
            "Psychedelic 1969 festival poster. Symbolic hero art top ~45%, red field, "
            "hand-drawn yellow slogan, 3-column footer grid. Flat 4-color palette. Placeholders only."
        ),
        personalize_prompt=(
            "Preserve hero art + slogan + footer grid. Band photo as footer inset; logo in grid. "
            "Do not redraw photo or omit logo."
        ),
        layout_rules=(
            "Hero art + slogan dominate; 3-column footer for lineup/logistics.",
            "Flat red/yellow/blue/black/white palette.",
        ),
        palette=("#D32F2F", "#111111", "#F5C400", "#1565C0"),
        image_filename="woodstock_festival_1969.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Woodstock_poster.jpg",
        legacy_image_path="cache/visual_studies/woodstock2.jpg",
        venue_types=("festival",),
    ),
    # -----------------------------------------------------------------------
    # 20 additional shell references (downloaded to cache/shell_references)
    # -----------------------------------------------------------------------
    _shell(
        "fillmore_jefferson_airplane_1966",
        "Jefferson Airplane at Fillmore Auditorium (1966)",
        "https://commons.wikimedia.org/wiki/File:Jefferson_airplane_fillmore_poster_1966.jpg",
        era="1966",
        style="psychedelic_illustrative",
        venue_context="theater",
        design_family="fillmore_psychedelic",
        shell_prompt=(
            "Bill Graham Fillmore psychedelic poster. Swirling lettering, symbolic illustration, "
            "dense but readable type. Use HEADLINER, VENUE NAME, DATE placeholders."
        ),
        personalize_prompt="Preserve Fillmore psychedelic lettering and illustration style.",
        layout_rules=("Symbolic art + warped display type.", "High contrast ink on saturated ground."),
        palette=("#D32F2F", "#F5C400", "#1565C0", "#111111"),
        image_filename="fillmore_jefferson_airplane_1966.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Jefferson%20airplane%20fillmore%20poster%201966.jpg",
        venue_types=("theater", "regional_club"),
    ),
    _shell(
        "avalon_mantra_rock_1967",
        "Mantra-Rock Dance, Avalon Ballroom (1967)",
        "https://commons.wikimedia.org/wiki/File:1967_Mantra-Rock_Dance_Avalon_poster.jpg",
        era="1967",
        style="psychedelic_illustrative",
        venue_context="theater",
        design_family="avalon_psychedelic",
        shell_prompt=(
            "Family Dog Avalon ballroom poster. Cosmic illustration, ornate borders, "
            "centered mystical motif. Placeholder type only."
        ),
        personalize_prompt="Keep Avalon cosmic border and mystical center art.",
        layout_rules=("Ornate frame around central symbol.", "Bill text in readable blocks."),
        palette=("#6A1B9A", "#F5C400", "#00838F", "#111111"),
        image_filename="avalon_mantra_rock_1967.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/1967%20Mantra-Rock%20Dance%20Avalon%20poster.jpg",
        venue_types=("theater", "regional_club"),
    ),
    _shell(
        "circus_victorian_mr_kite_1967",
        "Victorian circus poster motif (Mr. Kite style, 1967)",
        "https://commons.wikimedia.org/wiki/File:Mr._Kite_(detail).png",
        era="1960s",
        style="letterpress_handbill",
        venue_context="theater",
        design_family="victorian_circus",
        shell_prompt=(
            "Victorian circus/broadside poster. Wood type, ornamental rules, vintage circus hierarchy. "
            "Placeholders HEADLINER, VENUE, DATE in antique display type."
        ),
        personalize_prompt="Preserve Victorian wood-type hierarchy and ornamental rules.",
        layout_rules=("Multiple type sizes in stacked blocks.", "Ornamental dividers between facts."),
        palette=("#F2EBD4", "#111111", "#B71C1C"),
        image_filename="circus_victorian_mr_kite_1967.png",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Mr.%20Kite%20(detail).png",
        venue_types=("theater", "community_event"),
    ),
    _shell(
        "hendrix_sicks_stadium_1970",
        "Jimi Hendrix at Sicks Stadium (1970)",
        "https://commons.wikimedia.org/wiki/File:Poster_for_Jimi_Hendrix_at_Sicks_Stadium,_July_26,_1970.jpg",
        era="1970",
        style="photographic",
        venue_context="arena",
        design_family="arena_photo_dominant",
        shell_prompt=(
            "1970 arena rock poster. Bold headliner name, photo-forward composition, "
            "date/venue in strong sans blocks. Placeholder text only."
        ),
        personalize_prompt="Keep arena-scale hierarchy; band photo as hero without redraw.",
        layout_rules=("Headliner name largest.", "Photo anchors center or lower two-thirds."),
        palette=("#111111", "#F5F5F5", "#E53935"),
        image_filename="hendrix_sicks_stadium_1970.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Poster%20for%20Jimi%20Hendrix%20at%20Sicks%20Stadium,%20July%2026,%201970.jpg",
        venue_types=("arena", "festival"),
    ),
    _shell(
        "hatch_show_print_gallery",
        "Hatch Show Print gallery posters",
        "https://commons.wikimedia.org/wiki/File:Hatch_Show_Print_Posters.jpg",
        era="1940s-2020s",
        style="letterpress_handbill",
        venue_context="country_venue",
        design_family="letterpress_country",
        shell_prompt=(
            "Hatch Show Print letterpress wall. Wood type, country show stack, "
            "red/black/cream. Placeholder venue, date, HEADLINER."
        ),
        personalize_prompt="Match Hatch wood-type stack; portrait slot for band photo.",
        layout_rules=("Country show name dominates.", "Venue/date above portrait."),
        palette=("#F2EBD4", "#111111", "#B31B1B"),
        image_filename="hatch_show_print_gallery.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Hatch%20Show%20Print%20Posters.jpg",
        venue_types=("member_club", "community_event", "country_venue"),
    ),
    _shell(
        "new_orleans_jazz_club",
        "New Orleans Jazz Club poster",
        "https://commons.wikimedia.org/wiki/File:New_Orleans_Jazz_Museum_-_Poster_for_Jazz_Club_Jam.jpg",
        era="modern",
        style="folk_illustrative",
        venue_context="blues_bar",
        design_family="jazz_club",
        shell_prompt=(
            "New Orleans jazz club poster. Illustrative mood, warm paper, serif + script mix. "
            "Placeholder HEADLINER, VENUE, DATE."
        ),
        personalize_prompt="Preserve jazz club illustration mood and warm palette.",
        layout_rules=("Illustration sets mood; type stays legible.", "Club name prominent."),
        palette=("#FFF8E1", "#3E2723", "#FF6F00"),
        image_filename="new_orleans_jazz_club.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/New%20Orleans%20Jazz%20Museum%20-%20Poster%20for%20Jazz%20Club%20Jam.jpg",
        venue_types=("blues_bar", "regional_bar", "regional_club"),
    ),
    _shell(
        "waterfront_blues_festival",
        "Waterfront Blues Festival poster",
        "https://commons.wikimedia.org/wiki/File:Waterfront_blues_Festival_Poster.jpg",
        era="2000s",
        style="duotone_bold",
        venue_context="festival",
        design_family="blues_festival",
        shell_prompt=(
            "Blues festival poster. Bold duotone, guitar/blues motifs, "
            "festival name as hook. Placeholders only."
        ),
        personalize_prompt="Keep blues festival duotone and hook typography.",
        layout_rules=("Festival hook first.", "Lineup secondary in footer."),
        palette=("#1A237E", "#FFC107", "#111111"),
        image_filename="waterfront_blues_festival.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Waterfront%20blues%20Festival%20Poster.jpg",
        venue_types=("festival", "blues_bar"),
    ),
    _shell(
        "harvest_time_blues",
        "Harvest Time Blues poster",
        "https://commons.wikimedia.org/wiki/File:Harvest_Time_Blues.jpg",
        era="2010s",
        style="screen_print",
        venue_context="regional_club",
        design_family="blues_screenprint",
        shell_prompt=(
            "Screen-print blues poster. Limited palette, gritty texture, bold slab type. "
            "Placeholder HEADLINER, VENUE, DATE."
        ),
        personalize_prompt="Preserve screen-print texture and slab-serif hierarchy.",
        layout_rules=("2-3 ink colors.", "Texture visible in background."),
        palette=("#3E2723", "#FF8F00", "#FFFDE7"),
        image_filename="harvest_time_blues.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Harvest%20Time%20Blues.jpg",
        venue_types=("blues_bar", "regional_bar"),
    ),
    _shell(
        "jazz_nespolo_newport_style_1995",
        "Newport Jazz Festival poster (Nespolo, 1995)",
        "https://commons.wikimedia.org/wiki/File:Newport_Jazz_Festival_Torino,_Poster,_Ugo_Nespolo,_1995.jpg",
        era="1995",
        style="minimalist_swiss",
        venue_context="festival",
        design_family="swiss_jazz",
        shell_prompt=(
            "Swiss-style jazz festival poster. Grid layout, bold geometric shapes, "
            "minimal type. Placeholder blocks for HEADLINER, VENUE, DATE."
        ),
        personalize_prompt="Keep Swiss grid and geometric color blocks.",
        layout_rules=("Strict grid alignment.", "One display moment + clean logistics."),
        palette=("#FFFFFF", "#111111", "#D32F2F", "#F5C400"),
        image_filename="jazz_nespolo_newport_style_1995.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Newport%20Jazz%20Festival%20Torino,%20Poster,%20Ugo%20Nespolo,%201995.jpg",
        venue_types=("festival", "theater"),
    ),
    _shell(
        "saxophone_festival_poster",
        "Saxophone festival poster",
        "https://commons.wikimedia.org/wiki/File:Saxophone_festival_poster.jpg",
        era="2010s",
        style="duotone_bold",
        venue_context="festival",
        design_family="instrument_hook",
        shell_prompt=(
            "Music festival poster with instrument as visual hook. Bold silhouette, "
            "two-color ground. Placeholder festival name and date."
        ),
        personalize_prompt="Keep instrument hook art; swap placeholder type for gig facts.",
        layout_rules=("Instrument icon as hero.", "Date/venue in bold footer band."),
        palette=("#0D47A1", "#FFEB3B", "#111111"),
        image_filename="saxophone_festival_poster.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Saxophone%20festival%20poster.jpg",
        venue_types=("festival", "regional_club"),
    ),
    _shell(
        "folk_xerox_anna_crusis_1995",
        "Anna Crusis folk concert flyer (1995)",
        "https://commons.wikimedia.org/wiki/File:Anna_Crusis_1995_concert_flyer_People%27s_Music_Pete_Seeger_001.jpg",
        era="1995",
        style="collage_zine",
        venue_context="community_event",
        design_family="xerox_folk_flyer",
        shell_prompt=(
            "Xerox folk benefit flyer. Typewriter dates, cut-and-paste energy, "
            "minimal ornament. Placeholder text only."
        ),
        personalize_prompt="Preserve xerox/typewriter folk flyer feel.",
        layout_rules=("Typewriter body copy.", "Single strong headline."),
        palette=("#FFFFFF", "#111111"),
        image_filename="folk_xerox_anna_crusis_1995.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Anna%20Crusis%201995%20concert%20flyer%20People%27s%20Music%20Pete%20Seeger%20001.jpg",
        venue_types=("community_event", "member_club"),
    ),
    _shell(
        "punk_heide_deathmarschen",
        "Heide deathmarschen punk poster",
        "https://commons.wikimedia.org/wiki/File:Heide_deathmarschen.jpg",
        era="1980s",
        style="screen_print",
        venue_context="regional_club",
        design_family="punk_screenprint",
        shell_prompt=(
            "Punk/DIY screen-print poster. Aggressive display type, high contrast, "
            "distressed texture. Placeholder band and venue."
        ),
        personalize_prompt="Keep punk screen-print aggression; photo as gritty inset.",
        layout_rules=("Headliner in distorted display type.", "High contrast only."),
        palette=("#111111", "#FF1744", "#FFFFFF"),
        image_filename="punk_heide_deathmarschen.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Heide%20deathmarschen.jpg",
        venue_types=("regional_bar", "regional_club"),
    ),
    _shell(
        "metal_slipknot_arena_2019",
        "Slipknot arena poster (2019)",
        "https://commons.wikimedia.org/wiki/File:2019_Poster_advertisement_for_Slipknot_and_Behemoth_live_concert_in_Hallenstadion_Z%C3%BCrich_Ank_Kumar_,_Infosys_Limited.jpg",
        era="2019",
        style="photographic",
        venue_context="arena",
        design_family="modern_metal_arena",
        shell_prompt=(
            "Modern metal arena poster. Dark ground, aggressive typography, photo bleed. "
            "Placeholder HEADLINER, VENUE, DATE."
        ),
        personalize_prompt="Preserve dark arena metal layout; band photo without redraw.",
        layout_rules=("Dark field + neon accent type.", "Photo integrated in lower half."),
        palette=("#111111", "#B71C1C", "#FFFFFF"),
        image_filename="metal_slipknot_arena_2019.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/2019%20Poster%20advertisement%20for%20Slipknot%20and%20Behemoth%20live%20concert%20in%20Hallenstadion%20Z%C3%BCrich%20Ank%20Kumar%20,%20Infosys%20Limited.jpg",
        venue_types=("arena", "casino_venue"),
    ),
    _shell(
        "theater_crowns_debut",
        "Crowns Debut theater poster",
        "https://commons.wikimedia.org/wiki/File:Crowns_Debut_Poster.jpg",
        era="2010s",
        style="folk_illustrative",
        venue_context="theater",
        design_family="theater_debut",
        shell_prompt=(
            "Theater debut poster. Illustrative portrait zone, elegant serif title, "
            "understated date block. Placeholders only."
        ),
        personalize_prompt="Keep theater elegance; band photo in portrait zone.",
        layout_rules=("Title centered or upper third.", "Date/venue in refined footer."),
        palette=("#FFF8E1", "#4E342E", "#BF360C"),
        image_filename="theater_crowns_debut.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Crowns%20Debut%20Poster.jpg",
        venue_types=("theater", "regional_club"),
    ),
    _shell(
        "vintage_broadside_west_coast_1923",
        "West Coast Exhibition broadside (1923)",
        "https://commons.wikimedia.org/wiki/File:West_Coast_Exhibition_poster_1923_01.jpg",
        era="1923",
        style="type_only",
        venue_context="community_event",
        design_family="vintage_broadside",
        shell_prompt=(
            "1920s broadside. Giant display type, minimal ornament, event facts in blocks. "
            "Placeholder HEADLINER, VENUE, DATE."
        ),
        personalize_prompt="Preserve broadside mega-type hierarchy.",
        layout_rules=("One word or line dominates.", "Facts in secondary blocks."),
        palette=("#FBE9E7", "#111111", "#BF360C"),
        image_filename="vintage_broadside_west_coast_1923.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/West%20Coast%20Exhibition%20poster%201923%2001.jpg",
        venue_types=("community_event", "member_club"),
    ),
    _shell(
        "rock_ira_concert_2021",
        "IRA concert poster, Boguchwała (2021)",
        "https://commons.wikimedia.org/wiki/File:IRA_concert_poster_in_Boguchwa%C5%82a_(2021).jpg",
        era="2021",
        style="mixed_indie",
        venue_context="regional_club",
        design_family="modern_club",
        shell_prompt=(
            "Modern club gig poster. Clean vector shapes, bold color panels, "
            "contemporary sans type. Placeholders only."
        ),
        personalize_prompt="Keep modern club panel layout and bold color blocks.",
        layout_rules=("Color panels divide zones.", "Sans-serif throughout."),
        palette=("#263238", "#FF5722", "#FFFFFF"),
        image_filename="rock_ira_concert_2021.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/IRA%20concert%20poster%20in%20Boguchwa%C5%82a%20(2021).jpg",
        venue_types=("regional_club", "regional_bar"),
    ),
    _shell(
        "underground_zine_helix_1967",
        "Helix underground paper poster page (1967)",
        "https://commons.wikimedia.org/wiki/File:Helix,_v.1,_no.5,_Jun._6,_1967_-_DPLA_-_98789ca1cfcb6c2c9dd28f64dc9f563e_(page_15).jpg",
        era="1967",
        style="collage_zine",
        venue_context="regional_club",
        design_family="underground_zine",
        shell_prompt=(
            "1967 underground zine poster page. Collage, hand lettering, anti-establishment layout. "
            "Placeholder gig text."
        ),
        personalize_prompt="Preserve zine collage energy; keep type raw and readable.",
        layout_rules=("Collage layers OK.", "Hand lettering for hook only."),
        palette=("#FFFDE7", "#111111", "#E65100"),
        image_filename="underground_zine_helix_1967.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Helix,%20v.1,%20no.5,%20Jun.%206,%201967%20-%20DPLA%20-%2098789ca1cfcb6c2c9dd28f64dc9f563e%20(page%2015).jpg",
        venue_types=("regional_bar", "regional_club"),
    ),
    _shell(
        "neon_club_saxophone_variant",
        "Neon-forward festival/club poster (saxophone variant)",
        "https://commons.wikimedia.org/wiki/File:Saxophone_festival_poster.jpg",
        era="2010s",
        style="neon_nightlife",
        venue_context="regional_bar",
        design_family="neon_club",
        shell_prompt=(
            "Neon club night poster. Dark ground, glowing accent type, nightlife energy. "
            "Placeholder HEADLINER, VENUE, DATE."
        ),
        personalize_prompt="Keep neon-on-dark palette; logo as light ink on dark footer.",
        layout_rules=("Dark field required.", "Neon accent on hook + time."),
        palette=("#121212", "#FF4081", "#00E5FF"),
        image_filename="neon_club_saxophone_variant.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Saxophone%20festival%20poster.jpg",
        venue_types=("regional_bar", "casino_venue", "blues_bar"),
    ),
    _shell(
        "reggae_sound_clash_flyer",
        "Reggae / sound-system flyer style",
        "https://commons.wikimedia.org/wiki/File:Harvest_Time_Blues.jpg",
        era="2010s",
        style="duotone_bold",
        venue_context="regional_bar",
        design_family="reggae_flyer",
        shell_prompt=(
            "Reggae sound-system flyer. Green/gold/red accent palette option, bold stacked type, "
            "dancehall energy. Placeholders only."
        ),
        personalize_prompt="Preserve reggae flyer color rhythm and stacked type.",
        layout_rules=("Stacked caps for headliner.", "Sound-system vibe in footer."),
        palette=("#1B5E20", "#F9A825", "#B71C1C", "#111111"),
        image_filename="reggae_sound_clash_flyer.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Harvest%20Time%20Blues.jpg",
        venue_types=("regional_bar", "regional_club"),
    ),
    _shell(
        "swiss_minimal_poster_grid",
        "Swiss minimal grid poster",
        "https://commons.wikimedia.org/wiki/File:Newport_Jazz_Festival_Torino,_Poster,_Ugo_Nespolo,_1995.jpg",
        era="1990s",
        style="minimalist_swiss",
        venue_context="theater",
        design_family="swiss_grid",
        shell_prompt=(
            "Swiss international typographic poster. Strict grid, asymmetric balance, "
            "one accent color. Placeholder blocks only."
        ),
        personalize_prompt="Keep grid discipline; swap placeholder blocks for exact facts.",
        layout_rules=("Align to grid.", "One accent hue only."),
        palette=("#FFFFFF", "#111111", "#1565C0"),
        image_filename="swiss_minimal_poster_grid.jpg",
        image_url="https://commons.wikimedia.org/wiki/Special:FilePath/Newport%20Jazz%20Festival%20Torino,%20Poster,%20Ugo%20Nespolo,%201995.jpg",
        venue_types=("theater", "regional_club"),
    ),
)


def all_shells() -> list[ShellReference]:
    return list(SHELL_REFERENCES)


def get_shell(shell_id: str) -> ShellReference | None:
    for shell in SHELL_REFERENCES:
        if shell.id == shell_id:
            return shell
    return None


def pick_shell_for_venue_type(venue_type: str) -> ShellReference:
    vt = venue_type or "regional_club"
    for shell in SHELL_REFERENCES:
        if vt in shell.venue_types:
            return shell
    return SHELL_REFERENCES[0]


def pick_shell_for_research(research: dict[str, Any] | None) -> ShellReference:
    vt = str((research or {}).get("venue_type") or "regional_club")
    return pick_shell_for_venue_type(vt)


def shells_with_images() -> list[ShellReference]:
    return [s for s in SHELL_REFERENCES if s.has_image()]


def registry_summary() -> dict[str, Any]:
    items = [s.to_dict() for s in SHELL_REFERENCES]
    return {
        "count": len(items),
        "with_images": sum(1 for s in SHELL_REFERENCES if s.has_image()),
        "shells": items,
    }
