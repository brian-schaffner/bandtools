"""Background runner for two-pass shell design jobs."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from bridge.job_status import (
    complete_job,
    fail_job,
    is_job_active,
    pause_job_for_route,
    report_progress,
    resume_job,
    start_job,
)
from design_shell_generate import (
    build_shell_briefing_sheet,
    build_shell_prompt,
    generate_design_shell_openai,
)
from gig_calendar import GigEvent, event_from_dict, set_test_mode
from output_paths import get_output_dir, output_relative, resolve_output_path
from personalize_shell_flyer import (
    build_personalize_canvas,
    build_personalize_prompt,
    personalize_shell_openai,
)
from personalize_shell_flyer import DEFAULT_PHOTO, _resolve_logo
from shell_asset_policy import (
    FinalRoute,
    asset_mode_for_route,
    asset_mode_label,
    final_route_label,
    suggest_final_route,
)
from shell_evaluation_card import build_shell_evaluation_card
from shell_pre_pass import build_prepass_mockup, prepass_quality
from shell_references import ShellReference, get_shell
from text_validation import resolve_venue_address

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = get_output_dir() / "shell_design"
JOBS_DIR = OUT_DIR / "jobs"

ProgressCallback = Callable[..., None]

VENUE_TYPES = (
    "festival",
    "member_club",
    "community_event",
    "blues_bar",
    "regional_bar",
    "theater",
    "arena",
    "regional_club",
)


def new_shell_job_id() -> str:
    return f"shell-{uuid.uuid4().hex[:12]}"


def demo_event_for_venue_type(venue_type: str) -> GigEvent:
    vt = venue_type or "regional_club"
    if vt == "festival":
        return GigEvent(
            event_date=date(2026, 8, 15),
            time_label="2:00 PM",
            title="Lindsey Lane Band at Kentucky River Festival",
            venue="Kentucky River Festival",
            suggested_name="Aug 15 Kentucky River Festival",
        )
    if vt in {"blues_bar", "regional_bar"}:
        return GigEvent(
            event_date=date(2026, 6, 21),
            time_label="9:00 PM",
            title="Lindsey Lane Band at Stevie Ray's Blues Bar",
            venue="Stevie Ray's Blues Bar",
            suggested_name="Jun 21 Stevie Ray's Blues Bar",
        )
    return GigEvent(
        event_date=date(2026, 7, 4),
        time_label="6:30 PM",
        title="Lindsey Lane Band at American Legion Post 15",
        venue="American Legion Post 15",
        suggested_name="Jul 4 American Legion Post 15",
    )


def _save_job_summary(job_id: str, summary: dict[str, Any]) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"{job_id}_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path


def load_job_summary(job_id: str) -> Optional[dict[str, Any]]:
    path = JOBS_DIR / f"{job_id}_summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _event_context(event: GigEvent) -> tuple[str, str, str]:
    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    return band, date_str, time_str


def _run_pass1(
    job_id: str,
    shell: ShellReference,
    output_dir: Path,
    progress: ProgressCallback,
) -> tuple[dict[str, Any], Path]:
    stem = shell.id
    briefing_path = output_dir / f"{stem}_pass1_briefing.png"
    shell_path = output_dir / f"{stem}_design_shell.png"

    progress(
        step="pass1",
        substep="briefing",
        message="Pass 1 · building style briefing sheet",
        progress=8,
        log=True,
    )
    build_shell_briefing_sheet(shell, briefing_path)
    progress(
        step="pass1",
        substep="api",
        message="Pass 1 · OpenAI creating design shell (placeholders only)",
        progress=14,
        log=True,
    )
    generate_design_shell_openai(shell, shell_path, briefing_path=briefing_path)
    if not shell_path.is_file():
        raise FileNotFoundError(f"Pass 1 shell image missing: {shell_path}")

    pass1 = {
        "shell_id": shell.id,
        "shell_title": shell.title,
        "design_family": shell.design_family,
        "briefing_rel": output_relative(briefing_path),
        "shell_rel": output_relative(shell_path),
        "prompt": build_shell_prompt(shell),
    }
    manifest_path = output_dir / f"{stem}_pass1_manifest.json"
    manifest_path.write_text(json.dumps(pass1, indent=2), encoding="utf-8")
    progress(
        step="pass1",
        substep="saved",
        message="Pass 1 complete — design shell ready",
        progress=40,
        log=True,
    )
    return pass1, shell_path


def _run_prepass(
    job_id: str,
    shell: ShellReference,
    shell_path: Path,
    event: GigEvent,
    output_dir: Path,
    progress: ProgressCallback,
) -> dict[str, Any]:
    band, date_str, time_str = _event_context(event)
    pass_stem = f"{event.gig_id}_{shell.id}"
    mockup_path = output_dir / f"{pass_stem}_prepass_mockup.png"
    suggested = suggest_final_route(shell)

    progress(
        step="prepass",
        substep="api",
        message="Pre-pass · fast text-only mockup with your gig details",
        progress=46,
        log=True,
    )
    build_prepass_mockup(
        shell,
        shell_path,
        mockup_path,
        band=band,
        venue=event.venue,
        date=date_str,
        time=time_str,
    )
    if not mockup_path.is_file():
        raise FileNotFoundError(f"Pre-pass mockup missing: {mockup_path}")

    progress(
        step="prepass",
        substep="saved",
        message="Pre-pass mockup ready — choose your final path",
        progress=52,
        log=True,
    )
    return {
        "gig_id": event.gig_id,
        "mockup_rel": output_relative(mockup_path),
        "quality": prepass_quality(),
        "suggested_route": suggested,
    }


def _run_final_pass(
    job_id: str,
    shell: ShellReference,
    shell_path: Path,
    event: GigEvent,
    route: FinalRoute,
    output_dir: Path,
    progress: ProgressCallback,
) -> tuple[dict[str, Any], Path]:
    set_test_mode(True)
    band, date_str, time_str = _event_context(event)
    photo = DEFAULT_PHOTO
    logo = _resolve_logo(band, paper=(242, 235, 220))
    for label, path in [("shell", shell_path), ("photo", photo), ("logo", logo)]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")

    pass_stem = f"{event.gig_id}_{shell.id}"
    out_path = output_dir / f"{pass_stem}_personalized.png"
    canvas_preview = output_dir / f"{pass_stem}_pass2_canvas.png"
    compose_mode = asset_mode_for_route(shell, route)
    prompt = build_personalize_prompt(
        shell,
        venue=event.venue,
        date=date_str,
        time=time_str,
        band=band,
        address=resolve_venue_address(event),
        event=event,
        asset_mode=compose_mode,
    )

    if route == "text_only":
        pass2_msg = "Final pass · high-quality typography only (no photo or logo)"
    else:
        pass2_msg = f"Final pass · {asset_mode_label(compose_mode).lower()}"
    progress(
        step="pass2",
        substep="canvas",
        message=pass2_msg,
        progress=58,
        log=True,
    )
    if route == "photo_logo":
        c_path, _, _, _, _ = build_personalize_canvas(
            shell_path,
            photo,
            logo,
            output_dir / f".{pass_stem}_work",
            shell=shell,
            asset_mode=compose_mode,
        )
        canvas_preview.write_bytes(c_path.read_bytes())

    progress(
        step="pass2",
        substep="api",
        message=f"Final pass · {final_route_label(route).lower()}",
        progress=62,
        log=True,
    )
    personalize_shell_openai(
        shell,
        shell_path,
        photo,
        logo,
        prompt,
        out_path,
        band=band,
        venue=event.venue,
        date=date_str,
        time=time_str,
        final_mode=route,
        asset_mode=compose_mode,
    )

    pass2 = {
        "gig_id": event.gig_id,
        "shell_id": shell.id,
        "shell_title": shell.title,
        "shell_image": str(shell_path),
        "photo": str(photo),
        "logo": str(logo),
        "personalized_rel": output_relative(out_path),
        "route": route,
        "asset_mode": compose_mode,
        "prompt": prompt,
    }
    if route == "photo_logo":
        pass2["pass2_canvas_rel"] = output_relative(canvas_preview)

    manifest_path = output_dir / f"{pass_stem}_pass2_manifest.json"
    manifest_path.write_text(json.dumps(pass2, indent=2), encoding="utf-8")
    progress(
        step="pass2",
        substep="saved",
        message="Final pass complete — personalized flyer ready",
        progress=85,
        log=True,
    )
    return pass2, out_path


def _run_eval_card(
    shell: ShellReference,
    shell_path: Path,
    personalized_path: Path,
    event: GigEvent,
    date_str: str,
    progress: ProgressCallback,
) -> str:
    progress(
        step="eval",
        substep="start",
        message="Building 3-panel evaluation card",
        progress=88,
        log=True,
    )
    eval_path = OUT_DIR / f"{event.gig_id}_{shell.id}_eval.png"
    ref_path = shell.image_path()
    build_shell_evaluation_card(
        reference_path=ref_path if ref_path.is_file() else shell_path,
        shell_path=shell_path,
        personalized_path=personalized_path,
        output_path=eval_path,
        shell_title=shell.title,
        shell_id=shell.id,
        venue=event.venue,
        date=date_str,
        extra_lines=[
            f"Design family: {shell.design_family}",
            "Provider: openai",
        ],
    )
    progress(
        step="eval",
        substep="saved",
        message="Evaluation card built",
        progress=95,
        log=True,
    )
    return output_relative(eval_path)


def run_shell_pipeline(
    job_id: str,
    shell: ShellReference,
    event: Optional[GigEvent],
    *,
    pass1_only: bool = False,
    skip_prepass: bool = False,
    final_route: Optional[FinalRoute] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> dict[str, Any]:
    """Run pass 1, optional pre-pass mockup, and optional final pass."""
    title = shell.title[:60]
    if not is_job_active(job_id):
        detail = "Pass 1 design shell"
        if event and not pass1_only:
            detail = f"{event.venue} · pass 1 → mockup → final"
        start_job(job_id, "shell_design", title=title, detail=detail)

    def progress(**kwargs: Any) -> None:
        if on_progress:
            on_progress(**kwargs)
        report_progress(job_id, **kwargs)

    try:
        output_dir = OUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        pass1, shell_path = _run_pass1(job_id, shell, output_dir, progress)

        summary: dict[str, Any] = {
            "job_id": job_id,
            "shell_id": shell.id,
            "shell_title": shell.title,
            "design_family": shell.design_family,
            "pass1_only": pass1_only,
            "skip_prepass": skip_prepass,
            "pass1": pass1,
        }

        if pass1_only:
            summary["status"] = "done"
            _save_job_summary(job_id, summary)
            complete_job(job_id, "Design shell ready")
            return summary

        if event is None:
            raise ValueError("Gig event required for pre-pass and final passes")

        summary["gig_id"] = event.gig_id
        summary["event"] = event.to_dict()
        summary["route"] = {"suggested": suggest_final_route(shell), "chosen": final_route}

        if final_route is None and not skip_prepass:
            prepass = _run_prepass(job_id, shell, shell_path, event, output_dir, progress)
            summary["prepass"] = prepass
            summary["status"] = "awaiting_route"
            _save_job_summary(job_id, summary)
            pause_job_for_route(job_id, "Pre-pass mockup ready — choose your final path")
            return summary

        route: FinalRoute = final_route or suggest_final_route(shell)
        summary["route"]["chosen"] = route
        return run_shell_final(job_id, route, on_progress=on_progress, summary=summary)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))
        raise


def run_shell_final(
    job_id: str,
    route: FinalRoute,
    *,
    on_progress: Optional[ProgressCallback] = None,
    summary: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Run high-quality final pass after user chose a route (or skip-mockup run)."""
    summary = summary or load_job_summary(job_id)
    if summary is None:
        raise ValueError(f"No job summary for {job_id}")

    shell = get_shell(summary["shell_id"])
    if shell is None:
        raise ValueError(f"Unknown shell: {summary['shell_id']}")

    event_data = summary.get("event") or {}
    event = event_from_dict(event_data, gig_id=summary.get("gig_id"))
    if event is None:
        raise ValueError("Gig event missing from job summary")

    if not is_job_active(job_id):
        resume_job(
            job_id,
            detail=f"{event.venue} · {final_route_label(route)}",
            message="Starting final pass…",
        )

    def progress(**kwargs: Any) -> None:
        if on_progress:
            on_progress(**kwargs)
        report_progress(job_id, **kwargs)

    try:
        output_dir = OUT_DIR
        pass1 = summary["pass1"]
        shell_path = resolve_output_path(pass1["shell_rel"])
        if not shell_path.is_file():
            raise FileNotFoundError(f"Pass 1 shell missing: {shell_path}")

        summary.setdefault("route", {})
        summary["route"]["chosen"] = route
        pass2, out_path = _run_final_pass(
            job_id, shell, shell_path, event, route, output_dir, progress,
        )
        _, date_str, _ = _event_context(event)
        eval_rel = _run_eval_card(shell, shell_path, out_path, event, date_str, progress)

        summary.update(
            {
                "status": "done",
                "pass2": pass2,
                "evaluation_rel": eval_rel,
            }
        )
        _save_job_summary(job_id, summary)
        complete_job(job_id, "Shell design complete")
        return summary
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))
        raise
