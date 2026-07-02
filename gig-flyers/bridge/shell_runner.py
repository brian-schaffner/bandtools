"""Background runner for two-pass shell design jobs."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from bridge.job_status import complete_job, fail_job, is_job_active, report_progress, start_job
from design_shell_generate import (
    build_shell_briefing_sheet,
    build_shell_prompt,
    generate_design_shell_openai,
)
from gig_calendar import GigEvent, set_test_mode
from output_paths import get_output_dir, output_relative, resolve_output_path
from personalize_shell_flyer import (
    build_personalize_canvas,
    build_personalize_prompt,
    personalize_shell_openai,
)
from personalize_shell_flyer import DEFAULT_PHOTO, _resolve_logo
from shell_evaluation_card import build_shell_evaluation_card
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


def run_shell_pipeline(
    job_id: str,
    shell: ShellReference,
    event: Optional[GigEvent],
    *,
    pass1_only: bool = False,
    on_progress: Optional[ProgressCallback] = None,
) -> dict[str, Any]:
    """Run pass 1 (and optionally pass 2) for a shell design job."""
    title = shell.title[:60]
    if not is_job_active(job_id):
        detail = "Pass 1 design shell"
        if event and not pass1_only:
            detail = f"{event.venue} · pass 1 → pass 2"
        start_job(job_id, "shell_design", title=title, detail=detail)

    def progress(**kwargs: Any) -> None:
        if on_progress:
            on_progress(**kwargs)
        report_progress(job_id, **kwargs)

    try:
        output_dir = OUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
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
            progress=45 if not pass1_only else 100,
            log=True,
        )

        summary: dict[str, Any] = {
            "job_id": job_id,
            "shell_id": shell.id,
            "shell_title": shell.title,
            "design_family": shell.design_family,
            "pass1_only": pass1_only,
            "pass1": pass1,
        }

        if pass1_only:
            summary["status"] = "done"
            _save_job_summary(job_id, summary)
            complete_job(job_id, "Design shell ready")
            return summary

        if event is None:
            raise ValueError("Gig event required for pass 2 personalization")

        set_test_mode(True)
        photo = DEFAULT_PHOTO
        logo = _resolve_logo("Lindsey Lane Band", paper=(242, 235, 220))
        for label, path in [("shell", shell_path), ("photo", photo), ("logo", logo)]:
            if not path.is_file():
                raise FileNotFoundError(f"Missing {label}: {path}")

        pass_stem = f"{event.gig_id}_{shell.id}"
        out_path = output_dir / f"{pass_stem}_personalized.png"
        canvas_preview = output_dir / f"{pass_stem}_pass2_canvas.png"
        date_str = event.event_date.strftime("%A, %B %d, %Y")
        time_str = event.time_label or "TBA"
        prompt = build_personalize_prompt(
            shell,
            venue=event.venue,
            date=date_str,
            time=time_str,
            band="Lindsey Lane Band",
            address=resolve_venue_address(event),
        )

        progress(
            step="pass2",
            substep="canvas",
            message="Pass 2 · styling photo & logo to match shell palette",
            progress=48,
            log=True,
        )
        c_path, _, _, _ = build_personalize_canvas(
            shell_path, photo, logo, output_dir / f".{pass_stem}_work", shell=shell,
        )
        canvas_preview.write_bytes(c_path.read_bytes())
        progress(
            step="pass2",
            substep="api",
            message="Pass 2 · OpenAI personalizing with your gig details",
            progress=55,
            log=True,
        )
        personalize_shell_openai(shell, shell_path, photo, logo, prompt, out_path)

        pass2 = {
            "gig_id": event.gig_id,
            "shell_id": shell.id,
            "shell_title": shell.title,
            "shell_image": str(shell_path),
            "photo": str(photo),
            "logo": str(logo),
            "personalized_rel": output_relative(out_path),
            "pass2_canvas_rel": output_relative(canvas_preview),
            "prompt": prompt,
        }
        manifest_path = output_dir / f"{pass_stem}_pass2_manifest.json"
        manifest_path.write_text(json.dumps(pass2, indent=2), encoding="utf-8")

        progress(
            step="pass2",
            substep="saved",
            message="Pass 2 complete — personalized flyer ready",
            progress=85,
            log=True,
        )

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
            personalized_path=resolve_output_path(pass2["personalized_rel"]),
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

        summary.update(
            {
                "status": "done",
                "gig_id": event.gig_id,
                "event": event.to_dict(),
                "pass2": pass2,
                "evaluation_rel": output_relative(eval_path),
            }
        )
        _save_job_summary(job_id, summary)
        complete_job(job_id, "Two-pass shell design complete")
        return summary
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))
        raise
