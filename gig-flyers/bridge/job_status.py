"""In-memory generation job status for async flyer workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from gen_timing import get_estimates, get_generate_estimate, quality_for_tier, tier_for_option

MAX_LOG_ENTRIES = 8


def option_letters() -> tuple[str, ...]:
    from option_slots import round_option_letters

    return round_option_letters()

_lock = Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_option(*, phase: str = "pending") -> dict[str, Any]:
    return {
        "phase": phase,
        "progress": 0,
        "attempt": 0,
        "note": "",
        "image_url": "",
        "exhausted": False,
        "provider_label": "",
        "estimated_generate_seconds": 0.0,
        "generate_started_at": None,
    }


def _option_generate_estimate(letter: str, provider: str) -> float:
    tier = tier_for_option(letter)
    quality = quality_for_tier(tier, use_reference=True)
    return get_generate_estimate(provider, quality, tier)


def _sync_job_generate_estimate(job: dict[str, Any]) -> None:
    options = job.get("options") or {}
    estimates = [
        float(entry.get("estimated_generate_seconds", 0))
        for entry in options.values()
        if float(entry.get("estimated_generate_seconds", 0)) > 0
    ]
    if estimates:
        job["estimated_generate_seconds"] = max(estimates)
    else:
        job["estimated_generate_seconds"] = get_estimates()["generate_seconds"]


def _freeze_option_generate_timing(job: dict[str, Any], letter: str, provider: str) -> None:
    options = job.setdefault("options", _default_options())
    entry = options.setdefault(letter, _default_option())
    entry["estimated_generate_seconds"] = _option_generate_estimate(letter, provider)
    entry["generate_started_at"] = _now_iso()
    _sync_job_generate_estimate(job)


def _default_options() -> dict[str, dict[str, Any]]:
    return {letter: _default_option() for letter in option_letters()}


def _option_snapshot(options: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {letter: dict(options.get(letter, _default_option())) for letter in option_letters()}


def _bump_options_revision(job: dict[str, Any]) -> None:
    job["options_revision"] = int(job.get("options_revision", 0)) + 1


def _format_log_line(
    step: str,
    substep: str,
    message: str,
    detail: str,
    option: str,
    attempt: int,
) -> str:
    parts: list[str] = []
    if option:
        parts.append(f"[{option}]")
    if step:
        parts.append(step.replace("_", " "))
    if substep:
        parts.append(f"({substep})")
    text = message or detail or substep or step
    if attempt:
        text = f"{text} [attempt {attempt}]"
    parts.append(text)
    return " ".join(parts).strip()


def _append_log(job: dict[str, Any], text: str) -> None:
    log = job.setdefault("log", [])
    log.append({"at": _now_iso(), "text": text})
    if len(log) > MAX_LOG_ENTRIES:
        job["log"] = log[-MAX_LOG_ENTRIES:]
    job["log_revision"] = int(job.get("log_revision", 0)) + 1


def _infer_option_phase(step: str, substep: str) -> Optional[str]:
    if step == "generate":
        if substep == "error":
            return "error"
        if substep == "remake":
            return "remaking"
        if substep in {"start", "prompt", "provider", "api_start", "heartbeat", "saved", "retry", "fallback", "fallback_done"}:
            return "generating"
    if step == "review":
        if substep == "passed":
            return "passed"
        if substep == "remake":
            return "failed"
        if substep in {"start", "heartbeat", "verdict", "error", "preview"}:
            return "reviewing"
    return None


def _infer_option_progress(
    phase: str,
    substep: str,
    entry: dict[str, Any],
    *,
    explicit: Optional[int] = None,
) -> int:
    if explicit is not None:
        return min(100, max(0, int(explicit)))
    if phase in {"passed", "failed", "error"}:
        return 100
    if phase == "remaking" and substep == "remake":
        return 0
    if phase == "generating" and substep == "start":
        return 0
    if phase == "generating" and substep == "saved":
        return 100
    if phase == "reviewing":
        return 100
    return int(entry.get("progress", 0))


def _sync_option_from_report(
    job: dict[str, Any],
    option: str,
    *,
    step: str,
    substep: str,
    message: str,
    detail: str,
    progress: int,
    attempt: int,
    option_phase: Optional[str] = None,
    option_progress: Optional[int] = None,
    option_note: Optional[str] = None,
    option_image_url: Optional[str] = None,
    option_exhausted: Optional[bool] = None,
    option_provider_label: Optional[str] = None,
) -> None:
    if substep == "heartbeat":
        return

    letter = (option or "").upper()
    if letter not in option_letters():
        return

    options = job.setdefault("options", _default_options())
    entry = options.setdefault(letter, _default_option())
    phase = option_phase or _infer_option_phase(step, substep)
    if not phase:
        return

    new_progress = _infer_option_progress(
        phase, substep, entry, explicit=option_progress
    )

    new_attempt = attempt or entry.get("attempt", 0)
    if phase in {"generating", "remaking"} and substep in {"start", "remake"}:
        new_attempt = attempt or (new_attempt or 1)

    note = option_note
    if note is None and phase == "failed":
        note = detail or message
    elif note is None and phase == "passed":
        note = ""

    if phase == "remaking" and substep == "remake":
        option_image_url = ""

    changed = False
    if entry.get("phase") != phase:
        entry["phase"] = phase
        changed = True
        if phase in {"generating", "remaking"}:
            from image_providers.base import resolve_image_provider_for_option

            provider = resolve_image_provider_for_option(letter)
            _freeze_option_generate_timing(job, letter, provider)
    if entry.get("progress") != new_progress:
        entry["progress"] = new_progress
    if new_attempt and entry.get("attempt") != new_attempt:
        entry["attempt"] = new_attempt
        changed = True
    if note is not None and entry.get("note") != note:
        entry["note"] = note
        changed = True
    if option_image_url is not None and entry.get("image_url") != option_image_url:
        entry["image_url"] = option_image_url
        changed = True
    if option_exhausted is not None and entry.get("exhausted") != option_exhausted:
        entry["exhausted"] = bool(option_exhausted)
        changed = True
    if option_provider_label is not None and entry.get("provider_label") != option_provider_label:
        entry["provider_label"] = option_provider_label
        changed = True
    if changed:
        _bump_options_revision(job)


def update_option(
    gig_id: str,
    option: str,
    *,
    phase: Optional[str] = None,
    progress: Optional[int] = None,
    attempt: Optional[int] = None,
    note: Optional[str] = None,
    image_url: Optional[str] = None,
    exhausted: Optional[bool] = None,
) -> None:
    letter = (option or "").upper()
    if letter not in option_letters():
        return
    with _lock:
        job = _jobs.get(gig_id)
        if not job:
            return
        options = job.setdefault("options", _default_options())
        entry = options.setdefault(letter, _default_option())
        changed = False
        if phase is not None and entry.get("phase") != phase:
            entry["phase"] = phase
            changed = True
        if progress is not None:
            new_progress = min(100, max(0, int(progress)))
            if entry.get("progress") != new_progress:
                entry["progress"] = new_progress
        if attempt is not None and entry.get("attempt") != attempt:
            entry["attempt"] = attempt
            changed = True
        if note is not None and entry.get("note") != note:
            entry["note"] = note
            changed = True
        if image_url is not None and entry.get("image_url") != image_url:
            entry["image_url"] = image_url
            changed = True
        if exhausted is not None and entry.get("exhausted") != exhausted:
            entry["exhausted"] = bool(exhausted)
            changed = True
        if changed:
            job["updated_at"] = _now_iso()
            _bump_options_revision(job)


def _idle_status(gig_id: str) -> dict[str, Any]:
    estimates = get_estimates()
    return {
        "gig_id": gig_id,
        "job_type": None,
        "status": "idle",
        "step": "",
        "substep": "",
        "message": "",
        "detail": "",
        "progress": 0,
        "option": "",
        "attempt": 0,
        "options": _default_options(),
        "options_revision": 0,
        "estimated_option_seconds": estimates["option_total_seconds"],
        "estimated_generate_seconds": estimates["generate_seconds"],
        "estimated_review_seconds": estimates["review_seconds"],
        "log": [],
        "log_revision": 0,
        "heartbeat_revision": 0,
        "provider_label": "",
        "active_provider": "",
        "title": "",
        "updated_at": None,
        "error": None,
    }


def start_job(
    gig_id: str,
    job_type: str,
    *,
    title: str = "",
    detail: str = "",
) -> None:
    from image_providers.base import (
        is_provider_split_enabled,
        provider_display_label,
        provider_short_label,
        resolve_image_provider,
        resolve_image_provider_for_option,
        split_provider_summary,
    )

    estimates = get_estimates()
    provider = resolve_image_provider()
    options = _default_options()
    if is_provider_split_enabled():
        for letter in option_letters():
            p = resolve_image_provider_for_option(letter)
            options[letter]["provider_label"] = f"{letter}: {provider_short_label(p)}"
            options[letter]["estimated_generate_seconds"] = _option_generate_estimate(letter, p)
        provider_label = split_provider_summary()
    else:
        provider_label = provider_display_label(provider)
        for letter in option_letters():
            options[letter]["estimated_generate_seconds"] = _option_generate_estimate(letter, provider)
    job_generate_estimate = max(
        float(options[letter]["estimated_generate_seconds"]) for letter in option_letters()
    )
    with _lock:
        _jobs[gig_id] = {
            "gig_id": gig_id,
            "job_type": job_type,
            "status": "running",
            "step": "starting",
            "substep": "init",
            "message": "Starting…",
            "detail": detail,
            "progress": 0,
            "option": "",
            "attempt": 0,
            "options": options,
            "options_revision": 0,
            "estimated_option_seconds": estimates["option_total_seconds"],
            "estimated_generate_seconds": job_generate_estimate,
            "estimated_review_seconds": estimates["review_seconds"],
            "log": [],
            "log_revision": 0,
            "heartbeat_revision": 0,
            "provider_label": provider_label,
            "active_provider": provider,
            "title": title,
            "updated_at": _now_iso(),
            "error": None,
        }
        _append_log(_jobs[gig_id], "Job started")


def report_progress(
    gig_id: str,
    *,
    step: str,
    substep: str = "",
    message: str = "",
    detail: str = "",
    progress: int = 0,
    option: str = "",
    attempt: int = 0,
    log: bool = True,
    option_phase: Optional[str] = None,
    option_progress: Optional[int] = None,
    option_note: Optional[str] = None,
    option_image_url: Optional[str] = None,
    option_exhausted: Optional[bool] = None,
    provider_label: Optional[str] = None,
    active_provider: Optional[str] = None,
) -> None:
    with _lock:
        job = _jobs.get(gig_id)
        if not job or job.get("status") != "running":
            return
        job["step"] = step
        job["substep"] = substep
        job["message"] = message or detail or substep or step
        if detail:
            job["detail"] = detail
        job["progress"] = min(100, max(0, int(progress)))
        if option:
            job["option"] = option
        if attempt:
            job["attempt"] = attempt
        if provider_label:
            job["provider_label"] = provider_label
        if active_provider:
            job["active_provider"] = active_provider
        job["updated_at"] = _now_iso()

        if option:
            _sync_option_from_report(
                job,
                option,
                step=step,
                substep=substep,
                message=message,
                detail=detail,
                progress=progress,
                attempt=attempt,
                option_phase=option_phase,
                option_progress=option_progress,
                option_note=option_note,
                option_image_url=option_image_url,
                option_exhausted=option_exhausted,
                option_provider_label=provider_label,
            )

        line = _format_log_line(step, substep, message, detail, option, attempt)
        if log and line:
            _append_log(job, line)
        else:
            job["heartbeat_revision"] = int(job.get("heartbeat_revision", 0)) + 1


def update_progress(gig_id: str, step: str, message: str, progress: int) -> None:
    """Backward-compatible wrapper."""
    report_progress(gig_id, step=step, message=message, progress=progress)


def pause_job_for_route(job_id: str, message: str = "Review mockup and choose path") -> None:
    """Pause a shell job after pre-pass mockup until the user picks a final route."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "awaiting_route"
        job["step"] = "prepass"
        job["substep"] = "review"
        job["message"] = message
        job["progress"] = 52
        job["updated_at"] = _now_iso()
        _append_log(job, message)


def resume_job(job_id: str, *, detail: str = "", message: str = "Resuming final pass…") -> None:
    """Resume a shell job after the user chose a final route."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["message"] = message
        if detail:
            job["detail"] = detail
        job["updated_at"] = _now_iso()
        _append_log(job, message)


def complete_job(gig_id: str, message: str = "Done") -> None:
    with _lock:
        job = _jobs.get(gig_id)
        if not job:
            return
        job["status"] = "done"
        job["step"] = "done"
        job["substep"] = "complete"
        job["message"] = message
        job["progress"] = 100
        job["updated_at"] = _now_iso()
        options = job.setdefault("options", _default_options())
        for letter in option_letters():
            entry = options.setdefault(letter, _default_option())
            if entry.get("phase") not in {"passed", "failed"}:
                entry["phase"] = "passed"
                entry["progress"] = 100
        _bump_options_revision(job)
        _append_log(job, message)


def fail_job(gig_id: str, error: str) -> None:
    with _lock:
        job = _jobs.get(gig_id)
        if not job:
            _jobs[gig_id] = {
                **_idle_status(gig_id),
                "status": "error",
                "step": "error",
                "message": error,
                "error": error,
                "updated_at": _now_iso(),
            }
            _append_log(_jobs[gig_id], f"Error: {error}")
            return
        job["status"] = "error"
        job["step"] = "error"
        job["substep"] = "failed"
        job["message"] = error
        job["error"] = error
        job["updated_at"] = _now_iso()
        active = (job.get("option") or "").upper()
        options = job.setdefault("options", _default_options())
        if active in option_letters():
            entry = options.setdefault(active, _default_option())
            if entry.get("phase") not in {"passed"}:
                entry["phase"] = "error"
                entry["progress"] = 100
                entry["note"] = error[:240]
                _bump_options_revision(job)
        _append_log(job, f"Error: {error}")


def get_job_status(gig_id: str) -> dict[str, Any]:
    with _lock:
        job = _jobs.get(gig_id)
        if job:
            snapshot = dict(job)
            snapshot["log"] = [dict(entry) for entry in job.get("log", [])]
            snapshot["options"] = _option_snapshot(job.get("options", {}))
            snapshot["log_revision"] = int(job.get("log_revision", 0))
            snapshot["heartbeat_revision"] = int(job.get("heartbeat_revision", 0))
            snapshot["options_revision"] = int(job.get("options_revision", 0))
            return snapshot
    return _idle_status(gig_id)


def is_job_active(gig_id: str) -> bool:
    with _lock:
        job = _jobs.get(gig_id)
        return bool(job and job.get("status") == "running")


def clear_job(gig_id: str) -> None:
    with _lock:
        _jobs.pop(gig_id, None)


def clear_all_jobs() -> None:
    """Test helper."""
    with _lock:
        _jobs.clear()
