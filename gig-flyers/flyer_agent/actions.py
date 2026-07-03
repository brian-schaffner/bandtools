"""Agent actions — thin wrappers over existing generation pipeline."""

from __future__ import annotations

from typing import Any, Optional

from flyer_generator import generate_for_gig
from gig_calendar import find_gig_by_id
from state import begin_regenerate_round, can_regenerate, get_gig_state, is_approved, upsert_gig


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
    tag_generation_source(gig_id, "agent")
    return generate_for_gig(
        gig_id,
        count=3,
        feedback=feedback,
        base_option=option.upper(),
        on_progress=on_progress,
        generation_source="agent",
    )
