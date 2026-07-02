"""Rapid prototype loop — 3 options per round, rank + feedback drives the next 3."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

from design_explorer import (
    ExploreSpec,
    ROOT,
    _render_explore_spec,
    enumerate_explore_specs,
)
from flyer_generator import gig_output_dir, resolve_gig_event
from gig_research import research_gig
from photo_selector import select_band_photo
from preference_model import (
    apply_feedback_text,
    apply_rankings_to_preferences,
    preference_weights,
)
from state import (
    append_feedback,
    get_gig_state,
    load_design_preferences,
    mark_approved,
    save_design_preferences,
    upsert_gig,
)

FEEDBACK_KEYWORDS: dict[str, tuple[str, str]] = {
    "duotone": ("archetype", "duotone_modern"),
    "xerox": ("archetype", "xerox_punk"),
    "psychedelic": ("archetype", "psychedelic"),
    "neon": ("archetype", "neon_bar"),
    "zine": ("archetype", "pasteup_zine"),
    "broadside": ("medium_variant", "broadside"),
    "paste": ("medium_variant", "paste_up"),
    "stamp": ("accent", "stamp"),
    "starburst": ("accent", "starburst"),
    "tape": ("accent", "tape"),
    "red": ("palette", "red_cream"),
    "yellow": ("palette", "yellow_black"),
    "simple": ("family", "A"),
    "handbill": ("family", "B"),
    "wild": ("family", "C"),
}


def prototype_max_rounds() -> int:
    raw = os.getenv("PROTOTYPE_MAX_ROUNDS", "5").strip()
    try:
        return max(1, min(12, int(raw)))
    except ValueError:
        return 5


def default_prototype_session() -> dict[str, Any]:
    return {
        "status": "idle",
        "round": 0,
        "max_rounds": prototype_max_rounds(),
        "options": {},
        "round_history": [],
        "used_spec_ids": [],
        "winner_slot": None,
    }


def get_prototype_session(gig_id: str) -> dict[str, Any]:
    record = get_gig_state(gig_id) or {}
    session = dict(record.get("prototype") or default_prototype_session())
    session.setdefault("max_rounds", prototype_max_rounds())
    return session


def _spec_score(spec: ExploreSpec, weights: dict[str, dict[str, int]], used: set[str]) -> float:
    score = 0.0
    for key, value in spec.tags.items():
        if key in weights and value:
            score += weights[key].get(value, 0)
    if spec.wild:
        score += weights.get("family", {}).get("C", 0) * 0.25
    if spec.spec_id in used:
        score -= 8
    return score


def select_prototype_specs(
    gig_id: str,
    *,
    round_num: int,
    preferences: dict[str, Any],
    used_spec_ids: list[str],
    feedback_text: str = "",
) -> list[ExploreSpec]:
    """Pick 3 diverse approaches for this prototype round."""
    import random

    pool = enumerate_explore_specs(gig_id, max_count=999)
    weights = preference_weights(preferences)
    if feedback_text.strip():
        weights = apply_feedback_text(weights, feedback_text, FEEDBACK_KEYWORDS)

    recent = set(used_spec_ids[-9:])
    rng = random.Random(int(hashlib.sha256(f"proto:{gig_id}:{round_num}".encode()).hexdigest()[:8], 16))
    scored = sorted(pool, key=lambda s: _spec_score(s, weights, recent), reverse=True)

    chosen: list[ExploreSpec] = []
    families_seen: set[str] = set()

    # Best weighted pick
    for spec in scored:
        if spec.spec_id not in {c.spec_id for c in chosen}:
            chosen.append(spec)
            families_seen.add(spec.family)
            break

    # Different family when possible
    for spec in scored:
        if len(chosen) >= 2:
            break
        if spec.spec_id in {c.spec_id for c in chosen}:
            continue
        if spec.family not in families_seen or len(families_seen) >= 3:
            chosen.append(spec)
            families_seen.add(spec.family)

    # Wild or exploratory third
    wild_pool = [s for s in scored if s.wild and s.spec_id not in {c.spec_id for c in chosen}]
    if wild_pool and round_num <= 2:
        chosen.append(wild_pool[0])
    else:
        for spec in scored:
            if len(chosen) >= 3:
                break
            if spec.spec_id not in {c.spec_id for c in chosen}:
                chosen.append(spec)

    while len(chosen) < 3 and len(chosen) < len(pool):
        for spec in scored:
            if spec not in chosen:
                chosen.append(spec)
                if len(chosen) >= 3:
                    break

    # Round-specific seeds for C recipes so repeats look different
    result: list[ExploreSpec] = []
    for idx, spec in enumerate(chosen[:3]):
        if spec.recipe is not None:
            from structured_layout.graphic_composer import GraphicRecipe

            seed = int(
                hashlib.sha256(f"{gig_id}:{round_num}:{idx}:{spec.spec_id}".encode()).hexdigest()[:8],
                16,
            )
            recipe = GraphicRecipe(
                archetype=spec.recipe.archetype,
                palette_id=spec.recipe.palette_id,
                palette=spec.recipe.palette,
                accent=spec.recipe.accent,
                layers=spec.recipe.layers,
                mirror=spec.recipe.mirror,
                seed=seed,
            )
            spec = ExploreSpec(
                spec_id=f"{spec.spec_id}-r{round_num}-{idx + 1}",
                family=spec.family,
                label=spec.label,
                tags=dict(spec.tags),
                wild=spec.wild,
                recipe=recipe,
                medium_variant=spec.medium_variant,
            )
        result.append(spec)
    rng.shuffle(result)
    return result


def generate_prototype_round(
    gig_id: str,
    *,
    round_num: Optional[int] = None,
    feedback_text: str = "",
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    from progress_helper import emit_progress

    event = resolve_gig_event(gig_id)
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    session = get_prototype_session(gig_id)
    proto_round = round_num or int(session.get("round") or 0) + 1
    preferences = load_design_preferences()

    emit_progress(on_progress, step="prototype", substep="prep", message="Researching gig…", progress=5)
    research = research_gig(event, on_progress=on_progress)
    selected_photo = select_band_photo(event, research, on_progress=on_progress)
    if not selected_photo or not selected_photo.get("path"):
        raise ValueError("No band photo available for prototype generation")
    photo_path = ROOT / selected_photo["path"]

    specs = select_prototype_specs(
        gig_id,
        round_num=proto_round,
        preferences=preferences,
        used_spec_ids=list(session.get("used_spec_ids") or []),
        feedback_text=feedback_text,
    )

    out_dir = gig_output_dir(event) / "prototype"
    out_dir.mkdir(parents=True, exist_ok=True)
    options: dict[str, dict[str, Any]] = {}

    for slot_idx, spec in enumerate(specs, start=1):
        slot = str(slot_idx)
        emit_progress(
            on_progress,
            step="prototype",
            substep="render",
            message=f"Prototype {slot}/3: {spec.label}",
            progress=10 + slot_idx * 25,
        )
        filename = f"prototype_r{proto_round}_{slot}.png"
        out_path = out_dir / filename
        variant = _render_explore_spec(
            spec,
            event=event,
            band=band,
            photo_path=photo_path,
            out_path=out_path,
            research=research,
        )
        options[slot] = {
            **asdict(variant),
            "slot": slot,
            "round": proto_round,
        }

    used = list(session.get("used_spec_ids") or [])
    for spec in specs:
        base_id = re.sub(r"-r\d+-\d+$", "", spec.spec_id)
        used.append(base_id)

    manifest = {
        "gig_id": gig_id,
        "round": proto_round,
        "options": options,
        "feedback_applied": feedback_text,
    }
    manifest_path = out_dir / f"manifest_r{proto_round}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    event_dict = event.to_dict() if hasattr(event, "to_dict") else (get_gig_state(gig_id) or {}).get("event", {})
    upsert_gig(
        gig_id,
        status="prototype_review",
        prototype={
            **session,
            "status": "active",
            "round": proto_round,
            "max_rounds": session.get("max_rounds") or prototype_max_rounds(),
            "options": options,
            "used_spec_ids": used[-30:],
        },
        event=event_dict,
    )

    emit_progress(
        on_progress,
        step="prototype",
        substep="done",
        message=f"Prototype round {proto_round} ready",
        progress=100,
    )
    return manifest


def submit_prototype_turn(
    gig_id: str,
    *,
    rankings: list[dict[str, Any]],
    feedback: str,
    action: str,
    winner_slot: Optional[str] = None,
) -> dict[str, Any]:
    """Process rank + feedback; next round, approve winner, or forfeit."""
    session = get_prototype_session(gig_id)
    proto_round = int(session.get("round") or 0)
    options = session.get("options") or {}

    if action == "forfeit":
        append_feedback(gig_id, "prototype_forfeit", "", feedback, f"FORFEIT round {proto_round}")
        upsert_gig(
            gig_id,
            status="prototype_forfeit",
            prototype={**session, "status": "forfeit", "round_history": _append_history(session, rankings, feedback)},
        )
        return {"status": "forfeit", "round": proto_round}

    if action == "approve":
        slot = (winner_slot or "").strip()
        if slot not in options:
            raise ValueError("Pick which prototype wins before approving")
        winner = options[slot]
        path_rel = winner.get("path_rel")
        if not path_rel:
            raise ValueError("Winning prototype has no image")
        source = ROOT / path_rel
        append_feedback(gig_id, "prototype_approve", slot, feedback, f"APPROVE prototype {slot} round {proto_round}")
        dest = mark_approved(gig_id, f"P{slot}", source)
        upsert_gig(
            gig_id,
            prototype={
                **session,
                "status": "success",
                "winner_slot": slot,
                "round_history": _append_history(session, rankings, feedback),
            },
        )
        return {"status": "success", "round": proto_round, "winner_slot": slot, "path": str(dest)}

    if proto_round >= int(session.get("max_rounds") or prototype_max_rounds()):
        upsert_gig(
            gig_id,
            status="prototype_forfeit",
            prototype={**session, "status": "forfeit", "round_history": _append_history(session, rankings, feedback)},
        )
        return {"status": "forfeit", "reason": "max_rounds", "round": proto_round}

    # Rankings → preferences for next round
    enriched = []
    for item in rankings:
        slot = str(item.get("slot", ""))
        opt = options.get(slot, {})
        enriched.append(
            {
                "rank": item.get("rank"),
                "slot": slot,
                "tags": opt.get("tags") or {},
                "liked_elements": item.get("liked_elements") or [],
            }
        )

    prefs = apply_rankings_to_preferences(load_design_preferences(), enriched)
    if feedback.strip():
        prefs = apply_feedback_text_to_preferences(prefs, feedback)
    save_design_preferences(prefs)

    append_feedback(
        gig_id,
        "prototype_next",
        "",
        feedback,
        f"PROTOTYPE round {proto_round} → next (rankings: {rankings})",
    )

    history = _append_history(session, rankings, feedback)
    upsert_gig(
        gig_id,
        prototype={**session, "round_history": history},
    )

    manifest = generate_prototype_round(gig_id, feedback_text=feedback)
    return {"status": "next", "round": manifest["round"], "manifest": manifest}


def _append_history(session: dict[str, Any], rankings: list[dict[str, Any]], feedback: str) -> list[dict[str, Any]]:
    history = list(session.get("round_history") or [])
    history.append(
        {
            "round": session.get("round"),
            "rankings": rankings,
            "feedback": feedback,
            "options": session.get("options"),
        }
    )
    return history[-12:]


def apply_feedback_text_to_preferences(preferences: dict[str, Any], feedback: str) -> dict[str, Any]:
    weights = preference_weights(preferences)
    boosted = apply_feedback_text(weights, feedback, FEEDBACK_KEYWORDS)
    store = dict(preferences)
    store["global"] = boosted
    return store


def start_prototype_session(gig_id: str, on_progress: Callable[..., None] | None = None) -> dict[str, Any]:
    upsert_gig(
        gig_id,
        prototype={
            **default_prototype_session(),
            "status": "active",
            "max_rounds": prototype_max_rounds(),
        },
    )
    return generate_prototype_round(gig_id, round_num=1, on_progress=on_progress)
