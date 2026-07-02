"""Tight placeholder text regions per shell family — avoid repainting illustration."""

from __future__ import annotations

from shell_references import PLACEHOLDER_LABELS, ShellReference
from shell_render_registry import get_render_spec
from shell_render_spec import frac_boxes_to_pixels

# Fractional boxes (x1, y1, x2, y2) per design_family, in placeholder order where present.
_FAMILY_SLOTS: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    "fillmore_psychedelic": (
        (0.14, 0.05, 0.86, 0.22),  # HEADLINER on yellow circle
        (0.10, 0.78, 0.90, 0.86),  # VENUE NAME in bottom frame
        (0.10, 0.86, 0.90, 0.91),  # DATE
        (0.10, 0.91, 0.90, 0.95),  # TIME
        (0.10, 0.95, 0.90, 0.99),  # SUPPORTING ACTS
    ),
    "avalon_psychedelic": (
        (0.12, 0.04, 0.88, 0.20),
        (0.10, 0.76, 0.90, 0.84),
        (0.10, 0.84, 0.90, 0.89),
        (0.10, 0.89, 0.90, 0.93),
        (0.10, 0.93, 0.90, 0.98),
    ),
    "victorian_circus": (
        (0.08, 0.06, 0.92, 0.16),
        (0.08, 0.72, 0.92, 0.80),
        (0.08, 0.80, 0.92, 0.86),
        (0.08, 0.86, 0.92, 0.91),
        (0.08, 0.91, 0.92, 0.96),
    ),
}

_DEFAULT_TYPOGRAPHY_SLOTS = (
    (0.12, 0.05, 0.88, 0.20),
    (0.10, 0.78, 0.90, 0.86),
    (0.10, 0.86, 0.90, 0.91),
    (0.10, 0.91, 0.90, 0.95),
    (0.10, 0.95, 0.90, 0.99),
)


def typography_text_zones(
    size: tuple[int, int],
    shell: ShellReference,
) -> list[tuple[int, int, int, int]]:
    """Editable regions from authoritative shell render spec."""
    spec = get_render_spec(shell)
    return list(frac_boxes_to_pixels(size, spec.editable_regions))


def slot_prompt(placeholder: str, value: str, shell: ShellReference) -> str:
    """One placeholder swap — preserve shell lettering style."""
    return (
        f"Replace ONLY the placeholder text \"{placeholder}\" with \"{value}\".\n"
        "Use the EXACT same hand-lettered / psychedelic / wood-type style, colors, "
        "warp, and placement as the placeholder — not plain sans-serif.\n"
        "Change nothing else on the poster: no photos, no new logos, no recoloring, "
        "no repainting of illustration or borders.\n"
        f"Shell guidance: {shell.personalize_prompt}"
    )


def placeholder_values(
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
) -> dict[str, str]:
    return {
        "HEADLINER": band,
        "VENUE NAME": venue,
        "DATE": date,
        "TIME": time,
        "SUPPORTING ACTS": "",
    }
