"""Photo treatment doctrine: defines what operations are allowed/forbidden on band photos.

The uploaded band photo is source artwork, not inspiration. The AI should treat it
exactly like an art director placing a photograph into an InDesign layout — never
regenerate, redraw, or reinterpret the underlying pixels of the musicians.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Operations that ARE allowed on band photos (PIL/post-processing only)
PHOTO_ALLOWED: tuple[str, ...] = (
    "crop",
    "scale",
    "translate",
    "rotate <=2°",
    "perspective correction",
    "brightness",
    "contrast",
    "curves",
    "saturation",
    "film grain",
    "paper texture",
    "halftone",
    "multiply blend",
    "screen blend",
    "overlay blend",
    "edge feather",
    "vignette",
    "color toning",
    "frame clipping",
)

# Operations that are FORBIDDEN on band photos (never send to AI for modification)
PHOTO_FORBIDDEN: tuple[str, ...] = (
    "repaint",
    "redraw",
    "inpaint",
    "outpaint",
    "replace faces",
    "change expressions",
    "invent limbs",
    "change clothing",
    "change instruments",
    "hallucinate fingers",
    "hallucinate guitars",
    "hallucinate people",
    "generate new humans",
    "AI face enhancement",
    "beauty filter",
    "style transfer",
    "artistic reinterpretation",
)


@dataclass(frozen=True)
class PhotoTreatmentDoctrine:
    """Encapsulates the photo treatment rules for prompt generation and validation."""

    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]

    def allowed_prompt_block(self) -> list[str]:
        """Generate prompt lines describing allowed photo operations."""
        lines = [
            "PHOTO TREATMENT — ALLOWED OPERATIONS (PIL preprocessing only, never AI):",
        ]
        lines.extend(f"  - {op}" for op in self.allowed)
        return lines

    def forbidden_prompt_block(self) -> list[str]:
        """Generate prompt lines describing forbidden photo operations."""
        lines = [
            "PHOTO TREATMENT — FORBIDDEN OPERATIONS (automatic failure if detected):",
        ]
        lines.extend(f"  - {op}" for op in self.forbidden)
        return lines

    def full_prompt_block(self) -> list[str]:
        """Generate complete photo treatment prompt section."""
        lines = [
            "",
            "=== PHOTO TREATMENT DOCTRINE ===",
            "The uploaded band photo is SOURCE ARTWORK, not inspiration.",
            "Treat it exactly like an art director placing a photograph into an InDesign layout.",
            "The AI should NEVER satisfy 'photo fidelity' by simply placing the original rectangle on top.",
            "",
        ]
        lines.extend(self.allowed_prompt_block())
        lines.append("")
        lines.extend(self.forbidden_prompt_block())
        lines.append("")
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": list(self.allowed),
            "forbidden": list(self.forbidden),
        }


# Default doctrine instance
DEFAULT_DOCTRINE = PhotoTreatmentDoctrine(
    allowed=PHOTO_ALLOWED,
    forbidden=PHOTO_FORBIDDEN,
)


def get_photo_treatment_doctrine() -> PhotoTreatmentDoctrine:
    """Return the current photo treatment doctrine."""
    return DEFAULT_DOCTRINE


def photo_treatment_prompt_block() -> list[str]:
    """Generate the photo treatment prompt block for flyer generation."""
    return DEFAULT_DOCTRINE.full_prompt_block()


def is_operation_allowed(operation: str) -> bool:
    """Check if a photo operation is in the allowed list."""
    op_lower = operation.lower().strip()
    return any(allowed.lower() in op_lower or op_lower in allowed.lower() 
               for allowed in PHOTO_ALLOWED)


def is_operation_forbidden(operation: str) -> bool:
    """Check if a photo operation is in the forbidden list."""
    op_lower = operation.lower().strip()
    return any(forbidden.lower() in op_lower or op_lower in forbidden.lower() 
               for forbidden in PHOTO_FORBIDDEN)


# Two-stage pipeline configuration
TWO_STAGE_PIPELINE_DESCRIPTION = """
TWO-STAGE FLYER GENERATION PIPELINE:

Stage 1 — LAYOUT GENERATION (no photo):
  - Generate: background, typography, boxes, graphic elements
  - Input: Blank cream canvas with photo slot marked
  - Output: Complete flyer design with empty photo area
  - The AI has NO access to band photo pixels

Stage 2 — PHOTO PLACEMENT (PIL only, no AI):
  - Places the photograph into the reserved slot
  - Applies ONLY allowed operations: crop, scale, blend, clipping mask
  - Uses PIL/Pillow exclusively — never sends photo to AI
  - The photo pixels are NEVER seen or modified by the AI model

This separation is much more robust than asking one model to do everything.
The AI cannot hallucinate band members if it never sees the photo.
"""


def two_stage_prompt_preamble() -> list[str]:
    """Prompt preamble explaining the two-stage pipeline to the AI."""
    return [
        "TWO-STAGE PIPELINE ACTIVE — YOU ARE IN STAGE 1 (LAYOUT ONLY):",
        "- You are generating the flyer LAYOUT: background, typography, boxes, graphic elements",
        "- A band photo will be composited into the marked slot AFTER your generation",
        "- Do NOT draw, paint, generate, or imagine any people, faces, band members, or musicians",
        "- Do NOT draw instruments, microphones, guitars, drums, or band equipment",
        "- The photo slot is marked with a faint rectangle — leave it as plain cream paper",
        "- Focus entirely on: venue name, date, time, band name, decorative borders, textures",
        "- Your output will have a real photograph pasted into it by PIL (not you)",
        "",
    ]
