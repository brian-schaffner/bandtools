"""Parse natural-language Flyer Agent chat into executable intents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

REVISE_WORDS = (
    "revise", "change", "fix", "tweak", "adjust", "update", "feedback", "modify", "like", "love", "prefer",
)
GENERATE_WORDS = ("generate", "create", "make posters", "make flyer", "make options")
REGENERATE_WORDS = ("regenerate", "fresh round", "start over", "redo", "from scratch")

_DASH_CHARS = r"\-–—"  # hyphen, en dash, em dash

_OPTION_MARKER = re.compile(
    r"(?:"
    rf"option\s*([abc])\b"
    rf"|revise\s+([abc])\b"
    rf"|^([abc])\s*[:{_DASH_CHARS}]"
    rf"|\b([abc])\s*[:{_DASH_CHARS}]"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChatIntent:
    kind: str  # none | revise | revise_incomplete | generate | regenerate | explain | approve | approve_incomplete
    option: Optional[str] = None
    feedback: Optional[str] = None


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(word in lower for word in words)


def _extract_option_and_feedback(text: str) -> tuple[Optional[str], Optional[str]]:
    match = _OPTION_MARKER.search(text)
    if not match:
        return None, None

    option = next(g.upper() for g in match.groups() if g)
    tail = text[match.end() :].strip()
    tail = re.sub(rf"^[\s:{_DASH_CHARS}]+", "", tail).strip()
    tail = re.sub(r"^(but|and)\s+", "", tail, flags=re.I).strip()
    if not tail:
        # Feedback may precede option in rare phrasing; use full message minus option token.
        head = text[: match.start()].strip()
        head = re.sub(r"^(revise|change|fix|tweak|adjust|update|modify)\s+", "", head, flags=re.I)
        tail = head.strip()
    feedback = tail or None
    return option, feedback


def parse_chat_intent(message: str, *, detail: dict[str, Any]) -> ChatIntent:
    """Return the primary executable or informational intent for a chat message."""
    text = (message or "").strip()
    if not text:
        return ChatIntent("none")

    lower = text.lower()

    if _contains_any(lower, REGENERATE_WORDS):
        if detail.get("can_regenerate"):
            return ChatIntent("regenerate")
        if detail.get("can_generate"):
            return ChatIntent("generate")
        return ChatIntent("none")

    option, feedback = _extract_option_and_feedback(text)
    has_revise_signal = _contains_any(lower, REVISE_WORDS) or bool(option and feedback)

    if has_revise_signal or (option and feedback):
        if option and feedback and detail.get("can_revise"):
            return ChatIntent("revise", option=option, feedback=feedback)
        if _contains_any(lower, REVISE_WORDS) or option:
            return ChatIntent("revise_incomplete")
        return ChatIntent("none")

    if _contains_any(lower, GENERATE_WORDS):
        if detail.get("can_generate"):
            return ChatIntent("generate")
        if detail.get("can_regenerate"):
            return ChatIntent("regenerate")
        return ChatIntent("none")

    if _contains_any(lower, ("approve", "pick", "choose")):
        opt_match = re.search(r"\boption\s*([abc])\b", lower) or re.search(
            r"\b(?:approve|pick|choose)\s+([abc])\b", lower
        )
        option = opt_match.group(1).upper() if opt_match else None
        if detail.get("flyers"):
            if option:
                return ChatIntent("approve", option=option)
            return ChatIntent("approve_incomplete")
        return ChatIntent("none")

    if _contains_any(lower, ("venue", "research", "style", "design", "explain", "why", "how")):
        return ChatIntent("explain")

    return ChatIntent("none")
