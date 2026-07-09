"""Flyer Agent chat — LLM orchestration with rule-based fallback."""

from __future__ import annotations

from typing import Any, Optional

from flyer_agent.agent import FlyerAgent
from flyer_agent.intent import ChatIntent
from flyer_agent.llm_chat import resolve_chat_intent
from option_slots import is_wild_option


def _research_blurb(research: Optional[dict[str, Any]]) -> str:
    if not research:
        return ""
    parts = [
        str(research.get("design_language") or "").strip(),
        ", ".join((research.get("design_notes") or [])[:2]),
    ]
    text = " · ".join(p for p in parts if p)
    return text[:240]


def _revise_explanation(*, option: str, feedback: str, current_round: int, llm_reply: Optional[str]) -> str:
    if llm_reply:
        return llm_reply
    next_round = max(current_round, 0) + 1
    opt = option.upper()
    if is_wild_option(opt):
        return (
            f"Got it — you like Option {opt} (fully designed).\n"
            f"Notes: “{feedback}”\n\n"
            f"Round r{next_round}: three variants that keep your wild D design but "
            f"swap in your real band photo from the reference shoot"
            + (f", plus: {feedback}" if feedback else "")
            + ".\n\n"
            "Working on it now — I’ll update the posters when the round is ready."
        )
    return (
        f"Got it — you like Option {option.upper()} and want to explore:\n"
        f"“{feedback}”\n\n"
        f"This creates a new round (r{next_round}) with three variants of Option {option.upper()} "
        f"— same layout, each applying your notes with a distinct color direction.\n\n"
        "Working on it now — I’ll update the posters when the round is ready."
    )


def _generate_explanation(*, venue: str, llm_reply: Optional[str]) -> str:
    if llm_reply:
        return llm_reply
    return (
        f"Generating three A/B/C poster options for {venue}. "
        "This usually takes a minute or two — I’ll refresh the poster panel when they’re ready."
    )


def _regenerate_explanation(*, venue: str, current_round: int, llm_reply: Optional[str]) -> str:
    if llm_reply:
        return llm_reply
    next_round = max(current_round, 0) + 1
    return (
        f"Starting a completely fresh round (r{next_round}) for {venue} — "
        "three new options from scratch, replacing the current set."
    )


def _approve_explanation(*, option: str, llm_reply: Optional[str]) -> str:
    if llm_reply:
        return llm_reply
    return f"Approving Option {option.upper()} — locking it in as the official flyer for this gig."


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
    if intent.kind == "approve" and intent.option:
        return {"type": "approve", "option": intent.option.upper()}
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
                "I can generate posters, revise options, approve a pick, or explain design choices."
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
    if detail.get("flyers") and detail.get("workflow") != "approved":
        actions.append({"id": "approve", "label": "Approve an option", "kind": "approve_hint"})

    intent, llm_reply, intent_source = resolve_chat_intent(text, detail=detail)
    execution = _build_execution(intent, detail=detail)

    if intent.kind == "revise" and execution:
        return {
            "reply": _revise_explanation(
                option=execution["option"],
                feedback=execution["feedback"],
                current_round=current_round,
                llm_reply=llm_reply,
            ),
            "actions": actions,
            "execution": execution,
            "job": None,
            "intent_source": intent_source,
        }

    if intent.kind == "generate" and execution:
        return {
            "reply": _generate_explanation(venue=venue, llm_reply=llm_reply),
            "actions": actions,
            "execution": execution,
            "job": None,
            "intent_source": intent_source,
        }

    if intent.kind == "regenerate" and execution:
        return {
            "reply": _regenerate_explanation(venue=venue, current_round=current_round, llm_reply=llm_reply),
            "actions": actions,
            "execution": execution,
            "job": None,
            "intent_source": intent_source,
        }

    if intent.kind == "approve" and execution:
        return {
            "reply": _approve_explanation(option=execution["option"], llm_reply=llm_reply),
            "actions": actions,
            "execution": execution,
            "job": None,
            "intent_source": intent_source,
        }

    if intent.kind == "revise_incomplete":
        if detail.get("can_revise"):
            opts = ", ".join(f["option"] for f in (detail.get("flyers") or []))
            return {
                "reply": llm_reply
                or (
                    f"Tell me which option ({opts}) to revise and what to change — "
                    "e.g. “I like option A, but make it pastel.”"
                ),
                "actions": actions,
                "execution": None,
                "job": None,
                "intent_source": intent_source,
            }
        return {
            "reply": rec.get("message", "Generate flyers first, then we can revise."),
            "actions": actions,
            "execution": None,
            "job": None,
            "intent_source": intent_source,
        }

    if intent.kind == "approve_incomplete":
        opts = ", ".join(f["option"] for f in (detail.get("flyers") or []))
        return {
            "reply": llm_reply or f"Which option should I approve — {opts}? Say “approve A”.",
            "actions": actions,
            "execution": None,
            "job": None,
            "intent_source": intent_source,
        }

    if intent.kind == "explain":
        blurb = research_note or "Standard regional promoter handbill language applies."
        return {
            "reply": llm_reply
            or (
                f"For {venue}: {blurb}. "
                f"Current status: {detail.get('workflow_label', 'unknown')}. {rec.get('message', '')}"
            ),
            "actions": actions,
            "execution": None,
            "job": None,
            "intent_source": intent_source,
        }

    flyer_count = len(detail.get("flyers") or [])
    intro = f"{venue} — {event.get('short_date', '')} at {event.get('time', 'TBA')}."
    status = f"Status: {detail.get('workflow_label', 'new')}"
    posters = f"{flyer_count} poster option(s) ready for review." if flyer_count else "No posters yet."
    research = f" Design context: {research_note}." if research_note else ""
    hint = ""
    if detail.get("can_revise"):
        hint = " Say “I like option A, but make it pastel.” to fan out variants."
    elif detail.get("can_generate"):
        hint = " Say “generate” to create three options."
    return {
        "reply": llm_reply or f"{intro} {status}. {posters}{research} {rec.get('message', '')}{hint}".strip(),
        "actions": actions,
        "execution": None,
        "job": None,
        "intent_source": intent_source,
    }
