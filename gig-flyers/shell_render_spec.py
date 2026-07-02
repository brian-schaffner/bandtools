"""Authoritative rendering rules for shell pass 2 — layout is data, not prompts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

PhotoStyle = Literal[
    "none",
    "hero_photo",
    "inset_photo",
    "hero_illustration",
    "background_photo",
    "collage",
]
LogoPolicy = Literal["none", "badge", "integrated", "footer"]
TextEngine = Literal["openai", "deterministic", "hybrid"]
PhotoProcessing = Literal[
    "remove_background",
    "threshold",
    "duotone",
    "halftone",
    "distress",
    "feather",
    "matte",
]

# Fractional box (x1, y1, x2, y2) in 0–1 canvas coordinates.
FracBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class ShellRenderSpec:
    """Explicit pass-2 rules for one shell or design family."""

    photo_style: PhotoStyle
    logo_policy: LogoPolicy
    text_engine: TextEngine
    photo_processing: tuple[PhotoProcessing, ...]
    photo_slot: FracBox
    editable_regions: tuple[FracBox, ...]
    preserve_regions: tuple[FracBox, ...] = ()

    def uses_band_photo(self) -> bool:
        return self.photo_style != "none"

    def uses_band_logo(self) -> bool:
        return self.logo_policy != "none"

    def openai_text_slots(self) -> tuple[str, ...]:
        """Which placeholder labels still go through OpenAI in hybrid mode."""
        from shell_references import PLACEHOLDER_LABELS

        if self.text_engine == "openai":
            return PLACEHOLDER_LABELS
        if self.text_engine == "deterministic":
            return ()
        # hybrid — stylized headliner only; facts are deterministic
        return ("HEADLINER",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def frac_boxes_to_pixels(
    size: tuple[int, int],
    boxes: tuple[FracBox, ...],
) -> tuple[tuple[int, int, int, int], ...]:
    w, h = size
    out: list[tuple[int, int, int, int]] = []
    for x1, y1, x2, y2 in boxes:
        out.append((int(w * x1), int(h * y1), int(w * x2), int(h * y2)))
    return tuple(out)
