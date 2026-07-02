"""Rapid prototype loop — 3 options per round, rank + feedback drives the next 3."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

from design_explorer import (
    ExploreSpec,
    ROOT,
    _render_explore_spec,
    enumerate_explore_specs,
    materialize_spec_for_round,
    spec_signature,
)
from flyer_generator import gig_output_dir, resolve_gig_event
from output_paths import resolve_output_path
from gig_research import research_gig
from photo_selector import select_band_photo
from preference_model import (
    apply_feedback_text,
    apply_rankings_to_preferences,
    apply_rankings_to_weights,
    copy_weights,
    merge_session_weights,
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
    "pasteup": ("archetype", "pasteup_zine"),
    "broadside": ("medium_variant", "broadside"),
    "boutique": ("archetype", "boutique"),
    "country": ("archetype", "country_fair"),
    "paste": ("medium_variant", "paste_up"),
    "stamp": ("accent", "stamp"),
    "starburst": ("accent", "starburst"),
    "tape": ("accent", "tape"),
    "red": ("palette", "red_cream"),
    "yellow": ("palette", "yellow_black"),
    "blue": ("palette", "blue_white"),
    "simple": ("family", "A"),
    "handbill": ("family", "B"),
    "collage": ("family", "C"),
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
        "tag_weights": {},
        "winner_slot": None,
    }


def get_prototype_session(gig_id: str) -> dict[str, Any]:
    record = get_gig_state(gig_id) or {}
    session = dict(record.get("prototype") or default_prototype_session())
    session.setdefault("max_rounds", prototype_max_rounds())
    return session


def _base_spec_id(spec_id: str) -> str:
    return re.sub(r"-r\d+-s\d+$", "", spec_id)


def _signatures_from_history(round_history: list[dict[str, Any]], *, last_n: int | None = None) -> set[str]:
    sigs: set[str] = set()
    entries = round_history if last_n is None else round_history[-last_n:]
    for entry in entries:
        for opt in (entry.get("options") or {}).values():
            tags = opt.get("tags") or {}
            sigs.add(
                "|".join(
                    [
                        tags.get("family", opt.get("family", "")),
                        tags.get("archetype", ""),
                        tags.get("palette", ""),
                        tags.get("medium_variant", ""),
                        tags.get("accent", ""),
                    ]
                )
            )
    return {s for s in sigs if s.strip("|")}


def _spec_score(
    spec: ExploreSpec,
    weights: dict[str, dict[str, int]],
    *,
    used_bases: set[str],
    blocked_sigs: set[str],
    round_num: int,
    archetype_counts: dict[str, int],
) -> float:
    score = float(round_num % 7) * 0.05
    for key, value in spec.tags.items():
        if key in weights and value:
            score += weights[key].get(value, 0) * 1.25

    arch = spec.tags.get("archetype", "")
    if arch:
        score += max(0, 4 - archetype_counts.get(arch, 0)) * 3.0

    if spec.wild:
        score += 2.0 + (round_num % 3) * 0.75

    base = _base_spec_id(spec.spec_id)
    if base in used_bases:
        score -= 100
    if spec_signature(spec) in blocked_sigs:
        score -= 60

    return score


def _softmax_pick(
    rng: random.Random,
    candidates: list[ExploreSpec],
    scores: dict[str, float],
    *,
    temperature: float = 2.0,
) -> ExploreSpec:
    import math

    weights = [math.exp(scores.get(spec.spec_id, 0.0) / max(0.5, temperature)) for spec in candidates]
    total = sum(weights)
    pick = rng.random() * total
    acc = 0.0
    for spec, w in zip(candidates, weights):
        acc += w
        if pick <= acc:
            return spec
    return candidates[-1]


def _feedback_wants_handbill(feedback_text: str) -> bool:
    text = feedback_text.lower()
    return any(w in text for w in ("handbill", "paste", "broadside", "simple stack", "conservative", "option b", "option a"))


def select_prototype_specs(
    gig_id: str,
    *,
    round_num: int,
    preferences: dict[str, Any],
    used_spec_ids: list[str],
    feedback_text: str = "",
    round_history: list[dict[str, Any]] | None = None,
    session_weights: dict[str, dict[str, int]] | None = None,
) -> list[ExploreSpec]:
    """Pick 3 diverse approaches — rankings + feedback steer the next batch."""
    full_pool = enumerate_explore_specs(gig_id, max_count=999)
    allow_handbill = _feedback_wants_handbill(feedback_text)
    pool = [s for s in full_pool if s.family == "C"]
    if allow_handbill:
        pool = full_pool
    if len(pool) < 3:
        pool = full_pool

    weights = merge_session_weights(
        base_preferences=preferences,
        session_weights=session_weights,
        feedback_text=feedback_text,
        keywords=FEEDBACK_KEYWORDS,
    )

    used_bases = {_base_spec_id(s) for s in used_spec_ids}
    blocked_sigs = _signatures_from_history(round_history or [])
    recent_sigs = _signatures_from_history(round_history or [], last_n=3)

    rng = random.Random(int(hashlib.sha256(f"proto-pick:{gig_id}:{round_num}:{feedback_text[:48]}".encode()).hexdigest()[:8], 16))

    archetype_counts: dict[str, int] = {}
    for sig in recent_sigs:
        parts = sig.split("|")
        if len(parts) > 1 and parts[1]:
            archetype_counts[parts[1]] = archetype_counts.get(parts[1], 0) + 1

    scores = {
        spec.spec_id: _spec_score(
            spec,
            weights,
            used_bases=used_bases,
            blocked_sigs=blocked_sigs,
            round_num=round_num,
            archetype_counts=archetype_counts,
        )
        for spec in pool
    }

    chosen: list[ExploreSpec] = []
    chosen_sigs: set[str] = set()
    chosen_archetypes: set[str] = set()

    def _available(from_pool: list[ExploreSpec] | None = None, *, allow_used: bool = False) -> list[ExploreSpec]:
        src = from_pool if from_pool is not None else pool
        taken = {_base_spec_id(s.spec_id) for s in chosen}
        out: list[ExploreSpec] = []
        for spec in src:
            base = _base_spec_id(spec.spec_id)
            if base in taken:
                continue
            if not allow_used and base in used_bases:
                continue
            sig = spec_signature(spec)
            if sig in chosen_sigs or sig in blocked_sigs:
                continue
            out.append(spec)
        if len(out) < 3 and not allow_used:
            return _available(from_pool, allow_used=True)
        return out

    def _track(spec: ExploreSpec) -> None:
        chosen_sigs.add(spec_signature(spec))
        arch = spec.tags.get("archetype")
        if arch:
            chosen_archetypes.add(arch)

    def _pick(from_pool: list[ExploreSpec], temp: float) -> ExploreSpec | None:
        avail = _available(from_pool)
        if not avail:
            return None
        return _softmax_pick(rng, avail, scores, temperature=temp)

    # Slot 1: strongest match to accumulated preferences / feedback.
    top_archetypes = sorted(
        {s.tags.get("archetype", "") for s in pool if s.tags.get("archetype")},
        key=lambda arch: weights.get("archetype", {}).get(arch, 0),
        reverse=True,
    )
    slot1_pool = pool
    if top_archetypes and weights.get("archetype"):
        lead = top_archetypes[0]
        if weights["archetype"].get(lead, 0) > 0:
            biased = [s for s in pool if s.tags.get("archetype") == lead]
            if biased:
                slot1_pool = biased
    pick = _pick(slot1_pool, 1.4)
    if pick:
        chosen.append(pick)
        _track(pick)

    if allow_handbill:
        b_pool = [s for s in full_pool if s.family == "B"]
        pick = _pick(b_pool, 1.8)
        if pick and all(_base_spec_id(pick.spec_id) != _base_spec_id(s.spec_id) for s in chosen):
            chosen.append(pick)
            _track(pick)

    # Slot 2+: force different archetypes when possible.
    avail = _available()
    prefer = [s for s in avail if s.tags.get("archetype") and s.tags.get("archetype") not in chosen_archetypes]
    pick = _softmax_pick(rng, prefer or avail, scores, temperature=1.6) if (prefer or avail) else None
    if pick:
        chosen.append(pick)
        _track(pick)

    avail = _available()
    wild = [s for s in avail if s.wild]
    prefer = [s for s in (wild or avail) if s.tags.get("archetype") not in chosen_archetypes]
    pick_pool = prefer or wild or avail
    pick = _softmax_pick(rng, pick_pool, scores, temperature=1.5) if pick_pool else None
    if pick:
        chosen.append(pick)
        _track(pick)

    while len(chosen) < 3:
        avail = _available()
        if not avail:
            break
        pick = _softmax_pick(rng, avail, scores, temperature=2.0)
        chosen.append(pick)
        _track(pick)

    pref_dict = {"global": weights}
    result: list[ExploreSpec] = []
    for slot, spec in enumerate(chosen[:3], start=1):
        result.append(
            materialize_spec_for_round(
                spec,
                gig_id=gig_id,
                round_num=round_num,
                slot=slot,
                preferences=pref_dict,
            )
        )
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
    session_weights = session.get("tag_weights") or None

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
        round_history=list(session.get("round_history") or []),
        session_weights=session_weights if isinstance(session_weights, dict) else None,
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
        used.append(_base_spec_id(spec.spec_id))

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
        source = resolve_output_path(path_rel)
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

    session_weights = copy_weights(
        session.get("tag_weights") or preference_weights(load_design_preferences())
    )
    session_weights = apply_rankings_to_weights(session_weights, enriched)
    if feedback.strip():
        session_weights = apply_feedback_text(session_weights, feedback, FEEDBACK_KEYWORDS)

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
        prototype={**session, "round_history": history, "tag_weights": session_weights},
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
