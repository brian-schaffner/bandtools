#!/usr/bin/env python3
"""Select the best band publicity photo for a gig context."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from gig_calendar import GigEvent, ROOT
from progress_helper import ProgressCallback, emit_progress

DEFAULT_BANDPHOTOS_DIR = ROOT / "bandphotos"
MANIFEST_NAME = "manifest.yaml"

VENUE_PHOTO_SCORES: dict[str, dict[str, int]] = {
    "blues_bar": {"instruments": 10, "group_energetic": 6, "group_standing": 4},
    "country_bar": {"group_energetic": 10, "instruments": 7, "group_standing": 5},
    "member_club": {"group_standing": 10, "instruments": 6, "group_energetic": 5},
    "community_event": {"group_standing": 9, "instruments": 5, "group_energetic": 4},
    "festival": {"group_energetic": 10, "instruments": 8, "group_standing": 6},
    "casino_venue": {"group_standing": 8, "group_energetic": 7, "instruments": 6},
    "winery": {"group_standing": 9, "group_energetic": 6, "instruments": 5},
    "regional_bar": {"instruments": 8, "group_energetic": 7, "group_standing": 6},
    "regional_club": {"instruments": 8, "group_standing": 7, "group_energetic": 6},
}


@dataclass
class BandPhoto:
    id: str
    path: Path
    photo_type: str
    description: str
    filename: str
    member_count: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        rel = str(self.path.relative_to(ROOT))
        out: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "path": rel,
            "type": self.photo_type,
            "description": self.description,
        }
        if self.member_count is not None:
            out["member_count"] = self.member_count
        return out


def bandphotos_dir() -> Path:
    custom = os.getenv("GIG_BANDPHOTOS_DIR", "").strip()
    return Path(custom) if custom else DEFAULT_BANDPHOTOS_DIR


def _load_manifest() -> list[dict[str, Any]]:
    manifest_path = bandphotos_dir() / MANIFEST_NAME
    if manifest_path.is_file():
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        return list(data.get("photos", []))

    # Fallback: scan image files with generic metadata
    photos = []
    for idx, path in enumerate(sorted(bandphotos_dir().glob("*"))):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        photos.append(
            {
                "id": path.stem[:12],
                "filename": path.name,
                "type": "unknown",
                "description": f"Band publicity photo {path.name}",
            }
        )
    return photos


def list_band_photos() -> list[BandPhoto]:
    directory = bandphotos_dir()
    photos: list[BandPhoto] = []
    for row in _load_manifest():
        filename = row.get("filename", "")
        path = directory / filename
        if not path.is_file():
            continue
        photos.append(
            BandPhoto(
                id=str(row.get("id", path.stem)),
                path=path.resolve(),
                photo_type=str(row.get("type", "unknown")),
                description=str(row.get("description", "")).strip(),
                filename=filename,
                member_count=int(row["member_count"]) if row.get("member_count") is not None else None,
            )
        )
    return photos


def _score_photo(photo: BandPhoto, venue_type: str, design_language: str) -> int:
    scores = VENUE_PHOTO_SCORES.get(venue_type, VENUE_PHOTO_SCORES["regional_club"])
    score = scores.get(photo.id, scores.get(photo.photo_type, 5))

    text = f"{venue_type} {design_language}".lower()
    if photo.photo_type == "instrument" and any(k in text for k in ("blues", "club", "bar")):
        score += 2
    if photo.photo_type == "group_standing" and any(k in text for k in ("legion", "vfw", "community", "member")):
        score += 2
    if photo.photo_type == "group_energetic" and any(k in text for k in ("fair", "festival", "country", "party")):
        score += 2
    return score


def select_band_photo(
    event: GigEvent,
    research: dict[str, Any],
    on_progress: Optional[ProgressCallback] = None,
) -> Optional[dict[str, Any]]:
    emit_progress(
        on_progress,
        step="photo",
        substep="scan",
        message="Scanning bandphotos…",
        progress=16,
    )
    photos = list_band_photos()
    if not photos:
        emit_progress(
            on_progress,
            step="photo",
            substep="none",
            message="No band photos on file",
            progress=18,
        )
        return None

    venue_type = str(research.get("venue_type", "regional_club"))
    design_language = str(research.get("design_language", ""))
    photo_ids = " vs ".join(p.id for p in photos[:4])
    emit_progress(
        on_progress,
        step="photo",
        substep="scoring",
        message=f"Scoring {photo_ids}…",
        detail=f"Venue type: {venue_type}",
        progress=17,
    )

    ranked = sorted(
        photos,
        key=lambda p: _score_photo(p, venue_type, design_language),
        reverse=True,
    )
    best = ranked[0]
    score = _score_photo(best, venue_type, design_language)
    result = best.to_dict()
    result["score"] = score
    result["reason"] = (
        f"Best match for {venue_type} ({design_language}): "
        f"{best.photo_type} photo scored {score}"
    )
    emit_progress(
        on_progress,
        step="photo",
        substep="selected",
        message=f"Selected: {best.id} ({venue_type} match, score {score})",
        detail=result["reason"],
        progress=18,
    )
    return result


def resolve_band_photo_selection(
    event: GigEvent,
    research: dict[str, Any],
    *,
    photo_id: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> Optional[dict[str, Any]]:
    """Pick a band photo by explicit id or venue-aware auto selection."""
    if photo_id:
        for photo in list_band_photos():
            if photo.id == photo_id.strip():
                result = photo.to_dict()
                result["reason"] = f"User-selected band photo: {photo.id}"
                emit_progress(
                    on_progress,
                    step="photo",
                    substep="selected",
                    message=f"Using band photo: {photo.id}",
                    progress=18,
                )
                return result
    return select_band_photo(event, research, on_progress=on_progress)


def photo_prompt_block(selected: Optional[dict[str, Any]]) -> list[str]:
    if not selected:
        return [
            "BAND PHOTO:",
            "- No band publicity photo on file; use a believable generic band-instruments photo style.",
            "",
        ]
    member_count = selected.get("member_count")
    member_rule = (
        f"- ALL {member_count} band members from the reference MUST remain fully visible on the flyer."
        if member_count
        else "- ALL band members from the reference MUST remain fully visible on the flyer."
    )
    return [
        "BAND PHOTO FIDELITY (MANDATORY — highest priority after event text):",
        f"- Input/reference band photo: {selected.get('description', '')}",
        "- The band photo is pre-composited on the canvas in a mask-protected region — do not alter those pixels.",
        "- Same faces, instruments, poses, and member count as the reference — no redraw or AI restyle.",
        member_rule,
        "- NO warping, stretching, re-posing, AI face changes, beauty-filter smoothing, or munging.",
        "- NO cropping that cuts off faces, bodies, or band members at the frame edge.",
        "- Scale/place as a promoter paste-up publicity still only — do not redraw or reinterpret the photo.",
        "- Color grading or duotone tint for flyer design is OK — composition and people are not.",
        f"- Source file: {selected.get('filename', 'band photo')}",
        "",
        "NEGATIVE (never do these to the band photo):",
        "- Generating a new band photo instead of using the input image",
        "- Partial crop showing fewer members than the reference",
        "- Elongated or squashed faces/bodies",
        "- Replacing band members with different people",
        "- Blurring or melting instrument details",
        "",
    ]
