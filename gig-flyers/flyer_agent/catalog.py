"""Curated catalog of strong flyer designs for agent inspiration."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "data" / "good_designs.json"
_catalog_lock = threading.Lock()

DEFAULT_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "classic-handbill-mustard",
        "title": "Classic mustard handbill",
        "tags": ["handbill", "mustard", "typography", "regional"],
        "notes": "Bold condensed headline, cream paper, single band photo block, venue/date footer.",
        "source": "style.yaml reference_models",
    },
    {
        "id": "paste-up-collage",
        "title": "Paste-up collage (Option C)",
        "tags": ["collage", "creative", "layered", "mixed-media"],
        "notes": "Cut-paper layers, torn edges, high contrast accents — band photo in hero lockup.",
        "source": "graphic_composer archetypes",
    },
    {
        "id": "arena-photo-dominant",
        "title": "Arena photo-dominant shell",
        "tags": ["shell", "hero-photo", "duotone", "large-type"],
        "notes": "Full-bleed band photo with printed-poster treatment; minimal cream text bands.",
        "source": "shell_references / arena_photo_dominant",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_catalog() -> dict[str, Any]:
    return {"version": 1, "updated_at": _now_iso(), "entries": list(DEFAULT_ENTRIES)}


def _read_catalog_file() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return _empty_catalog()
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_catalog()
    if not isinstance(data.get("entries"), list):
        data["entries"] = list(DEFAULT_ENTRIES)
    return data


def load_design_catalog(*, limit: int = 50, tag: Optional[str] = None) -> list[dict[str, Any]]:
    data = _read_catalog_file()
    entries = list(data.get("entries") or [])
    if tag:
        needle = tag.strip().lower()
        entries = [e for e in entries if needle in [t.lower() for t in (e.get("tags") or [])]]
    return entries[:limit]


def save_design_catalog(entries: list[dict[str, Any]]) -> dict[str, Any]:
    with _catalog_lock:
        payload = {"version": 1, "updated_at": _now_iso(), "entries": entries}
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload


def add_catalog_entry(
    *,
    title: str,
    tags: list[str],
    notes: str,
    image_path: Optional[str] = None,
    source: str = "manual",
) -> dict[str, Any]:
    data = _read_catalog_file()
    entries = list(data.get("entries") or [])
    entry_id = title.lower().replace(" ", "-")[:48]
    entries.insert(
        0,
        {
            "id": entry_id,
            "title": title,
            "tags": tags,
            "notes": notes,
            "image_path": image_path,
            "source": source,
            "added_at": _now_iso(),
        },
    )
    save_design_catalog(entries)
    return entries[0]


def sync_approved_flyers_to_catalog(limit: int = 20) -> int:
    """Import recently approved flyers into the catalog (idempotent by path)."""
    from state import load_state

    state = load_state()
    existing_paths = {
        str(e.get("image_path"))
        for e in load_design_catalog(limit=1000)
        if e.get("image_path")
    }
    added = 0
    entries = list(_read_catalog_file().get("entries") or [])

    for gig_id, record in (state.get("gigs") or {}).items():
        if record.get("status") != "approved":
            continue
        path = record.get("approved_path")
        if not path or path in existing_paths:
            continue
        event = record.get("event") or {}
        title = f"Approved — {event.get('short_date', '')} @ {event.get('venue', gig_id)}"
        entries.insert(
            0,
            {
                "id": f"approved-{gig_id}",
                "title": title.strip(),
                "tags": ["approved", "production", record.get("approved_option", "").lower()],
                "notes": f"Approved option {record.get('approved_option')} for {gig_id}",
                "image_path": path,
                "source": "approved_flyer",
                "added_at": _now_iso(),
            },
        )
        existing_paths.add(path)
        added += 1
        if added >= limit:
            break

    if added:
        save_design_catalog(entries)
    return added
