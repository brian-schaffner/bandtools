"""Preference weights for design element sampling."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any


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
    keys = ("archetype", "palette", "accent", "family", "medium_variant", "layers")
    return {key: dict(prefs.get(key, {})) for key in keys}


def apply_feedback_text(
    weights: dict[str, dict[str, int]],
    feedback: str,
    keywords: dict[str, tuple[str, str]],
) -> dict[str, dict[str, int]]:
    """Boost tag weights when feedback mentions design keywords."""
    text = feedback.lower()
    result = {key: dict(vals) for key, vals in weights.items()}
    for word, (category, value) in keywords.items():
        if word in text:
            bucket = result.setdefault(category, {})
            bucket[value] = bucket.get(value, 0) + 2
    return result


def apply_rankings_to_preferences(
    preferences: dict[str, Any] | None,
    rankings: list[dict[str, Any]],
) -> dict[str, Any]:
    store: dict[str, Any] = dict(preferences or {})
    global_prefs: dict[str, dict[str, int]] = {
        key: dict(store.get("global", {}).get(key, {}))
        for key in ("archetype", "palette", "accent", "family", "medium_variant", "layers")
    }

    for item in rankings:
        rank = int(item.get("rank") or 0)
        if rank <= 0:
            continue
        boost = max(1, 6 - rank)
        penalty = -2 if rank >= 4 else 0
        delta = boost + penalty
        tags = item.get("tags") or {}
        for key in ("archetype", "palette", "accent", "family", "medium_variant"):
            value = tags.get(key)
            if value:
                global_prefs[key][value] = global_prefs[key].get(value, 0) + delta
        layers = tags.get("layers")
        if layers:
            global_prefs["layers"][layers] = global_prefs["layers"].get(layers, 0) + delta
        for liked in item.get("liked_elements") or []:
            if ":" in liked:
                k, v = liked.split(":", 1)
                if k in global_prefs and v:
                    global_prefs[k][v] = global_prefs[k].get(v, 0) + 3

    store["global"] = global_prefs
    store["updated_at"] = datetime.now(timezone.utc).isoformat()
    return store
