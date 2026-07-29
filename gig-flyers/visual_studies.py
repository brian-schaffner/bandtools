"""Visual studies of real gig flyers — observations from looking at actual artwork."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STUDY_CACHE = ROOT / "cache" / "visual_studies"

HATCH_RED = "#B31B1B"
HATCH_INK = "#111111"
HATCH_PAPER = "#F2EBD4"


@dataclass(frozen=True)
class VisualObservation:
    """One concrete thing seen in the artwork."""

    element: str
    detail: str


@dataclass(frozen=True)
class VisualStudy:
    """Findings from studying one real poster image."""

    id: str
    title: str
    source_url: str
    image_path: str
    year: str
    context: str
    observations: tuple[VisualObservation, ...]
    layout_rules: tuple[str, ...]
    palette: tuple[str, ...]
    medium_variant: str | None = None
    graphic_archetype: str | None = None

    def guidance_lines(self) -> list[str]:
        lines = [f"Study: {self.title} ({self.year})"]
        for obs in self.observations:
            lines.append(f"- {obs.element}: {obs.detail}")
        lines.append("Layout rules learned:")
        for rule in self.layout_rules:
            lines.append(f"  • {rule}")
        return lines

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["observations"] = [asdict(o) for o in self.observations]
        data["guidance"] = self.guidance_lines()
        return data


VISUAL_STUDIES: tuple[VisualStudy, ...] = (
    VisualStudy(
        id="hatch_hank_williams_1953",
        title="Hank Williams at Canton Memorial Auditorium (Hatch Show Print)",
        source_url="https://digi.countrymusichalloffame.org/digital/collection/hatch3/id/26648",
        image_path=str(STUDY_CACHE / "hank_hatch.jpg"),
        year="1953",
        context="letterpress country show poster",
        observations=(
            VisualObservation("hierarchy", "Venue + date sit ABOVE the artist name, not below."),
            VisualObservation("color", "Two inks only: red and black on cream paper — no gradients."),
            VisualObservation("type", "Band name is the widest/largest element on the page (condensed caps)."),
            VisualObservation("photo", "Square portrait centered between a black presenter bar and the name."),
            VisualObservation("alignment", "Everything center-aligned in a vertical stack."),
            VisualObservation("presenter_bar", "Black rectangle with white type ('GRAND OLE OPRY') separates date from photo."),
            VisualObservation("personality", "Small quote at top sets tone before any logistics."),
        ),
        layout_rules=(
            "Stack top→bottom: venue, date, presenter bar, portrait photo, mega band name.",
            "Use only 2 ink colors + paper (red for venue/date/name, black for bars and secondary).",
            "Center-align all type; photo ~35–40% of height, square-ish.",
            "Presenter bar: solid black fill, white uppercase label.",
            "Band name font size should exceed venue by ~2×.",
        ),
        palette=(HATCH_PAPER, HATCH_INK, HATCH_RED),
        medium_variant="hatch_stack",
    ),
    VisualStudy(
        id="altamont_free_concert_1969",
        title="Altamont Free Concert (Rolling Stones)",
        source_url="https://commons.wikimedia.org/wiki/File:Altamont_free_concert_poster.jpg",
        image_path=str(STUDY_CACHE / "altamont2.jpg"),
        year="1969",
        context="free festival / multi-act bill",
        observations=(
            VisualObservation("hierarchy", "Headliner at very top; 'FREE CONCERT' is the promotional hook in red caps."),
            VisualObservation("color_rhythm", "Red and black alternate by line — date black, location red."),
            VisualObservation("photo", "High-contrast B&W performance photo ~40% width, anchors lower-left."),
            VisualObservation("sidebar", "Supporting acts live in a right column, not a bottom list."),
            VisualObservation("stars", "Small stars flank 'FREE CONCERT' as accent punctuation."),
            VisualObservation("footer", "Odd details (security, numbering) relegated to tiny footer type."),
        ),
        layout_rules=(
            "Headline block first: headliner, promo hook, date, location — before photo.",
            "Use red/black alternation on separate lines for scanability.",
            "Multi-act bills: sidebar column for openers, not stacked at bottom.",
            "Photo: gritty B&W, high contrast, overlaps text block edge.",
            "Keep footer microcopy separate from main hierarchy.",
        ),
        palette=("#F5F0E6", "#111111", "#C41E3A"),
        medium_variant="altamont_sidebar",
    ),
    VisualStudy(
        id="woodstock_festival_1969",
        title="Woodstock Music & Art Fair",
        source_url="https://commons.wikimedia.org/wiki/File:Woodstock_poster.jpg",
        image_path=str(STUDY_CACHE / "woodstock_thumb.jpg"),
        year="1969",
        context="festival / multi-day bill",
        observations=(
            VisualObservation("hero", "Single symbolic illustration (bird + guitar) fills top ~45% — not a photo."),
            VisualObservation("slogan", "Festival hook ('3 DAYS OF PEACE & MUSIC') is largest type, not band name."),
            VisualObservation("grid", "Bottom third is 3-column grid: lineup | logistics | slogan."),
            VisualObservation("palette", "Flat 4-color art on solid red field — no photo realism."),
            VisualObservation("dates", "Dates in bold black sans, separated from dense lineup text."),
            VisualObservation("density", "Lineup is tertiary small type; slogan and dates carry first read."),
        ),
        layout_rules=(
            "Festival: lead with symbolic hero art + slogan, not performer photo.",
            "Use 3-column footer grid when listing many acts + logistics.",
            "Limit palette to 4 flat colors; avoid photographic hero.",
            "Dates in bold isolated block; lineup smallest tier.",
            "Solid color field behind art unifies busy information.",
        ),
        palette=("#D32F2F", "#111111", "#F5C400", "#1565C0"),
        graphic_archetype="psychedelic",
    ),
)


def all_studies() -> list[VisualStudy]:
    return list(VISUAL_STUDIES)


def get_study(study_id: str) -> VisualStudy | None:
    for study in VISUAL_STUDIES:
        if study.id == study_id:
            return study
    return None


def pick_study_for_research(research: dict[str, Any] | None) -> VisualStudy:
    venue_type = str((research or {}).get("venue_type") or "regional_club")
    if venue_type == "festival":
        return get_study("woodstock_festival_1969")  # type: ignore[return-value]
    if venue_type in {"member_club", "community_event"}:
        return get_study("hatch_hank_williams_1953")  # type: ignore[return-value]
    if venue_type in {"regional_bar", "blues_bar", "casino_venue"}:
        return get_study("altamont_free_concert_1969")  # type: ignore[return-value]
    return get_study("hatch_hank_williams_1953")  # type: ignore[return-value]


def combined_guidance(study: VisualStudy) -> str:
    return "\n".join(study.guidance_lines())
