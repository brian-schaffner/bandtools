"""PicTex flexbox renderer (legacy symmetric handbills).

Option B asymmetric paste-up handbills are rendered via structured_renderer (PIL).
This module remains for optional symmetric PicTex experiments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from gig_calendar import GigEvent
from text_validation import featured_act_line, is_house_series_gig, resolve_venue_address
from progress_helper import ProgressCallback, emit_progress

CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 1536
PAPER_COLOR = "#F5F0E6"


def pictex_available() -> bool:
    try:
        import pictex  # noqa: F401

        return True
    except ImportError:
        return False


def _build_handbill_tree(
    *,
    venue: str,
    featuring: str,
    date: str,
    time: str,
    address: str,
    photo_path: Path,
):
    from pictex import Canvas, Column, Text, Image

    photo = Image(str(photo_path)).max_width("90%")

    date_time = f"{date} | {time}" if time else date

    children = [
        Text(venue.upper())
        .font_size(56)
        .font_weight(900)
        .color("#111111")
        .text_align("center"),
        Text(featuring)
        .font_size(38)
        .font_weight(700)
        .color("#111111")
        .text_align("center"),
        photo,
    ]
    if time:
        children.extend([
            Text(date)
            .font_size(34)
            .font_weight(700)
            .color("#111111")
            .text_align("center"),
            Text(time)
            .font_size(30)
            .font_weight(600)
            .color("#111111")
            .text_align("center"),
        ])
    else:
        children.append(
            Text(date_time)
            .font_size(34)
            .font_weight(700)
            .color("#111111")
            .text_align("center")
        )
    children.append(
        Text(address)
        .font_size(20)
        .font_weight(400)
        .color("#222222")
        .text_align("center")
    )

    return (
        Column(*children)
        .gap(14)
        .align_items("center")
        .padding(48)
        .width(CANVAS_WIDTH)
    )


def render_handbill_flyer(
    event: GigEvent,
    photo_path: Path,
    output_path: Path,
    *,
    band: str = "",
    on_progress: Optional[ProgressCallback] = None,
    option: str = "B",
) -> None:
    """Render a Tuesday Jam / house-gig handbill via PicTex flex layout."""
    if not pictex_available():
        raise RuntimeError("PicTex is not installed — pip install pictex or use structured renderer")

    from pictex import Canvas

    band_name = band or os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    venue = event.venue
    featuring = featured_act_line(band_name) if is_house_series_gig(event) else band_name
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or ""
    address = resolve_venue_address(event)

    emit_progress(
        on_progress,
        step="render",
        substep="pictex",
        message=f"Rendering PicTex handbill for option {option}...",
        option=option,
    )

    tree = _build_handbill_tree(
        venue=venue,
        featuring=featuring,
        date=date_str,
        time=time_str,
        address=address,
        photo_path=photo_path,
    )

    canvas = (
        Canvas()
        .size(CANVAS_WIDTH, CANVAS_HEIGHT)
        .background_color(PAPER_COLOR)
    )
    image = canvas.render(tree)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path))

    emit_progress(
        on_progress,
        step="render",
        substep="saved",
        message=f"Saved PicTex handbill: {output_path.name}",
        option=option,
    )
