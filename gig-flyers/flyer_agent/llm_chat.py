"""LLM-backed Flyer Agent chat orchestration with rule-based fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from flyer_agent.intent import ChatIntent, parse_chat_intent

_CHAT_ACTIONS = frozenset({"generate", "regenerate", "revise", "approve", "explain", "clarify", "none"})


def _strip_json_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _gig_context_blob(detail: dict[str, Any]) -> str:
    event = detail.get("event") or {}
    flyers = ", ".join(f["option"] for f in (detail.get("flyers") or []))
    return (
        f"Venue: {event.get('venue', '')}\n"
        f"Date: {event.get('short_date', '')} {event.get('time', '')}\n"
        f"Round: {detail.get('round', 0)}\n"
        f"Status: {detail.get('workflow_label', '')}\n"
        f"Options available: {flyers or 'none'}\n"
        f"can_generate={detail.get('can_generate')}\n"
        f"can_revise={detail.get('can_revise')}\n"
        f"can_regenerate={detail.get('can_regenerate')}\n"
    )


def _llm_enabled() -> bool:
    flag = os.getenv("FLYER_AGENT_LLM_CHAT", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _call_llm(message: str, detail: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from openai import OpenAI

        client = OpenAI()
        system = (
            "You are the Flyer Agent for concert poster design. "
            "Return ONLY valid JSON with keys: action, option, feedback, reply.\n"
            "action must be one of: generate, regenerate, revise, approve, explain, clarify, none.\n"
            "option is A, B, or C when relevant, else null.\n"
            "feedback is the user's revision notes when action=revise, else null.\n"
            "reply is a concise friendly message to show the user before acting.\n"
            "For revise: user likes a chosen option and wants variants of THAT option with their feedback "
            "(e.g. 'I like A but pastel' -> action=revise, option=A, feedback='pastel colors').\n"
            "For approve: action=approve, option=A|B|C.\n"
            "Use clarify when option or feedback is missing for a revise request."
        )
        user = f"Gig context:\n{_gig_context_blob(detail)}\n\nUser message:\n{message}"
        response = client.chat.completions.create(
            model=os.getenv("FLYER_AGENT_CHAT_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = _strip_json_fence(response.choices[0].message.content or "")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        action = str(data.get("action") or "none").lower()
        if action not in _CHAT_ACTIONS:
            return None
        option = data.get("option")
        if option:
            option = str(option).upper().strip()[:1]
            if option not in {"A", "B", "C"}:
                option = None
        feedback = data.get("feedback")
        feedback = str(feedback).strip() if feedback else None
        reply = str(data.get("reply") or "").strip()
        return {"action": action, "option": option, "feedback": feedback, "reply": reply}
    except Exception:
        return None


def _intent_from_llm(data: dict[str, Any], *, detail: dict[str, Any]) -> ChatIntent:
    action = data["action"]
    option = data.get("option")
    feedback = data.get("feedback")

    if action == "clarify":
        return ChatIntent("revise_incomplete")
    if action == "revise":
        if option and feedback and detail.get("can_revise"):
            return ChatIntent("revise", option=option, feedback=feedback)
        return ChatIntent("revise_incomplete")
    if action == "generate" and detail.get("can_generate"):
        return ChatIntent("generate")
    if action == "regenerate" and detail.get("can_regenerate"):
        return ChatIntent("regenerate")
    if action == "approve" and detail.get("flyers"):
        if option:
            return ChatIntent("approve", option=option)
        return ChatIntent("approve_incomplete")
    if action == "explain":
        return ChatIntent("explain")
    return ChatIntent("none")


def _reply_from_llm(data: dict[str, Any], *, fallback: str) -> str:
    reply = (data.get("reply") or "").strip()
    return reply or fallback


def resolve_chat_intent(message: str, *, detail: dict[str, Any]) -> tuple[ChatIntent, Optional[str], str]:
    """Return intent, optional LLM reply override, and source label (llm|rules)."""
    text = (message or "").strip()
    if _llm_enabled():
        llm = _call_llm(text, detail)
        if llm:
            intent = _intent_from_llm(llm, detail=detail)
            if intent.kind != "none" or llm.get("action") == "none":
                return intent, _reply_from_llm(llm, fallback=""), "llm"
    intent = parse_chat_intent(text, detail=detail)
    return intent, None, "rules"
