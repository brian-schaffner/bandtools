"""Flyer Agent chat — intent parsing and assistant replies (LLM-ready hook)."""

from __future__ import annotations

import os
from typing import Any, Optional

from flyer_agent.agent import FlyerAgent
from flyer_agent.intent import ChatIntent, parse_chat_intent


def _research_blurb(research: Optional[dict[str, Any]]) -> str:
    if not research:
        return ""
    parts = [
        str(research.get("design_language") or "").strip(),
        ", ".join((research.get("design_notes") or [])[:2]),
    ]
    text = " · ".join(p for p in parts if p)
    return text[:240]


def _uses_structured_layout() -> bool:
    disabled = os.getenv("STRUCTURED_LAYOUT_DISABLED", "").strip().lower() in {"1", "true", "yes"}
    if disabled:
        return False
    options = os.getenv("STRUCTURED_LAYOUT_OPTIONS", "A,B,C").upper()
    return bool(options.strip())


def _revise_explanation(*, option: str, feedback: str, current_round: int) -> str:
    next_round = max(current_round, 0) + 1
    layout_note = (
        " Layout revisions adjust typography, color, and template composition within the structured poster engine."
        if _uses_structured_layout()
        else " Revisions use the image generation pipeline with your feedback applied to the chosen option."
    )
    return (
        f"Got it — revising from Option {option.upper()} with your feedback:\n"
        f"“{feedback}”\n\n"
        f"This creates a new round (r{next_round}) of all three posters (A/B/C). "
        f"Option {option.upper()} will reflect your notes; B and C get fresh variations."
        f"{layout_note}\n\n"
        "Working on it now — I’ll update the posters when the round is ready."
    )


def _generate_explanation(*, venue: str) -> str:
    return (
        f"Generating three A/B/C poster options for {venue}. "
        "This usually takes a minute or two — I’ll refresh the poster panel when they’re ready."
    )


def _regenerate_explanation(*, venue: str, current_round: int) -> str:
    next_round = max(current_round, 0) + 1
    return (
        f"Starting a completely fresh round (r{next_round}) for {venue} — "
        "three new options from scratch, replacing the current set."
    )


def _build_execution(intent: ChatIntent, *, detail: dict[str, Any]) -> Optional[dict[str, Any]]:
    if intent.kind == "revise" and intent.option and intent.feedback:
        return {
            "type": "revise",
            "option": intent.option.upper(),
            "feedback": intent.feedback,
            "current_round": int(detail.get("round") or 0),
        }
    if intent.kind == "generate":
        return {"type": "generate", "current_round": int(detail.get("round") or 0)}
    if intent.kind == "regenerate":
        return {"type": "regenerate", "current_round": int(detail.get("round") or 0)}
    return None


def agent_chat_reply(
    message: str,
    *,
    gig_id: Optional[str] = None,
    agent: Optional[FlyerAgent] = None,
) -> dict[str, Any]:
    """Return assistant reply, optional execution spec, and suggested actions."""
    agent = agent or FlyerAgent()
    text = (message or "").strip()

    if not gig_id:
        return {
            "reply": (
                "Select an upcoming gig from the left sidebar. "
                "I can generate posters, revise options, or explain venue-aware design choices."
            ),
            "actions": [],
            "execution": None,
            "job": None,
        }

    detail = agent.gig_detail(gig_id)
    if not detail:
        return {
            "reply": "I couldn't find that gig. Pick another from the sidebar.",
            "actions": [],
            "execution": None,
            "job": None,
        }

    rec = agent.recommend_action(gig_id)
    event = detail.get("event") or {}
    venue = event.get("venue") or gig_id
    research_note = _research_blurb(detail.get("research"))
    actions: list[dict[str, str]] = []
    current_round = int(detail.get("round") or 0)

    if detail.get("can_generate"):
        actions.append({"id": "generate", "label": "Generate 3 options", "kind": "generate"})
    if detail.get("can_regenerate"):
        actions.append({"id": "regenerate", "label": "Regenerate fresh round", "kind": "regenerate"})
    if detail.get("can_revise"):
        actions.append({"id": "revise", "label": "Revise an option", "kind": "revise_hint"})
    if detail.get("flyers"):
        actions.append({"id": "review", "label": "Open full review", "kind": "review"})

    intent = parse_chat_intent(text, detail=detail)
    execution = _build_execution(intent, detail=detail)

    if intent.kind == "revise" and execution:
        return {
            "reply": _revise_explanation(
                option=execution["option"],
                feedback=execution["feedback"],
                current_round=current_round,
            ),
            "actions": actions,
            "execution": execution,
            "job": None,
        }

    if intent.kind == "generate" and execution:
        return {
            "reply": _generate_explanation(venue=venue),
            "actions": actions,
            "execution": execution,
            "job": None,
        }

    if intent.kind == "regenerate" and execution:
        return {
            "reply": _regenerate_explanation(venue=venue, current_round=current_round),
            "actions": actions,
            "execution": execution,
            "job": None,
        }

    if intent.kind == "revise_incomplete":
        if detail.get("can_revise"):
            opts = ", ".join(f["option"] for f in (detail.get("flyers") or []))
            return {
                "reply": (
                    f"Tell me which option ({opts}) to revise and what to change — "
                    "e.g. “Revise option B: larger headline, warmer mustard background.”"
                ),
                "actions": actions,
                "execution": None,
                "job": None,
            }
        return {
            "reply": rec.get("message", "Generate flyers first, then we can revise."),
            "actions": actions,
            "execution": None,
            "job": None,
        }

    if intent.kind == "explain":
        blurb = research_note or "Standard regional promoter handbill language applies."
        return {
            "reply": (
                f"For {venue}: {blurb}. "
                f"Current status: {detail.get('workflow_label', 'unknown')}. {rec.get('message', '')}"
            ),
            "actions": actions,
            "execution": None,
            "job": None,
        }

    if intent.kind == "approve":
        if detail.get("flyers"):
            return {
                "reply": (
                    "Review the options in the center panel. "
                    "When you're ready to approve one, open the full review UI to pick A, B, or C."
                ),
                "actions": actions,
                "execution": None,
                "job": None,
            }

    # Default contextual status
    flyer_count = len(detail.get("flyers") or [])
    intro = f"{venue} — {event.get('short_date', '')} at {event.get('time', 'TBA')}."
    status = f"Status: {detail.get('workflow_label', 'unknown')}"
    posters = f"{flyer_count} poster option(s) ready for review." if flyer_count else "No posters yet."
    research = f" Design context: {research_note}." if research_note else ""
    hint = ""
    if detail.get("can_revise"):
        hint = " Say “Revise option A: …” to start a revision."
    elif detail.get("can_generate"):
        hint = " Say “generate” to create three options."
    return {
        "reply": f"{intro} {status}. {posters}{research} {rec.get('message', '')}{hint}".strip(),
        "actions": actions,
        "execution": None,
        "job": None,
    }
