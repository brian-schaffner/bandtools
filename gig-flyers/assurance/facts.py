"""Gig-fact validation on rendered flyers (wild + structured)."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from config.profiles import assurance_fact_gate_enabled
from gig_calendar import GigEvent
from text_validation import validate_required_footer_text


def _encode_image_b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")


def extract_visible_text(path: Path) -> str:
    """OCR-like extraction via vision mini; returns empty string on failure."""
    if not path.is_file() or path.stat().st_size < 512:
        return ""
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return ""
    try:
        from openai import OpenAI

        client = OpenAI()
        model = os.getenv("ASSURANCE_FACT_MODEL", os.getenv("AI_REVIEWER_MODEL", "gpt-4o-mini"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "List ALL visible text on this concert flyer, one line per text element. "
                                "Preserve spelling exactly as shown. No commentary."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{_encode_image_b64(path)}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=400,
            temperature=0,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


def validate_gig_facts_in_text(text: str, event: GigEvent, *, band: str) -> list[str]:
    issues = list(validate_required_footer_text(text, event, band=band))
    lower = text.lower()
    band_lower = band.lower()
    if band_lower and band_lower not in lower:
        issues.append(f"Band name not found in visible text: {band}")
    time_label = (event.time_label or "").strip()
    if time_label and time_label.lower() not in {"tba", "tbd"}:
        digits = re.sub(r"\D", "", time_label)
        if digits and digits not in re.sub(r"\D", "", text):
            issues.append(f"Show time may be missing or wrong (expected {time_label})")
    return issues


def validate_gig_facts_on_image(
    path: Path,
    event: GigEvent,
    *,
    band: str,
    extracted_text: str | None = None,
) -> dict[str, Any]:
    """Run fact gate; returns {passed, issues, extracted_text}."""
    if not assurance_fact_gate_enabled():
        return {"passed": True, "issues": [], "extracted_text": extracted_text or ""}

    text = (extracted_text or "").strip() or extract_visible_text(path)
    issues = validate_gig_facts_in_text(text, event, band=band) if text else [
        "Could not extract visible text for fact validation"
    ]
    return {
        "passed": not issues,
        "issues": issues,
        "extracted_text": text,
    }
