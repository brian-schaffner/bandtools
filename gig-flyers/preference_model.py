"""Preference weights for design element sampling."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

PREFERENCE_KEYS = ("archetype", "palette", "accent", "family", "medium_variant", "layers")

RANK_DELTA = {1: 6, 2: 2, 3: -4}

NEGATIVE_PREFIXES = (
    "no ",
    "not ",
    "less ",
    "hate ",
    "avoid ",
    "skip ",
    "without ",
    "don't like ",
    "dont like ",
    "too much ",
    "too many ",
)


def _negative_mention(text: str, word: str) -> bool:
    return any(f"{prefix}{word}" in text for prefix in NEGATIVE_PREFIXES)


def _empty_weights() -> dict[str, dict[str, int]]:
    return {key: {} for key in PREFERENCE_KEYS}


def weighted_choice(rng: random.Random, items: list[str], weights_map: dict[str, int]) -> str:
    weights = [max(0.1, float(weights_map.get(item, 0) + 1)) for item in items]
    total = sum(weights)
    pick = rng.random() * total
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if pick <= acc:
            return item
    return items[-1]


def preference_weights(preferences: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    prefs = (preferences or {}).get("global", {})
    return {key: dict(prefs.get(key, {})) for key in PREFERENCE_KEYS}


def copy_weights(weights: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {key: dict(vals) for key, vals in weights.items()}


def apply_feedback_text(
    weights: dict[str, dict[str, int]],
    feedback: str,
    keywords: dict[str, tuple[str, str]],
) -> dict[str, dict[str, int]]:
    """Boost or penalize tag weights when feedback mentions design keywords."""
    text = feedback.lower()
    result = copy_weights(weights)
    keyword_terms = list(keywords.keys())

    for word, (category, value) in keywords.items():
        if word not in text:
            continue
        bucket = result.setdefault(category, {})
        if _negative_mention(text, word):
            bucket[value] = bucket.get(value, 0) - 4
        else:
            bucket[value] = bucket.get(value, 0) + 3

    # Natural-language boosts for archetype names (underscores → spaces).
    for word, (category, value) in keywords.items():
        if category != "archetype":
            continue
        readable = value.replace("_", " ")
        if readable in text and word not in text:
            result[category][value] = result[category].get(value, 0) + 2

    if any(w in text for w in ("boring", "basic", "same", "again", "recycle", "repetitive")):
        result.setdefault("family", {})["C"] = result["family"].get("C", 0) - 2
        wild_bucket = result.setdefault("archetype", {})
        for arch in ("xerox_punk", "duotone_modern", "psychedelic", "neon_bar"):
            wild_bucket[arch] = wild_bucket.get(arch, 0) - 1

    if any(w in text for w in ("wild", "weird", "bold", "experimental", "different", "surprise")):
        for arch in ("psychedelic", "neon_bar", "pasteup_zine", "broadside"):
            result.setdefault("archetype", {})[arch] = result["archetype"].get(arch, 0) + 3

    if "more" in text:
        for term in keyword_terms:
            if f"more {term}" in text:
                category, value = keywords[term]
                result.setdefault(category, {})[value] = result[category].get(value, 0) + 4

    return result


def apply_rankings_to_weights(
    weights: dict[str, dict[str, int]],
    rankings: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    result = copy_weights(weights)
    for item in rankings:
        rank = int(item.get("rank") or 0)
        delta = RANK_DELTA.get(rank, 0)
        if delta == 0:
            continue
        tags = item.get("tags") or {}
        for key in PREFERENCE_KEYS:
            if key == "layers":
                layers = tags.get("layers")
                if layers:
                    result[key][layers] = result[key].get(layers, 0) + delta
                continue
            value = tags.get(key)
            if value:
                result[key][value] = result[key].get(value, 0) + delta
        for liked in item.get("liked_elements") or []:
            if ":" in liked:
                k, v = liked.split(":", 1)
                if k in result and v:
                    result[k][v] = result[k].get(v, 0) + 3
    return result


def apply_rankings_to_preferences(
    preferences: dict[str, Any] | None,
    rankings: list[dict[str, Any]],
) -> dict[str, Any]:
    store: dict[str, Any] = dict(preferences or {})
    global_prefs = apply_rankings_to_weights(preference_weights(preferences), rankings)
    store["global"] = global_prefs
    store["updated_at"] = datetime.now(timezone.utc).isoformat()
    return store


def merge_session_weights(
    *,
    base_preferences: dict[str, Any] | None,
    session_weights: dict[str, dict[str, int]] | None,
    feedback_text: str,
    keywords: dict[str, tuple[str, str]],
) -> dict[str, dict[str, int]]:
    """Effective weights for the next prototype batch."""
    if session_weights:
        weights = copy_weights(session_weights)
    else:
        weights = copy_weights(preference_weights(base_preferences))

    if feedback_text.strip():
        weights = apply_feedback_text(weights, feedback_text, keywords)
    return weights
