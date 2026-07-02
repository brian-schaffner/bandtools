#!/usr/bin/env python3
"""Persistent workflow state for gig flyer generation."""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
APPROVED_DIR = ROOT / "output" / "approved"
_state_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_state() -> dict[str, Any]:
    return {"gigs": {}, "last_poll_rowid": 0}


def _read_state_file() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return _empty_state()
    raw = STATE_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return _empty_state()
    try:
        with STATE_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return _empty_state()


def load_state() -> dict[str, Any]:
    with _state_lock:
        return _read_state_file()


def save_state(state: dict[str, Any]) -> None:
    with _state_lock:
        with STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")


def get_gig_state(gig_id: str) -> Optional[dict[str, Any]]:
    return load_state().get("gigs", {}).get(gig_id)


def upsert_gig(gig_id: str, **fields: Any) -> dict[str, Any]:
    with _state_lock:
        state = _read_state_file()
        gigs = state.setdefault("gigs", {})
        record = gigs.setdefault(
            gig_id,
            {
                "status": "new",
                "round": 0,
                "options": {},
                "feedback_history": [],
                "used_variations": [],
                "updated_at": _now_iso(),
            },
        )
        record.update(fields)
        record["updated_at"] = _now_iso()
        with STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        return record


def mark_pending_review(gig_id: str, options: dict[str, str], prompts: dict[str, str], round_num: int) -> None:
    upsert_gig(
        gig_id,
        status="pending_review",
        round=round_num,
        options=options,
        prompts=prompts,
    )


def append_feedback(gig_id: str, action: str, option: str, feedback: str, raw_text: str) -> None:
    with _state_lock:
        state = _read_state_file()
        record = state.setdefault("gigs", {}).setdefault(gig_id, {})
        history = record.setdefault("feedback_history", [])
        history.append(
            {
                "at": _now_iso(),
                "action": action,
                "option": option,
                "feedback": feedback,
                "raw_text": raw_text,
            }
        )
        record["updated_at"] = _now_iso()
        with STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")


def mark_approved(gig_id: str, option: str, source_path: Path) -> Path:
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    dest = APPROVED_DIR / f"{gig_id}_{option}.png"
    shutil.copy2(source_path, dest)
    upsert_gig(gig_id, status="approved", approved_option=option, approved_path=str(dest))
    return dest


def begin_regenerate_round(gig_id: str) -> dict[str, Any]:
    """Prepare an approved gig for a fresh generation round."""
    record = get_gig_state(gig_id) or {}
    fields: dict[str, Any] = {"status": "regenerating"}
    if record.get("status") == "approved" and record.get("approved_option"):
        history = list(record.get("approval_history", []))
        history.append(
            {
                "at": _now_iso(),
                "round": int(record.get("round") or 0),
                "option": record.get("approved_option"),
                "path": record.get("approved_path"),
            }
        )
        fields["approval_history"] = history
        fields["approved_option"] = None
        fields["approved_path"] = None
    return upsert_gig(gig_id, **fields)


def is_approved(gig_id: str) -> bool:
    record = get_gig_state(gig_id)
    return bool(record and record.get("status") == "approved")


def is_eligible_for_auto_generation(gig_id: str) -> bool:
    """True when a gig has not yet started the flyer workflow."""
    record = get_gig_state(gig_id)
    if not record:
        return True
    status = record.get("status", "new")
    if status == "approved":
        return False
    if status == "pending_review":
        return False
    if record.get("round", 0) > 0 or record.get("options"):
        return False
    return status in {"new", "unknown"}


def has_existing_generation(gig_id: str) -> bool:
    record = get_gig_state(gig_id) or {}
    return bool(record.get("round", 0) > 0 or record.get("options"))


def can_regenerate(gig_id: str) -> bool:
    record = get_gig_state(gig_id) or {}
    if record.get("status") == "approved":
        return True
    return has_existing_generation(gig_id)


def load_design_preferences() -> dict[str, Any]:
    state = load_state()
    return dict(state.get("design_preferences") or {})


def save_design_preferences(preferences: dict[str, Any]) -> None:
    state = load_state()
    state["design_preferences"] = preferences
    save_state(state)


def save_explore_batch(gig_id: str, manifest: dict[str, Any]) -> None:
    record = get_gig_state(gig_id) or {}
    batches = list(record.get("explore_batches") or [])
    batches.append({**manifest, "saved_at": _now_iso()})
    upsert_gig(gig_id, explore_batches=batches[-5:])


def save_explore_rankings(gig_id: str, batch_id: str, rankings: list[dict[str, Any]]) -> dict[str, Any]:
    from preference_model import apply_rankings_to_preferences

    prefs = apply_rankings_to_preferences(load_design_preferences(), rankings)
    save_design_preferences(prefs)
    upsert_gig(
        gig_id,
        explore_rankings={batch_id: {"rankings": rankings, "at": _now_iso()}},
    )
    return prefs


def get_last_poll_rowid() -> int:
    return int(load_state().get("last_poll_rowid", 0))


def set_last_poll_rowid(rowid: int) -> None:
    state = load_state()
    state["last_poll_rowid"] = rowid
    save_state(state)
