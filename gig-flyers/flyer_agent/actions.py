"""Agent actions — thin wrappers over existing generation pipeline."""

from __future__ import annotations

from typing import Any, Optional

from flyer_generator import generate_for_gig
from gig_calendar import find_gig_by_id
from output_paths import resolve_output_path
from state import (
    append_feedback,
    begin_regenerate_round,
    can_regenerate,
    get_gig_state,
    is_approved,
    mark_approved,
    upsert_gig,
)
from flyer_agent.revision_brief import build_revision_brief


def tag_generation_source(gig_id: str, source: str) -> None:
    upsert_gig(gig_id, generation_source=source)


def prepare_gig_for_generation(gig_id: str, *, source: str = "agent") -> dict[str, Any]:
    event = find_gig_by_id(gig_id)
    if not event:
        raise ValueError(f"Unknown gig: {gig_id}")
    upsert_gig(gig_id, event=event.to_dict(), generation_source=source)
    return event.to_dict()


def agent_generate(
    gig_id: str,
    *,
    count: int = 3,
    on_progress: Optional[Any] = None,
) -> dict[str, Any]:
    prepare_gig_for_generation(gig_id, source="agent")
    manifest = generate_for_gig(gig_id, count=count, on_progress=on_progress, generation_source="agent")
    tag_generation_source(gig_id, "agent")
    return manifest


def agent_regenerate(
    gig_id: str,
    *,
    on_progress: Optional[Any] = None,
) -> dict[str, Any]:
    if not can_regenerate(gig_id):
        raise ValueError("No existing generation to regenerate")
    record = get_gig_state(gig_id) or {}
    if record.get("status") == "approved":
        begin_regenerate_round(gig_id)
    tag_generation_source(gig_id, "agent")
    return generate_for_gig(
        gig_id,
        count=3,
        fresh_start=True,
        on_progress=on_progress,
        generation_source="agent",
    )


def agent_revise(
    gig_id: str,
    *,
    option: str,
    feedback: str,
    on_progress: Optional[Any] = None,
) -> dict[str, Any]:
    if is_approved(gig_id):
        raise ValueError("Cannot revise an approved gig")
    brief = build_revision_brief(feedback, base_option=option)
    tag_generation_source(gig_id, "agent")
    upsert_gig(gig_id, last_revision_brief=brief.summary)
    return generate_for_gig(
        gig_id,
        count=3,
        feedback=feedback,
        base_option=option.upper(),
        on_progress=on_progress,
        generation_source="agent",
        revision_brief=brief,
    )


def agent_approve(gig_id: str, *, option: str) -> dict[str, Any]:
    record = get_gig_state(gig_id) or {}
    if not record:
        raise ValueError(f"Unknown gig: {gig_id}")
    if is_approved(gig_id):
        raise ValueError("Gig already approved")
    letter = option.upper()
    rel = (record.get("options") or {}).get(letter)
    if not rel:
        raise ValueError(f"Option {letter} not found")
    source = resolve_output_path(rel)
    if not source.is_file():
        raise ValueError(f"Missing image for option {letter}")
    append_feedback(gig_id, "approve", letter, "", f"APPROVE {letter} (Flyer Agent)")
    dest = mark_approved(gig_id, letter, source)
    return {"status": "approved", "option": letter, "path": str(dest)}
