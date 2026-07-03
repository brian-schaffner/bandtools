"""Periodic background design research for the flyer agent."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
RESEARCH_CACHE_PATH = ROOT / "cache" / "design_research.json"
_research_lock = threading.Lock()

DEFAULT_FINDINGS: list[dict[str, Any]] = [
    {
        "id": "halftone-duotone-revival",
        "topic": "Halftone duotone revival",
        "summary": "Printed-poster treatments (threshold, duotone, distress) read authentic for regional club gigs.",
        "tags": ["print", "texture", "vintage"],
        "source": "shell pipeline / style doctrine",
    },
    {
        "id": "cream-paper-typography",
        "topic": "Cream paper + bold condensed type",
        "summary": "Reserve cream areas for headline hierarchy; never place decorative frames around band photos.",
        "tags": ["typography", "layout", "handbill"],
        "source": "style.yaml anti-patterns",
    },
    {
        "id": "venue-aware-palette",
        "topic": "Venue-aware palette shifts",
        "summary": "Outdoor/festival gigs favor warmer sun-faded tones; legion halls and clubs favor mustard/black/cream.",
        "tags": ["color", "venue", "research"],
        "source": "gig_research.py venue rules",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_research() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "findings": list(DEFAULT_FINDINGS),
    }


def _read_research_file() -> dict[str, Any]:
    if not RESEARCH_CACHE_PATH.exists():
        return _empty_research()
    try:
        data = json.loads(RESEARCH_CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_research()
    if not isinstance(data.get("findings"), list):
        data["findings"] = list(DEFAULT_FINDINGS)
    return data


def load_design_research(*, limit: int = 20) -> list[dict[str, Any]]:
    return list(_read_research_file().get("findings") or [])[:limit]


def save_design_research(findings: list[dict[str, Any]]) -> dict[str, Any]:
    with _research_lock:
        payload = {"version": 1, "updated_at": _now_iso(), "findings": findings}
        RESEARCH_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESEARCH_CACHE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload


def run_design_research(*, use_llm: bool = False) -> dict[str, Any]:
    """Refresh design research findings from style doctrine + optional LLM."""
    from flyer_generator import load_style
    from gig_calendar import get_future_gigs
    from gig_research import research_gig

    style = load_style()
    findings = list(_read_research_file().get("findings") or [])

    # Venue sampling from upcoming gigs
    venue_notes: list[dict[str, Any]] = []
    for event in get_future_gigs(min_days=0, max_days=45)[:5]:
        research = research_gig(event)
        venue_notes.append(
            {
                "id": f"venue-{event.gig_id}",
                "topic": f"Venue context — {event.venue}",
                "summary": "; ".join(
                    filter(
                        None,
                        [
                            str(research.get("design_language", "")),
                            ", ".join((research.get("design_notes") or [])[:2]),
                        ],
                    )
                )[:400],
                "tags": ["venue", str(research.get("venue_type", "regional"))],
                "source": "gig_research scan",
                "gig_id": event.gig_id,
                "researched_at": _now_iso(),
            }
        )

    # Style doctrine refresh
    anti = style.get("anti_patterns") or []
    if anti:
        findings.insert(
            0,
            {
                "id": f"doctrine-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                "topic": "Style doctrine refresh",
                "summary": "Avoid: " + "; ".join(str(a) for a in anti[:5]),
                "tags": ["doctrine", "anti-patterns"],
                "source": "style.yaml",
                "researched_at": _now_iso(),
            },
        )

    # Merge venue notes (dedupe by id)
    seen = {f.get("id") for f in findings}
    for note in venue_notes:
        if note["id"] not in seen:
            findings.insert(0, note)
            seen.add(note["id"])

    if use_llm and os.getenv("OPENAI_API_KEY"):
        llm_finding = _llm_design_research(style)
        if llm_finding:
            findings.insert(0, llm_finding)

    findings = findings[:40]
    payload = save_design_research(findings)
    return {"added": len(venue_notes), "total": len(findings), "updated_at": payload["updated_at"]}


def _llm_design_research(style: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from openai import OpenAI

        client = OpenAI()
        models = style.get("reference_models") or []
        prompt = (
            "You are a concert poster design researcher. Given these reference models: "
            f"{models[:4]}. Suggest ONE fresh design idea for a regional cover-band gig flyer "
            "in 2 sentences. Focus on layout, typography, and print texture — no band names."
        )
        response = client.chat.completions.create(
            model=os.getenv("GIG_RESEARCH_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return None
        return {
            "id": f"llm-{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
            "topic": "LLM design scan",
            "summary": text,
            "tags": ["llm", "trend"],
            "source": "openai research worker",
            "researched_at": _now_iso(),
        }
    except Exception:
        return None
