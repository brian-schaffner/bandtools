"""Flyer Agent chat — rule-based assistant replies (LLM-ready hook)."""

from __future__ import annotations

from typing import Any, Optional

from flyer_agent.agent import FlyerAgent


def _research_blurb(research: Optional[dict[str, Any]]) -> str:
    if not research:
        return ""
    parts = [
        str(research.get("design_language") or "").strip(),
        ", ".join((research.get("design_notes") or [])[:2]),
    ]
    text = " · ".join(p for p in parts if p)
    return text[:240]


def agent_chat_reply(
    message: str,
    *,
    gig_id: Optional[str] = None,
    agent: Optional[FlyerAgent] = None,
) -> dict[str, Any]:
    """Return assistant reply and suggested actions for the chat UI."""
    agent = agent or FlyerAgent()
    text = (message or "").strip()
    lower = text.lower()

    if not gig_id:
        return {
            "reply": (
                "Select an upcoming gig from the left sidebar. "
                "I can help you generate posters, revise options, or explain venue-aware design choices."
            ),
            "actions": [],
        }

    detail = agent.gig_detail(gig_id)
    if not detail:
        return {"reply": "I couldn't find that gig. Pick another from the sidebar.", "actions": []}

    rec = agent.recommend_action(gig_id)
    event = detail.get("event") or {}
    venue = event.get("venue") or gig_id
    research_note = _research_blurb(detail.get("research"))
    actions: list[dict[str, str]] = []

    if detail.get("can_generate"):
        actions.append({"id": "generate", "label": "Generate 3 options", "kind": "generate"})
    if detail.get("can_regenerate"):
        actions.append({"id": "regenerate", "label": "Regenerate fresh round", "kind": "regenerate"})
    if detail.get("can_revise"):
        actions.append({"id": "revise", "label": "Revise an option", "kind": "revise_hint"})
    if detail.get("flyers"):
        actions.append({"id": "review", "label": "Open full review", "kind": "review"})

    if any(word in lower for word in ("generate", "create", "make", "start")):
        if detail.get("can_generate"):
            return {
                "reply": (
                    f"I'll generate three A/B/C poster options for {venue}. "
                    "Use the Generate button above or say which style you prefer — conservative handbill, "
                    "paste-up, or creative collage."
                ),
                "actions": actions,
            }
        if detail.get("can_regenerate"):
            return {
                "reply": (
                    f"This gig already has flyers for {venue}. "
                    "Say regenerate if you want a completely fresh round from scratch."
                ),
                "actions": actions,
            }

    if any(word in lower for word in ("regenerate", "fresh", "start over", "redo")):
        if detail.get("can_regenerate"):
            return {
                "reply": f"Regenerating will replace the current round with three new options for {venue}.",
                "actions": actions,
            }
        return {
            "reply": "There is nothing to regenerate yet — generate a first round first.",
            "actions": actions,
        }

    if any(word in lower for word in ("revise", "change", "fix", "feedback", "tweak")):
        if detail.get("can_revise"):
            opts = ", ".join(f["option"] for f in (detail.get("flyers") or []))
            return {
                "reply": (
                    f"Tell me which option ({opts}) to revise and what to change — "
                    "e.g. “Option B: larger headline, warmer mustard background, no photo frame.” "
                    "I'll apply that as revision feedback."
                ),
                "actions": actions,
            }
        return {"reply": rec.get("message", "Generate flyers first, then we can revise."), "actions": actions}

    if any(word in lower for word in ("venue", "research", "style", "design")):
        blurb = research_note or "Standard regional promoter handbill language applies."
        return {
            "reply": (
                f"For {venue}: {blurb}. "
                f"Current status: {detail.get('workflow_label', 'unknown')}. {rec.get('message', '')}"
            ),
            "actions": actions,
        }

    if any(word in lower for word in ("approve", "pick", "choose")):
        if detail.get("flyers"):
            return {
                "reply": (
                    "Review the options in the center panel. "
                    "When you're ready to approve one, open the full review UI to pick A, B, or C."
                ),
                "actions": actions,
            }

    # Default contextual greeting
    flyer_count = len(detail.get("flyers") or [])
    intro = f"{venue} — {event.get('short_date', '')} at {event.get('time', 'TBA')}."
    status = f"Status: {detail.get('workflow_label', 'new')}"
    posters = f"{flyer_count} poster option(s) ready for review." if flyer_count else "No posters yet."
    research = f" Design context: {research_note}." if research_note else ""
    return {
        "reply": f"{intro} {status}. {posters}{research} {rec.get('message', '')}".strip(),
        "actions": actions,
    }
