"""Background runner for two-pass shell design jobs."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from bridge.job_status import complete_job, fail_job, is_job_active, report_progress, start_job
from design_shell_generate import generate_design_shell
from gig_calendar import GigEvent, set_test_mode
from output_paths import get_output_dir
from personalize_shell_flyer import personalize_design_shell
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
        progress(
            step="pass1",
            substep="start",
            message="Pass 1: generating design shell…",
            progress=8,
            log=True,
        )
        pass1 = generate_design_shell(shell.id)
        shell_path = ROOT / pass1["shell_rel"]
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
        progress(
            step="pass2",
            substep="start",
            message="Pass 2: personalizing with band photo & logo…",
            progress=55,
            log=True,
        )
        pass2 = personalize_design_shell(
            event,
            shell.id,
            shell_path,
            address=resolve_venue_address(event),
        )
        progress(
            step="pass2",
            substep="saved",
            message="Pass 2 complete — personalized flyer ready",
            progress=85,
            log=True,
        )

        date_str = event.event_date.strftime("%A, %B %d, %Y")
        eval_path = OUT_DIR / f"{event.gig_id}_{shell.id}_eval.png"
        ref_path = shell.image_path()
        build_shell_evaluation_card(
            reference_path=ref_path if ref_path.is_file() else shell_path,
            shell_path=shell_path,
            personalized_path=ROOT / pass2["personalized_rel"],
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
                "evaluation_rel": str(eval_path.relative_to(ROOT)),
            }
        )
        _save_job_summary(job_id, summary)
        complete_job(job_id, "Two-pass shell design complete")
        return summary
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))
        raise
