"""Per-step OpenAI image model selection for the shell design pipeline."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Literal

from shell_asset_policy import FinalRoute, asset_mode_for_shell
from shell_references import ShellReference

ShellStep = Literal["pass1", "prepass", "final_text", "final_photo"]

_STEP_ENV = {
    "pass1": "OPENAI_IMAGE_MODEL_SHELL_PASS1",
    "prepass": "OPENAI_IMAGE_MODEL_SHELL_PREPAS",
    "final_text": "OPENAI_IMAGE_MODEL_SHELL_FINAL_TEXT",
    "final_photo": "OPENAI_IMAGE_MODEL_SHELL_FINAL_PHOTO",
}

_QUALITY_ENV = {
    "pass1": "OPENAI_IMAGE_QUALITY_SHELL_PASS1",
    "prepass": "SHELL_PREPASS_QUALITY",
    "final_text": "OPENAI_IMAGE_QUALITY_SHELL_FINAL_TEXT",
    "final_photo": "OPENAI_IMAGE_QUALITY_SHELL_FINAL_PHOTO",
}


@dataclass(frozen=True)
class ShellModelChoice:
    step: ShellStep
    model: str
    quality: str
    size: str
    input_fidelity: str | None
    score: float
    rationale: str

    def label(self) -> str:
        fidelity = f", fidelity={self.input_fidelity}" if self.input_fidelity else ""
        return f"{self.model} ({self.quality}{fidelity})"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelProfile:
    id: str
    creative_score: float
    masked_edit_score: float
    text_score: float
    photo_preserve_score: float
    draft_speed_score: float
    supports_input_fidelity: bool
    default_quality: dict[ShellStep, str]


_MODELS: tuple[ModelProfile, ...] = (
    ModelProfile(
        id="gpt-image-2",
        creative_score=100,
        masked_edit_score=98,
        text_score=100,
        photo_preserve_score=98,
        draft_speed_score=95,
        supports_input_fidelity=False,
        default_quality={
            "pass1": "high",
            "prepass": "low",
            "final_text": "high",
            "final_photo": "high",
        },
    ),
    ModelProfile(
        id="gpt-image-1.5",
        creative_score=88,
        masked_edit_score=95,
        text_score=92,
        photo_preserve_score=90,
        supports_input_fidelity=True,
        draft_speed_score=70,
        default_quality={
            "pass1": "high",
            "prepass": "medium",
            "final_text": "high",
            "final_photo": "high",
        },
    ),
    ModelProfile(
        id="gpt-image-1",
        creative_score=75,
        masked_edit_score=80,
        text_score=78,
        photo_preserve_score=82,
        supports_input_fidelity=True,
        draft_speed_score=65,
        default_quality={
            "pass1": "high",
            "prepass": "medium",
            "final_text": "high",
            "final_photo": "high",
        },
    ),
    ModelProfile(
        id="gpt-image-1-mini",
        creative_score=55,
        masked_edit_score=60,
        text_score=58,
        photo_preserve_score=50,
        supports_input_fidelity=True,
        draft_speed_score=100,
        default_quality={
            "pass1": "medium",
            "prepass": "low",
            "final_text": "medium",
            "final_photo": "medium",
        },
    ),
)


def _policy_mode() -> str:
    return (os.getenv("SHELL_MODEL_POLICY") or "auto").strip().lower()


def _default_size() -> str:
    return os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")


def _allowed_models() -> tuple[str, ...]:
    raw = (os.getenv("SHELL_MODEL_CANDIDATES") or "").strip()
    if raw:
        return tuple(m.strip() for m in raw.split(",") if m.strip())
    return tuple(m.id for m in _MODELS)


def _profile(model_id: str) -> ModelProfile | None:
    for profile in _MODELS:
        if profile.id == model_id:
            return profile
    return None


def _env_override(step: ShellStep) -> str | None:
    key = _STEP_ENV[step]
    val = (os.getenv(key) or "").strip()
    return val or None


def _quality_override(step: ShellStep) -> str | None:
    key = _QUALITY_ENV[step]
    val = (os.getenv(key) or "").strip().lower()
    return val or None


def _global_model() -> str:
    return (os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip()


def _score_for_step(profile: ModelProfile, step: ShellStep, shell: ShellReference) -> float:
    if step == "pass1":
        score = profile.creative_score
        if shell.style in {"photographic", "letterpress_handbill"}:
            score += 4
        return score

    if step == "prepass":
        return profile.draft_speed_score + profile.masked_edit_score * 0.35

    if step == "final_text":
        score = profile.text_score + profile.masked_edit_score * 0.25
        if asset_mode_for_shell(shell) == "typography_only":
            score += 8
        if shell.style == "psychedelic_illustrative":
            score += 6
        return score

    score = profile.photo_preserve_score + profile.masked_edit_score * 0.2
    mode = asset_mode_for_shell(shell)
    if mode == "photo_hero":
        score += 8
    elif mode == "photo_inset":
        score += 4
    if shell.style == "photographic":
        score += 4
    return score


def _rationale(step: ShellStep, profile: ModelProfile, shell: ShellReference, score: float) -> str:
    if step == "pass1":
        return (
            f"Creative shell from reference — {profile.id} scored {score:.0f} for "
            f"{shell.style.replace('_', ' ')} / {shell.design_family}"
        )
    if step == "prepass":
        return (
            f"Fast masked text mockup — {profile.id} favors speed + edit fidelity "
            f"(score {score:.0f})"
        )
    if step == "final_text":
        return (
            f"High-fidelity typography slots — {profile.id} scored {score:.0f} for "
            f"text-heavy {shell.design_family}"
        )
    return (
        f"Photo/logo compose + masked edit — {profile.id} scored {score:.0f} for "
        f"{asset_mode_for_shell(shell)} on {shell.design_family}"
    )


def _input_fidelity_for(profile: ModelProfile, step: ShellStep) -> str | None:
    if not profile.supports_input_fidelity:
        return None
    if step in {"prepass", "final_text", "final_photo"}:
        return "high"
    return None


def select_model_for_step(
    shell: ShellReference,
    step: ShellStep,
    *,
    route: FinalRoute | None = None,
) -> ShellModelChoice:
    """Evaluate candidate models and return the best choice for this step."""
    del route  # reserved for future route-aware tuning

    override = _env_override(step)
    if override:
        profile = _profile(override)
        quality = _quality_override(step) or (
            profile.default_quality[step] if profile else "high"
        )
        return ShellModelChoice(
            step=step,
            model=override,
            quality=quality,
            size=_default_size(),
            input_fidelity=_input_fidelity_for(profile, step) if profile else "high",
            score=100.0,
            rationale=f"Env override {_STEP_ENV[step]}={override}",
        )

    if _policy_mode() == "fixed":
        model = _global_model()
        profile = _profile(model)
        quality = _quality_override(step) or (
            profile.default_quality[step] if profile else "high"
        )
        return ShellModelChoice(
            step=step,
            model=model,
            quality=quality,
            size=_default_size(),
            input_fidelity=_input_fidelity_for(profile, step) if profile else "high",
            score=100.0,
            rationale=f"SHELL_MODEL_POLICY=fixed using OPENAI_IMAGE_MODEL={model}",
        )

    allowed = set(_allowed_models())
    best: ShellModelChoice | None = None
    for profile in _MODELS:
        if profile.id not in allowed:
            continue
        if step == "prepass" and profile.id == "gpt-image-1-mini":
            # Mini is prepass-only in auto mode — skip for other steps below
            pass
        elif step != "prepass" and profile.id == "gpt-image-1-mini":
            continue

        score = _score_for_step(profile, step, shell)
        quality = _quality_override(step) or profile.default_quality[step]
        choice = ShellModelChoice(
            step=step,
            model=profile.id,
            quality=quality,
            size=_default_size(),
            input_fidelity=_input_fidelity_for(profile, step),
            score=score,
            rationale=_rationale(step, profile, shell, score),
        )
        if best is None or choice.score > best.score:
            best = choice

    if best is not None:
        return best

    fallback = _global_model()
    profile = _profile(fallback)
    return ShellModelChoice(
        step=step,
        model=fallback,
        quality=_quality_override(step) or "high",
        size=_default_size(),
        input_fidelity=_input_fidelity_for(profile, step) if profile else "high",
        score=0.0,
        rationale="No candidates matched — falling back to OPENAI_IMAGE_MODEL",
    )


def build_run_model_plan(shell: ShellReference) -> dict[str, Any]:
    """Evaluate and record the best model for each pipeline step."""
    steps: dict[str, ShellModelChoice] = {
        "pass1": select_model_for_step(shell, "pass1"),
        "prepass": select_model_for_step(shell, "prepass"),
        "final_text": select_model_for_step(shell, "final_text"),
        "final_photo": select_model_for_step(shell, "final_photo"),
    }
    return {
        "policy": _policy_mode(),
        "candidates": list(_allowed_models()),
        "steps": {name: choice.to_dict() for name, choice in steps.items()},
    }


def model_choice_for_step(plan: dict[str, Any] | None, step: ShellStep) -> ShellModelChoice | None:
    if not plan:
        return None
    raw = (plan.get("steps") or {}).get(step)
    if not raw:
        return None
    return ShellModelChoice(
        step=step,
        model=str(raw["model"]),
        quality=str(raw["quality"]),
        size=str(raw.get("size") or _default_size()),
        input_fidelity=raw.get("input_fidelity"),
        score=float(raw.get("score") or 0),
        rationale=str(raw.get("rationale") or ""),
    )


def final_step_for_route(route: FinalRoute) -> ShellStep:
    return "final_text" if route == "text_only" else "final_photo"
