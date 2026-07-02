"""Resolve gig metadata from state, calendar, or on-disk manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from gig_calendar import GigEvent, event_from_dict, find_gig_by_id, is_test_mode, _events_from_mock
from state import get_gig_state

from output_paths import get_output_dir

OUTPUT_DIR = get_output_dir()

_PLACEHOLDER_IDS = frozenset({"gig_id", "your-gig-id", "undefined", "null", "none"})


def is_placeholder_gig_id(gig_id: str) -> bool:
    gid = (gig_id or "").strip()
    if not gid:
        return True
    if gid.startswith("{") and gid.endswith("}"):
        return True
    return gid.lower() in _PLACEHOLDER_IDS


def _gig_output_dir(gig_id: str) -> Optional[Path]:
    direct = OUTPUT_DIR / gig_id
    if direct.is_dir():
        return direct
    if not OUTPUT_DIR.exists():
        return None
    date_prefix = gig_id.split("_", 1)[0]
    for path in OUTPUT_DIR.iterdir():
        if path.is_dir() and path.name.startswith(date_prefix):
            return path
    return None


def _event_from_manifest_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data.get("event") or {})


def load_event_dict(gig_id: str) -> Optional[dict[str, Any]]:
    """Best-effort event metadata without raising."""
    record = get_gig_state(gig_id) or {}
    if record.get("event"):
        return dict(record["event"])

    gig_dir = _gig_output_dir(gig_id)
    if gig_dir:
        for pattern in ("manifest_r*.json", "prototype/*/manifest.json"):
            manifests = sorted(gig_dir.glob(pattern))
            for manifest in reversed(manifests):
                event = _event_from_manifest_file(manifest)
                if event.get("venue"):
                    return event

    found = find_gig_by_id(gig_id)
    if found:
        return found.to_dict()

    if is_test_mode():
        for event in _events_from_mock():
            if event.gig_id == gig_id:
                return event.to_dict()

    return None


def resolve_gig_event(gig_id: str) -> GigEvent:
    """Resolve gig metadata from state, manifests, calendar, or mock data."""
    if is_placeholder_gig_id(gig_id):
        raise ValueError(
            "Invalid gig link — open Prototype mode from a gig review page "
            "(Pick a gig → Review), not a template URL like /prototype/{gig_id}"
        )

    event_dict = load_event_dict(gig_id)
    if event_dict:
        return event_from_dict(event_dict, gig_id=gig_id)

    raise ValueError(f"Gig not found: {gig_id}. Generate flyers or pick the gig from the calendar first.")
