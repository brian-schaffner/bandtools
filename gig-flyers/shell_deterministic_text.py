"""Deterministic PIL text placement for shell pass 2 — no OpenAI for layout."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from shell_references import PLACEHOLDER_LABELS, ShellReference
from shell_render_registry import get_render_spec
from shell_render_spec import frac_boxes_to_pixels
from shell_text_slots import placeholder_values


def _load_font(size: int, *, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    if not bold:
        names = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        )
    for path in names:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    *,
    bold: bool = True,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    x1, y1, x2, y2 = box
    max_w, max_h = x2 - x1, y2 - y1
    for size in range(min(max_h - 4, 72), 8, -2):
        font = _load_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= max_w and th <= max_h:
            return font
    return _load_font(10, bold=bold)


def _ink_for_zone(shell: ShellReference, box: tuple[int, int, int, int], canvas: Image.Image) -> tuple[int, int, int]:
    x1, y1, x2, y2 = box
    sample = canvas.crop((x1, y1, x2, min(y2, y1 + max(8, (y2 - y1) // 2))))
    px = list(sample.convert("RGB").resize((1, 1), Image.Resampling.LANCZOS).getdata())
    r, g, b = px[0]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum > 140:
        return (20, 20, 20)
    return (245, 235, 210)


def apply_deterministic_text(
    canvas_path: Path,
    shell: ShellReference,
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
    labels: tuple[str, ...] | None = None,
) -> None:
    """Paint gig facts into editable regions using shell registry geometry."""
    spec = get_render_spec(shell)
    values = placeholder_values(band=band, venue=venue, date=date, time=time)
    target_labels = labels or tuple(
        label for label in PLACEHOLDER_LABELS if label not in spec.openai_text_slots()
    )
    if not target_labels:
        return

    canvas = Image.open(canvas_path).convert("RGB")
    w, h = canvas.size
    zones = frac_boxes_to_pixels((w, h), spec.editable_regions)
    draw = ImageDraw.Draw(canvas)

    for label, zone in zip(PLACEHOLDER_LABELS, zones):
        if label not in target_labels:
            continue
        value = values.get(label, "").strip()
        if not value:
            continue
        ink = _ink_for_zone(shell, zone, canvas)
        bold = label == "HEADLINER"
        font = _fit_font(draw, value, zone, bold=bold)
        bbox = draw.textbbox((0, 0), value, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x1, y1, x2, y2 = zone
        x = x1 + max(0, (x2 - x1 - tw) // 2)
        y = y1 + max(0, (y2 - y1 - th) // 2)
        draw.text((x, y), value, fill=ink, font=font)

    canvas.save(canvas_path, format="PNG")
