"""Explicit render specs per design family — no prompt inference."""

from __future__ import annotations

from shell_references import ShellReference
from shell_render_spec import FracBox, ShellRenderSpec

# Default editable regions: headliner, venue, date, time, supporting (matches PLACEHOLDER_LABELS order).
_DEFAULT_EDITABLE: tuple[FracBox, ...] = (
    (0.12, 0.05, 0.88, 0.20),
    (0.10, 0.78, 0.90, 0.86),
    (0.10, 0.86, 0.90, 0.91),
    (0.10, 0.91, 0.90, 0.95),
    (0.10, 0.95, 0.90, 0.99),
)

_ARENA_EDITABLE: tuple[FracBox, ...] = (
    (0.08, 0.07, 0.92, 0.21),   # HEADLINER
    (0.08, 0.72, 0.92, 0.80),   # VENUE
    (0.08, 0.80, 0.92, 0.86),   # DATE
    (0.08, 0.86, 0.92, 0.91),   # TIME
    (0.08, 0.58, 0.92, 0.66),   # SUPPORTING ACTS
)

_FILLMORE_EDITABLE: tuple[FracBox, ...] = (
    (0.14, 0.05, 0.86, 0.22),
    (0.10, 0.78, 0.90, 0.86),
    (0.10, 0.86, 0.90, 0.91),
    (0.10, 0.91, 0.90, 0.95),
    (0.10, 0.95, 0.90, 0.99),
)

_INSET_SLOT: FracBox = (0.05, 0.60, 0.47, 0.86)
_FOOTER_INSET_SLOT: FracBox = (0.25, 0.72, 0.75, 0.88)
_CENTER_HERO_SLOT: FracBox = (0.11, 0.24, 0.89, 0.68)
_BACKGROUND_SLOT: FracBox = (0.0, 0.18, 1.0, 0.82)

_NO_PHOTO = ShellRenderSpec(
    photo_style="none",
    logo_policy="none",
    text_engine="hybrid",
    photo_processing=(),
    photo_slot=(0.0, 0.0, 0.0, 0.0),
    editable_regions=_FILLMORE_EDITABLE,
)

_FAMILY_SPECS: dict[str, ShellRenderSpec] = {
    "fillmore_psychedelic": _NO_PHOTO,
    "avalon_psychedelic": ShellRenderSpec(
        photo_style="none",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=(),
        photo_slot=(0.0, 0.0, 0.0, 0.0),
        editable_regions=(
            (0.12, 0.04, 0.88, 0.20),
            (0.10, 0.76, 0.90, 0.84),
            (0.10, 0.84, 0.90, 0.89),
            (0.10, 0.89, 0.90, 0.93),
            (0.10, 0.93, 0.90, 0.98),
        ),
    ),
    "victorian_circus": ShellRenderSpec(
        photo_style="none",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=(),
        photo_slot=(0.0, 0.0, 0.0, 0.0),
        editable_regions=(
            (0.08, 0.06, 0.92, 0.16),
            (0.08, 0.72, 0.92, 0.80),
            (0.08, 0.80, 0.92, 0.86),
            (0.08, 0.86, 0.92, 0.91),
            (0.08, 0.91, 0.92, 0.96),
        ),
    ),
    "arena_photo_dominant": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=(
            "remove_background",
            "threshold",
            "duotone",
            "halftone",
            "distress",
            "feather",
        ),
        photo_slot=_CENTER_HERO_SLOT,
        editable_regions=_ARENA_EDITABLE,
    ),
    "letterpress_stack": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "distress", "feather"),
        photo_slot=(0.15, 0.28, 0.85, 0.62),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "letterpress_country": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "distress", "feather"),
        photo_slot=(0.20, 0.30, 0.80, 0.58),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "gritty_sidebar_bill": ShellRenderSpec(
        photo_style="inset_photo",
        logo_policy="badge",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "feather"),
        photo_slot=_INSET_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "festival_hero_grid": ShellRenderSpec(
        photo_style="inset_photo",
        logo_policy="footer",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "feather"),
        photo_slot=_FOOTER_INSET_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "jazz_club": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "halftone", "feather"),
        photo_slot=_CENTER_HERO_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "blues_festival": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="footer",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "distress", "feather"),
        photo_slot=(0.10, 0.20, 0.90, 0.52),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "blues_screenprint": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "halftone", "distress"),
        photo_slot=(0.08, 0.18, 0.92, 0.50),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "swiss_jazz": ShellRenderSpec(
        photo_style="inset_photo",
        logo_policy="integrated",
        text_engine="deterministic",
        photo_processing=("remove_background", "duotone", "feather"),
        photo_slot=(0.58, 0.12, 0.94, 0.38),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "instrument_hook": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "feather"),
        photo_slot=(0.15, 0.25, 0.85, 0.60),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "xerox_folk_flyer": ShellRenderSpec(
        photo_style="inset_photo",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone"),
        photo_slot=_INSET_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "punk_screenprint": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "distress"),
        photo_slot=(0.10, 0.20, 0.90, 0.55),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "modern_metal_arena": ShellRenderSpec(
        photo_style="hero_photo",
        logo_policy="badge",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "feather"),
        photo_slot=_CENTER_HERO_SLOT,
        editable_regions=_ARENA_EDITABLE,
    ),
    "theater_debut": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "halftone", "feather"),
        photo_slot=(0.12, 0.22, 0.88, 0.58),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "vintage_broadside": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone", "distress", "feather"),
        photo_slot=(0.10, 0.24, 0.90, 0.62),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "modern_club": ShellRenderSpec(
        photo_style="hero_photo",
        logo_policy="badge",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "feather"),
        photo_slot=_CENTER_HERO_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "underground_zine": ShellRenderSpec(
        photo_style="inset_photo",
        logo_policy="none",
        text_engine="hybrid",
        photo_processing=("remove_background", "threshold", "duotone"),
        photo_slot=_INSET_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "neon_club": ShellRenderSpec(
        photo_style="hero_photo",
        logo_policy="integrated",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "feather"),
        photo_slot=_CENTER_HERO_SLOT,
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "reggae_flyer": ShellRenderSpec(
        photo_style="hero_illustration",
        logo_policy="footer",
        text_engine="hybrid",
        photo_processing=("remove_background", "duotone", "distress", "feather"),
        photo_slot=(0.10, 0.22, 0.90, 0.54),
        editable_regions=_DEFAULT_EDITABLE,
    ),
    "swiss_grid": ShellRenderSpec(
        photo_style="inset_photo",
        logo_policy="integrated",
        text_engine="deterministic",
        photo_processing=("remove_background", "duotone"),
        photo_slot=(0.62, 0.10, 0.95, 0.36),
        editable_regions=_DEFAULT_EDITABLE,
    ),
}

# Per-shell overrides when a specific reference needs different rules than its family.
_SHELL_OVERRIDES: dict[str, ShellRenderSpec] = {}


def _with_preserve_regions(spec: ShellRenderSpec) -> ShellRenderSpec:
    """Default preserve_regions to the photo slot when artwork must stay locked."""
    if spec.preserve_regions:
        return spec
    if spec.photo_style != "none" and spec.photo_slot != (0.0, 0.0, 0.0, 0.0):
        return ShellRenderSpec(
            photo_style=spec.photo_style,
            logo_policy=spec.logo_policy,
            text_engine=spec.text_engine,
            photo_processing=spec.photo_processing,
            photo_slot=spec.photo_slot,
            editable_regions=spec.editable_regions,
            preserve_regions=(spec.photo_slot,),
        )
    return spec


def get_render_spec(shell: ShellReference) -> ShellRenderSpec:
    if shell.id in _SHELL_OVERRIDES:
        return _with_preserve_regions(_SHELL_OVERRIDES[shell.id])
    spec = _FAMILY_SPECS.get(shell.design_family)
    if spec is not None:
        return _with_preserve_regions(spec)
    return _with_preserve_regions(
        ShellRenderSpec(
            photo_style="inset_photo",
            logo_policy="none",
            text_engine="hybrid",
            photo_processing=("remove_background", "duotone", "feather"),
            photo_slot=_INSET_SLOT,
            editable_regions=_DEFAULT_EDITABLE,
        )
    )
