"""LLM-generated revision briefs for fan-out poster variants."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RevisionVariant:
    label: str
    bg: str
    text: str


@dataclass
class RevisionBrief:
    summary: str
    font_scale: float = 1.0
    variants: list[RevisionVariant] = field(default_factory=list)

    def variant_at(self, index: int, count: int = 3) -> Optional[RevisionVariant]:
        if not self.variants:
            return None
        return self.variants[index % len(self.variants)]


def _strip_json_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _default_pastel_variants() -> list[RevisionVariant]:
    return [
        RevisionVariant("blush pastel", "#FADADD", "#7A5C6A"),
        RevisionVariant("sky pastel", "#D4E4F7", "#4A5F7A"),
        RevisionVariant("mint pastel", "#D8F3DC", "#4A6B55"),
    ]


def _parse_brief(data: dict[str, Any], feedback: str) -> RevisionBrief:
    summary = str(data.get("summary") or feedback).strip()[:200]
    font_scale = float(data.get("font_scale") or 1.0)
    font_scale = max(0.7, min(1.5, font_scale))
    variants: list[RevisionVariant] = []
    for item in data.get("variants") or []:
        if not isinstance(item, dict):
            continue
        bg = str(item.get("bg") or "").strip()
        text = str(item.get("text") or "").strip()
        label = str(item.get("label") or "variant").strip()
        if bg.startswith("#") and text.startswith("#"):
            variants.append(RevisionVariant(label=label[:40], bg=bg, text=text))
    if len(variants) < 3 and "pastel" in feedback.lower():
        variants = _default_pastel_variants()
    return RevisionBrief(summary=summary, font_scale=font_scale, variants=variants[:3])


def build_revision_brief(feedback: str, *, base_option: str) -> RevisionBrief:
    """Build a structured revision brief; uses LLM when available."""
    text = (feedback or "").strip()
    if not text:
        return RevisionBrief(summary="", variants=[])

    if os.getenv("OPENAI_API_KEY", "").strip():
        try:
            from openai import OpenAI

            client = OpenAI()
            prompt = (
                f"The user likes option {base_option.upper()} and wants a revision round with this feedback:\n"
                f"\"{text}\"\n\n"
                "Return JSON with:\n"
                "- summary: one sentence design direction\n"
                "- font_scale: number 0.85-1.35 (1.0 = unchanged; >1 = larger type)\n"
                "- variants: array of exactly 3 objects, each with label, bg (hex), text (hex), "
                "giving distinct but related interpretations of the feedback for slots A/B/C.\n"
                "Example for pastel: blush, sky, mint palettes."
            )
            response = client.chat.completions.create(
                model=os.getenv("FLYER_AGENT_REVISION_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            raw = _strip_json_fence(response.choices[0].message.content or "")
            data = json.loads(raw)
            if isinstance(data, dict):
                brief = _parse_brief(data, text)
                if brief.variants:
                    return brief
        except Exception:
            pass

    # Keyword fallback
    lower = text.lower()
    variants = _default_pastel_variants() if "pastel" in lower else []
    scale = 1.28 if re.search(r"larger|bigger", lower) else 1.0
    return RevisionBrief(summary=text, font_scale=scale, variants=variants)
