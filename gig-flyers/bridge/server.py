#!/usr/bin/env python3
"""Local FastAPI bridge: web review, iMessage links, email delivery."""

from __future__ import annotations

import asyncio
import html as html_module
import json
import os
import sys
from functools import partial
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.email import send_flyer_image  # noqa: E402
from bridge.imessage import (  # noqa: E402
    fetch_new_incoming_messages,
    parse_reply,
    send_image,
    send_text,
)
from bridge.interactive import (  # noqa: E402
    build_picker_data,
    render_generating_page,
    render_home_page,
    render_picker_page,
)
from bridge.job_status import (  # noqa: E402
    complete_job,
    fail_job,
    get_job_status,
    is_job_active,
    report_progress,
    start_job,
)
from bridge.routing import add_get, add_post  # noqa: E402
from bridge.review import (  # noqa: E402
    build_review_data,
    build_review_link_message,
    home_page_path,
    pick_page_path,
    render_processing_page,
    render_regenerating_page,
    render_review_page,
    review_page_path,
    review_url,
)
from flyer_generator import generate_for_gig  # noqa: E402
from gig_calendar import CalendarUnavailableError, find_gig_by_id  # noqa: E402
from output_paths import resolve_output_path  # noqa: E402
from state import (  # noqa: E402
    append_feedback,
    get_gig_state,
    get_last_poll_rowid,
    mark_approved,
    set_last_poll_rowid,
    upsert_gig,
)

load_dotenv(ROOT / ".env")

app = FastAPI(title="Gig Flyer Bridge", version="2.0.0")
app.mount("/output", StaticFiles(directory=str(ROOT / "output")), name="output")
app.mount("/bandphotos", StaticFiles(directory=str(ROOT / "bandphotos")), name="bandphotos")

POLL_SECONDS = int(os.getenv("BRIDGE_POLL_SECONDS", "30"))
_revise_in_flight: set[str] = set()
_generate_in_flight: set[str] = set()


def _check_secret(secret: Optional[str]) -> None:
    expected = os.getenv("BRIDGE_SECRET", "change-me")
    if secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


class SendReviewRequest(BaseModel):
    gig_id: str
    round: int = Field(default=1)
    event: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, str]


class FeedbackItem(BaseModel):
    gig_id: str
    action: str
    option: str
    feedback: str = ""
    raw_text: str
    rowid: int


class ProcessFeedbackRequest(BaseModel):
    feedback: FeedbackItem


class ApproveBody(BaseModel):
    option: str


class ReviseBody(BaseModel):
    option: str
    feedback: str


def _resolve_option_path(gig_id: str, option: str) -> Path:
    record = get_gig_state(gig_id) or {}
    options = record.get("options", {})
    rel = options.get(option.upper()) or options.get(option)
    if not rel:
        raise HTTPException(status_code=400, detail=f"Option {option} not found")
    path = resolve_output_path(rel)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Missing image for option {option}")
    return path


def _gig_label(event: dict[str, Any]) -> str:
    short_date = event.get("short_date") or event.get("date", "")
    venue = event.get("venue", "")
    return f"{short_date} @ {venue}".strip()


async def _notify_cursor_webhook(payload: dict[str, Any]) -> None:
    url = os.getenv("CURSOR_WEBHOOK_URL", "").strip()
    if not url:
        return
    headers = {"Content-Type": "application/json"}
    secret = os.getenv("CURSOR_WEBHOOK_SECRET", "").strip()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(url, json=payload, headers=headers)


async def _approve_gig(gig_id: str, option: str, raw_text: str) -> dict[str, Any]:
    record = get_gig_state(gig_id)
    if not record:
        raise HTTPException(status_code=404, detail="Unknown gig")

    append_feedback(gig_id, "approve", option.upper(), "", raw_text)
    source = _resolve_option_path(gig_id, option.upper())
    dest = mark_approved(gig_id, option.upper(), source)
    event = record.get("event", {})
    label = _gig_label(event)

    delivery: dict[str, str] = {}
    try:
        send_image(dest, caption=f"Approved flyer — {label} (option {option.upper()})")
        delivery["imessage"] = "sent"
    except Exception as exc:  # noqa: BLE001
        delivery["imessage"] = f"failed: {exc}"

    try:
        method = send_flyer_image(dest, label, option.upper())
        delivery["email"] = method
    except Exception as exc:  # noqa: BLE001
        delivery["email"] = f"failed: {exc}"

    send_text(f"Approved option {option.upper()} for {label}. Review: {review_url(gig_id)}")
    return {"status": "approved", "path": str(dest), "delivery": delivery}


def _gig_event_summary(gig_id: str) -> dict[str, Any]:
    record = get_gig_state(gig_id) or {}
    return record.get("event") or {}


def _progress_callback(gig_id: str):
    def callback(**kwargs: Any) -> None:
        report_progress(gig_id, **kwargs)

    return callback


async def _run_generation_job(
    gig_id: str,
    job_type: str,
    *,
    detail: str = "",
    generate_kwargs: Optional[dict[str, Any]] = None,
    send_link: bool = True,
) -> None:
    event = _gig_event_summary(gig_id)
    title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue TBA')}".strip()
    if not is_job_active(gig_id):
        start_job(gig_id, job_type, title=title, detail=detail)
    kwargs = dict(generate_kwargs or {})
    kwargs.setdefault("on_progress", _progress_callback(gig_id))

    try:
        manifest = await asyncio.to_thread(partial(generate_for_gig, gig_id, **kwargs))
        if manifest.get("skipped"):
            complete_job(gig_id, "Already approved")
            return
        if send_link:
            report_progress(
                gig_id,
                step="sending",
                substep="imessage",
                message="Posting to iMessage…",
                progress=96,
            )
            event = manifest.get("event", event)
            link_msg = build_review_link_message(event, gig_id, len(manifest.get("options", {})))
            send_text(link_msg)
            report_progress(
                gig_id,
                step="sending",
                substep="sent",
                message="Review link sent",
                progress=98,
            )
        complete_job(gig_id, "Done")
    except Exception as exc:  # noqa: BLE001
        fail_job(gig_id, str(exc))
        _log_bridge_error(f"{job_type} background error for {gig_id}: {exc}")
    finally:
        _generate_in_flight.discard(gig_id)
        _revise_in_flight.discard(gig_id)


async def _run_revise_generation(gig_id: str, option: str, feedback: str) -> dict[str, Any]:
    await _run_generation_job(
        gig_id,
        "revise",
        detail=f"Revising option {option}: {feedback}",
        generate_kwargs={
            "count": 3,
            "round_num": None,
            "feedback": feedback,
            "base_option": option.upper(),
        },
        send_link=True,
    )
    record = get_gig_state(gig_id) or {}
    return {
        "status": "revised",
        "review_url": review_url(gig_id),
        "event": record.get("event", {}),
    }


async def _revise_gig(gig_id: str, option: str, feedback: str, raw_text: str) -> dict[str, Any]:
    record = get_gig_state(gig_id)
    if not record:
        raise HTTPException(status_code=404, detail="Unknown gig")

    append_feedback(gig_id, "revise", option.upper(), feedback, raw_text)
    return await _run_revise_generation(gig_id, option, feedback)


def _log_bridge_error(message: str) -> None:
    log_path = ROOT / "logs" / "bridge.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{message}\n")


async def _revise_gig_background(gig_id: str, option: str, feedback: str) -> None:
    await _run_revise_generation(gig_id, option, feedback)


async def _run_regenerate_background(gig_id: str) -> None:
    await _run_generation_job(
        gig_id,
        "regenerate",
        detail="Fresh round from scratch",
        generate_kwargs={"count": 3, "fresh_start": True},
        send_link=True,
    )


async def _start_regenerate(gig_id: str) -> Response:
    from state import begin_regenerate_round, can_regenerate

    record = get_gig_state(gig_id) or {}
    if not can_regenerate(gig_id):
        raise HTTPException(status_code=409, detail="No existing generation to regenerate")
    if gig_id in _generate_in_flight:
        event = record.get("event") or {}
        return HTMLResponse(render_regenerating_page(gig_id, event))

    if record.get("status") == "approved":
        begin_regenerate_round(gig_id)

    append_feedback(gig_id, "regenerate", "", "", "REGENERATE (fresh round)")
    _generate_in_flight.add(gig_id)
    event = record.get("event") or {}
    title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue TBA')}".strip()
    start_job(gig_id, "regenerate", title=title, detail="Fresh round from scratch")
    asyncio.create_task(_run_regenerate_background(gig_id))
    return HTMLResponse(render_regenerating_page(gig_id, event))


async def _run_interactive_generation(gig_id: str) -> None:
    await _run_generation_job(
        gig_id,
        "generate",
        detail="Initial generation from gig picker",
        generate_kwargs={"count": 3},
        send_link=True,
    )


@app.get("/health")
@app.get("/flyers/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@add_get(app, "/", response_class=HTMLResponse)
async def home_page() -> HTMLResponse:
    return HTMLResponse(render_home_page())


@add_get(app, "/pick", response_class=HTMLResponse)
async def pick_page() -> HTMLResponse:
    try:
        data = build_picker_data()
        return HTMLResponse(render_picker_page(data))
    except CalendarUnavailableError as exc:
        _log_bridge_error(f"pick page error: {exc}")
        body = f"""<!DOCTYPE html><html><body style="font-family:system-ui;margin:2rem">
        <h1>Could not load calendar</h1>
        <p>{html_module.escape(str(exc))}</p>
        <p>No cached calendar is available yet. Warm the cache when the site responds:</p>
        <p><code>python3 -c "from gig_calendar import get_all_events; get_all_events(force_refresh=True)"</code></p>
        <p><a href="{html_module.escape(home_page_path())}">Home</a></p>
        </body></html>"""
        return HTMLResponse(body, status_code=503)
    except Exception as exc:  # noqa: BLE001
        _log_bridge_error(f"pick page error: {exc}")
        body = f"""<!DOCTYPE html><html><body style="font-family:system-ui;margin:2rem">
        <h1>Could not load calendar</h1>
        <p>{html_module.escape(str(exc))}</p>
        <p><a href="{html_module.escape(home_page_path())}">Home</a></p>
        </body></html>"""
        return HTMLResponse(body, status_code=503)


@add_post(app, "/pick/{gig_id}/generate")
async def pick_generate(gig_id: str) -> Response:
    from state import is_approved, is_eligible_for_auto_generation, upsert_gig

    if is_approved(gig_id):
        raise HTTPException(status_code=400, detail="Gig already approved")
    record = get_gig_state(gig_id) or {}
    if record.get("status") == "pending_review":
        return RedirectResponse(url=review_page_path(gig_id), status_code=303)
    if not is_eligible_for_auto_generation(gig_id):
        raise HTTPException(status_code=409, detail="Flyer generation already in progress for this gig")
    if gig_id in _generate_in_flight:
        event = record.get("event") or {}
        return HTMLResponse(render_generating_page(gig_id, event))

    gig = find_gig_by_id(gig_id)
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found on calendar")
    event = gig.to_dict()
    upsert_gig(gig_id, event=event)
    _generate_in_flight.add(gig_id)
    title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue TBA')}".strip()
    start_job(gig_id, "generate", title=title, detail="Initial generation from gig picker")
    asyncio.create_task(_run_interactive_generation(gig_id))
    return HTMLResponse(render_generating_page(gig_id, event))


@add_post(app, "/pick/{gig_id}/regenerate")
async def pick_regenerate(gig_id: str) -> Response:
    try:
        return await _start_regenerate(gig_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        return _error_response(gig_id, exc)


@add_get(app, "/review/{gig_id}/status")
async def review_job_status(gig_id: str) -> JSONResponse:
    return JSONResponse(
        content=get_job_status(gig_id),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@add_get(app, "/review/{gig_id}/status/stream")
async def review_job_status_stream(gig_id: str) -> StreamingResponse:
    async def event_generator():
        last_fp = ""
        idle_ticks = 0
        while idle_ticks < 180:
            snap = get_job_status(gig_id)
            fp = (
                f"{snap.get('log_revision')}:{snap.get('heartbeat_revision')}:"
                f"{snap.get('options_revision')}:{snap.get('updated_at')}:"
                f"{snap.get('status')}:{snap.get('message')}"
            )
            if fp != last_fp:
                yield f"data: {json.dumps(snap)}\n\n"
                last_fp = fp
            if snap.get("status") in ("done", "error"):
                break
            if snap.get("status") == "idle":
                idle_ticks += 1
            else:
                idle_ticks = 0
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/review/{gig_id}", response_class=HTMLResponse)
async def review_page(gig_id: str) -> HTMLResponse:
    try:
        data = build_review_data(gig_id)
        if not data.get("history_rounds") and not data.get("current_options") and not data.get("event"):
            return _error_response(gig_id, ValueError("Gig not found"), status_code=404)
        return HTMLResponse(render_review_page(data))
    except Exception as exc:  # noqa: BLE001
        return _error_response(gig_id, exc)


@app.post("/review/{gig_id}/approve")
async def review_approve_web(gig_id: str, option: str = Form(...)) -> Response:
    try:
        await _approve_gig(gig_id, option.upper(), f"APPROVE {option.upper()} (web)")
    except Exception as exc:  # noqa: BLE001
        return _error_response(gig_id, exc)
    return RedirectResponse(url=review_page_path(gig_id), status_code=303)


@add_post(app, "/review/{gig_id}/regenerate")
async def review_regenerate_web(gig_id: str) -> Response:
    try:
        return await _start_regenerate(gig_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        return _error_response(gig_id, exc)


@app.post("/review/{gig_id}/revise")
async def review_revise_web(
    gig_id: str,
    option: str = Form(...),
    feedback: str = Form(...),
) -> Response:
    try:
        record = get_gig_state(gig_id)
        if not record:
            raise ValueError("Unknown gig")
        cleaned = feedback.strip()
        if not cleaned:
            raise ValueError("Feedback is required")
        if gig_id in _revise_in_flight:
            return HTMLResponse(render_processing_page(gig_id, option.upper(), cleaned))
        raw_text = f"REVISE {option.upper()}: {cleaned}"
        append_feedback(gig_id, "revise", option.upper(), cleaned, raw_text)
        _revise_in_flight.add(gig_id)
        event = record.get("event") or {}
        title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue TBA')}".strip()
        start_job(
            gig_id,
            "revise",
            title=title,
            detail=f"Revising option {option.upper()}: {cleaned}",
        )
        asyncio.create_task(_revise_gig_background(gig_id, option.upper(), cleaned))
        return HTMLResponse(render_processing_page(gig_id, option.upper(), cleaned))
    except Exception as exc:  # noqa: BLE001
        return _error_response(gig_id, exc)


def _error_response(gig_id: str, exc: Exception, status_code: int = 500) -> HTMLResponse:
    body = f"""<!DOCTYPE html><html><body style="font-family:system-ui;margin:2rem">
    <h1>Something went wrong</h1>
    <p>{html_module.escape(str(exc))}</p>
    <p><a href="{review_page_path(gig_id)}">Back to review</a></p>
    </body></html>"""
    return HTMLResponse(body, status_code=status_code)


@app.post("/review/{gig_id}/approve.json")
async def review_approve_api(gig_id: str, body: ApproveBody) -> dict[str, Any]:
    return await _approve_gig(gig_id, body.option.upper(), f"APPROVE {body.option.upper()} (api)")


@app.post("/review/{gig_id}/revise.json")
async def review_revise_api(gig_id: str, body: ReviseBody) -> dict[str, Any]:
    return await _revise_gig(
        gig_id,
        body.option.upper(),
        body.feedback.strip(),
        f"REVISE {body.option.upper()}: {body.feedback}",
    )


@app.post("/send-review")
async def send_review(
    body: SendReviewRequest,
    secret: Optional[str] = Header(None, alias="X-Secret"),
) -> dict[str, Any]:
    _check_secret(secret)
    record = get_gig_state(body.gig_id) or {}
    options = body.options or record.get("options", {})
    if not options:
        raise HTTPException(status_code=400, detail="No options to send")

    event = body.event or record.get("event") or {}
    if not event:
        gig = find_gig_by_id(body.gig_id)
        event = gig.to_dict() if gig else {"gig_id": body.gig_id}

    message = build_review_link_message(event, body.gig_id, len(options))
    send_text(message)
    return {
        "sent": True,
        "gig_id": body.gig_id,
        "review_url": review_url(body.gig_id),
        "options": list(options.keys()),
    }


@app.get("/pending-feedback")
async def pending_feedback(
    secret: Optional[str] = Header(None, alias="X-Secret"),
) -> dict[str, Any]:
    _check_secret(secret)
    since = get_last_poll_rowid()
    messages = fetch_new_incoming_messages(since)
    parsed_items = []
    max_rowid = since

    for msg in messages:
        max_rowid = max(max_rowid, int(msg["rowid"]))
        parsed = parse_reply(msg["text"])
        if parsed.action == "unknown":
            continue
        record = _latest_pending_gig()
        if not record:
            continue
        parsed_items.append(
            {
                "gig_id": record["gig_id"],
                "action": parsed.action,
                "option": parsed.option,
                "feedback": parsed.feedback,
                "raw_text": parsed.raw_text,
                "rowid": msg["rowid"],
            }
        )

    return {"since_rowid": since, "max_rowid": max_rowid, "items": parsed_items}


def _latest_pending_gig() -> Optional[dict[str, Any]]:
    from state import load_state

    state = load_state()
    pending = [
        (gid, rec)
        for gid, rec in state.get("gigs", {}).items()
        if rec.get("status") in {"pending_review", "iterating"}
    ]
    if not pending:
        return None
    pending.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
    gig_id, rec = pending[0]
    return {"gig_id": gig_id, **rec}


@app.post("/process-feedback")
async def process_feedback(
    body: ProcessFeedbackRequest,
    secret: Optional[str] = Header(None, alias="X-Secret"),
) -> dict[str, Any]:
    _check_secret(secret)
    item = body.feedback
    set_last_poll_rowid(max(get_last_poll_rowid(), item.rowid))

    if item.action == "approve":
        return await _approve_gig(item.gig_id, item.option, item.raw_text)

    if item.action == "revise":
        return await _revise_gig(item.gig_id, item.option, item.feedback, item.raw_text)

    send_text("Could not parse that reply. Open the review link or use APPROVE B / REVISE B: feedback")
    return {"status": "unknown"}


async def _poll_loop() -> None:
    while True:
        try:
            since = get_last_poll_rowid()
            messages = fetch_new_incoming_messages(since)
            max_rowid = since
            for msg in messages:
                max_rowid = max(max_rowid, int(msg["rowid"]))
                parsed = parse_reply(msg["text"])
                if parsed.action == "unknown":
                    continue
                record = _latest_pending_gig()
                if not record:
                    continue
                payload = {
                    "gig_id": record["gig_id"],
                    "action": parsed.action,
                    "option": parsed.option,
                    "feedback": parsed.feedback,
                    "raw_text": parsed.raw_text,
                    "rowid": msg["rowid"],
                }
                await process_feedback(
                    ProcessFeedbackRequest(feedback=FeedbackItem(**payload)),
                    secret=os.getenv("BRIDGE_SECRET", "change-me"),
                )
                await _notify_cursor_webhook({"type": "flyer_feedback", **payload})
            if max_rowid > since:
                set_last_poll_rowid(max_rowid)
        except FileNotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001
            log_path = ROOT / "logs" / "bridge.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"poll error: {exc}\n")
        await asyncio.sleep(POLL_SECONDS)


async def _run_prototype_job(gig_id: str, *, start: bool = False, submit: Optional[dict[str, Any]] = None) -> None:
    event = _gig_event_summary(gig_id)
    title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue TBA')}".strip()
    if not is_job_active(gig_id):
        start_job(gig_id, "prototype", title=title, detail="Prototype batch")
    callback = _progress_callback(gig_id)
    try:
        if start:
            await asyncio.to_thread(
                __import__("prototype_session").start_prototype_session,
                gig_id,
                on_progress=callback,
            )
        elif submit:
            await asyncio.to_thread(
                __import__("prototype_session").submit_prototype_turn,
                gig_id,
                **submit,
            )
        complete_job(gig_id, "Prototype ready")
    except Exception as exc:  # noqa: BLE001
        fail_job(gig_id, str(exc))
        _log_bridge_error(f"prototype error for {gig_id}: {exc}")
    finally:
        _generate_in_flight.discard(gig_id)


@add_get(app, "/prototype/{gig_id}", response_class=HTMLResponse)
async def prototype_page(gig_id: str) -> HTMLResponse:
    from bridge.prototype import render_prototype_page

    try:
        return HTMLResponse(render_prototype_page(gig_id))
    except Exception as exc:  # noqa: BLE001
        return _error_response(gig_id, exc)


@add_post(app, "/prototype/{gig_id}/start")
async def prototype_start(gig_id: str) -> Response:
    from bridge.prototype import prototype_page_path, render_prototype_generating_page
    from gig_resolve import is_placeholder_gig_id, resolve_gig_event

    if is_placeholder_gig_id(gig_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid gig link — use Prototype mode from a gig review page, not /prototype/{gig_id}",
        )

    record = get_gig_state(gig_id) or {}
    if gig_id in _generate_in_flight:
        return HTMLResponse(render_prototype_generating_page(gig_id, record.get("event") or {}))

    from gig_resolve import resolve_gig_event

    try:
        event_obj = resolve_gig_event(gig_id)
        upsert_gig(gig_id, event=event_obj.to_dict())
    except ValueError as exc:
        pick = pick_page_path()
        body = f"""<!DOCTYPE html><html><body style="font-family:system-ui;margin:2rem">
        <h1>Gig not found</h1>
        <p>{html_module.escape(str(exc))}</p>
        <p><a href="{html_module.escape(pick)}">Pick a gig from the calendar</a>
        or open an existing <a href="{html_module.escape(review_page_path(gig_id))}">review page</a>.</p>
        </body></html>"""
        return HTMLResponse(body, status_code=404)

    _generate_in_flight.add(gig_id)
    asyncio.create_task(_run_prototype_job(gig_id, start=True))
    return HTMLResponse(render_prototype_generating_page(gig_id, record.get("event") or {}))


@add_post(app, "/prototype/{gig_id}/submit")
async def prototype_submit(
    gig_id: str,
    request: Request,
    action: str = Form(...),
    feedback: str = Form(""),
) -> Response:
    from bridge.prototype import prototype_page_path, render_prototype_generating_page

    form = await request.form()
    rankings: list[dict[str, Any]] = []
    for slot in ("1", "2", "3"):
        rank_raw = form.get(f"rank_{slot}")
        if rank_raw:
            rankings.append({"slot": slot, "rank": int(rank_raw)})
    winner_slot = form.get("winner_slot")
    if winner_slot is not None:
        winner_slot = str(winner_slot)

    if action == "next" and len(rankings) != 3:
        raise HTTPException(status_code=400, detail="Rank all 3 prototypes (1st, 2nd, 3rd) before continuing")
    ranks = [r["rank"] for r in rankings]
    if action == "next" and sorted(ranks) != [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Each rank 1, 2, and 3 must be used exactly once")

    if action == "approve":
        if not winner_slot:
            raise HTTPException(status_code=400, detail="Select which prototype wins")
        try:
            from prototype_session import submit_prototype_turn

            submit_prototype_turn(
                gig_id,
                rankings=rankings,
                feedback=feedback.strip(),
                action="approve",
                winner_slot=winner_slot,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(gig_id, exc)
        return RedirectResponse(url=review_page_path(gig_id), status_code=303)

    if action == "forfeit":
        from prototype_session import submit_prototype_turn

        submit_prototype_turn(
            gig_id,
            rankings=rankings,
            feedback=feedback.strip(),
            action="forfeit",
        )
        return RedirectResponse(url=prototype_page_path(gig_id), status_code=303)

    if gig_id in _generate_in_flight:
        record = get_gig_state(gig_id) or {}
        return HTMLResponse(render_prototype_generating_page(gig_id, record.get("event") or {}))

    _generate_in_flight.add(gig_id)
    asyncio.create_task(
        _run_prototype_job(
            gig_id,
            submit={
                "rankings": rankings,
                "feedback": feedback.strip(),
                "action": "next",
            },
        )
    )
    record = get_gig_state(gig_id) or {}
    return HTMLResponse(render_prototype_generating_page(gig_id, record.get("event") or {}))


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(_poll_loop())


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BRIDGE_PORT", "8010"))
    uvicorn.run("bridge.server:app", host="127.0.0.1", port=port, reload=False)
